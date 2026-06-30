from __future__ import annotations

import json
import re
from typing import Any

from app.platform.plugins.agent_tools.common import json_markdown, string_value
from app.platform.plugins.agent_tools.types import (
    AgentChatProjection,
    AgentEventProjection,
    AgentSubagentState,
)
from app.platform.plugins.agent_tools.user_input import extract_real_user_input
from app.models import Event

PARENT_MESSAGE_RE = re.compile(
    r"\[Message\]\s+"
    r"timestamp=(?P<timestamp>\S+)\s+"
    r"sender=(?P<sender>\S+)\s+"
    r"priority=(?P<priority>\S+)\s+"
    r"content=(?P<content>.*?)(?:\n</SYSTEM_MESSAGE>|$)",
    re.DOTALL,
)


def extract_parent_message(payload: dict[str, Any]) -> dict[str, str] | None:
    if string_value(payload.get("type")) != "SYSTEM_MESSAGE":
        return None
    content = string_value(payload.get("content"))
    if content is None:
        return None
    match = PARENT_MESSAGE_RE.search(content)
    if match is None:
        return None
    message = {key: value.strip() for key, value in match.groupdict().items() if value is not None}
    return message if message.get("sender") and message.get("content") else None


def payload_subagent_id(payload: dict[str, Any]) -> str | None:
    value = string_value(payload.get("agentId")) or string_value(payload.get("subagent_id")) or string_value(payload.get("subagentId"))
    if value:
        return value
    metadata = payload.get("subagent")
    if isinstance(metadata, dict):
        value = string_value(metadata.get("agent_id")) or string_value(metadata.get("agentId"))
        if value:
            return value
    tool_use_result = payload.get("toolUseResult")
    if isinstance(tool_use_result, dict):
        value = string_value(tool_use_result.get("agentId"))
        if value:
            return value
    parent_message = extract_parent_message(payload)
    if parent_message is not None:
        return parent_message.get("sender")
    return None


def payload_subagent_tool_use_id(payload: dict[str, Any]) -> str | None:
    value = string_value(payload.get("subagent_tool_use_id")) or string_value(payload.get("subagentToolUseId"))
    if value:
        return value
    metadata = payload.get("subagent")
    if isinstance(metadata, dict):
        value = string_value(metadata.get("tool_use_id")) or string_value(metadata.get("toolUseId"))
        if value:
            return value
    tool_use_result = payload.get("toolUseResult")
    if isinstance(tool_use_result, dict):
        value = string_value(tool_use_result.get("toolUseId"))
        if value:
            return value
    step_index = payload.get("step_index")
    if isinstance(step_index, int) and payload.get("type") == "INVOKE_SUBAGENT":
        return f"step-{step_index - 1}"
    return None


def subagent_state(event: Event) -> AgentSubagentState:
    payload = event.payload_json
    return AgentSubagentState(
        is_sidechain=payload.get("isSidechain") is True and payload_subagent_id(payload) is not None,
        is_call=subagent_call_projection(payload, event.kind) is not None,
        is_result=subagent_result_projection(payload, event.kind) is not None,
    )


def _invoke_subagent_call(payload: dict[str, Any]) -> dict[str, Any] | None:
    tool_calls = payload.get("tool_calls")
    if not isinstance(tool_calls, list):
        return None
    for call in tool_calls:
        if isinstance(call, dict) and call.get("name") == "invoke_subagent":
            return call
    return None


def _subagent_parts(args: dict[str, Any]) -> list[str]:
    subagents_val = args.get("Subagents")
    subagents: Any = []
    if isinstance(subagents_val, str):
        try:
            subagents = json.loads(subagents_val)
        except Exception:
            pass
    elif isinstance(subagents_val, list):
        subagents = subagents_val

    parts: list[str] = []
    if isinstance(subagents, list) and subagents:
        for subagent in subagents:
            if not isinstance(subagent, dict):
                continue
            prompt = subagent.get("Prompt")
            role = subagent.get("Role")
            typename = subagent.get("TypeName")
            if role:
                parts.append(f"Description: {role}")
            if typename:
                parts.append(f"Type: {typename}")
            if prompt:
                parts.append(prompt)
    return parts


