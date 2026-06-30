from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Event, VirtualWindow

TERMINAL_INPUT_COMMAND_KIND = "terminal_input_command"


@dataclass(frozen=True)
class TerminalInputActivity:
    first_event: Event
    latest_event: Event
    total: int


async def terminal_input_activity(
    session: AsyncSession,
    window: VirtualWindow,
) -> TerminalInputActivity | None:
    filters = (
        Event.client_id == window.client_id,
        Event.virtual_window_id == window.id,
        Event.kind == TERMINAL_INPUT_COMMAND_KIND,
    )
    total = await session.scalar(select(func.count()).select_from(Event).where(*filters))
    if not total:
        return None

    first_event = await session.scalar(
        select(Event)
        .where(*filters)
        .order_by(Event.created_at, Event.id)
        .limit(1)
    )
    latest_event = await session.scalar(
        select(Event)
        .where(*filters)
        .order_by(desc(Event.created_at), desc(Event.id))
        .limit(1)
    )
    if first_event is None or latest_event is None:
        return None

    return TerminalInputActivity(
        first_event=first_event,
        latest_event=latest_event,
        total=int(total),
    )
