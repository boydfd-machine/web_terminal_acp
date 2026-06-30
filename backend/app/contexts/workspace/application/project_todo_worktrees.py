from __future__ import annotations

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.contexts.workspace.infrastructure.project_todo_worktrees_repository import (
    sync_project_todo_worktree_summaries_for_window,
)


async def refresh_project_todo_worktree_summaries_for_window(
    session: AsyncSession,
    *,
    client_id: UUID,
    window_id: UUID,
) -> bool:
    return await sync_project_todo_worktree_summaries_for_window(
        session,
        client_id,
        window_id,
    )
