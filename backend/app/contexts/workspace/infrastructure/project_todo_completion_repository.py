from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.contexts.workspace.application.project_todo_artifacts import (
    ProjectTodoArtifactGeneration,
    create_missing_project_todo_requested_artifacts,
)
from app.contexts.workspace.domain.project_todo_recurrence import PROJECT_TODO_EXECUTION_PERIODIC
from app.contexts.workspace.infrastructure.project_review_config_repository import (
    get_or_create_project_review_config,
)
from app.contexts.workspace.infrastructure.project_todo_artifacts_repository import (
    project_todo_has_incomplete_requested_artifacts,
)
from app.contexts.workspace.infrastructure.project_todo_reviews_repository import (
    create_local_review_target,
    create_project_todo_work_snapshot,
)
from app.contexts.workspace.infrastructure.project_todo_runs_repository import (
    complete_latest_project_todo_run_for_window,
)
from app.contexts.workspace.infrastructure.project_todo_sort_repository import next_project_todo_sort_order
from app.contexts.workspace.infrastructure.project_todo_worktrees_repository import (
    implementation_worktree_summary,
)
from app.models import ProjectTodo, ProjectTodoStatus


async def _mark_implementation_awaiting_review(
    session: AsyncSession,
    todo: ProjectTodo,
    completed_at: datetime,
) -> None:
    config = await get_or_create_project_review_config(session, todo.client_id, todo.project_path)
    todo.sort_order = await next_project_todo_sort_order(session, todo.client_id, todo.project_path)
    todo.status = ProjectTodoStatus.awaiting_review
    todo.dispatch_stage = None
    todo.dispatch_error = None
    todo.awaiting_review_at = completed_at
    todo.review_status = "PENDING"
    todo.review_unseen = True
    todo.review_strategy = config.pr_provider or todo.review_strategy
    if todo.assigned_window_id is not None:
        summary = await implementation_worktree_summary(session, todo.assigned_window_id)
        todo.implementation_worktree_json = summary
        snapshot = await create_project_todo_work_snapshot(
            session,
            todo,
            role="implementation",
            window_id=todo.assigned_window_id,
            worktree_summary=summary,
            captured_at=completed_at,
        )
        if config.auto_create_review_target and (config.pr_provider or "LOCAL_CARD") == "LOCAL_CARD":
            await create_local_review_target(session, todo, snapshot)


async def _mark_implementation_completed(
    session: AsyncSession,
    todo: ProjectTodo,
    completed_at: datetime,
    window_id: UUID | None,
    *,
    remote_client_available: Callable[[UUID], bool] | None = None,
) -> list[ProjectTodoArtifactGeneration]:
    if todo.execution_kind == PROJECT_TODO_EXECUTION_PERIODIC:
        if window_id is not None:
            await complete_latest_project_todo_run_for_window(
                session,
                todo,
                window_id,
                completed_at=completed_at,
            )
        todo.sort_order = await next_project_todo_sort_order(session, todo.client_id, todo.project_path)
        todo.status = ProjectTodoStatus.todo
        todo.dispatch_stage = None
        todo.dispatch_error = None
        todo.dispatched_at = None
        todo.awaiting_review_at = None
        todo.completed_at = None
        todo.review_status = "NOT_REQUESTED"
        todo.review_window_id = None
        todo.review_prompt = None
        todo.review_dispatched_at = None
        todo.reviewed_at = None
        todo.review_unseen = False
        todo.needs_human_review = False
        return []
    generations = await create_missing_project_todo_requested_artifacts(
        session,
        [todo],
        include_dispatched=True,
        remote_client_available=remote_client_available,
    )
    if generations or await project_todo_has_incomplete_requested_artifacts(session, todo):
        return generations
    await _mark_implementation_awaiting_review(session, todo, completed_at)
    return []
