from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from app.platform.plugins.agent_tools.common import (
    content_text,
    fallback_projection,
    json_markdown,
    json_text,
    message_content,
    stable_hash,
    string_value,
)
from app.platform.plugins.agent_tools.adapters.antigravity_subagents import (
    extract_parent_message,
    payload_subagent_id,
    subagent_call_chat_projection,
    subagent_call_projection,
    subagent_prompt_chat_projection,
    subagent_result_chat_projection,
    subagent_result_projection,
    subagent_state as antigravity_subagent_state,
)
from app.platform.plugins.agent_tools.types import (
    AgentChatProjection,
    AgentEventProjection,
    AgentSubagentState,
    AgentToolStorage,
)
from app.platform.plugins.agent_tools.user_input import extract_real_user_input
from app.models import Event, EventSourceType
from app.platform.ingest.normalizers import NormalizedEvent

_MAX_SOURCE_ID_LENGTH = 512
_MAX_KIND_LENGTH = 128
_HASH_SUFFIX_LENGTH = 16
_MISSING_SOURCE_PATH = "<unknown-source-path>"

_TYPE_TO_KIND = {
    "USER_INPUT": "user_message",
    "PLANNER_RESPONSE": "assistant_message",
    "CODE_ACTION": "assistant_message",
    "RUN_COMMAND": "tool_result",
    "VIEW_FILE": "tool_result",
    "GREP_SEARCH": "tool_result",
    "LIST_DIRECTORY": "tool_result",
    "INVOKE_SUBAGENT": "tool_result",
    "GENERIC": "event",
    "CONVERSATION_HISTORY": "context",
    "SYSTEM_MESSAGE": "system_message",
    "ERROR_MESSAGE": "error",
    "CHECKPOINT": "checkpoint",
}

def _bounded_string(value: str, max_length: int) -> str:
    if len(value) <= max_length:
        return value

    suffix = f":{stable_hash(value)[:_HASH_SUFFIX_LENGTH]}"
    return f"{value[: max_length - len(suffix)]}{suffix}"


def _session_id(payload: dict[str, Any], source_path: str | None) -> str:
    value = string_value(payload.get("session_id")) or string_value(payload.get("conversationId"))
    if value:
        return value
    if source_path:
        return _session_id_from_source_path(source_path) or source_path
    return "antigravity_cli"


def _session_id_from_source_path(source_path: str) -> str | None:
    path = Path(source_path)
    try:
        brain_index = path.parts.index("brain")
    except ValueError:
        return None
    session_index = brain_index + 1
    if session_index >= len(path.parts):
        return None
    session_id = path.parts[session_index].strip()
    return session_id or None


def _kind(payload: dict[str, Any]) -> str:
    raw_kind = string_value(payload.get("kind"))
    if raw_kind:
        return raw_kind
    raw_type = string_value(payload.get("type"))
    return _TYPE_TO_KIND.get(raw_type or "", (raw_type or "event").lower())


def _body_text(payload: dict[str, Any]) -> str | None:
    content = payload.get("content")
    if content is not None:
        text = content_text(content)
        if text:
            return text

    text = string_value(payload.get("text"))
    if text:
        return text

    thinking = string_value(payload.get("thinking"))
    if thinking:
        return thinking

    message = message_content(payload)
    if message:
        return message

    tool_calls = payload.get("tool_calls")
    if isinstance(tool_calls, list) and tool_calls:
        return json_text(tool_calls)

    return None


def _chat_body_text(payload: dict[str, Any]) -> str | None:
    content = payload.get("content")
    if isinstance(content, str) and content.strip():
        return content
    if isinstance(content, list):
        text = content_text(content)
        return text if text else None
    return string_value(payload.get("text"))


def _tool_call_names(payload: dict[str, Any]) -> list[str]:
    calls = payload.get("tool_calls")
    if not isinstance(calls, list):
        return []
    names: list[str] = []
    for call in calls:
        if not isinstance(call, dict):
            continue
        name = string_value(call.get("name"))
        if name:
            names.append(name)
    return names


