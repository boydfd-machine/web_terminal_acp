from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable, Sequence
from contextlib import AbstractAsyncContextManager
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.contexts.clients.application.client_lookup import get_client
from app.contexts.terminal_runtime.application.client_connections import ClientConnectionRegistry
from app.contexts.terminal_runtime.application.runtime_provider import TmuxManager
from app.contexts.windows.application.errors import WindowServiceError
from app.contexts.windows.application.runtime_client import runtime_client_from_model
from app.contexts.windows.application.window_creation import create_virtual_window_for_client
from app.contexts.windows.api.schemas import WindowCreateIn
from app.contexts.workspace.application.project_todo_dispatch import (
    _wait_for_runtime_window,
    dispatch_project_todo_prompt,
)
from app.contexts.workspace.application.project_todo_dispatch_failure import (
    mark_project_todo_dispatch_failed,
    publish_project_todo_dispatch_invalidation,
)
from app.contexts.workspace.domain.project_todo_recurrence import (
    PROJECT_TODO_TERMINAL_REUSE,
)
from app.contexts.workspace.infrastructure.project_todo_dependencies_repository import (
    QueuedProjectTodoDispatch,
    clear_project_todo_queued_dispatch,
    has_incomplete_dependencies,
    ready_queued_dispatches_for_project,
    ready_queued_dispatches_for_upstream,
)
from app.contexts.workspace.infrastructure.project_todo_runs_repository import (
    create_project_todo_run,
    mark_project_todo_run_dispatched,
    mark_project_todo_run_window,
)
from app.contexts.workspace.infrastructure.project_todos_repository import next_project_todo_sort_order
from app.models import ProjectTodo, ProjectTodoStatus
from app.platform.common_schemas import AgentLaunchIn
from app.platform.ui_events import UiEventHub

logger = logging.getLogger(__name__)

SessionFactory = Callable[[], AbstractAsyncContextManager[AsyncSession]]
PROJECT_TODO_DISPATCH_STAGE_STARTING = "STARTING"
PROJECT_TODO_DISPATCH_STAGE_WINDOW_CREATED = "WINDOW_CREATED"
PROJECT_TODO_DISPATCH_STAGE_TERMINAL_READY = "TERMINAL_READY"
PROJECT_TODO_DISPATCH_STAGE_FAILED = "FAILED"

_dispatches_in_progress: set[UUID] = set()


async def start_project_todo_window_dispatch(
    *,
    session: AsyncSession,
    todo: ProjectTodo,
    agent_launch: AgentLaunchIn,
    dispatch_mode: str,
    prompt: str,
    output_language: str | None,
    tmux_manager: TmuxManager,
    registry: ClientConnectionRegistry | None,
    session_factory: SessionFactory,
    ui_event_hub: UiEventHub,
    trigger_reason: str = "manual",
) -> ProjectTodo:
    if not _reserve_dispatch(todo.id):
        return todo
    try:
        _prepare_project_todo_dispatch(
            todo,
            agent_launch=agent_launch,
            prompt=prompt,
            output_language=output_language,
        )
        run = await create_project_todo_run(
            session,
            todo,
            agent_launch_json=agent_launch.model_dump(mode="json"),
            dispatch_mode=dispatch_mode,
            prompt=prompt,
            trigger_reason=trigger_reason,
            window_id=todo.assigned_window_id if todo.terminal_policy == PROJECT_TODO_TERMINAL_REUSE else None,
        )
        await clear_project_todo_queued_dispatch(session, todo.id)
        await session.commit()
        await session.refresh(todo)
        _schedule_reserved_project_todo_dispatch(
            todo.id,
            run.id,
            agent_launch=agent_launch,
            dispatch_mode=dispatch_mode,
            prompt=prompt,
            tmux_manager=tmux_manager,
            registry=registry,
            session_factory=session_factory,
            ui_event_hub=ui_event_hub,
            upstream_todo_id=None,
        )
        await publish_project_todo_dispatch_invalidation(ui_event_hub, todo, reason="project_todo_dispatch_started")
        return todo
    except Exception:
        _dispatches_in_progress.discard(todo.id)
        raise


