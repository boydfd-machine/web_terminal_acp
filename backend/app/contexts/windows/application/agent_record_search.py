from __future__ import annotations

from uuid import UUID

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.contexts.windows.api.schemas import (
    AgentRecordSearchOut,
    AgentRecordSearchResultOut,
    SearchMatchOut,
)
from app.contexts.windows.application.agent_event_projection import payload_provider
from app.contexts.windows.application.agent_record_projection import (
    _chat_message_out,
    _deduped_chat_projection_items,
    _sessions_by_source_id,
    _subagent_targets_by_tool_use_id,
)
from app.models import Event, EventSourceType

AGENT_RECORD_SEARCH_SCAN_EVENT_LIMIT = 2000


def agent_record_search_event_filter():
    return or_(
        Event.kind.in_(("user_message", "assistant_message")),
        and_(
            Event.kind == "system_message",
            Event.source_type == EventSourceType.agent_tool_record,
        ),
        Event.kind.in_(("response_item", "event_msg")),
    )


async def search_agent_record_messages(
    session: AsyncSession,
    *,
    client_id: UUID,
    query: str,
    window_id: UUID | None = None,
    limit: int = 25,
    offset: int = 0,
) -> AgentRecordSearchOut:
    normalized_query = query.strip()
    if not normalized_query:
        return AgentRecordSearchOut(
            query=normalized_query,
            results=[],
            total=0,
            limit=limit,
            offset=offset,
            has_more=False,
            scope="window" if window_id is not None else "global",
        )

    event_filters = [
        Event.client_id == client_id,
        agent_record_search_event_filter(),
    ]
    if window_id is not None:
        event_filters.append(Event.virtual_window_id == window_id)

    raw_events = list(
        await session.scalars(
            select(Event)
            .options(selectinload(Event.ai_session))
            .where(*event_filters)
            .order_by(Event.created_at.desc(), Event.id.desc())
            .limit(AGENT_RECORD_SEARCH_SCAN_EVENT_LIMIT)
        )
    )
    events = list(reversed(raw_events))
    sessions_by_source_id = _sessions_by_source_id(events)
    subagent_targets_by_tool_use_id = _subagent_targets_by_tool_use_id(events)
    matches: list[AgentRecordSearchResultOut] = []
    for event, projection in _deduped_chat_projection_items(events):
        if event.virtual_window_id is None:
            continue
        text_matches = _search_text_matches(projection.body, normalized_query, field="body")
        if not text_matches:
            continue
        message = _chat_message_out(
            event,
            projection,
            sessions_by_source_id,
            subagent_targets_by_tool_use_id,
        )
        provider = event.ai_session.provider if event.ai_session is not None else payload_provider(event)
        matches.append(
            AgentRecordSearchResultOut(
                message=message,
                window_id=event.virtual_window_id,
                session_id=event.ai_session_id,
                provider=provider,
                matches=text_matches,
            )
        )

    matches.reverse()
    paged = matches[offset : offset + limit]
    return AgentRecordSearchOut(
        query=normalized_query,
        results=paged,
        total=len(matches),
        limit=limit,
        offset=offset,
        has_more=offset + len(paged) < len(matches),
        scope="window" if window_id is not None else "global",
    )


def _search_text_matches(text: str, query: str, *, field: str) -> list[SearchMatchOut]:
    lowered_text = text.lower()
    lowered_query = query.lower()
    if not lowered_query:
        return []
    matches: list[SearchMatchOut] = []
    start = 0
    while len(matches) < 20:
        index = lowered_text.find(lowered_query, start)
        if index < 0:
            break
        matches.append(SearchMatchOut(field=field, start=index, end=index + len(query)))
        start = index + max(len(query), 1)
    return matches
