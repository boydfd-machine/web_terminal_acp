from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.contexts.terminal_artifacts.application.artifact_completion import (
    complete_project_todos_after_artifact_status_change as complete_todos_after_artifact_status_change,
)
from app.contexts.terminal_artifacts.infrastructure.repository import (
    list_incomplete_terminal_artifacts,
    mark_artifact_failed,
)
from app.models import ProjectTodoArtifact, TerminalArtifact, TerminalArtifactStatus

PROJECT_TODO_ARTIFACT_PURPOSE = "todo_artifact"


async def reconcile_interrupted_terminal_artifacts(
    session: AsyncSession,
    *,
    error: str = "terminal artifact generation was interrupted by server restart",
) -> int:
    artifacts = await list_incomplete_terminal_artifacts(session)
    changed_count = 0
    for artifact in artifacts:
        if await _pending_project_todo_artifact_dispatch_can_be_compensated(session, artifact):
            continue
        await mark_artifact_failed(session, artifact, error=error)
        artifact.ephemeral_window_id = None
        await complete_todos_after_artifact_status_change(session, artifact.id)
        changed_count += 1
    if changed_count:
        await session.flush()
    return changed_count


async def _pending_project_todo_artifact_dispatch_can_be_compensated(
    session: AsyncSession,
    artifact: TerminalArtifact,
) -> bool:
    if artifact.status is not TerminalArtifactStatus.pending:
        return False
    link_id = await session.scalar(
        select(ProjectTodoArtifact.id).where(
            ProjectTodoArtifact.terminal_artifact_id == artifact.id,
            ProjectTodoArtifact.purpose == PROJECT_TODO_ARTIFACT_PURPOSE,
        )
    )
    return link_id is not None