def _tool_body(payload: dict[str, Any]) -> str:
    names = _tool_call_names(payload)
    content = _body_text(payload)
    if names and content:
        return f"{', '.join(names)}\n\n{content}"
    if names:
        return ", ".join(names)
    if content:
        return content
    return json_markdown(payload)


def _fingerprint_payload(payload: dict[str, Any]) -> dict[str, Any]:
    stable_payload = dict(payload)
    stable_payload.pop("project_path", None)
    stable_payload.pop("WEB_TERMINAL_PROJECT_PATH", None)
    return stable_payload


def _extract_conversation_id(content: str | None) -> str | None:
    if not content:
        return None
    match = re.search(r'"conversationId"\s*:\s*"([^"]+)"', content)
    if match:
        return match.group(1).strip()
    return None


class AntigravityCliAdapter:
    provider_id = "antigravity_cli"
    source_types = (EventSourceType.agent_tool_record,)
    legacy_source_types = ()
    command_names = ("agy-p", "agy")
    ai_activity = True

    def prepare_storage(self, window_id: str) -> AgentToolStorage:
        home = Path("~/.web-terminal-acp") / "antigravity-cli-homes" / window_id
        command_home = Path("~/.web-terminal-acp") / "antigravity-cli-homes" / ".managed-home" / window_id
        return AgentToolStorage(
            env={
                "WEB_TERMINAL_ANTIGRAVITY_HOME": str(home),
                "WEB_TERMINAL_ANTIGRAVITY_COMMAND_HOME": str(command_home),
            },
            directories=(home, command_home),
        )

    def normalize(
        self, payload: dict[str, Any], *, source_path: str | None, cursor: str | int | None
    ) -> NormalizedEvent:
        session_id = _session_id(payload, source_path)
        if payload.get("isSidechain") is True:
            if not session_id.startswith("agent-"):
                session_id = f"agent-{session_id}"
        kind = _kind(payload)
        if extract_parent_message(payload) is not None:
            kind = "assistant_message"
        kind = _bounded_string(kind, _MAX_KIND_LENGTH)
        source_id = _bounded_string(session_id, _MAX_SOURCE_ID_LENGTH)
        payload_json = {**payload, "provider": self.provider_id}
        text = _body_text(payload_json) or json_text(payload_json)
        fingerprint = "agent_tool_record:antigravity_cli:" + stable_hash(
            {
                "provider": self.provider_id,
                "source_path": source_path or _MISSING_SOURCE_PATH,
                "cursor": cursor,
                "step_index": payload.get("step_index"),
                "payload_hash": stable_hash(_fingerprint_payload(payload)),
            }
        )
        return NormalizedEvent(
            source_type=EventSourceType.agent_tool_record,
            source_id=source_id,
            kind=kind,
            payload_json=payload_json,
            fingerprint=fingerprint,
            text=text,
        )

    def project_event(self, event: Event) -> AgentEventProjection:
        payload = event.payload_json

        subagent_call = subagent_call_projection(payload, event.kind)
        if subagent_call is not None:
            return subagent_call

        subagent_result = subagent_result_projection(payload, event.kind)
        if subagent_result is not None:
            return subagent_result

        raw_type = string_value(payload.get("type"))
        source = string_value(payload.get("source"))
        status = string_value(payload.get("status"))
        subtype = " · ".join(part for part in (raw_type, status) if part) or event.kind
        body = _body_text(payload)

        if event.kind == "user_message" or raw_type == "USER_INPUT" or source == "USER_EXPLICIT":
            if payload.get("isSidechain") is True and payload_subagent_id(payload):
                body = extract_real_user_input(body, provider=self.provider_id) or body
                return AgentEventProjection(
                    tone="subagent-context",
                    label="Subagent prompt",
                    body=body or json_markdown(payload),
                    body_format="markdown" if body else "json",
                    subtype=event.kind,
                )
            real_user_input = extract_real_user_input(body, provider=self.provider_id)
            if real_user_input is None and body:
                return AgentEventProjection("context", "Context", body, subtype=subtype)
            return AgentEventProjection(
                "user-input",
                "User input",
                real_user_input or body or json_markdown(payload),
                "markdown" if real_user_input or body else "json",
                subtype=subtype,
            )

        if event.kind in {"tool_call", "tool_result"} or raw_type in {
            "RUN_COMMAND",
            "VIEW_FILE",
            "GREP_SEARCH",
            "LIST_DIRECTORY",
            "INVOKE_SUBAGENT",
        }:
            label = "Tool call" if event.kind == "tool_call" else "Tool response"
            tone = "tool-call" if event.kind == "tool_call" else "tool-result"
            return AgentEventProjection(tone, label, _tool_body(payload), subtype=subtype)

        if event.kind == "assistant_message" or source == "MODEL":
            if _tool_call_names(payload):
                return AgentEventProjection(
                    "tool-call",
                    "Tool call",
                    _tool_body(payload),
                    subtype=subtype,
                )
            if body:
                return AgentEventProjection("agent", "Agent response", body, subtype=subtype)

        if source == "SYSTEM" or event.kind == "system_message":
            return AgentEventProjection(
                "system",
                "System message",
                body or json_markdown(payload),
                "markdown" if body else "json",
                subtype=subtype,
            )

        return fallback_projection(event)

    def project_chat(self, event: Event) -> AgentChatProjection | None:
        payload = event.payload_json

        subagent_call = subagent_call_chat_projection(event)
        if subagent_call is not None:
            return subagent_call

        subagent_result = subagent_result_chat_projection(event)
        if subagent_result is not None:
            return subagent_result

        body = _chat_body_text(payload)
        source = str(event.ai_session_id or event.source_id)
        raw_type = string_value(payload.get("type"))
        payload_source = string_value(payload.get("source"))

        if event.kind == "user_message" or raw_type == "USER_INPUT" or payload_source == "USER_EXPLICIT":
            if not body:
                return None
            if payload.get("isSidechain") is True and payload_subagent_id(payload):
                subagent_prompt = subagent_prompt_chat_projection(event, body)
                if subagent_prompt is not None:
                    return subagent_prompt
            body = extract_real_user_input(body, provider=self.provider_id)
            if body is None:
                return None
            return AgentChatProjection("user", body, dedupe_key=f"{source}:user:{body}")

        if (
            (event.kind == "assistant_message" or raw_type in {"PLANNER_RESPONSE", "CODE_ACTION"})
            and payload_source == "MODEL"
            and not _tool_call_names(payload)
        ):
            if not body:
                return None
            subagent_id = payload_subagent_id(payload)
            return AgentChatProjection(
                "agent",
                body,
                dedupe_key=f"{source}:agent:{body}",
                agent_message_type="agent",
                subagent_id=subagent_id,
            )

        return None

    def is_completion(self, event: Event) -> bool:
        payload = event.payload_json
        if string_value(payload.get("source")) != "MODEL":
            return False
        if string_value(payload.get("status")) != "DONE":
            return False
        if _tool_call_names(payload):
            return False
        if event.kind != "assistant_message":
            return False
        raw_type = string_value(payload.get("type"))
        return raw_type in {"PLANNER_RESPONSE", "CODE_ACTION"} and _chat_body_text(payload) is not None

    def subagent_state(self, event: Event) -> AgentSubagentState:
        return antigravity_subagent_state(event)

    def summary_text(self, event: Event) -> str:
        chat = self.project_chat(event)
        if chat is not None:
            return chat.body
        return _body_text(event.payload_json) or json_text(event.payload_json)

    def index_text(self, event: Event) -> str:
        return self.summary_text(event)
