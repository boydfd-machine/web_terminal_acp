from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.contexts.workspace.domain.project_todo_recurrence import (
    PROJECT_TODO_RUN_DISPATCHED,
    PROJECT_TODO_RUN_STARTING,
)
from app.contexts.workspace.infrastructure.project_todo_sort_repository import next_project_todo_sort_order
from app.models import ProjectTodo, ProjectTodoRun, ProjectTodoStatus, VirtualWindow

PROJECT_TODO_DISPATCH_STAGE_TERMINAL_READY = "TERMINAL_READY"


async def sync_started_project_todo_dispatches(
    session: AsyncSession,
    client_id: UUID,
    project_path: str,
) -> bool:
    rows = list(
        await session.execute(
            select(ProjectTodo)
            .add_columns(VirtualWindow.agent_activity_latest_user_input_at)
            .join(VirtualWindow, VirtualWindow.id == ProjectTodo.assigned_window_id)
            .where(
                ProjectTodo.client_id == client_id,
                ProjectTodo.project_path == project_path,
                ProjectTodo.status == ProjectTodoStatus.todo,
                ProjectTodo.dispatch_stage == PROJECT_TODO_DISPATCH_STAGE_TERMINAL_READY,
                ProjectTodo.assigned_window_id.is_not(None),
                VirtualWindow.agent_activity_latest_user_input_at.is_not(None),
            )
        )
    )
    changed = False
    for todo, user_input_at in rows:
        dispatched_at = _ensure_aware(user_input_at)
        run = await _latest_starting_dispatch_run(session, todo.id, todo.assigned_window_id)
        if not _agent_input_confirms_dispatch(todo, dispatched_at, run):
            continue
        todo.sort_order = await next_project_todo_sort_order(session, todo.client_id, todo.project_path)
        todo.status = ProjectTodoStatus.dispatched
        todo.dispatch_stage = None
        todo.dispatch_error = None
        todo.dispatched_at = dispatched_at
        todo.awaiting_review_at = None
        todo.completed_at = None
        todo.review_status = "NOT_REQUESTED"
        todo.review_window_id = None
        todo.review_prompt = None
        todo.review_dispatched_at = None
        todo.reviewed_at = None
        todo.review_unseen = False
        todo.needs_human_review = False
        todo.implementation_worktree_json = None
        if run is not None:
            run.status = PROJECT_TODO_RUN_DISPATCHED
            run.dispatched_at = dispatched_at
            run.last_error = None
        changed = True
    if changed:
        await session.flush()
    return changed


async def _latest_starting_dispatch_run(
    session: AsyncSession,
    todo_id: UUID,
    window_id: UUID | None,
) -> ProjectTodoRun | None:
    if window_id is None:
        return None
    return await session.scalar(
        select(ProjectTodoRun)
        .where(
            ProjectTodoRun.project_todo_id == todo_id,
            ProjectTodoRun.window_id == window_id,
            ProjectTodoRun.status == PROJECT_TODO_RUN_STARTING,
        )
        .order_by(desc(ProjectTodoRun.run_number), desc(ProjectTodoRun.created_at), desc(ProjectTodoRun.id))
        .limit(1)
    )


def _agent_input_confirms_dispatch(
    todo: ProjectTodo,
    user_input_at: datetime,
    run: ProjectTodoRun | None,
) -> bool:
    if run is not None and run.started_at is not None:
        return user_input_at >= _ensure_aware(run.started_at)
    return user_input_at >= _ensure_aware(todo.updated_at)


def _ensure_aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)
