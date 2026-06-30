from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from typing import Literal

from fastapi import HTTPException
from sqlalchemy import Text, and_, case, cast, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.platform.plugins.agent_tools.types import AgentChatProjection
from app.contexts.windows.application.agent_event_projection import (
    agent_message_type as _agent_message_type,
    project_chat as _project_chat,
    projection_target_source_id as _projection_target_source_id,
    string_value as _string_value,
    target_session_id_for_source as _target_session_id_for_source,
)
from app.contexts.activity.application.agent_token_usage import payload_is_token_usage_only
from app.models import AiSession, Event, EventSourceType
from app.contexts.windows.api.schemas import (
    AgentChatMessageOut,
    CommandHistoryItemOut,
)
from app.contexts.windows.application.agent_record_chat_paging import (
    AgentChatOrder,
    ChatMessagePage,
    chat_event_order_by,
    has_unresolved_leading_duplicate,
    latest_chat_message_page,
)
from app.contexts.agent_profiles.application.capabilities import (
    AgentClientCapabilityError,
    require_local_agent_capability as service_require_local_agent_capability,
    require_supported_agent_capability as service_require_supported_agent_capability,
    require_supported_provider as service_require_supported_provider,
)

AgentChatRole = Literal["all", "user", "agent", "subagent_call", "subagent_result"]
AgentClientCapability = Literal["launch", "client_config", "window_config", "profile_config"]
AGENT_RECORD_CHAT_EVENT_BATCH_SIZE = 500
AGENT_RECORD_DETAIL_RELATED_EVENT_LIMIT = 500


def _chat_message_out(
    event: Event,
    projection: AgentChatProjection,
    sessions_by_source_id: dict[str, AiSession] | None = None,
    subagent_targets_by_tool_use_id: dict[str, str] | None = None,
) -> AgentChatMessageOut:
    sessions_by_source_id = sessions_by_source_id or {}
    target_session_source_id = _projection_target_source_id(
        projection,
        subagent_targets_by_tool_use_id or {},
    )
    return AgentChatMessageOut(
        id=event.id,
        ai_session_id=event.ai_session_id,
        source_type=event.source_type.value,
        source_id=event.source_id,
        role=projection.role,
        body=projection.body,
        body_format=projection.body_format,
        agent_message_type=_agent_message_type(projection.agent_message_type),
        subagent_id=projection.subagent_id,
        subagent_tool_use_id=projection.subagent_tool_use_id,
        target_session_id=_target_session_id_for_source(target_session_source_id, sessions_by_source_id),
        target_session_source_id=target_session_source_id,
        created_at=event.created_at,
    )


def _payload_datetime(event: Event, key: str) -> datetime | None:
    value = event.payload_json.get(key)
    if not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _payload_command(event: Event) -> str:
    command = _string_value(event.payload_json.get("command"))
    return command if command is not None else ""


def _payload_sequence(event: Event) -> int | str | None:
    sequence = event.payload_json.get("sequence")
    return sequence if isinstance(sequence, (int, str)) else None


def _payload_exit_status(event: Event) -> int | str | None:
    exit_status = event.payload_json.get("exit_status")
    return exit_status if isinstance(exit_status, (int, str)) else None


def _payload_sequence_key(event: Event) -> str | None:
    sequence = _payload_sequence(event)
    return str(sequence) if sequence is not None else None


def _command_history_item_out(event: Event, finished_by_sequence: dict[str, Event]) -> CommandHistoryItemOut:
    sequence_key = _payload_sequence_key(event)
    finished = finished_by_sequence.get(sequence_key) if sequence_key is not None else None
    finished_at = _payload_datetime(finished, "captured_at") if finished is not None else None
    return CommandHistoryItemOut(
        id=event.id,
        command=_payload_command(event),
        shell=_string_value(event.payload_json.get("shell")),
        cwd=_string_value(event.payload_json.get("cwd")),
        sequence=_payload_sequence(event),
        exit_status=_payload_exit_status(finished) if finished is not None else None,
        captured_at=_payload_datetime(event, "captured_at") or event.created_at,
        finished_at=finished_at,
        created_at=event.created_at,
    )


