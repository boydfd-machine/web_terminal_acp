from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from datetime import datetime
from uuid import UUID

from app.config import get_settings
from app.contexts.terminal_runtime.application.broker import TerminalBroker
from app.contexts.terminal_runtime.application.client_connections import (
    ClientConnectionRegistry,
)
from app.contexts.terminal_runtime.application.runtime_provider import (
    RemoteRuntime,
    TmuxManager,
    get_tmux_manager,
)
from app.contexts.terminal_runtime.application.process_liveness import (
    pane_has_active_non_shell_process,
)
from app.contexts.workspace.application.project_todo_completion_aux_agent import (
    run_verification_prompt as _run_verification_prompt,
)
from app.contexts.workspace.application.project_todo_background_completion import (
    BACKGROUND_WORK_RECHECK_ATTEMPT,
    active_processes_look_like_background_work as _active_processes_look_like_background_work,
    background_work_waiting_error,
)
from app.contexts.workspace.application.project_todo_completion_background_gate import (
    background_completion_review_time,
    background_verification_incomplete_waiting_error,
)
from app.contexts.workspace.application.project_todo_completion_prompt import VerificationVerdict
from app.contexts.workspace.application.project_todo_artifact_scheduler import (
    complete_project_todo_implementation,
)
from app.db import SessionLocal
from app.models import Client, ClientRuntime, ProjectTodo, ProjectTodoStatus, VirtualWindow
from app.contexts.windows.application.window_lookup import get_window_for_client

logger = logging.getLogger(__name__)


VERIFICATION_DISPATCH_STAGE = "verifying"

# Per-process set of todos currently being verified. Prevents the tmux window
# storm regression where multiple completion events for the same window each
# schedule their own verification task, and every task spawns its own ephemeral
# aux-agent window even though only one of them can actually act on the todo.
_verifications_in_progress: set[UUID] = set()


def _reserve_verification(todo_id: UUID) -> bool:
    if todo_id in _verifications_in_progress:
        return False
    _verifications_in_progress.add(todo_id)
    return True


def _release_verification(todo_id: UUID) -> None:
    _verifications_in_progress.discard(todo_id)


def schedule_todo_completion_verification(
    todo_id: UUID,
    *,
    client_id: UUID,
    completed_at: datetime,
    window_id: UUID,
    session_factory=SessionLocal,
    tmux_manager: TmuxManager | None = None,
    terminal_broker: TerminalBroker | None = None,
    registry: ClientConnectionRegistry | None = None,
    remote_runtime_factory=None,
    attempt: int = 1,
    delay_seconds: float = 0.0,
) -> asyncio.Task[None]:
    task = asyncio.create_task(
        _delayed_verify_todo_completion(
            todo_id,
            client_id=client_id,
            completed_at=completed_at,
            window_id=window_id,
            session_factory=session_factory,
            tmux_manager=tmux_manager or get_tmux_manager(),
            terminal_broker=terminal_broker,
            registry=registry,
            remote_runtime_factory=remote_runtime_factory,
            attempt=attempt,
            delay_seconds=delay_seconds,
        )
    )
    task.add_done_callback(_log_verification_task_failure)
    return task


def make_verification_scheduler(
    *,
    client_id: UUID,
    window_id: UUID | None = None,
    session_factory=SessionLocal,
    registry: ClientConnectionRegistry | None = None,
) -> Callable[[ProjectTodo, datetime], bool]:
    """Return a callable usable as `verification_scheduler` for
    `sync_dispatched_project_todos` / `sync_project_todos_for_completed_window`.

    Returns True when a verification task has been scheduled (caller should skip
    the immediate `_mark_implementation_completed` upgrade).
    """

    def scheduler(todo: ProjectTodo, completed_at: datetime) -> bool:
        if not get_settings().project_todo_completion_verification_enabled:
            return False
        effective_window_id = window_id or todo.assigned_window_id
        if effective_window_id is None:
            return False
        schedule_todo_completion_verification(
            todo.id,
            client_id=client_id,
            completed_at=completed_at,
            window_id=effective_window_id,
            session_factory=session_factory,
            registry=registry,
        )
        return True

    return scheduler


