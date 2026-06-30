from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from contextlib import AbstractAsyncContextManager
from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.contexts.terminal_runtime.application.broker import TerminalBroker
from app.contexts.terminal_runtime.application.client_connections import ClientConnectionRegistry
from app.contexts.terminal_runtime.application.local_runtime_factory import create_local_terminal_runtime
from app.contexts.terminal_runtime.application.runtime_binding import RuntimeWindowBinding
from app.contexts.terminal_runtime.application.agent_prompt_input import looks_like_agent_command
from app.contexts.terminal_runtime.application.runtime_provider import (
    RemoteRuntime,
    TmuxManager,
)
from app.contexts.windows.application.window_lookup import get_window_for_client, patch_runtime_window
from app.contexts.windows.application.window_projection import (
    agent_provider_for_window as _agent_provider_for_window,
)
from app.contexts.workspace.application.project_todo_dispatch import (
    PROJECT_TODO_CAPTURE_HISTORY_LINES,
    _PromptOutputCollector,
    _command_bytes_for_prompt,
    _schedule_summary_after_submitted_todo_prompt,
    _wait_for_agent_working,
    append_project_todo_reference_context,
)
from app.contexts.workspace.application.project_todo_reference_context import (
    prompt_references_for_project_todos,
)
from app.contexts.workspace.application.project_todo_comment_readiness import (
    comment_agent_relaunch_bytes,
    wait_for_comment_agent_terminal_ready,
)
from app.contexts.workspace.application.project_todo_dispatch_after import (
    PROJECT_TODO_DISPATCH_STAGE_STARTING,
    PROJECT_TODO_DISPATCH_STAGE_TERMINAL_READY,
    PROJECT_TODO_DISPATCH_STAGE_WINDOW_CREATED,
    _finish_dispatch_task,
    _reserve_dispatch,
    _update_dispatch_stage,
)
from app.contexts.workspace.application.project_todo_dispatch_failure import (
    mark_project_todo_dispatch_failed,
    publish_project_todo_dispatch_invalidation,
)
from app.contexts.workspace.infrastructure.project_todo_dependencies_repository import (
    clear_project_todo_queued_dispatch,
)
from app.contexts.workspace.infrastructure.project_todo_reference_resolver import (
    resolve_project_todo_references_from_text,
)
from app.contexts.workspace.infrastructure.project_todos_repository import next_project_todo_sort_order
from app.models import Client, ClientRuntime, ProjectTodo, ProjectTodoStatus, VirtualWindow
from app.platform.plugins.agent_plugins import get_agent_plugin_registry
from app.platform.ui_events import UiEventHub

logger = logging.getLogger(__name__)

SessionFactory = Callable[[], AbstractAsyncContextManager[AsyncSession]]


def build_project_todo_comment_prompt(
    *,
    project_path: str,
    title: str,
    comment: str,
) -> str:
    return "\n\n".join(
        [
            "You are receiving a follow-up comment for this project todo.",
            f"Project path: {project_path}",
            f"Todo: {title}",
            f"Comment:\n{comment}",
            "Address this comment in the current session and report progress when appropriate.",
        ]
    )


async def submit_project_todo_comment(
    *,
    session: AsyncSession,
    client: Client,
    todo: ProjectTodo,
    comment: str,
    artifact_kinds: list[str] | None = None,
    tmux_manager: TmuxManager,
    registry: ClientConnectionRegistry | None,
    session_factory: SessionFactory,
    ui_event_hub: UiEventHub,
) -> ProjectTodo:
    if todo.assigned_window_id is None:
        raise RuntimeError("todo has no assigned terminal")
    window = await get_window_for_client(session, todo.client_id, todo.assigned_window_id)
    if window is None:
        raise RuntimeError("assigned terminal not found")
    referenced_todos = await resolve_project_todo_references_from_text(
        session,
        client_id=todo.client_id,
        project_path=todo.project_path,
        source_todo_id=todo.id,
        text=comment,
    )
    prompt_references = await prompt_references_for_project_todos(session, referenced_todos)
    prompt = build_project_todo_comment_prompt(
        project_path=todo.project_path,
        title=todo.title,
        comment=comment,
    )
    prompt = append_project_todo_reference_context(prompt, prompt_references)
    if not _reserve_dispatch(todo.id):
        raise RuntimeError("todo already has a prompt dispatch in progress")

    scheduled = False
    try:
        await _prepare_project_todo_comment_dispatch(
            session,
            todo,
            prompt=prompt,
            artifact_kinds=artifact_kinds,
        )
        await session.commit()
        await session.refresh(todo)
        _schedule_reserved_project_todo_comment_dispatch(
            todo.id,
            client_id=client.id,
            window_id=window.id,
            prompt=prompt,
            tmux_manager=tmux_manager,
            registry=registry,
            session_factory=session_factory,
            ui_event_hub=ui_event_hub,
        )
        scheduled = True
        await publish_project_todo_dispatch_invalidation(ui_event_hub, todo, reason="project_todo_comment_started")
    except Exception:
        if not scheduled:
            _finish_dispatch_task(todo.id, _completed_success_task())
        raise
    await session.refresh(todo)
    return todo


