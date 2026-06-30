from __future__ import annotations

from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


async def try_acquire_window_refresh_lock(session: AsyncSession, window_id: UUID) -> bool:
    if session.get_bind().dialect.name != "postgresql":
        return True
    acquired = await session.scalar(
        text("SELECT pg_try_advisory_xact_lock(hashtextextended(:lock_key, 0))"),
        {"lock_key": f"git-worktree-refresh:{window_id}"},
    )
    return acquired is True
