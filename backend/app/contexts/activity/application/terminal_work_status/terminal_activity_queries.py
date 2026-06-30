# ruff: noqa: F821
"""Executed into the terminal_work_status package globals."""

from importlib import import_module

_status_service = import_module("app.contexts.activity.application.terminal_work_status.status_service")
globals().update(
    {name: value for name, value in _status_service.__dict__.items() if not name.startswith("__")}
)


@dataclass(frozen=True)
class _CommandFinishState:
    finished: dict[UUID, dict[str, datetime]]
    failed: dict[UUID, dict[str, datetime]]


async def _finished_command_sequences_by_window(
    session: AsyncSession,
    client_id: UUID,
    window_ids: list[UUID],
    *,
    latest_commands: dict[UUID, Event],
) -> _CommandFinishState:
    if not window_ids:
        return _CommandFinishState({}, {})

    command_refs: dict[UUID, tuple[str, datetime]] = {}
    for window_id in window_ids:
        command = latest_commands.get(window_id)
        if command is None:
            continue
        sequence = command.payload_json.get("sequence")
        if sequence is None:
            continue
        command_refs[window_id] = (str(sequence), _aware_utc(command.created_at))
    if not command_refs:
        return _CommandFinishState({}, {})

    earliest_command_at = min(created_at for _sequence, created_at in command_refs.values())
    rows = await session.execute(
        select(Event.virtual_window_id, Event.payload_json, Event.created_at).where(
            Event.client_id == client_id,
            Event.virtual_window_id.in_(tuple(command_refs)),
            Event.kind == TERMINAL_COMMAND_FINISHED_KIND,
            Event.created_at >= earliest_command_at,
        )
    )
    sequences: dict[UUID, dict[str, datetime]] = {}
    failed_sequences: dict[UUID, dict[str, datetime]] = {}
    for window_id, payload, created_at in rows:
        if window_id is None:
            continue
        sequence = payload.get("sequence")
        if sequence is None:
            continue
        key = str(sequence)
        expected = command_refs.get(window_id)
        if expected is None:
            continue
        expected_sequence, command_created_at = expected
        if key != expected_sequence or _aware_utc(created_at) < command_created_at:
            continue
        current = sequences.setdefault(window_id, {}).get(key)
        if current is None or created_at > current:
            sequences.setdefault(window_id, {})[key] = created_at
        if _command_finished_unsuccessfully(payload):
            current_failed = failed_sequences.setdefault(window_id, {}).get(key)
            if current_failed is None or created_at > current_failed:
                failed_sequences.setdefault(window_id, {})[key] = created_at
    return _CommandFinishState(sequences, failed_sequences)


def _latest_failed_agent_command_at(
    window_ids: list[UUID],
    *,
    failed_sequences: dict[UUID, dict[str, datetime]],
) -> dict[UUID, datetime]:
    latest: dict[UUID, datetime] = {}
    for window_id in window_ids:
        values = failed_sequences.get(window_id, {}).values()
        if values:
            latest[window_id] = max(_aware_utc(value) for value in values)
    return latest


def _command_finished_unsuccessfully(payload: dict) -> bool:
    exit_status = payload.get("exit_status")
    if exit_status in (None, ""):
        return False
    try:
        return int(exit_status) != 0
    except (TypeError, ValueError):
        return str(exit_status) != "0"


async def _latest_terminal_output_activity_by_window(
    session: AsyncSession,
    client_id: UUID,
    window_ids: list[UUID],
) -> dict[UUID, datetime]:
    if not window_ids:
        return {}

    rows = await session.execute(
        select(VirtualWindow.id, VirtualWindow.terminal_last_output_at).where(
            VirtualWindow.client_id == client_id,
            VirtualWindow.id.in_(window_ids),
            VirtualWindow.terminal_last_output_at.is_not(None),
        )
    )
    return {window_id: activity_at for window_id, activity_at in rows if activity_at is not None}


async def _latest_created_at_by_window_and_kinds(
    session: AsyncSession,
    client_id: UUID,
    window_ids: list[UUID],
    *,
    kinds: tuple[str, ...],
) -> dict[UUID, datetime]:
    return await _latest_created_at_by_window_for_event_values(
        session,
        client_id,
        window_ids,
        value_column=Event.kind,
        values=kinds,
    )


async def _latest_created_at_by_window_for_event_values(
    session: AsyncSession,
    client_id: UUID,
    window_ids: list[UUID],
    *,
    value_column,
    values: tuple,
) -> dict[UUID, datetime]:
    if not window_ids or not values:
        return {}

    columns = [VirtualWindow.id]
    for index, value in enumerate(values):
        latest_created_at = (
            select(Event.created_at)
            .where(
                Event.client_id == client_id,
                Event.virtual_window_id == VirtualWindow.id,
                value_column == value,
            )
            .order_by(desc(Event.created_at))
            .limit(1)
            .scalar_subquery()
            .label(f"latest_created_at_{index}")
        )
        columns.append(latest_created_at)

    rows = await session.execute(
        select(*columns).where(
            VirtualWindow.client_id == client_id,
            VirtualWindow.id.in_(window_ids),
        )
    )
    latest: dict[UUID, datetime] = {}
    for row in rows:
        window_id = row[0]
        candidates = [created_at for created_at in row[1:] if created_at is not None]
        if candidates:
            latest[window_id] = max(candidates)
    return latest


def _merge_latest_created_at(*items: dict[UUID, datetime]) -> dict[UUID, datetime]:
    latest: dict[UUID, datetime] = {}
    for item in items:
        for window_id, created_at in item.items():
            aware_created_at = _aware_utc(created_at)
            if window_id not in latest or aware_created_at > latest[window_id]:
                latest[window_id] = aware_created_at
    return latest


async def _latest_ai_sessions_by_window(
    session: AsyncSession,
    client_id: UUID,
    window_ids: list[UUID],
) -> dict[UUID, AiSession]:
    if not window_ids:
        return {}

    latest_updated_at = (
        select(
            AiSession.virtual_window_id.label("window_id"),
            func.max(AiSession.updated_at).label("max_updated_at"),
        )
        .where(
            AiSession.client_id == client_id,
            AiSession.virtual_window_id.in_(window_ids),
        )
        .group_by(AiSession.virtual_window_id)
        .subquery()
    )

    rows = list(
        await session.scalars(
            select(AiSession)
            .join(
                latest_updated_at,
                and_(
                    AiSession.virtual_window_id == latest_updated_at.c.window_id,
                    AiSession.updated_at == latest_updated_at.c.max_updated_at,
                ),
            )
            .where(
                AiSession.client_id == client_id,
                AiSession.virtual_window_id.in_(window_ids),
            )
            .order_by(AiSession.virtual_window_id, desc(AiSession.created_at))
        )
    )
    latest_by_window: dict[UUID, AiSession] = {}
    for ai_session in rows:
        if (
            ai_session.virtual_window_id is not None
            and ai_session.virtual_window_id not in latest_by_window
        ):
            latest_by_window[ai_session.virtual_window_id] = ai_session
    return latest_by_window


def _event_agent(event: Event | None) -> str | None:
    if event is None:
        return None
    command = event.payload_json.get("command")
    return agent_from_command(command if isinstance(command, str) else None)


def _event_has_agent_task(event: Event | None) -> bool:
    if event is None:
        return False
    command = event.payload_json.get("command")
    return agent_command_has_inline_task(command if isinstance(command, str) else None)


def _aware_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _dialect_name(session: AsyncSession) -> str:
    return session.get_bind().dialect.name
