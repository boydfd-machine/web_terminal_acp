from __future__ import annotations

from collections.abc import Callable
from contextlib import AbstractAsyncContextManager
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.contexts.workspace.infrastructure.project_todo_runs_repository import mark_project_todo_run_failed
from app.models import ProjectTodo
from app.platform.ui_events import UiEventHub

SessionFactory = Callable[[], AbstractAsyncContextManager[AsyncSession]]
PROJECT_TODO_DISPATCH_ERROR_MAX_LENGTH = 2000


async def mark_project_todo_dispatch_failed(
    todo_id: UUID,
    run_id: UUID | None = None,
    *,
    error: str,
    session_factory: SessionFactory,
    ui_event_hub: UiEventHub,
) -> None:
    async with session_factory() as session:
        todo = await session.get(ProjectTodo, todo_id)
        if todo is None:
            return
        todo.dispatch_stage = "FAILED"
        todo.dispatch_error = truncate_dispatch_error(error)
        await mark_project_todo_run_failed(session, todo, run_id, error=todo.dispatch_error)
        await session.commit()
        await session.refresh(todo)
        await publish_project_todo_dispatch_invalidation(
            ui_event_hub,
            todo,
            reason="project_todo_dispatch_failed",
        )


async def publish_project_todo_dispatch_invalidation(
    ui_event_hub: UiEventHub,
    todo: ProjectTodo,
    *,
    reason: str,
) -> None:
    resources = ["project_todos"]
    if todo.assigned_window_id is not None:
        resources.extend(["tree", "window", "search", "terminal_recents"])
    await ui_event_hub.publish_invalidation(
        resources,
        client_id=todo.client_id,
        window_id=todo.assigned_window_id,
        reason=reason,
    )


def truncate_dispatch_error(error: str) -> str:
    normalized = error.strip() or "dispatch failed"
    if len(normalized) <= PROJECT_TODO_DISPATCH_ERROR_MAX_LENGTH:
        return normalized
    return normalized[:PROJECT_TODO_DISPATCH_ERROR_MAX_LENGTH]