def _dedupe_chat_messages(
    events: list[Event],
    role: AgentChatRole = "all",
    sessions_by_source_id: dict[str, AiSession] | None = None,
) -> list[AgentChatMessageOut]:
    sessions_by_source_id = sessions_by_source_id or _sessions_by_source_id(events)
    subagent_targets_by_tool_use_id = _subagent_targets_by_tool_use_id(events)
    return [
        _chat_message_out(
            event,
            projection,
            sessions_by_source_id,
            subagent_targets_by_tool_use_id,
        )
        for event, projection in _deduped_chat_projection_items(events)
        if _chat_role_matches(projection, role)
    ]


@dataclass(frozen=True)
class CompactAgentChatMessage:
    role: Literal["user", "agent"]
    body: str
    body_format: Literal["markdown", "json"]
    source_id: str
    created_at: datetime


async def _load_chat_message_page(
    session: AsyncSession,
    *,
    event_filters: list[object],
    target_event_filters: list[object],
    role: AgentChatRole,
    sessions_by_source_id: dict[str, AiSession],
    messages_limit: int,
    messages_offset: int,
    messages_order: AgentChatOrder = "earliest",
) -> ChatMessagePage:
    raw_total = (
        await session.scalar(select(func.count()).select_from(Event).where(*event_filters))
    ) or 0
    batch_size = max(messages_limit + messages_offset + 1, AGENT_RECORD_CHAT_EVENT_BATCH_SIZE)
    target_count = messages_offset + messages_limit + 1
    chat_items: list[tuple[Event, AgentChatProjection]] = []
    pending_duplicate_items: list[tuple[Event, AgentChatProjection]] = []
    target_events: list[Event] = []
    raw_offset = 0
    exhausted = True
    deduped_items: list[tuple[Event, AgentChatProjection]] = []

    while raw_offset < raw_total:
        raw_events = list(
            await session.scalars(
                select(Event)
                .options(selectinload(Event.ai_session))
                .where(*event_filters)
                .order_by(*chat_event_order_by(messages_order))
                .offset(raw_offset)
                .limit(batch_size)
            )
        )
        if not raw_events:
            break
        if messages_order == "latest":
            raw_events.reverse()
            target_events = [*raw_events, *target_events]
        else:
            target_events.extend(raw_events)
        raw_offset += len(raw_events)
        if messages_order == "latest":
            chat_items = [*_deduped_chat_projection_items(raw_events), *chat_items]
        else:
            next_items = pending_duplicate_items + _deduped_chat_projection_items(raw_events)
            pending_duplicate_items = _trailing_duplicate_chat_projection_items(next_items)
            chat_items = [*chat_items, *next_items[: len(next_items) - len(pending_duplicate_items)]]
        deduped_items = _dedupe_chat_projection_items(chat_items)
        if (
            raw_offset < raw_total
            and not has_unresolved_leading_duplicate(deduped_items, messages_order)
            and _matching_chat_item_count(deduped_items, role) >= target_count
        ):
            exhausted = False
            break

    if exhausted:
        chat_items.extend(pending_duplicate_items)
        deduped_items = _dedupe_chat_projection_items(chat_items)
    target_events.extend(
        await _load_antigravity_subagent_target_events(
            session,
            event_filters=target_event_filters,
        )
    )
    subagent_targets_by_tool_use_id = _subagent_targets_by_tool_use_id(target_events)
    messages = [
        _chat_message_out(
            event,
            projection,
            sessions_by_source_id,
            subagent_targets_by_tool_use_id,
        )
        for event, projection in deduped_items
        if _chat_role_matches(projection, role)
    ]
    if messages_order == "latest":
        return latest_chat_message_page(
            messages,
            messages_limit=messages_limit,
            messages_offset=messages_offset,
            exhausted=exhausted,
        )
    paged_messages = messages[messages_offset : messages_offset + messages_limit]
    has_more = len(messages) > messages_offset + len(paged_messages)
    total = len(messages) if exhausted else messages_offset + len(paged_messages) + (1 if has_more else 0)
    return ChatMessagePage(
        messages=paged_messages,
        total=total,
        total_exact=exhausted,
        has_more=has_more,
    )