async def dispatch_ready_project_todos_after_dependency_satisfied(
    *,
    session: AsyncSession,
    upstream_todo: ProjectTodo,
    tmux_manager: TmuxManager,
    registry: ClientConnectionRegistry | None,
    session_factory: SessionFactory,
    ui_event_hub: UiEventHub,
) -> list[ProjectTodo]:
    ready_dispatches = await ready_queued_dispatches_for_upstream(session, upstream_todo.id)
    return await _dispatch_queued_project_todos(
        session=session,
        ready_dispatches=ready_dispatches,
        tmux_manager=tmux_manager,
        registry=registry,
        session_factory=session_factory,
        ui_event_hub=ui_event_hub,
        upstream_todo=upstream_todo,
    )


async def dispatch_ready_project_todos(
    *,
    session: AsyncSession,
    client_id: UUID,
    project_path: str,
    tmux_manager: TmuxManager,
    registry: ClientConnectionRegistry | None,
    session_factory: SessionFactory,
    ui_event_hub: UiEventHub,
) -> list[ProjectTodo]:
    ready_dispatches = await ready_queued_dispatches_for_project(
        session,
        client_id=client_id,
        project_path=project_path,
    )
    return await _dispatch_queued_project_todos(
        session=session,
        ready_dispatches=ready_dispatches,
        tmux_manager=tmux_manager,
        registry=registry,
        session_factory=session_factory,
        ui_event_hub=ui_event_hub,
    )


async def _dispatch_queued_project_todos(
    *,
    session: AsyncSession,
    ready_dispatches: Sequence[QueuedProjectTodoDispatch],
    tmux_manager: TmuxManager,
    registry: ClientConnectionRegistry | None,
    session_factory: SessionFactory,
    ui_event_hub: UiEventHub,
    upstream_todo: ProjectTodo | None = None,
) -> list[ProjectTodo]:
    dispatched: list[ProjectTodo] = []
    for queued in ready_dispatches:
        if not _reserve_dispatch(queued.todo.id):
            continue
        try:
            _prepare_project_todo_dispatch(
                queued.todo,
                agent_launch=queued.agent_launch,
                prompt=queued.prompt,
                output_language=queued.todo.dispatch_output_language,
            )
            run = await create_project_todo_run(
                session,
                queued.todo,
                agent_launch_json=queued.agent_launch.model_dump(mode="json"),
                dispatch_mode=queued.dispatch_mode,
                prompt=queued.prompt,
                trigger_reason="dependency",
                window_id=queued.todo.assigned_window_id
                if queued.todo.terminal_policy == PROJECT_TODO_TERMINAL_REUSE
                else None,
            )
            await clear_project_todo_queued_dispatch(session, queued.todo.id)
            await session.commit()
            await session.refresh(queued.todo)
            _schedule_reserved_project_todo_dispatch(
                queued.todo.id,
                run.id,
                agent_launch=queued.agent_launch,
                dispatch_mode=queued.dispatch_mode,
                prompt=queued.prompt,
                tmux_manager=tmux_manager,
                registry=registry,
                session_factory=session_factory,
                ui_event_hub=ui_event_hub,
                upstream_todo_id=upstream_todo.id if upstream_todo is not None else None,
            )
            dispatched.append(queued.todo)
            await publish_project_todo_dispatch_invalidation(
                ui_event_hub,
                queued.todo,
                reason="project_todo_dispatch_started",
            )
        except Exception:
            _dispatches_in_progress.discard(queued.todo.id)
            raise
    return dispatched


def _reserve_dispatch(todo_id: UUID) -> bool:
    if todo_id in _dispatches_in_progress:
        return False
    _dispatches_in_progress.add(todo_id)
    return True


