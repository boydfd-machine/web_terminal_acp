from __future__ import annotations

from pathlib import Path
from typing import Any

from app.platform.plugins.agent_tools.common import (
    agent_tool_record_event,
    content_text,
    fallback_projection,
    json_markdown,
    json_text,
    message_content,
    string_value,
)
from app.platform.plugins.agent_tools.types import (
    AgentChatProjection,
    AgentEventProjection,
    AgentSubagentState,
    AgentToolStorage,
)
from app.platform.plugins.agent_tools.user_input import extract_real_user_input
from app.platform.plugins.agent_tools.adapters.claude_code_subagents import (
    payload_subagent_id,
    subagent_call_chat_projection,
    subagent_call_projection,
    subagent_prompt_chat_projection,
    subagent_result_chat_projection,
    subagent_result_projection,
    subagent_source_id as source_id_for_subagent,
    subagent_state as claude_code_subagent_state,
)
from app.models import Event, EventSourceType
from app.platform.ingest.normalizers import NormalizedEvent, normalize_claude_jsonl


def _message(payload: dict[str, Any]) -> dict[str, Any]:
    message = payload.get("message")
    return message if isinstance(message, dict) else {}


def _message_role(payload: dict[str, Any]) -> str | None:
    message_role = string_value(_message(payload).get("role"))
    return message_role or string_value(payload.get("type"))


def _raw_content(payload: dict[str, Any]) -> Any:
    message = _message(payload)
    if "content" in message:
        return message.get("content")
    return payload.get("content")


def _body_text(payload: dict[str, Any]) -> str | None:
    content = _raw_content(payload)
    if content is None:
        return None
    text = content_text(content)
    return text if text else None


def _chat_body_text(payload: dict[str, Any]) -> str | None:
    content = _raw_content(payload)
    if isinstance(content, str):
        return content if content else None
    if isinstance(content, dict):
        block_type = string_value(content.get("type"))
        if block_type in {"tool_use", "tool_result"}:
            return None
        text = string_value(content.get("text"))
        return text if text else None
    if not isinstance(content, list):
        return None

    parts: list[str] = []
    for block in content:
        if isinstance(block, str):
            if block:
                parts.append(block)
            continue
        if not isinstance(block, dict):
            continue
        block_type = string_value(block.get("type"))
        if block_type in {"tool_use", "tool_result"}:
            continue
        if block_type and block_type != "text":
            continue
        text = string_value(block.get("text"))
        if text:
            parts.append(text)
    return "\n".join(parts) or None


def _has_tool_result_content(payload: dict[str, Any]) -> bool:
    content = _raw_content(payload)
    if isinstance(content, dict):
        return string_value(content.get("type")) == "tool_result"
    if not isinstance(content, list):
        return False
    return any(isinstance(block, dict) and string_value(block.get("type")) == "tool_result" for block in content)


def _content_blocks(payload: dict[str, Any]) -> list[dict[str, Any]]:
    content = _raw_content(payload)
    if not isinstance(content, list):
        return []
    return [block for block in content if isinstance(block, dict)]


def _tool_blocks(payload: dict[str, Any]) -> list[dict[str, Any]]:
    blocks = []
    for block in _content_blocks(payload):
        block_type = string_value(block.get("type"))
        if block_type in {"tool_use", "tool_result"}:
            blocks.append(block)
    return blocks


