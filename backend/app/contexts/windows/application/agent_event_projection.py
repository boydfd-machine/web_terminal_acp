from __future__ import annotations

import contextlib
from typing import Literal
from uuid import UUID

from app.platform.plugins.agent_tools import get_agent_tool_registry
from app.platform.plugins.agent_tools.common import fallback_projection
from app.platform.plugins.agent_tools.types import AgentChatProjection, AgentEventProjection, AgentToolAdapter
from app.models import AiSession, Event, EventSourceType
from app.contexts.activity.api.schemas import AgentEventOut, AgentEventProjectionOut
from app.contexts.agent_profiles.application.capabilities import canonical_provider


def canonical_agent_provider(provider: str) -> str:
    return canonical_provider(provider)


def string_value(value: object) -> str | None:
    return value if isinstance(value, str) and value.strip() else None


def payload_provider(event: Event) -> str | None:
    provider = event.payload_json.get("provider")
    if isinstance(provider, str) and provider.strip():
        return canonical_agent_provider(provider.strip())
    return None


def adapter_for_event(event: Event) -> AgentToolAdapter | None:
    registry = get_agent_tool_registry()

    if event.ai_session is not None and event.ai_session.provider:
        with contextlib.suppress(ValueError):
            return registry.by_provider(canonical_agent_provider(event.ai_session.provider))

    if event.source_type is EventSourceType.agent_tool_record:
        provider = payload_provider(event)
        if provider is not None:
            with contextlib.suppress(ValueError):
                return registry.by_provider(provider)
        return None

    with contextlib.suppress(KeyError, ValueError):
        return registry.by_source_type(event.source_type)
    return None


def agent_message_type(value: str | None) -> Literal["agent", "subagent_call", "subagent_result"] | None:
    if value in {"agent", "subagent_call", "subagent_result"}:
        return value
    return None


def target_session_id_for_source(
    source_id: str | None,
    sessions_by_source_id: dict[str, AiSession],
) -> UUID | None:
    if source_id is None:
        return None
    return sessions_by_source_id.get(source_id).id if source_id in sessions_by_source_id else None


def projection_target_source_id(
    projection: AgentEventProjection | AgentChatProjection,
    subagent_targets_by_tool_use_id: dict[str, str],
) -> str | None:
    if projection.target_session_source_id is not None:
        return projection.target_session_source_id
    if projection.subagent_tool_use_id is None:
        return None
    return subagent_targets_by_tool_use_id.get(projection.subagent_tool_use_id)


def projection_out(
    projection: AgentEventProjection,
    sessions_by_source_id: dict[str, AiSession] | None = None,
    subagent_targets_by_tool_use_id: dict[str, str] | None = None,
) -> AgentEventProjectionOut:
    sessions_by_source_id = sessions_by_source_id or {}
    target_session_source_id = projection_target_source_id(
        projection,
        subagent_targets_by_tool_use_id or {},
    )
    return AgentEventProjectionOut(
        tone=projection.tone,
        label=projection.label,
        body=projection.body,
        body_format=projection.body_format,
        subtype=projection.subtype,
        agent_message_type=agent_message_type(projection.agent_message_type),
        subagent_id=projection.subagent_id,
        subagent_tool_use_id=projection.subagent_tool_use_id,
        target_session_id=target_session_id_for_source(target_session_source_id, sessions_by_source_id),
        target_session_source_id=target_session_source_id,
    )


def project_event(
    event: Event,
    sessions_by_source_id: dict[str, AiSession] | None = None,
    subagent_targets_by_tool_use_id: dict[str, str] | None = None,
) -> AgentEventProjectionOut:
    adapter = adapter_for_event(event)
    projection: AgentEventProjection | None = None
    if adapter is not None:
        with contextlib.suppress(Exception):
            projection = adapter.project_event(event)
    return projection_out(
        projection or fallback_projection(event),
        sessions_by_source_id,
        subagent_targets_by_tool_use_id,
    )


def to_agent_event_out(
    event: Event,
    sessions_by_source_id: dict[str, AiSession] | None = None,
    subagent_targets_by_tool_use_id: dict[str, str] | None = None,
) -> AgentEventOut:
    return AgentEventOut(
        id=event.id,
        ai_session_id=event.ai_session_id,
        source_type=event.source_type.value,
        source_id=event.source_id,
        kind=event.kind,
        payload_json=event.payload_json,
        projection=project_event(event, sessions_by_source_id, subagent_targets_by_tool_use_id),
        created_at=event.created_at,
    )


def project_chat(event: Event) -> AgentChatProjection | None:
    adapter = adapter_for_event(event)
    if adapter is not None:
        with contextlib.suppress(Exception):
            return adapter.project_chat(event)
    return None
