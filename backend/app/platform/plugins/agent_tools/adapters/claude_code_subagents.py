from __future__ import annotations

import re
from typing import Any

from app.platform.plugins.agent_tools.common import content_text, json_markdown, string_value
from app.platform.plugins.agent_tools.types import (
    AgentChatProjection,
    AgentEventProjection,
    AgentSubagentState,
)
from app.models import Event

_FINISHED_TASK_STATUSES = {"completed", "failed", "error", "cancelled", "canceled"}
_TASK_NOTIFICATION_STATUS_RE = re.compile(
    r"<status>\s*([^<\s]+)\s*</status>",
    re.IGNORECASE,
)


def _message(payload: dict[str, Any]) -> dict[str, Any]:
    message = payload.get("message")
    return message if isinstance(message, dict) else {}


def _raw_content(payload: dict[str, Any]) -> Any:
    message = _message(payload)
    if "content" in message:
        return message.get("content")
    return payload.get("content")


def _content_blocks(payload: dict[str, Any]) -> list[dict[str, Any]]:
    content = _raw_content(payload)
    if not isinstance(content, list):
        return []
    return [block for block in content if isinstance(block, dict)]


def _tool_use_blocks(payload: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        block for block in _content_blocks(payload)
        if string_value(block.get("type")) == "tool_use"
    ]


def _tool_result_blocks(payload: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        block for block in _content_blocks(payload)
        if string_value(block.get("type")) == "tool_result"
    ]


def _agent_tool_use_block(payload: dict[str, Any]) -> dict[str, Any] | None:
    for block in _tool_use_blocks(payload):
        if string_value(block.get("name")) == "Agent":
            return block
    return None


def _agent_tool_result_block(payload: dict[str, Any]) -> dict[str, Any] | None:
    tool_use_id = payload_subagent_tool_use_id(payload)
    for block in _tool_result_blocks(payload):
        if tool_use_id is None or string_value(block.get("tool_use_id")) == tool_use_id:
            return block
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
    for block in _tool_result_blocks(payload):
        value = string_value(block.get("tool_use_id"))
        if value:
            return value
    return None


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
    return None


def subagent_source_id(agent_id: str | None) -> str | None:
    return f"agent-{agent_id}" if agent_id else None


def subagent_state(event: Event) -> AgentSubagentState:
    payload = event.payload_json
    async_launch = async_subagent_launch_event(event)
    return AgentSubagentState(
        is_sidechain=payload.get("isSidechain") is True and payload_subagent_id(payload) is not None,
        is_call=subagent_call_projection(payload, event.kind) is not None,
        is_result=(not async_launch and subagent_result_projection(payload, event.kind) is not None),
        is_async_launch=async_launch,
        is_finished_notification=finished_task_notification_event(event),
        pending_background_agent_count=pending_background_agent_count(event),
    )


def async_subagent_launch_event(event: Event) -> bool:
    result = _tool_use_result(event.payload_json)
    if result is None:
        return False
    return (
        result.get("isAsync") is True
        and string_value(result.get("status")) == "async_launched"
        and string_value(result.get("agentId")) is not None
    )


def pending_background_agent_count(event: Event) -> int | None:
    payload = event.payload_json
    if string_value(payload.get("type")) != "system":
        return None
    if string_value(payload.get("subtype")) != "turn_duration":
        return None
    value = payload.get("pendingBackgroundAgentCount")
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return max(0, value)
    if isinstance(value, str) and value.isdigit():
        return int(value)
    return None


def finished_task_notification_event(event: Event) -> bool:
    body = _message_text(event.payload_json)
    if body is None or "<task-notification" not in body.lower():
        return False
    status = _task_notification_status(body)
    return status in _FINISHED_TASK_STATUSES


def _tool_use_result(payload: dict[str, Any]) -> dict[str, Any] | None:
    result = payload.get("toolUseResult")
    return result if isinstance(result, dict) else None


def _message_text(payload: dict[str, Any]) -> str | None:
    message = payload.get("message")
    if isinstance(message, dict):
        content = message.get("content")
    else:
        content = payload.get("content")
    return content if isinstance(content, str) else None


def _task_notification_status(body: str) -> str | None:
    match = _TASK_NOTIFICATION_STATUS_RE.search(body)
    if match is None:
        return None
    return match.group(1).strip().lower() or None


def _subagent_id_for_tool_use(payload: dict[str, Any], tool_use_id: str | None) -> str | None:
    if tool_use_id is None:
        return None
    matches = payload.get("subagent_tool_use_results")
    if not isinstance(matches, list):
        return None
    for item in matches:
        if not isinstance(item, dict):
            continue
        item_tool_use_id = string_value(item.get("tool_use_id")) or string_value(item.get("toolUseId"))
        if item_tool_use_id == tool_use_id:
            return string_value(item.get("agent_id")) or string_value(item.get("agentId"))
    return None


def subagent_call_projection(payload: dict[str, Any], event_kind: str) -> AgentEventProjection | None:
    block = _agent_tool_use_block(payload)
    if block is None:
        return None
    input_payload = block.get("input")
    input_dict = input_payload if isinstance(input_payload, dict) else {}
    prompt = string_value(input_dict.get("prompt"))
    description = string_value(input_dict.get("description"))
    subagent_type = string_value(input_dict.get("subagent_type"))
    tool_use_id = string_value(block.get("id"))
    agent_id = _subagent_id_for_tool_use(payload, tool_use_id)
    parts = []
    if description:
        parts.append(f"Description: {description}")
    if subagent_type:
        parts.append(f"Type: {subagent_type}")
    if prompt:
        parts.append(prompt)
    body = "\n\n".join(parts) or json_markdown(input_payload or {})
    return AgentEventProjection(
        tone="subagent-call",
        label="Subagent call",
        body=body,
        body_format="markdown" if parts else "json",
        subtype=event_kind,
        agent_message_type="subagent_call",
        subagent_id=agent_id,
        subagent_tool_use_id=tool_use_id,
        target_session_source_id=subagent_source_id(agent_id),
    )


def _tool_result_content_text(block: dict[str, Any]) -> str:
    content = block.get("content")
    if isinstance(content, str):
        return content
    return content_text(content) if content is not None else json_markdown(block)


def subagent_result_projection(payload: dict[str, Any], event_kind: str) -> AgentEventProjection | None:
    block = _agent_tool_result_block(payload)
    if block is None:
        return None
    agent_id = payload_subagent_id(payload)
    if agent_id is None:
        return None
    tool_use_id = payload_subagent_tool_use_id(payload) or string_value(block.get("tool_use_id"))
    body = _tool_result_content_text(block)
    if agent_id:
        body = strip_subagent_usage_tail(body)
    return AgentEventProjection(
        tone="subagent-result",
        label="Subagent result",
        body=body,
        body_format="markdown",
        subtype=event_kind,
        agent_message_type="subagent_result",
        subagent_id=agent_id,
        subagent_tool_use_id=tool_use_id,
        target_session_source_id=subagent_source_id(agent_id),
    )


def strip_subagent_usage_tail(body: str) -> str:
    marker = "\nagentId:"
    index = body.find(marker)
    if index >= 0:
        return body[:index].strip()
    return body.strip()


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


def subagent_prompt_chat_projection(event: Event, body: str) -> AgentChatProjection | None:
    payload = event.payload_json
    if payload.get("isSidechain") is not True:
        return None
    agent_id = payload_subagent_id(payload)
    if agent_id is None:
        return None
    tool_use_id = payload_subagent_tool_use_id(payload)
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
    return string_value(event.payload_json.get("sessionId")) or str(event.source_id)


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
