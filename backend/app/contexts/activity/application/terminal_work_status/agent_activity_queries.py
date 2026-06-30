# ruff: noqa: F821
"""Executed into the terminal_work_status package globals."""

from importlib import import_module

_status_service = import_module("app.contexts.activity.application.terminal_work_status.status_service")
globals().update(
    {name: value for name, value in _status_service.__dict__.items() if not name.startswith("__")}
)


async def _recent_agent_events_by_window_postgresql(
    session: AsyncSession,
    client_id: UUID,
    window_ids: list[UUID],
) -> dict[UUID, list[Event]]:
    outer_window = aliased(VirtualWindow)
    recent_events_lateral = (
        select(*_activity_event_columns(Event))
        .where(
            Event.client_id == client_id,
            Event.virtual_window_id == outer_window.id,
            _agent_activity_source_type_filter(Event),
        )
        .order_by(desc(Event.created_at), desc(Event.id))
        .limit(AGENT_EVENT_SCAN_LIMIT_PER_WINDOW)
        .lateral("recent_agent_events")
    )
    rows = list(
        (
            await session.execute(
                select(*recent_events_lateral.c)
                .select_from(outer_window)
                .join(recent_events_lateral, true())
                .where(
                    outer_window.client_id == client_id,
                    outer_window.id.in_(window_ids),
                )
                .order_by(
                    outer_window.id,
                    desc(recent_events_lateral.c.created_at),
                    desc(recent_events_lateral.c.id),
                )
            )
        ).all()
    )
    return _group_events_by_window(_activity_events_from_rows(rows))


async def _recent_agent_events_by_window_ranked(
    session: AsyncSession,
    client_id: UUID,
    window_ids: list[UUID],
) -> dict[UUID, list[Event]]:
    rank = (
        func.row_number()
        .over(
            partition_by=Event.virtual_window_id,
            order_by=(desc(Event.created_at), desc(Event.id)),
        )
        .label("event_rank")
    )
    ranked_events = (
        select(Event.id.label("event_id"), rank)
        .where(
            Event.client_id == client_id,
            Event.virtual_window_id.in_(window_ids),
            _agent_activity_source_type_filter(Event),
        )
        .subquery()
    )
    rows = list(
        (
            await session.execute(
                select(*_activity_event_columns(Event))
                .join(ranked_events, Event.id == ranked_events.c.event_id)
                .where(ranked_events.c.event_rank <= AGENT_EVENT_SCAN_LIMIT_PER_WINDOW)
                .order_by(Event.virtual_window_id, ranked_events.c.event_rank)
            )
        ).all()
    )
    return _group_events_by_window(_activity_events_from_rows(rows))


