from __future__ import annotations

from typing import Any
from uuid import UUID

from app.client_agent.ai_events import ManagedAiEvent, managed_event_from_payload
from app.contexts.terminal_runtime.domain.protocol import AgentMessage


def managed_event_from_message(client_id: UUID, message: AgentMessage) -> ManagedAiEvent:
    if message.window_id is None:
        raise ValueError("window_id is required")

    provider = message.payload.get("provider")
    if not isinstance(provider, str) or not provider.strip():
        raise ValueError("provider is required")

    payload = message.payload.get("payload")
    if not isinstance(payload, dict):
        raise ValueError("payload is required")

    source_path = _optional_text(message.payload, payload, "source_path")
    cursor = _optional_cursor(message.payload, payload)
    offset = _optional_offset(message.payload, payload)
    project_path = _optional_text(
        message.payload,
        payload,
        "project_path",
        "projectPath",
    )

    event = managed_event_from_payload(
        client_id,
        message.window_id,
        provider.strip(),
        payload,
        source_path=source_path,
        offset=offset,
        cursor=cursor,
        project_path=project_path,
    )
    if event is None:
        raise ValueError("event attribution does not match client/window")
    return event


def agent_message_from_managed_event(event: ManagedAiEvent) -> AgentMessage:
    payload: dict[str, Any] = {
        "provider": event.provider,
        "payload": event.payload,
    }
    if event.source_path is not None:
        payload["source_path"] = event.source_path
    if event.offset is not None:
        payload["offset"] = event.offset
    if event.cursor is not None:
        payload["cursor"] = event.cursor
    if event.project_path is not None:
        payload["project_path"] = event.project_path
    return AgentMessage(
        type="ai_event",
        client_id=event.client_id,
        window_id=event.window_id,
        payload=payload,
    )


def _optional_text(
    message_payload: dict[str, Any],
    event_payload: dict[str, Any],
    *keys: str,
) -> str | None:
    for key in keys:
        value = message_payload.get(key)
        if value is None:
            value = event_payload.get(key)
        if value is None:
            continue
        if not isinstance(value, str):
            raise ValueError(f"{keys[0]} must be a string")
        return value
    return None


def _optional_cursor(
    message_payload: dict[str, Any],
    event_payload: dict[str, Any],
) -> str | int | None:
    value = message_payload.get("cursor")
    if value is None:
        value = event_payload.get("cursor")
    if value is not None and not isinstance(value, (str, int)):
        raise ValueError("cursor must be a string or integer")
    return value


def _optional_offset(
    message_payload: dict[str, Any],
    event_payload: dict[str, Any],
) -> int | None:
    value = message_payload.get("offset")
    if value is None:
        value = event_payload.get("offset")
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("offset must be an integer") from exc