async def load_compact_agent_chat_messages(
    session: AsyncSession,
    *,
    client_id,
    window_id,
    message_limit: int = 200,
) -> list[CompactAgentChatMessage]:
    events = list(
        await session.scalars(
            select(Event)
            .options(selectinload(Event.ai_session))
            .where(
                Event.client_id == client_id,
                Event.virtual_window_id == window_id,
                or_(
                    Event.kind.in_(("user_message", "assistant_message")),
                    and_(
                        Event.kind == "system_message",
                        Event.source_type == EventSourceType.agent_tool_record,
                    ),
                    Event.kind.in_(("response_item", "event_msg")),
                ),
            )
            .order_by(
                Event.created_at,
                case((Event.source_type == EventSourceType.terminal, 1), else_=0),
                Event.id,
            )
            .limit(max(message_limit * 4, AGENT_RECORD_CHAT_EVENT_BATCH_SIZE))
        )
    )
    compacted: list[CompactAgentChatMessage] = []
    pending_agent: CompactAgentChatMessage | None = None
    for event, projection in _deduped_chat_projection_items(events):
        if projection.role == "agent":
            pending_agent = CompactAgentChatMessage(
                role="agent",
                body=projection.body,
                body_format=projection.body_format,
                source_id=event.source_id,
                created_at=event.created_at,
            )
            continue
        if pending_agent is not None:
            compacted.append(pending_agent)
            pending_agent = None
        compacted.append(
            CompactAgentChatMessage(
                role="user",
                body=projection.body,
                body_format=projection.body_format,
                source_id=event.source_id,
                created_at=event.created_at,
            )
        )
    if pending_agent is not None:
        compacted.append(pending_agent)
    return compacted[:message_limit]


async def _load_antigravity_subagent_target_events(
    session: AsyncSession,
    *,
    event_filters: list[object],
) -> list[Event]:
    return list(
        await session.scalars(
            select(Event)
            .where(
                *event_filters,
                Event.kind == "tool_result",
                Event.source_type == EventSourceType.agent_tool_record,
                cast(Event.payload_json, Text).contains("antigravity_cli"),
                cast(Event.payload_json, Text).contains("INVOKE_SUBAGENT"),
            )
            .order_by(Event.created_at, Event.id)
            .limit(AGENT_RECORD_DETAIL_RELATED_EVENT_LIMIT)
        )
    )


def _matching_chat_item_count(items: list[tuple[Event, AgentChatProjection]], role: AgentChatRole) -> int:
    return sum(1 for _event, projection in items if _chat_role_matches(projection, role))


def _sessions_by_source_id(events: list[Event]) -> dict[str, AiSession]:
    sessions: dict[str, AiSession] = {}
    for event in events:
        if event.ai_session is not None:
            sessions[event.ai_session.source_id] = event.ai_session
    return sessions


def _subagent_targets_by_tool_use_id(events: list[Event]) -> dict[str, str]:
    targets: dict[str, str] = {}
    for event in events:
        payload = event.payload_json
        raw_target = _raw_antigravity_subagent_target(payload)
        if raw_target is not None:
            targets.setdefault(raw_target[0], raw_target[1])
        tool_use_result = payload.get("toolUseResult")
        if isinstance(tool_use_result, dict):
            tool_use_id = _string_value(tool_use_result.get("toolUseId"))
            agent_id = _string_value(tool_use_result.get("agentId"))
            if tool_use_id is not None and agent_id is not None:
                targets.setdefault(tool_use_id, f"agent-{agent_id}")
        subagent = payload.get("subagent")
        if isinstance(subagent, dict):
            tool_use_id = _string_value(subagent.get("toolUseId")) or _string_value(subagent.get("tool_use_id"))
            agent_id = _string_value(payload.get("agentId")) or _string_value(subagent.get("agentId")) or _string_value(subagent.get("agent_id"))
            if tool_use_id is not None and agent_id is not None:
                targets.setdefault(tool_use_id, f"agent-{agent_id}")
        matches = payload.get("subagent_tool_use_results")
        if isinstance(matches, list):
            for item in matches:
                if not isinstance(item, dict):
                    continue
                tool_use_id = _string_value(item.get("tool_use_id")) or _string_value(item.get("toolUseId"))
                agent_id = _string_value(item.get("agent_id")) or _string_value(item.get("agentId"))
                if tool_use_id is not None and agent_id is not None:
                    targets.setdefault(tool_use_id, f"agent-{agent_id}")
    return targets