async def _prepare_project_todo_comment_dispatch(
    session: AsyncSession,
    todo: ProjectTodo,
    *,
    prompt: str,
    artifact_kinds: list[str] | None = None,
) -> None:
    todo.sort_order = await next_project_todo_sort_order(session, todo.client_id, todo.project_path)
    todo.status = ProjectTodoStatus.todo
    todo.dispatch_prompt = prompt
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
    if artifact_kinds is not None:
        todo.artifact_kinds_json = artifact_kinds or None
    await clear_project_todo_queued_dispatch(session, todo.id)


def _schedule_reserved_project_todo_comment_dispatch(
    todo_id: UUID,
    *,
    client_id: UUID,
    window_id: UUID,
    prompt: str,
    tmux_manager: TmuxManager,
    registry: ClientConnectionRegistry | None,
    session_factory: SessionFactory,
    ui_event_hub: UiEventHub,
) -> None:
    task = asyncio.create_task(
        _dispatch_project_todo_comment_background(
            todo_id=todo_id,
            client_id=client_id,
            window_id=window_id,
            prompt=prompt,
            tmux_manager=tmux_manager,
            registry=registry,
            session_factory=session_factory,
            ui_event_hub=ui_event_hub,
        )
    )
    task.add_done_callback(lambda done: _finish_dispatch_task(todo_id, done))


async def _dispatch_project_todo_comment_background(
    *,
    todo_id: UUID,
    client_id: UUID,
    window_id: UUID,
    prompt: str,
    tmux_manager: TmuxManager,
    registry: ClientConnectionRegistry | None,
    session_factory: SessionFactory,
    ui_event_hub: UiEventHub,
) -> None:
    try:
        await _update_dispatch_stage(
            todo_id,
            PROJECT_TODO_DISPATCH_STAGE_WINDOW_CREATED,
            session_factory=session_factory,
            ui_event_hub=ui_event_hub,
            reason="project_todo_comment_terminal_attached",
        )
        await _submit_comment_prompt_by_id(
            client_id=client_id,
            window_id=window_id,
            prompt=prompt,
            tmux_manager=tmux_manager,
            registry=registry,
            session_factory=session_factory,
            on_terminal_ready=lambda: _update_dispatch_stage(
                todo_id,
                PROJECT_TODO_DISPATCH_STAGE_TERMINAL_READY,
                session_factory=session_factory,
                ui_event_hub=ui_event_hub,
                reason="project_todo_comment_terminal_ready",
            ),
        )
        await _mark_project_todo_comment_dispatched(
            todo_id,
            window_id=window_id,
            prompt=prompt,
            session_factory=session_factory,
            ui_event_hub=ui_event_hub,
        )
    except (TimeoutError, ValueError, RuntimeError) as exc:
        logger.exception("project todo comment dispatch failed", extra={"project_todo_id": str(todo_id)})
        await mark_project_todo_dispatch_failed(
            todo_id,
            error=str(exc),
            session_factory=session_factory,
            ui_event_hub=ui_event_hub,
        )
    except Exception as exc:
        logger.exception("project todo comment dispatch failed unexpectedly", extra={"project_todo_id": str(todo_id)})
        await mark_project_todo_dispatch_failed(
            todo_id,
            error=str(exc) or exc.__class__.__name__,
            session_factory=session_factory,
            ui_event_hub=ui_event_hub,
        )


async def _submit_comment_prompt_by_id(
    *,
    client_id: UUID,
    window_id: UUID,
    prompt: str,
    tmux_manager: TmuxManager,
    registry: ClientConnectionRegistry | None,
    session_factory: SessionFactory,
    on_terminal_ready: Callable[[], Awaitable[None]],
) -> None:
    async with session_factory() as session:
        window = await get_window_for_client(session, client_id, window_id)
        if window is None:
            raise RuntimeError("assigned terminal not found")
        client = await session.get(Client, client_id)
        if client is None:
            raise RuntimeError("client not found")
    await _submit_comment_prompt(
        client=client,
        window=window,
        prompt=prompt,
        tmux_manager=tmux_manager,
        registry=registry,
        session_factory=session_factory,
        on_terminal_ready=on_terminal_ready,
    )


