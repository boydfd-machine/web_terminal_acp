from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.contexts.activity.domain.event_kinds import AGENT_WORK_PRESENCE_KIND as AGENT_WORK_PRESENCE_KIND
from app.contexts.windows.application.window_lookup import get_window_for_client
from app.db import prefer_deferred_commit
from app.models import VirtualWindow


async def touch_agent_work_presence(
    session: AsyncSession,
    *,
    client_id: UUID,
    window_id: UUID,
    providers: list[str],
    reasons: list[str],
    observed_at: datetime | None = None,
) -> VirtualWindow:
    await prefer_deferred_commit(session)

    window = await get_window_for_client(session, client_id, window_id)
    if window is None:
        raise ValueError("window not found for client")

    current = observed_at or datetime.now(UTC)
    if current.tzinfo is None:
        current = current.replace(tzinfo=UTC)
    else:
        current = current.astimezone(UTC)

    del providers, reasons
    if window.agent_presence_latest_at is None or current >= window.agent_presence_latest_at:
        window.agent_presence_latest_at = current
    await session.flush()
    return window


async def touch_agent_work_presence_if_window_exists(
    session: AsyncSession,
    *,
    client_id: UUID,
    window_id: UUID,
    providers: list[str],
    reasons: list[str],
    observed_at: datetime | None = None,
) -> VirtualWindow | None:
    try:
        return await touch_agent_work_presence(
            session,
            client_id=client_id,
            window_id=window_id,
            providers=providers,
            reasons=reasons,
            observed_at=observed_at,
        )
    except ValueError as exc:
        if str(exc) != "window not found for client":
            raise
        return None