async def _agent_activity_state_by_window(
    session: AsyncSession,
    client_id: UUID,
    window_ids: list[UUID],
) -> _WindowAgentActivityState:
    if not window_ids:
        return _WindowAgentActivityState({}, {}, {}, {}, {})

    rows = await session.execute(
        select(
            VirtualWindow.id,
            VirtualWindow.agent_activity_latest_at,
            VirtualWindow.agent_activity_latest_event_id,
            VirtualWindow.agent_activity_latest_completed_at,
            VirtualWindow.agent_activity_latest_user_input_at,
            VirtualWindow.agent_activity_pending_subagent_count,
        ).where(
            VirtualWindow.client_id == client_id,
            VirtualWindow.id.in_(window_ids),
        )
    )
    latest_activity: dict[UUID, datetime] = {}
    latest_completed_at: dict[UUID, datetime] = {}
    latest_failed_at: dict[UUID, datetime] = {}
    latest_user_input_at: dict[UUID, datetime] = {}
    pending_subagent_count: dict[UUID, int] = {}
    missing_window_ids: list[UUID] = []
    stale_projection_window_ids: list[UUID] = []
    stale_projection_event_ids: dict[UUID, UUID] = {}
    for window_id, activity_at, latest_event_id, completed_at, user_input_at, pending_count in rows:
        if activity_at is None:
            missing_window_ids.append(window_id)
        else:
            latest_activity[window_id] = _aware_utc(activity_at)
        if completed_at is not None:
            completed_at = _aware_utc(completed_at)
            latest_completed_at[window_id] = completed_at
            if activity_at is not None and _aware_utc(activity_at) > completed_at:
                stale_projection_window_ids.append(window_id)
                if latest_event_id is not None:
                    stale_projection_event_ids[window_id] = latest_event_id
        elif latest_event_id is not None:
            stale_projection_window_ids.append(window_id)
            stale_projection_event_ids[window_id] = latest_event_id
        if user_input_at is not None:
            latest_user_input_at[window_id] = _aware_utc(user_input_at)
        if int(pending_count or 0) > 0:
            pending_subagent_count[window_id] = int(pending_count or 0)

    dialect_name = _dialect_name(session)
    if dialect_name == "postgresql":
        if stale_projection_window_ids:
            await _repair_stale_projected_agent_activity(
                session,
                client_id,
                stale_projection_event_ids,
                latest_activity=latest_activity,
                latest_completed_at=latest_completed_at,
                latest_failed_at=latest_failed_at,
            )
        return _WindowAgentActivityState(
            latest_activity,
            latest_completed_at,
            latest_failed_at,
            latest_user_input_at,
            pending_subagent_count,
        )
    else:
        fallback_window_ids = sorted({*missing_window_ids, *stale_projection_window_ids})

    fallback_events = await _recent_agent_events_by_window(session, client_id, fallback_window_ids)
    latest_activity.update(_latest_ai_activity_by_window(fallback_events))
    latest_completed_at.update(_latest_agent_completed_at_by_window(fallback_events))
    latest_failed_at.update(_latest_agent_failed_at_by_window(fallback_events))
    latest_user_input_at.update(
        _latest_agent_user_input_at_by_window_from_events(fallback_events)
    )
    return _WindowAgentActivityState(
        latest_activity,
        latest_completed_at,
        latest_failed_at,
        latest_user_input_at,
        pending_subagent_count,
    )


async def _repair_stale_projected_agent_activity(
    session: AsyncSession,
    client_id: UUID,
    latest_event_ids: dict[UUID, UUID],
    *,
    latest_activity: dict[UUID, datetime],
    latest_completed_at: dict[UUID, datetime],
    latest_failed_at: dict[UUID, datetime],
) -> None:
    if not latest_event_ids:
        return

    rows = list(
        (
            await session.execute(
                select(*_activity_event_columns(Event)).where(
                    Event.client_id == client_id,
                    Event.id.in_(tuple(latest_event_ids.values())),
                )
            )
        ).all()
    )
    events = _activity_events_from_rows(rows)
    events_by_id = {event.id: event for event in events}
    for window_id, event_id in latest_event_ids.items():
        event = events_by_id.get(event_id)
        if event is None or event.virtual_window_id != window_id:
            if window_id in latest_completed_at:
                latest_activity[window_id] = latest_completed_at[window_id]
            else:
                latest_activity.pop(window_id, None)
            continue
        if not event_is_agent_activity(event):
            if window_id in latest_completed_at:
                latest_activity[window_id] = latest_completed_at[window_id]
            else:
                latest_activity.pop(window_id, None)
            continue
        if event_is_agent_completion(event):
            completed_at = event_activity_time(event)
            current_completed_at = latest_completed_at.get(window_id)
            if current_completed_at is None or completed_at > current_completed_at:
                latest_completed_at[window_id] = completed_at
        if event_is_agent_failure(event):
            failed_at = event_activity_time(event)
            current_failed_at = latest_failed_at.get(window_id)
            if current_failed_at is None or failed_at > current_failed_at:
                latest_failed_at[window_id] = failed_at


def _group_events_by_window(rows: list[Event]) -> dict[UUID, list[Event]]:
    latest: dict[UUID, list[Event]] = {}
    for event in rows:
        if event.virtual_window_id is not None:
            latest.setdefault(event.virtual_window_id, []).append(event)
    return latest


def _agent_activity_source_type_filter(event_model=Event):
    return event_model.source_type.in_(
        tuple(literal_column(f"'{value}'") for value in AGENT_ACTIVITY_SOURCE_TYPES)
    )