def _log_verification_task_failure(task: asyncio.Task[None]) -> None:
    if task.cancelled():
        return
    exc = task.exception()
    if exc is not None:
        logger.error(
            "project todo completion verification task crashed",
            exc_info=(type(exc), exc, exc.__traceback__),
        )


async def _delayed_verify_todo_completion(
    todo_id: UUID,
    *,
    client_id: UUID,
    completed_at: datetime,
    window_id: UUID,
    session_factory,
    tmux_manager: TmuxManager,
    terminal_broker: TerminalBroker | None,
    registry: ClientConnectionRegistry | None,
    remote_runtime_factory=None,
    attempt: int,
    delay_seconds: float,
) -> None:
    if delay_seconds > 0:
        await asyncio.sleep(delay_seconds)
    if not _reserve_verification(todo_id):
        # Another verification task for this todo is already running. Skipping
        # avoids the tmux window storm where concurrent completion events each
        # spawn their own aux-agent ephemeral window for the same todo.
        logger.debug(
            "project todo completion verification skipped; another run is in progress",
            extra={"project_todo_id": str(todo_id), "attempt": attempt},
        )
        return
    try:
        await _verify_todo_completion(
            todo_id,
            client_id=client_id,
            completed_at=completed_at,
            window_id=window_id,
            session_factory=session_factory,
            tmux_manager=tmux_manager,
            terminal_broker=terminal_broker,
            registry=registry,
            remote_runtime_factory=remote_runtime_factory,
            attempt=attempt,
        )
    finally:
        _release_verification(todo_id)


async def _verify_todo_completion(
    todo_id: UUID,
    *,
    client_id: UUID,
    completed_at: datetime,
    window_id: UUID,
    session_factory,
    tmux_manager: TmuxManager,
    terminal_broker: TerminalBroker | None,
    registry: ClientConnectionRegistry | None,
    remote_runtime_factory=None,
    attempt: int,
) -> None:
    settings = get_settings()
    has_active, active_processes = await _query_active_processes(
        client_id=client_id,
        window_id=window_id,
        session_factory=session_factory,
        tmux_manager=tmux_manager,
        registry=registry,
        remote_runtime_factory=remote_runtime_factory,
    )
    if has_active and not _active_processes_look_like_background_work(active_processes):
        # Active processes that are not background work (e.g., a dev server,
        # MCP infrastructure, or the agent runtime itself) must NOT trigger
        # the aux agent. The aux terminal is heavy and should only run when
        # the agent has actual background work still running, or after we
        # have already waited for background work to finish. Otherwise simple
        # tasks like "say hi" would briefly drop into the verifying state and
        # spawn an ephemeral aux window before reaching review.
        has_active = False
    if not has_active:
        async with session_factory() as session:
            todo = await session.get(ProjectTodo, todo_id)
            if todo is None or todo.status != ProjectTodoStatus.dispatched:
                return
            background_review = await background_completion_review_time(
                session,
                todo,
                client_id=client_id,
                window_id=window_id,
                completed_at=completed_at,
                dispatch_stage=VERIFICATION_DISPATCH_STAGE,
            )
            if background_review is None:
                await session.commit()
                _schedule_background_work_recheck(
                    todo_id,
                    client_id=client_id,
                    completed_at=completed_at,
                    window_id=window_id,
                    session_factory=session_factory,
                    tmux_manager=tmux_manager,
                    terminal_broker=terminal_broker,
                    registry=registry,
                    remote_runtime_factory=remote_runtime_factory,
                )
                return
            if not background_review.waited_for_background_work:
                await complete_project_todo_implementation(
                    session,
                    todo,
                    background_review.completed_at,
                    window_id,
                    remote_client_available=None,
                )
                return
            review_completed_at = background_review.completed_at
            waited_for_background_work = True
        await _verify_with_auxiliary_agent(
            todo_id,
            client_id=client_id,
            window_id=window_id,
            completed_at=completed_at,
            review_completed_at=review_completed_at,
            attempt=attempt,
            active_processes=[],
            waited_for_background_work=waited_for_background_work,
            session_factory=session_factory,
            tmux_manager=tmux_manager,
            terminal_broker=terminal_broker,
            registry=registry,
            remote_runtime_factory=remote_runtime_factory,
        )
        return

    if _active_processes_look_like_background_work(active_processes):
        await _defer_completion_for_active_background_work(
            todo_id,
            client_id=client_id,
            completed_at=completed_at,
            window_id=window_id,
            active_processes=active_processes,
            session_factory=session_factory,
            tmux_manager=tmux_manager,
            terminal_broker=terminal_broker,
            registry=registry,
            remote_runtime_factory=remote_runtime_factory,
        )
        return

    async with session_factory() as session:
        todo = await session.get(ProjectTodo, todo_id)
        if todo is None or todo.status != ProjectTodoStatus.dispatched:
            return
        background_review = await background_completion_review_time(
            session,
            todo,
            client_id=client_id,
            window_id=window_id,
            completed_at=completed_at,
            dispatch_stage=VERIFICATION_DISPATCH_STAGE,
        )
        if background_review is None:
            await session.commit()
            _schedule_background_work_recheck(
                todo_id,
                client_id=client_id,
                completed_at=completed_at,
                window_id=window_id,
                session_factory=session_factory,
                tmux_manager=tmux_manager,
                terminal_broker=terminal_broker,
                registry=registry,
                remote_runtime_factory=remote_runtime_factory,
            )
            return
        waited_for_background_work = background_review.waited_for_background_work
        review_completed_at = background_review.completed_at

    await _verify_with_auxiliary_agent(
        todo_id=todo_id,
        client_id=client_id,
        window_id=window_id,
        completed_at=completed_at,
        review_completed_at=review_completed_at,
        attempt=attempt,
        active_processes=active_processes,
        waited_for_background_work=waited_for_background_work,
        session_factory=session_factory,
        tmux_manager=tmux_manager,
        terminal_broker=terminal_broker,
        registry=registry,
        remote_runtime_factory=remote_runtime_factory,
    )