def _schedule_reserved_project_todo_dispatch(
    todo_id: UUID,
    run_id: UUID,
    *,
    agent_launch: AgentLaunchIn,
    dispatch_mode: str,
    prompt: str,
    tmux_manager: TmuxManager,
    registry: ClientConnectionRegistry | None,
    session_factory: SessionFactory,
    ui_event_hub: UiEventHub,
    upstream_todo_id: UUID | None,
) -> None:
    task = asyncio.create_task(
        _dispatch_project_todo_background(
            todo_id=todo_id,
            run_id=run_id,
            agent_launch=agent_launch,
            dispatch_mode=dispatch_mode,
            prompt=prompt,
            tmux_manager=tmux_manager,
            registry=registry,
            session_factory=session_factory,
            ui_event_hub=ui_event_hub,
            upstream_todo_id=upstream_todo_id,
        )
    )
    task.add_done_callback(lambda done: _finish_dispatch_task(todo_id, done))


async def _dispatch_project_todo_background(
    *,
    todo_id: UUID,
    run_id: UUID,
    agent_launch: AgentLaunchIn,
    dispatch_mode: str,
    prompt: str,
    tmux_manager: TmuxManager,
    registry: ClientConnectionRegistry | None,
    session_factory: SessionFactory,
    ui_event_hub: UiEventHub,
    upstream_todo_id: UUID | None,
) -> None:
    try:
        await _run_project_todo_dispatch(
            todo_id=todo_id,
            run_id=run_id,
            agent_launch=agent_launch,
            dispatch_mode=dispatch_mode,
            prompt=prompt,
            tmux_manager=tmux_manager,
            registry=registry,
            session_factory=session_factory,
            ui_event_hub=ui_event_hub,
        )
    except (WindowServiceError, TimeoutError, ValueError, RuntimeError) as exc:
        logger.exception(
            "project todo dispatch failed",
            extra={
                "project_todo_id": str(todo_id),
                "upstream_todo_id": str(upstream_todo_id) if upstream_todo_id is not None else None,
            },
        )
        await mark_project_todo_dispatch_failed(
            todo_id,
            run_id,
            error=str(exc),
            session_factory=session_factory,
            ui_event_hub=ui_event_hub,
        )
    except Exception as exc:
        logger.exception(
            "project todo dispatch failed unexpectedly",
            extra={
                "project_todo_id": str(todo_id),
                "upstream_todo_id": str(upstream_todo_id) if upstream_todo_id is not None else None,
            },
        )
        await mark_project_todo_dispatch_failed(
            todo_id,
            run_id,
            error=str(exc) or exc.__class__.__name__,
            session_factory=session_factory,
            ui_event_hub=ui_event_hub,
        )