def _matched_subagent_id(payload: dict[str, Any], tool_use_id: str | None) -> str | None:
    matches = payload.get("subagent_tool_use_results")
    if not isinstance(matches, list) or not matches or tool_use_id is None:
        return None
    for item in matches:
        if isinstance(item, dict) and item.get("tool_use_id") == tool_use_id:
            return string_value(item.get("agent_id") or item.get("agentId"))
    return None


def subagent_call_projection(payload: dict[str, Any], event_kind: str) -> AgentEventProjection | None:
    invoke_call = _invoke_subagent_call(payload)
    if invoke_call is None:
        return None
    args = invoke_call.get("args") or {}
    if not isinstance(args, dict):
        return None
    parts = _subagent_parts(args)
    body = "\n\n".join(parts) if parts else json_markdown(args)
    step_index = payload.get("step_index")
    tool_use_id = f"step-{step_index}" if isinstance(step_index, int) else None
    agent_id = _matched_subagent_id(payload, tool_use_id)
    return AgentEventProjection(
        tone="subagent-call",
        label="Subagent call",
        body=body,
        body_format="markdown" if parts else "json",
        subtype=event_kind,
        agent_message_type="subagent_call",
        subagent_id=agent_id,
        subagent_tool_use_id=tool_use_id,
        target_session_source_id=f"agent-{agent_id}" if agent_id else None,
    )


def subagent_result_projection(payload: dict[str, Any], event_kind: str) -> AgentEventProjection | None:
    parent_message = extract_parent_message(payload)
    if parent_message is None:
        return None

    agent_id = payload_subagent_id(payload)
    if agent_id is None:
        return None
    tool_use_id = payload_subagent_tool_use_id(payload)
    body = parent_message.get("content", "").strip()
    return AgentEventProjection(
        tone="subagent-result",
        label="Subagent result",
        body=body or json_markdown(parent_message),
        body_format="markdown",
        subtype=event_kind,
        agent_message_type="subagent_result",
        subagent_id=agent_id,
        subagent_tool_use_id=tool_use_id,
        target_session_source_id=f"agent-{agent_id}" if agent_id else None,
    )


def subagent_call_chat_projection(event: Event) -> AgentChatProjection | None:
    projection = subagent_call_projection(event.payload_json, event.kind)
    if projection is None:
        return None
    source = subagent_call_source_id(event)
    key = f"{source}:subagent-call:{projection.subagent_tool_use_id or projection.body}"
    return AgentChatProjection(
        "agent",
        projection.body,
        projection.body_format,
        dedupe_key=key,
        agent_message_type="subagent_call",
        subagent_id=projection.subagent_id,
        subagent_tool_use_id=projection.subagent_tool_use_id,
        target_session_source_id=projection.target_session_source_id,
    )


def subagent_result_chat_projection(event: Event) -> AgentChatProjection | None:
    projection = subagent_result_projection(event.payload_json, event.kind)
    if projection is None:
        return None
    source = str(event.ai_session_id or event.source_id)
    key = f"{source}:subagent-result:{projection.subagent_tool_use_id or event.id}"
    return AgentChatProjection(
        "agent",
        projection.body,
        projection.body_format,
        dedupe_key=key,
        agent_message_type="subagent_result",
        subagent_id=projection.subagent_id,
        subagent_tool_use_id=projection.subagent_tool_use_id,
        target_session_source_id=projection.target_session_source_id,
    )


def subagent_prompt_chat_projection(event: Event, body: str) -> AgentChatProjection | None:
    payload = event.payload_json
    if payload.get("isSidechain") is not True:
        return None
    agent_id = payload_subagent_id(payload)
    if agent_id is None:
        return None
    tool_use_id = payload_subagent_tool_use_id(payload)
    body = extract_real_user_input(body, provider="antigravity_cli") or body
    source = subagent_call_source_id(event)
    key = f"{source}:subagent-call:{tool_use_id or body}"
    return AgentChatProjection(
        "agent",
        body,
        dedupe_key=key,
        is_canonical=False,
        is_duplicate_candidate=True,
        agent_message_type="subagent_call",
        subagent_id=agent_id,
        subagent_tool_use_id=tool_use_id,
    )


def subagent_call_source_id(event: Event) -> str:
    return string_value(event.payload_json.get("sessionId")) or string_value(event.payload_json.get("session_id")) or str(event.source_id)