async def _verify_with_auxiliary_agent(
    todo_id: UUID,
    *,
    client_id: UUID,
    window_id: UUID,
    completed_at: datetime,
    review_completed_at: datetime,
    attempt: int,
    active_processes: list[str],
    waited_for_background_work: bool,
    session_factory,
    tmux_manager: TmuxManager,
    terminal_broker: TerminalBroker | None,
    registry: ClientConnectionRegistry | None,
    remote_runtime_factory,
) -> None:
    settings = get_settings()
    verdict = await _run_verification_prompt(
        todo_id=todo_id,
        client_id=client_id,
        window_id=window_id,
        attempt=attempt,
        active_processes=active_processes,
        session_factory=session_factory,
        tmux_manager=tmux_manager,
        terminal_broker=terminal_broker,
        registry=registry,
        waited_for_background_work=waited_for_background_work,
    )

    async with session_factory() as session:
        todo = await session.get(ProjectTodo, todo_id)
        if todo is None:
            return
        if todo.status != ProjectTodoStatus.dispatched:
            return
        if verdict.verdict == "complete":
            await complete_project_todo_implementation(
                session,
                todo,
                review_completed_at,
                window_id,
                remote_client_available=None,
            )
            return
        max_attempts = settings.project_todo_completion_verification_max_attempts
        if attempt < max_attempts:
            if waited_for_background_work:
                todo.dispatch_stage = VERIFICATION_DISPATCH_STAGE
                todo.dispatch_error = background_verification_incomplete_waiting_error(
                    review_completed_at,
                    attempt=attempt,
                    verdict=verdict,
                )
                await session.commit()
                schedule_todo_completion_verification(
                    todo_id,
                    client_id=client_id,
                    completed_at=completed_at,
                    window_id=window_id,
                    session_factory=session_factory,
                    tmux_manager=tmux_manager,
                    terminal_broker=terminal_broker,
                    registry=registry,
                    remote_runtime_factory=remote_runtime_factory,
                    attempt=attempt + 1,
                )
                return
            todo.dispatch_stage = None
            todo.dispatch_error = (
                f"verification attempt {attempt} {verdict.verdict}: {verdict.evidence}"[:4000]
            )
            await session.commit()
            schedule_todo_completion_verification(
                todo_id,
                client_id=client_id,
                completed_at=completed_at,
                window_id=window_id,
                session_factory=session_factory,
                tmux_manager=tmux_manager,
                terminal_broker=terminal_broker,
                registry=registry,
                remote_runtime_factory=remote_runtime_factory,
                attempt=attempt + 1,
            )
            return
        todo.status = ProjectTodoStatus.blocked
        todo.blocked_reason = (
            f"Completion verification failed after {attempt} attempts. "
            f"Last verdict: {verdict.verdict}. Evidence: {verdict.evidence}"[:4000]
        )
        todo.dispatch_stage = None
        todo.dispatch_error = None
        await session.commit()


