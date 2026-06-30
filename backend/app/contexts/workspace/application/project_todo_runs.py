from __future__ import annotations

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.contexts.workspace.domain.project_todo_recurrence import ProjectTodoSchedule
from app.contexts.workspace.infrastructure.project_todo_runs_repository import (
    apply_project_todo_schedule,
    list_recent_project_todo_runs_for_todos,
)
from app.models import ProjectTodo, ProjectTodoRun

__all__ = [
    "ProjectTodoRun",
    "ProjectTodoSchedule",
    "apply_project_todo_schedule",
    "list_recent_project_todo_runs_for_todos",
]


async def recent_project_todo_runs_for_todos(
    session: AsyncSession,
    todo_ids: list[UUID],
) -> dict[UUID, list[ProjectTodoRun]]:
    return await list_recent_project_todo_runs_for_todos(session, todo_ids)


def apply_project_todo_schedule_patch(
    todo: ProjectTodo,
    schedule: ProjectTodoSchedule,
) -> None:
    apply_project_todo_schedule(todo, schedule)
