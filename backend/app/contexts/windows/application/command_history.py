from __future__ import annotations

from uuid import UUID

from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.contexts.windows.application.agent_record_projection import (
    _command_history_item_out,
    _payload_sequence_key,
)
from app.models import Event
from app.contexts.windows.api.schemas import CommandHistoryOut


async def read_command_history(
    session: AsyncSession,
    *,
    client_id: UUID,
    window_id: UUID,
    limit: int,
    offset: int,
) -> CommandHistoryOut:
    command_filters = (
        Event.client_id == client_id,
        Event.virtual_window_id == window_id,
        Event.kind == "terminal_input_command",
    )
    commands_total = await session.scalar(select(func.count()).select_from(Event).where(*command_filters))
    command_events = list(
        await session.scalars(
            select(Event)
            .where(*command_filters)
            .order_by(desc(Event.created_at), desc(Event.id))
            .offset(offset)
            .limit(limit)
        )
    )
    sequence_keys = [
        sequence_key
        for event in command_events
        if (sequence_key := _payload_sequence_key(event)) is not None
    ]
    finished_by_sequence: dict[str, Event] = {}
    if sequence_keys:
        finished_fingerprints = [
            f"terminal_command_finished:{window_id}:{sequence_key}"
            for sequence_key in sequence_keys
        ]
        finished_events = list(
            await session.scalars(
                select(Event)
                .where(
                    Event.client_id == client_id,
                    Event.virtual_window_id == window_id,
                    Event.kind == "terminal_command_finished",
                    Event.fingerprint.in_(finished_fingerprints),
                )
                .order_by(desc(Event.created_at), desc(Event.id))
            )
        )
        wanted = set(sequence_keys)
        for event in finished_events:
            sequence_key = _payload_sequence_key(event)
            if sequence_key is not None and sequence_key in wanted and sequence_key not in finished_by_sequence:
                finished_by_sequence[sequence_key] = event
    raw_commands_total = int(commands_total or 0)
    return CommandHistoryOut(
        window_id=window_id,
        commands=[_command_history_item_out(event, finished_by_sequence) for event in command_events],
        commands_total=raw_commands_total,
        commands_limit=limit,
        commands_offset=offset,
        commands_has_more=offset + limit < raw_commands_total,
    )