def _latest_agent_completed_at_by_window(
    recent_agent_events: dict[UUID, list[Event]],
) -> dict[UUID, datetime]:
    latest: dict[UUID, datetime] = {}
    for window_id, events in recent_agent_events.items():
        for event in events:
            if not event_is_agent_activity(event):
                continue
            if event_is_agent_completion(event):
                completed_at = event_activity_time(event)
                if window_id not in latest or completed_at > latest[window_id]:
                    latest[window_id] = completed_at
    return latest


def _latest_agent_failed_at_by_window(
    recent_agent_events: dict[UUID, list[Event]],
) -> dict[UUID, datetime]:
    latest: dict[UUID, datetime] = {}
    for window_id, events in recent_agent_events.items():
        for event in events:
            if not event_is_agent_activity(event):
                continue
            if event_is_agent_failure(event):
                failed_at = event_activity_time(event)
                if window_id not in latest or failed_at > latest[window_id]:
                    latest[window_id] = failed_at
    return latest


def _latest_ai_activity_by_window(
    recent_agent_events: dict[UUID, list[Event]],
) -> dict[UUID, datetime]:
    latest: dict[UUID, datetime] = {}
    for window_id, events in recent_agent_events.items():
        for event in events:
            if not event_is_agent_activity(event):
                continue
            activity_at = event_activity_time(event)
            if window_id not in latest or activity_at > latest[window_id]:
                latest[window_id] = activity_at
    return latest


async def _latest_agent_user_input_at_by_window(
    session: AsyncSession,
    client_id: UUID,
    window_ids: list[UUID],
) -> dict[UUID, datetime]:
    if not window_ids:
        return {}

    events = await _recent_agent_events_by_window(session, client_id, window_ids)
    return _latest_agent_user_input_at_by_window_from_events(events)


def _latest_agent_user_input_at_by_window_from_events(
    recent_agent_events: dict[UUID, list[Event]],
) -> dict[UUID, datetime]:
    latest: dict[UUID, datetime] = {}
    for window_id, events in recent_agent_events.items():
        for event in events:
            if not event_is_agent_user_input(event):
                continue
            activity_at = event_activity_time(event)
            if window_id not in latest or activity_at > latest[window_id]:
                latest[window_id] = activity_at
    return latest


async def _latest_events_by_window(
    session: AsyncSession,
    client_id: UUID,
    window_ids: list[UUID],
    *,
    kind: str,
) -> dict[UUID, Event]:
    if not window_ids:
        return {}

    if _dialect_name(session) == "postgresql":
        return await _latest_events_by_window_postgresql(
            session,
            client_id,
            window_ids,
            kind=kind,
        )

    latest_created_at = (
        select(
            Event.virtual_window_id.label("window_id"),
            func.max(Event.created_at).label("max_created_at"),
        )
        .where(
            Event.client_id == client_id,
            Event.virtual_window_id.in_(window_ids),
            Event.kind == kind,
        )
        .group_by(Event.virtual_window_id)
        .subquery()
    )

    rows = list(
        (
            await session.execute(
                select(*_activity_event_columns(Event))
                .join(
                    latest_created_at,
                    and_(
                        Event.virtual_window_id == latest_created_at.c.window_id,
                        Event.created_at == latest_created_at.c.max_created_at,
                    ),
                )
                .where(
                    Event.client_id == client_id,
                    Event.virtual_window_id.in_(window_ids),
                    Event.kind == kind,
                )
                .order_by(Event.virtual_window_id, desc(Event.id))
            )
        ).all()
    )
    latest: dict[UUID, Event] = {}
    for event in _activity_events_from_rows(rows):
        if event.virtual_window_id is not None and event.virtual_window_id not in latest:
            latest[event.virtual_window_id] = event
    return latest


async def _latest_events_by_window_postgresql(
    session: AsyncSession,
    client_id: UUID,
    window_ids: list[UUID],
    *,
    kind: str,
) -> dict[UUID, Event]:
    outer_window = aliased(VirtualWindow)
    latest_events_lateral = (
        select(*_activity_event_columns(Event))
        .where(
            Event.client_id == client_id,
            Event.virtual_window_id == outer_window.id,
            Event.kind == kind,
        )
        .order_by(desc(Event.created_at), desc(Event.id))
        .limit(1)
        .lateral("latest_window_event")
    )
    rows = list(
        (
            await session.execute(
                select(*latest_events_lateral.c)
                .select_from(outer_window)
                .join(latest_events_lateral, true())
                .where(
                    outer_window.client_id == client_id,
                    outer_window.id.in_(window_ids),
                )
            )
        ).all()
    )
    return {
        event.virtual_window_id: event
        for event in _activity_events_from_rows(rows)
        if event.virtual_window_id is not None
    }


