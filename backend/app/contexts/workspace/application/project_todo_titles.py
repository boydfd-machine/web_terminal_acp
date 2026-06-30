from __future__ import annotations

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.contexts.workspace.infrastructure.project_todos_repository import (
    assigned_project_todo_titles_by_window,
)


async def assigned_todo_titles_by_window(
    session: AsyncSession,
    window_ids: list[UUID],
    *,
    client_id: UUID | None = None,
) -> dict[UUID, str]:
    return await assigned_project_todo_titles_by_window(
        session,
        window_ids,
        client_id=client_id,
    )
