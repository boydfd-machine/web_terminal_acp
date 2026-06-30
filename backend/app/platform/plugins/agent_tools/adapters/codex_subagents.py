from __future__ import annotations

from typing import Any

from app.models import Event
from app.platform.plugins.agent_tools.types import AgentChatProjection, AgentEventProjection
from app.shared.codex_sessions import (
    codex_is_sidechain_payload,
    codex_subagent_id_from_payload,
    codex_subagent_tool_use_id_from_payload,
)


def message_content(item: dict[str, Any]) -> Any:
    if "content" in item:
        return item.get("content")
    message = item.get("message")
    if isinstance(message, dict):
        return message.get("content")
    return None


def message_role(item: dict[str, Any]) -> str | None:
    role = _string_value(item.get("role"))
    if role is not None:
        return role
    message = item.get("message")
    if isinstance(message, dict):
        return _string_value(message.get("role"))
    return None


def subagent_state_parts(item: dict[str, Any]) -> tuple[bool, bool, bool]:
    is_sidechain = codex_is_sidechain_payload(item) and codex_subagent_id_from_payload(item) is not None
    role = message_role(item)
    return is_sidechain, is_sidechain and role == "user", is_sidechain and role == "assistant"


def subagent_projection(
    item: dict[str, Any],
    *,
    body: str,
    body_format: str = "markdown",
    event_kind: str,
    message_type: str,
) -> AgentEventProjection | None:
    if not codex_is_sidechain_payload(item):
        return None
    agent_id = codex_subagent_id_from_payload(item)
    if agent_id is None:
        return None
    tool_use_id = codex_subagent_tool_use_id_from_payload(item)
    return AgentEventProjection(
        tone="subagent-call" if message_type == "subagent_call" else "subagent-result",
        label="Subagent call" if message_type == "subagent_call" else "Subagent result",
        body=body,
        body_format=body_format,
        subtype=event_kind,
        agent_message_type=message_type,
        subagent_id=agent_id,
        subagent_tool_use_id=tool_use_id,
        target_session_source_id=_subagent_source_id(agent_id),
    )


def subagent_chat_projection(
    event: Event,
    item: dict[str, Any],
    *,
    body: str,
    body_format: str = "markdown",
    message_type: str,
) -> AgentChatProjection | None:
    projection = subagent_projection(
        item,
        body=body,
        body_format=body_format,
        event_kind=event.kind,
        message_type=message_type,
    )
    if projection is None:
        return None
    source = str(event.ai_session_id or event.source_id)
    key_type = "subagent-call" if message_type == "subagent_call" else "subagent-result"
    return AgentChatProjection(
        role="agent",
        body=projection.body,
        body_format=projection.body_format,
        dedupe_key=f"{source}:{key_type}:{projection.subagent_tool_use_id or projection.body}",
        is_canonical=message_type == "subagent_result",
        is_duplicate_candidate=message_type == "subagent_call",
        agent_message_type=message_type,
        subagent_id=projection.subagent_id,
        subagent_tool_use_id=projection.subagent_tool_use_id,
        target_session_source_id=projection.target_session_source_id,
    )


def _subagent_source_id(agent_id: str | None) -> str | None:
    return f"agent-{agent_id}" if agent_id else None


def _string_value(value: Any) -> str | None:
    if isinstance(value, str):
        value = value.strip()
        return value or None
    if isinstance(value, (int, float, bool)):
        return str(value)
    return None
