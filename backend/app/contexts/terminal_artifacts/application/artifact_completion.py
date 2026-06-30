from __future__ import annotations

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession


async def complete_project_todos_after_artifact_status_change(
    session: AsyncSession,
    artifact_id: UUID,
) -> None:
    from app.contexts.workspace.application.project_todo_repository import (
        complete_project_todos_after_artifact_status_change as complete_todos,
    )

    await complete_todos(session, artifact_id)
