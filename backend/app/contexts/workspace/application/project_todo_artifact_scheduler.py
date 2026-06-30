from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.contexts.workspace.application.project_todo_artifacts import (
    ProjectTodoArtifactGeneration,
    schedule_project_todo_requested_artifacts,
)
from app.contexts.workspace.infrastructure.project_todo_completion_repository import (
    _mark_implementation_completed,
)
from app.models import ProjectTodo


def schedule_project_todo_artifact_generations(
    generations: list[ProjectTodoArtifactGeneration],
    runtime=None,
) -> None:
    if not generations:
        return
    if runtime is None:
        from app.contexts.terminal_artifacts.application import (
            TerminalArtifactGenerationRequest,
            schedule_terminal_artifact_generation,
        )

        for generation in generations:
            schedule_terminal_artifact_generation(
                TerminalArtifactGenerationRequest(
                    client_id=generation.client_id,
                    window_id=generation.window_id,
                    artifact_id=generation.artifact_id,
                    prompt=generation.prompt,
                    output_language=generation.output_language,
                )
            )
        return
    schedule_project_todo_requested_artifacts(generations, runtime)


async def complete_project_todo_implementation(
    session: AsyncSession,
    todo: ProjectTodo,
    completed_at: datetime,
    window_id: UUID | None,
    *,
    remote_client_available: Callable[[UUID], bool] | None,
) -> None:
    generations = await _mark_implementation_completed(
        session,
        todo,
        completed_at,
        window_id,
        remote_client_available=remote_client_available,
    )
    todo.dispatch_stage = None
    todo.dispatch_error = None
    await session.commit()
    schedule_project_todo_artifact_generations(generations)