async def _defer_completion_for_active_background_work(
    todo_id: UUID,
    *,
    client_id: UUID,
    completed_at: datetime,
    window_id: UUID,
    active_processes: list[str],
    session_factory,
    tmux_manager: TmuxManager,
    terminal_broker: TerminalBroker | None,
    registry: ClientConnectionRegistry | None,
    remote_runtime_factory,
) -> None:
    async with session_factory() as session:
        todo = await session.get(ProjectTodo, todo_id)
        if todo is None or todo.status != ProjectTodoStatus.dispatched:
            return
        todo.dispatch_stage = VERIFICATION_DISPATCH_STAGE
        todo.dispatch_error = background_work_waiting_error(active_processes)
        await session.commit()
    _schedule_background_work_recheck(
        todo_id,
        client_id=client_id,
        completed_at=completed_at,
        window_id=window_id,
        session_factory=session_factory,
        tmux_manager=tmux_manager,
        terminal_broker=terminal_broker,
        registry=registry,
        remote_runtime_factory=remote_runtime_factory,
    )


def _schedule_background_work_recheck(
    todo_id: UUID,
    *,
    client_id: UUID,
    completed_at: datetime,
    window_id: UUID,
    session_factory,
    tmux_manager: TmuxManager,
    terminal_broker: TerminalBroker | None,
    registry: ClientConnectionRegistry | None,
    remote_runtime_factory,
) -> None:
    schedule_todo_completion_verification(
        todo_id,
        client_id=client_id,
        completed_at=completed_at,
        window_id=window_id,
        session_factory=session_factory,
        tmux_manager=tmux_manager,
        terminal_broker=terminal_broker,
        registry=registry,
        remote_runtime_factory=remote_runtime_factory,
        attempt=BACKGROUND_WORK_RECHECK_ATTEMPT,
        delay_seconds=get_settings().project_todo_completion_verification_background_recheck_seconds,
    )


async def _query_active_processes(
    *,
    client_id: UUID,
    window_id: UUID,
    session_factory,
    tmux_manager: TmuxManager,
    registry: ClientConnectionRegistry | None = None,
    remote_runtime_factory=None,
) -> tuple[bool, list[str]]:
    async with session_factory() as session:
        client = await session.get(Client, client_id)
        window = await get_window_for_client(session, client_id, window_id)
    if client is None or window is None:
        return False, []
    pending_subagents = int(window.agent_activity_pending_subagent_count or 0)
    remote_runtime = None
    if client.runtime is not ClientRuntime.local and registry is not None:
        factory = remote_runtime_factory or (
            lambda requested_client_id, requested_registry: RemoteRuntime(
                client_id=requested_client_id,
                registry=requested_registry,
                request_timeout=10.0,
            )
        )
        remote_runtime = factory(client.id, registry)
    has_active, active_processes = await pane_has_active_non_shell_process(
        client,
        window,
        tmux_manager=tmux_manager,
        remote_runtime=remote_runtime,
    )
    if pending_subagents > 0:
        processes = list(active_processes)
        processes.append(f"pending subagent ({pending_subagents})")
        return True, processes
    return has_active, active_processes