def _raw_antigravity_subagent_target(payload: dict) -> tuple[str, str] | None:
    provider = _string_value(payload.get("provider"))
    if provider != "antigravity_cli":
        return None
    if _string_value(payload.get("type")) != "INVOKE_SUBAGENT":
        return None
    step_index = payload.get("step_index")
    if not isinstance(step_index, int):
        return None
    content = _string_value(payload.get("content"))
    if content is None:
        return None
    match = re.search(r'"conversationId"\s*:\s*"([^"]+)"', content)
    if match is None:
        return None
    agent_id = match.group(1).strip()
    if not agent_id:
        return None
    return f"step-{step_index - 1}", f"agent-{agent_id}"


def _chat_role_matches(projection: AgentChatProjection, role: AgentChatRole) -> bool:
    if role == "all":
        return True
    if role in {"subagent_call", "subagent_result"}:
        return projection.agent_message_type == role
    if role == "user":
        return projection.role == "user"
    return projection.role == role and (
        projection.agent_message_type in {None, "agent"} if role == "agent" else True
    )


def _dedupe_chat_projection_items(
    events: list[tuple[Event, AgentChatProjection]]
) -> list[tuple[Event, AgentChatProjection]]:
    canonical_keys = {
        projection.dedupe_key
        for _event, projection in events
        if projection.is_canonical and projection.dedupe_key is not None
    }
    canonical_role_bodies = {
        (projection.role, projection.agent_message_type, projection.body)
        for _event, projection in events
        if projection.is_canonical
    }
    return [
        (event, projection)
        for event, projection in events
        if not (
            projection.is_duplicate_candidate
            and (
                (
                    projection.dedupe_key is not None
                    and projection.dedupe_key in canonical_keys
                )
                or (projection.role, projection.agent_message_type, projection.body)
                in canonical_role_bodies
            )
        )
    ]


def _deduped_chat_projection_items(events: list[Event]) -> list[tuple[Event, AgentChatProjection]]:
    items: list[tuple[Event, AgentChatProjection]] = []
    for event in events:
        projection = _project_chat(event)
        if projection is None or projection.role not in {"user", "agent"}:
            continue
        items.append((event, projection))
    return _dedupe_chat_projection_items(items)


def _trailing_duplicate_chat_projection_items(
    items: list[tuple[Event, AgentChatProjection]],
) -> list[tuple[Event, AgentChatProjection]]:
    trailing: list[tuple[Event, AgentChatProjection]] = []
    for event, projection in reversed(items):
        if not projection.is_duplicate_candidate or projection.dedupe_key is None:
            break
        trailing.append((event, projection))
    trailing.reverse()
    return trailing


def _dedupe_detail_events(events: list[Event]) -> list[Event]:
    chat_items: list[tuple[Event, AgentChatProjection]] = []
    for event in events:
        projection = _project_chat(event)
        if projection is not None and projection.role in {"user", "agent"}:
            chat_items.append((event, projection))

    duplicate_event_ids = {event.id for event, _projection in chat_items} - {
        event.id for event, _projection in _dedupe_chat_projection_items(chat_items)
    }
    return [
        event
        for event in events
        if event.id not in duplicate_event_ids
        and not payload_is_token_usage_only(event.payload_json)
    ]


def _require_supported_agent_capability(provider: str | None, capability: AgentClientCapability) -> str:
    try:
        return service_require_supported_agent_capability(provider, capability)
    except AgentClientCapabilityError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc


def _require_local_agent_capability(agent: str, capability: AgentClientCapability) -> str:
    try:
        return service_require_local_agent_capability(agent, capability)
    except AgentClientCapabilityError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc


def _require_supported_provider(provider: str | None) -> str:
    try:
        return service_require_supported_provider(provider)
    except AgentClientCapabilityError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc


__all__ = [name for name in globals() if not name.startswith("__")]
