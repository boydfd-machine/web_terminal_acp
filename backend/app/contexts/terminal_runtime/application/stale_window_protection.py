from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import AsyncContextManager
from uuid import UUID

from sqlalchemy import and_, or_
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.contexts.activity.application.terminal_work_status import (
    TerminalWorkStatus,
    load_work_statuses,
)
from app.models import LOCAL_CLIENT_ID, VirtualWindow, WindowStatus

RECENT_ACTIVE_TMUX_WINDOW_RETAIN_LIMIT = 50
_IDLE_STATES = {"LONG_IDLE", "IDLE", "SLEEP", "SLEEPING"}

RetainWindowCheck = Callable[[object], Awaitable[bool]]
SessionFactory = Callable[[], AsyncContextManager[AsyncSession]]


def recent_active_tmux_window_retain_check(
    session_factory: SessionFactory,
    *,
    client_id: UUID = LOCAL_CLIENT_ID,
    limit: int = RECENT_ACTIVE_TMUX_WINDOW_RETAIN_LIMIT,
) -> RetainWindowCheck:
    async def should_retain(local_window_id: object) -> bool:
        try:
            window_id = UUID(str(local_window_id))
        except ValueError:
            return False
        async with session_factory() as session:
            retained = await retained_recent_active_tmux_window_ids(
                session,
                client_id,
                limit=limit,
            )
        return window_id in retained

    return should_retain


async def retained_recent_active_tmux_window_ids(
    session: AsyncSession,
    client_id: UUID,
    *,
    limit: int = RECENT_ACTIVE_TMUX_WINDOW_RETAIN_LIMIT,
    now: datetime | None = None,
) -> set[UUID]:
    if limit <= 0:
        return set()

    rows = list(
        (
            await session.execute(
                select(VirtualWindow.id, VirtualWindow.created_at).where(
                    VirtualWindow.client_id == client_id,
                    VirtualWindow.status == WindowStatus.active,
                    VirtualWindow.archived_at.is_(None),
                    or_(
                        and_(
                            VirtualWindow.tmux_session.is_not(None),
                            VirtualWindow.tmux_window_id.is_not(None),
                        ),
                        and_(
                            VirtualWindow.remote_session_id.is_not(None),
                            VirtualWindow.remote_window_id.is_not(None),
                        ),
                    ),
                )
            )
        ).all()
    )
    if not rows:
        return set()

    window_ids = [window_id for window_id, _created_at in rows]
    statuses = await load_work_statuses(session, client_id, window_ids, now=now)
    active: list[tuple[datetime, UUID]] = []
    for window_id, created_at in rows:
        status = statuses.get(window_id)
        if status is None or _is_idle_status(status):
            continue
        active.append((_latest_status_activity_at(status, created_at), window_id))

    active.sort(key=lambda item: (item[0], str(item[1])), reverse=True)
    return {window_id for _activity_at, window_id in active[:limit]}


def _is_idle_status(status: TerminalWorkStatus) -> bool:
    return status.state.upper() in _IDLE_STATES


def _latest_status_activity_at(status: TerminalWorkStatus, fallback: datetime) -> datetime:
    return max(
        _aware_utc(value)
        for value in (
            status.last_activity_at,
            status.last_working_activity_at,
            fallback,
        )
        if value is not None
    )


def _aware_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)
