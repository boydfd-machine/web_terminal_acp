from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ProjectTodo, ProjectTodoArtifact, TerminalArtifact

SOURCE_TODO_ARTIFACT_PURPOSE = "todo_artifact"


async def source_project_todo_id_for_artifact(
    session: AsyncSession,
    client_id: UUID,
    project_path: str,
    artifact_id: UUID,
) -> UUID | None:
    rows = list(
        await session.execute(
            select(ProjectTodoArtifact.project_todo_id, ProjectTodoArtifact.purpose)
            .join(ProjectTodo, ProjectTodo.id == ProjectTodoArtifact.project_todo_id)
            .join(TerminalArtifact, TerminalArtifact.id == ProjectTodoArtifact.terminal_artifact_id)
            .where(
                TerminalArtifact.id == artifact_id,
                TerminalArtifact.client_id == client_id,
                ProjectTodo.client_id == client_id,
                ProjectTodo.project_path == project_path,
            )
            .order_by(ProjectTodoArtifact.created_at, ProjectTodoArtifact.id)
        )
    )
    if not rows:
        return None
    rows.sort(key=lambda row: _artifact_source_purpose_rank(row[1]))
    return rows[0][0]


def _artifact_source_purpose_rank(purpose: str) -> int:
    if purpose == SOURCE_TODO_ARTIFACT_PURPOSE:
        return 0
    if purpose == "artifact_card":
        return 2
    return 1