def _merge_latest_working_activity(
    window_ids: list[UUID],
    *,
    latest_commands: dict[UUID, Event],
    latest_ai: dict[UUID, datetime],
    latest_agent_user_input_at: dict[UUID, datetime],
    pending_subagent_count: dict[UUID, int],
    finished_sequences: dict[UUID, dict[str, datetime]],
    now: datetime,
) -> dict[UUID, datetime]:
    latest_work: dict[UUID, datetime] = {}
    for window_id in window_ids:
        candidates: list[datetime] = []
        if window_id in latest_ai:
            latest_ai_at = _aware_utc(latest_ai[window_id])
            if _agent_command_allows_ai_activity(
                window_id,
                latest_ai_at=latest_ai_at,
                latest_commands=latest_commands,
                latest_agent_user_input_at=latest_agent_user_input_at,
                pending_subagent_count=pending_subagent_count,
                finished_sequences=finished_sequences,
                now=now,
            ):
                candidates.append(latest_ai_at)
        if candidates:
            latest_work[window_id] = max(_aware_utc(value) for value in candidates)
    return latest_work


def _latest_agent_active_at(
    window_ids: list[UUID],
    *,
    latest_commands: dict[UUID, Event],
    latest_ai: dict[UUID, datetime],
    latest_agent_user_input_at: dict[UUID, datetime],
    finished_sequences: dict[UUID, dict[str, datetime]],
) -> dict[UUID, datetime]:
    latest: dict[UUID, datetime] = {}
    for window_id in window_ids:
        command = latest_commands.get(window_id)
        if command is not None:
            if _event_agent(command) is None:
                continue
            if (
                not _event_has_agent_task(command)
                and window_id not in latest_ai
                and window_id not in latest_agent_user_input_at
            ):
                continue
            sequence = command.payload_json.get("sequence")
            if sequence is None or str(sequence) not in finished_sequences.get(window_id, {}):
                candidates = [_aware_utc(command.created_at)]
                if window_id in latest_ai:
                    candidates.append(_aware_utc(latest_ai[window_id]))
                if window_id in latest_agent_user_input_at:
                    candidates.append(_aware_utc(latest_agent_user_input_at[window_id]))
                latest[window_id] = max(candidates)
            continue
        if window_id in latest_ai:
            if window_id not in latest_agent_user_input_at:
                continue
            latest[window_id] = max(
                _aware_utc(latest_ai[window_id]),
                _aware_utc(latest_agent_user_input_at[window_id]),
            )
    return latest


def _agent_command_allows_ai_activity(
    window_id: UUID,
    *,
    latest_ai_at: datetime,
    latest_commands: dict[UUID, Event],
    latest_agent_user_input_at: dict[UUID, datetime],
    pending_subagent_count: dict[UUID, int],
    finished_sequences: dict[UUID, dict[str, datetime]],
    now: datetime,
) -> bool:
    if pending_subagent_count.get(window_id, 0) > 0:
        return True
    command = latest_commands.get(window_id)
    if command is None:
        user_input_at = latest_agent_user_input_at.get(window_id)
        return user_input_at is not None and latest_ai_at > _aware_utc(user_input_at)
    if _event_agent(command) is None:
        return False
    user_input_at = latest_agent_user_input_at.get(window_id)
    if user_input_at is not None and latest_ai_at <= _aware_utc(user_input_at):
        return False
    if not _event_has_agent_task(command) and user_input_at is None:
        return False
    sequence = command.payload_json.get("sequence")
    if sequence is None:
        return True
    finished_at = finished_sequences.get(window_id, {}).get(str(sequence))
    if finished_at is None:
        return True
    aware_finished_at = _aware_utc(finished_at)
    if latest_ai_at < aware_finished_at:
        return False
    return now - aware_finished_at <= timedelta(seconds=AGENT_EVENT_LATE_ARRIVAL_SECONDS)