async def _mark_project_todo_comment_dispatched(
    todo_id: UUID,
    *,
    window_id: UUID,
    prompt: str,
    session_factory: SessionFactory,
    ui_event_hub: UiEventHub,
) -> None:
    async with session_factory() as session:
        todo = await session.get(ProjectTodo, todo_id)
        if todo is None:
            return
        todo.status = ProjectTodoStatus.dispatched
        todo.assigned_window_id = window_id
        todo.dispatch_prompt = prompt
        todo.dispatch_stage = None
        todo.dispatch_error = None
        todo.dispatched_at = datetime.now(UTC)
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
        await session.commit()
        await session.refresh(todo)
        await publish_project_todo_dispatch_invalidation(ui_event_hub, todo, reason="project_todo_comment_dispatched")


def _completed_success_task() -> asyncio.Future[None]:
    future: asyncio.Future[None] = asyncio.get_running_loop().create_future()
    future.set_result(None)
    return future


async def _submit_comment_prompt(
    *,
    client: Client,
    window: VirtualWindow,
    prompt: str,
    tmux_manager: TmuxManager,
    registry: ClientConnectionRegistry | None,
    session_factory: SessionFactory,
    on_terminal_ready: Callable[[], Awaitable[None]] | None = None,
) -> None:
    binding = RuntimeWindowBinding.from_virtual_window(window)
    if binding is None:
        raise RuntimeError("assigned terminal runtime is not ready")

    broker = TerminalBroker()
    if client.runtime is ClientRuntime.local:
        broker.register_runtime(
            client.id,
            create_local_terminal_runtime(tmux_manager, session_factory=session_factory),
        )
    elif registry is not None:
        broker.register_runtime(client.id, RemoteRuntime(client_id=client.id, registry=registry))
    else:
        raise RuntimeError("remote runtime unavailable")

    hidden_view_id = uuid4()
    collector = _PromptOutputCollector()
    attached = False
    try:
        attached_runtime_window = await broker.attach(
            client.id,
            window.id,
            binding.runtime_window,
            output_callback=collector.feed,
            view_id=hidden_view_id,
        )
        attached = True
        if attached_runtime_window != binding.runtime_window:
            binding = binding.with_runtime_window(attached_runtime_window)
            await _persist_comment_runtime_window(
                client_id=client.id,
                window_id=window.id,
                binding=binding,
                session_factory=session_factory,
            )

        async def capture_output() -> bytes:
            return await broker.capture_output_bytes(
                client.id,
                window.id,
                binding.runtime_window,
                view_id=hidden_view_id,
                history_lines=PROJECT_TODO_CAPTURE_HISTORY_LINES,
            )

        prompt_shell_command = await _comment_prompt_shell_command(
            window=window,
            runtime_window_shell_command=binding.runtime_window.shell_command,
            session_factory=session_factory,
        )
        await wait_for_comment_agent_terminal_ready(
            prompt_shell_command=prompt_shell_command,
            collector=collector,
            capture_output=capture_output,
            relaunch_agent=lambda: broker.send_input_direct(
                client.id,
                window.id,
                binding.runtime_window,
                comment_agent_relaunch_bytes(prompt_shell_command, cwd=binding.runtime_window.cwd or window.cwd),
            ),
        )
        if on_terminal_ready is not None:
            await on_terminal_ready()
        data = _command_bytes_for_prompt(prompt_shell_command, prompt, submit_prompt=True)
        submitted_at = datetime.now(UTC)
        await broker.send_input_direct(client.id, window.id, binding.runtime_window, data)
        await _wait_for_agent_working(
            client_id=client.id,
            window_id=window.id,
            session_factory=session_factory,
            submitted_at=submitted_at,
        )
        await _schedule_summary_after_submitted_todo_prompt(
            client_id=client.id,
            window_id=window.id,
            session_factory=session_factory,
        )
    finally:
        if attached:
            try:
                await broker.unsubscribe(client.id, hidden_view_id, collector.feed)
            except Exception:
                logger.debug(
                    "project todo comment hidden terminal detach failed",
                    extra={"client_id": str(client.id), "window_id": str(window.id)},
                    exc_info=True,
                )


async def _comment_prompt_shell_command(
    *,
    window: VirtualWindow,
    runtime_window_shell_command: str | None,
    session_factory: SessionFactory,
) -> str | None:
    if runtime_window_shell_command and looks_like_agent_command(runtime_window_shell_command):
        return runtime_window_shell_command
    if window.shell_command and looks_like_agent_command(window.shell_command):
        return window.shell_command

    async with session_factory() as session:
        provider = await _agent_provider_for_window(session, window)
    if provider is None:
        return runtime_window_shell_command or window.shell_command

    try:
        return get_agent_plugin_registry().by_provider(provider).command.default_command
    except ValueError:
        return runtime_window_shell_command or window.shell_command


async def _persist_comment_runtime_window(
    *,
    client_id: UUID,
    window_id: UUID,
    binding: RuntimeWindowBinding,
    session_factory: SessionFactory,
) -> None:
    async with session_factory() as session:
        await patch_runtime_window(
            session,
            client_id,
            window_id,
            **binding.runtime_persistence_fields(),
        )
        await session.commit()