async def _run_project_todo_dispatch(
    *,
    todo_id: UUID,
    run_id: UUID,
    agent_launch: AgentLaunchIn,
    dispatch_mode: str,
    prompt: str,
    tmux_manager: TmuxManager,
    registry: ClientConnectionRegistry | None,
    session_factory: SessionFactory,
    ui_event_hub: UiEventHub,
) -> None:
    async with session_factory() as session:
        todo = await session.get(ProjectTodo, todo_id)
        if todo is None:
            return
        if await has_incomplete_dependencies(session, todo_id):
            raise RuntimeError("project todo dependencies are no longer complete")
        client = await get_client(session, todo.client_id)
        if client is None:
            raise RuntimeError("client not found")
        if todo.terminal_policy == PROJECT_TODO_TERMINAL_REUSE and todo.assigned_window_id is not None:
            target_window_id = todo.assigned_window_id
        else:
            result = await create_virtual_window_for_client(
                runtime_client_from_model(client),
                WindowCreateIn(cwd=todo.project_path, agent_launch=agent_launch),
                session,
                tmux_manager,
                registry,
                session_factory=session_factory,
                ui_event_hub=ui_event_hub,
            )
            target_window_id = result.window.id
            await mark_project_todo_run_window(session, run_id, target_window_id)

        await session.refresh(todo)
        todo.assigned_window_id = target_window_id
        todo.dispatch_stage = (
            PROJECT_TODO_DISPATCH_STAGE_TERMINAL_READY
            if todo.terminal_policy == PROJECT_TODO_TERMINAL_REUSE
            else PROJECT_TODO_DISPATCH_STAGE_WINDOW_CREATED
        )
        todo.dispatch_error = None
        await session.commit()
        await session.refresh(todo)
        await publish_project_todo_dispatch_invalidation(
            ui_event_hub,
            todo,
            reason="project_todo_dispatch_window_created",
        )

    await _wait_for_runtime_window(
        client_id=todo.client_id,
        window_id=target_window_id,
        session_factory=session_factory,
    )
    await _update_dispatch_stage(
        todo_id,
        PROJECT_TODO_DISPATCH_STAGE_TERMINAL_READY,
        session_factory=session_factory,
        ui_event_hub=ui_event_hub,
        reason="project_todo_dispatch_terminal_ready",
    )

    await dispatch_project_todo_prompt(
        client_id=todo.client_id,
        window_id=target_window_id,
        prompt=prompt,
        todo_id=todo_id,
        submit_prompt=dispatch_mode == "submit",
        session_factory=session_factory,
        tmux_manager=tmux_manager,
        registry=registry,
    )

    async with session_factory() as session:
        todo = await session.get(ProjectTodo, todo_id)
        if todo is None:
            return
        dispatched_at = datetime.now(UTC)
        todo.sort_order = await next_project_todo_sort_order(session, todo.client_id, todo.project_path)
        todo.status = ProjectTodoStatus.dispatched
        todo.assigned_window_id = target_window_id
        todo.assigned_agent = agent_launch.agent
        todo.agent_profile_id = agent_launch.profile_id
        todo.dispatch_prompt = prompt
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
        await clear_project_todo_queued_dispatch(session, todo.id)
        await mark_project_todo_run_dispatched(
            session,
            run_id,
            window_id=target_window_id,
            dispatched_at=dispatched_at,
        )
        await session.commit()
        await session.refresh(todo)
        await publish_project_todo_dispatch_invalidation(ui_event_hub, todo, reason="project_todo_dispatched")


def _prepare_project_todo_dispatch(
    todo: ProjectTodo,
    *,
    agent_launch: AgentLaunchIn,
    prompt: str,
    output_language: str | None,
) -> None:
    if todo.terminal_policy != PROJECT_TODO_TERMINAL_REUSE:
        todo.assigned_window_id = None
    todo.assigned_agent = agent_launch.agent
    todo.agent_profile_id = agent_launch.profile_id
    todo.dispatch_prompt = prompt
    todo.dispatch_output_language = output_language
    todo.dispatch_stage = PROJECT_TODO_DISPATCH_STAGE_STARTING
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
    todo.implementation_worktree_json = None


async def _update_dispatch_stage(
    todo_id: UUID,
    dispatch_stage: str,
    *,
    session_factory: SessionFactory,
    ui_event_hub: UiEventHub,
    reason: str,
) -> None:
    async with session_factory() as session:
        todo = await session.get(ProjectTodo, todo_id)
        if todo is None:
            return
        todo.dispatch_stage = dispatch_stage
        todo.dispatch_error = None
        await session.commit()
        await session.refresh(todo)
        await publish_project_todo_dispatch_invalidation(ui_event_hub, todo, reason=reason)


def _finish_dispatch_task(todo_id: UUID, task: asyncio.Task[None]) -> None:
    _dispatches_in_progress.discard(todo_id)
    if task.cancelled():
        return
    try:
        task.result()
    except Exception:
        logger.exception("project todo dispatch task crashed", extra={"project_todo_id": str(todo_id)})