class ClaudeCodeAdapter:
    provider_id = "claude_code"
    source_types = (EventSourceType.agent_tool_record,)
    legacy_source_types = (EventSourceType.claude_jsonl,)
    command_names = ("claude",)
    ai_activity = True

    def prepare_storage(self, window_id: str) -> AgentToolStorage:
        home = Path("~/.web-terminal-acp") / "claude-code-homes" / window_id
        return AgentToolStorage(env={"CLAUDE_CONFIG_DIR": str(home)}, directories=(home,))

    def normalize(
        self, payload: dict[str, Any], *, source_path: str | None, cursor: str | int | None
    ) -> NormalizedEvent:
        resolved_source_path = str(
            payload.get("source_path") or payload.get("path") or source_path or self.provider_id
        )
        offset = cursor if isinstance(cursor, int) else payload.get("offset")
        if not isinstance(offset, int):
            offset = int(offset) if isinstance(offset, str) and offset.isdigit() else 0
        legacy_event = normalize_claude_jsonl(payload, source_path=resolved_source_path, offset=offset)
        subagent_source_id = source_id_for_subagent(payload_subagent_id(payload))
        if subagent_source_id is not None and payload.get("isSidechain") is True:
            legacy_event = NormalizedEvent(
                source_type=legacy_event.source_type,
                source_id=subagent_source_id,
                kind=legacy_event.kind,
                payload_json=legacy_event.payload_json,
                fingerprint=legacy_event.fingerprint,
                text=legacy_event.text,
            )
        return agent_tool_record_event(
            self.provider_id,
            legacy_event,
        )

    def project_event(self, event: Event) -> AgentEventProjection:
        payload = event.payload_json
        subagent_call = subagent_call_projection(payload, event.kind)
        if subagent_call is not None:
            return subagent_call

        subagent_result = subagent_result_projection(payload, event.kind)
        if subagent_result is not None:
            return subagent_result

        tool_blocks = _tool_blocks(payload)
        if tool_blocks:
            first = tool_blocks[0]
            block_type = string_value(first.get("type"))
            if block_type == "tool_use":
                name = string_value(first.get("name")) or "tool"
                return AgentEventProjection(
                    tone="tool-call",
                    label="Tool call",
                    body=f"{name}\n\n{json_markdown(first.get('input') or {})}",
                    subtype=event.kind,
                )
            if block_type == "tool_result":
                content = first.get("content")
                if isinstance(content, str):
                    body = content
                    body_format = "markdown"
                else:
                    body = content_text(content) if content is not None else None
                    if body:
                        body_format = "markdown"
                    else:
                        body = json_markdown(content if content is not None else first)
                        body_format = "json"
                return AgentEventProjection(
                    tone="tool-result",
                    label="Tool response",
                    body=body,
                    body_format=body_format,
                    subtype=event.kind,
                )

        role = _message_role(payload)
        body = _body_text(payload)
        body_format = "markdown"
        if not body:
            body = json_markdown(payload)
            body_format = "json"
        if role == "user" or event.kind == "user_message":
            if payload.get("isSidechain") is True and payload_subagent_id(payload):
                return AgentEventProjection(
                    tone="subagent-context",
                    label="Subagent prompt",
                    body=body,
                    body_format=body_format,
                    subtype=event.kind,
                )
            real_user_input = extract_real_user_input(body if body_format == "markdown" else None, provider=self.provider_id)
            if real_user_input is None and (body_format == "markdown" or _has_tool_result_content(payload)):
                label = "Tool response" if _has_tool_result_content(payload) else "Context"
                tone = "tool-result" if _has_tool_result_content(payload) else "context"
                return AgentEventProjection(
                    tone=tone,
                    label=label,
                    body=body,
                    body_format=body_format,
                    subtype=event.kind,
                )
            if real_user_input is not None:
                body = real_user_input
                body_format = "markdown"
            return AgentEventProjection(
                tone="user-input",
                label="User input",
                body=body,
                body_format=body_format,
                subtype=event.kind,
            )
        if role == "assistant" or event.kind == "assistant_message":
            return AgentEventProjection(
                tone="agent",
                label="Agent response",
                body=body,
                body_format=body_format,
                subtype=event.kind,
            )
        return fallback_projection(event)

    def project_chat(self, event: Event) -> AgentChatProjection | None:
        subagent_call = subagent_call_chat_projection(event)
        if subagent_call is not None:
            return subagent_call

        subagent_result = subagent_result_chat_projection(event)
        if subagent_result is not None:
            return subagent_result

        role = _message_role(event.payload_json)
        body = _chat_body_text(event.payload_json)
        if not body:
            return None
        source = str(event.ai_session_id or event.source_id)
        if role == "user":
            subagent_prompt = subagent_prompt_chat_projection(event, body)
            if subagent_prompt is not None:
                return subagent_prompt
            body = extract_real_user_input(body, provider=self.provider_id)
            if body is None:
                return None
            return AgentChatProjection("user", body, dedupe_key=f"{source}:user:{body}")
        if role == "assistant":
            return AgentChatProjection(
                "agent",
                body,
                dedupe_key=f"{source}:agent:{body}",
                agent_message_type="agent",
                subagent_id=payload_subagent_id(event.payload_json),
            )
        return None

    def is_completion(self, event: Event) -> bool:
        payload = event.payload_json
        if (
            string_value(payload.get("type")) == "system"
            and string_value(payload.get("subtype")) == "turn_duration"
        ):
            return True

        message = _message(payload)
        stop_reason = string_value(message.get("stop_reason")) or string_value(payload.get("stop_reason"))
        if stop_reason != "end_turn":
            return False
        role = string_value(message.get("role")) or string_value(payload.get("type"))
        return role == "assistant" or string_value(payload.get("type")) == "assistant"

    def subagent_state(self, event: Event) -> AgentSubagentState:
        return claude_code_subagent_state(event)

    def summary_text(self, event: Event) -> str:
        chat = self.project_chat(event)
        if chat is not None:
            return chat.body
        return message_content(event.payload_json) or self.normalize(
            event.payload_json, source_path=event.source_id, cursor=None
        ).text or json_text(event.payload_json)

    def index_text(self, event: Event) -> str:
        return self.summary_text(event)
