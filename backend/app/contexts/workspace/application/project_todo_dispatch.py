from __future__ import annotations

import asyncio
import contextlib
import logging
import time
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from uuid import UUID

from jinja2 import StrictUndefined, TemplateError
from jinja2.sandbox import SandboxedEnvironment

from app.contexts.windows.application.window_lookup import get_window_for_client
from app.contexts.terminal_runtime.application.broker import TerminalBroker
from app.contexts.terminal_runtime.application.client_connections import ClientConnectionRegistry
from app.contexts.terminal_runtime.application.local_runtime_factory import create_local_terminal_runtime
from app.contexts.terminal_runtime.domain.types import RuntimeWindow
from app.contexts.terminal_runtime.application.runtime_provider import RemoteRuntime
from app.contexts.terminal_runtime.application.runtime_provider import TmuxManager
from app.contexts.terminal_runtime.application.agent_prompt_input import (
    agent_provider_for_prompt,
    agent_prompt_submit_bytes,
    command_bytes_for_agent_prompt,
    looks_like_agent_command,
    MULTILINE_PROMPT_BRACKETED_PASTE_PROVIDERS,
)
from app.contexts.activity.application.terminal_work_status import load_work_status
from app.contexts.workspace.application.summary_scheduler import (
    schedule_summary_after_project_todo_dispatch,
)
from app.contexts.workspace.application.project_todo_attachment_staging import (
    stage_project_todo_attachments_for_prompt,
)
from app.contexts.workspace.application.project_todo_prompt_references import (
    ProjectTodoPromptArtifact as ProjectTodoPromptArtifact,
    ProjectTodoPromptReference,
    ProjectTodoPromptSession as ProjectTodoPromptSession,
    ProjectTodoPromptTerminal as ProjectTodoPromptTerminal,
    ProjectTodoPromptTurn as ProjectTodoPromptTurn,
    append_project_todo_reference_context as append_project_todo_reference_context,
    project_todo_parent_context_section,
    project_todo_prompt_with_output_language,
    project_todo_reference_context_section,
    single_line_output_language,
)
from app.contexts.workspace.application.project_todo_prompt_readiness import (
    PROJECT_TODO_AGENT_READY_SETTLE_SECONDS,
    PromptOutputCollector as _PromptOutputCollector,
    wait_until_agent_ready as _wait_until_agent_ready,
)
from app.models import ClientRuntime

logger = logging.getLogger(__name__)

PROJECT_TODO_RUNTIME_READY_TIMEOUT_SECONDS = 90.0
PROJECT_TODO_AGENT_WORKING_TIMEOUT_SECONDS = 180.0
PROJECT_TODO_AGENT_WORKING_POLL_INTERVAL_SECONDS = 0.5
PROJECT_TODO_CAPTURE_HISTORY_LINES = 5000
PROJECT_TODO_FOLLOWUP_SUBMIT_INTERVAL_SECONDS = 0.5
PROJECT_TODO_FOLLOWUP_SUBMIT_DURATION_SECONDS = 10.0
PROJECT_TODO_FOLLOWUP_SUBMIT_PROVIDERS = frozenset({"claude_code"})


def build_project_todo_prompt(
    *,
    project_path: str,
    title: str,
    description: str | None,
    output_language: str | None = None,
    parent_todo: ProjectTodoPromptReference | None = None,
    parent_todos: list[ProjectTodoPromptReference] | None = None,
    referenced_todos: list[ProjectTodoPromptReference] | None = None,
) -> str:
    sections = [
        "You are assigned to complete this project todo.",
        f"Project path: {project_path}",
        f"Todo: {title}",
    ]
    if description:
        sections.append(f"Context:\n{description}")
    parent_section = project_todo_parent_context_section(parent_todo, parent_todos=parent_todos)
    if parent_section:
        sections.append(parent_section)
    reference_section = project_todo_reference_context_section(referenced_todos)
    if reference_section:
        sections.append(reference_section)
    return project_todo_prompt_with_output_language("\n\n".join(sections), output_language)


def build_project_todo_template_prompt(
    *,
    template: str,
    project_path: str,
    title: str,
    description: str | None,
    todo_type_id: str,
    artifact_kinds: list[str],
    input_artifact_ids: list[str] | None = None,
    output_language: str | None = None,
) -> str:
    try:
        rendered = _dispatch_template_environment().from_string(template).render(
            {
                "project_path": project_path,
                "title": title,
                "description": description or "",
                "todo_type_id": todo_type_id,
                "artifact_kinds": artifact_kinds,
                "input_artifact_ids": input_artifact_ids or [],
                "output_language": single_line_output_language(output_language),
            }
        )
    except TemplateError as exc:
        raise ValueError(f"dispatch template is invalid: {exc}") from exc
    prompt = rendered.strip()
    if not prompt:
        raise ValueError("dispatch template rendered an empty prompt")
    return project_todo_prompt_with_output_language(prompt, output_language)


def _dispatch_template_environment() -> SandboxedEnvironment:
    return SandboxedEnvironment(undefined=StrictUndefined, autoescape=False)


def build_project_todo_review_prompt(
    *,
    project_path: str,
    title: str,
    description: str | None,
    implementation_worktree: dict | None,
    output_language: str | None = None,
) -> str:
    sections = [
        "You are assigned to review a completed project todo before it is merged or marked done.",
        f"Project path: {project_path}",
        f"Todo: {title}",
    ]
    if description:
        sections.append(f"Original context:\n{description}")
    if implementation_worktree:
        sections.append(f"Implementation evidence:\n{implementation_worktree}")
    sections.append(
        "Review the implementation, inspect the changed commits/files, run focused validation, "
        "and report whether it is approved, needs changes, or needs human review."
    )
    return project_todo_prompt_with_output_language("\n\n".join(sections), output_language)


def schedule_project_todo_prompt_dispatch(
    *,
    client_id: UUID,
    window_id: UUID,
    prompt: str,
    todo_id: UUID | None = None,
    submit_prompt: bool = True,
    session_factory: Callable[[], object],
    tmux_manager: TmuxManager,
    registry: ClientConnectionRegistry | None,
) -> None:
    task = asyncio.create_task(
        dispatch_project_todo_prompt(
            client_id=client_id,
            window_id=window_id,
            prompt=prompt,
            todo_id=todo_id,
            submit_prompt=submit_prompt,
            session_factory=session_factory,
            tmux_manager=tmux_manager,
            registry=registry,
        )
    )
    task.add_done_callback(_log_dispatch_failure)


async def dispatch_project_todo_prompt(
    *,
    client_id: UUID,
    window_id: UUID,
    prompt: str,
    todo_id: UUID | None = None,
    submit_prompt: bool = True,
    session_factory: Callable[[], object],
    tmux_manager: TmuxManager,
    registry: ClientConnectionRegistry | None,
) -> None:
    runtime_kind, runtime_window = await _wait_for_runtime_window(
        client_id=client_id,
        window_id=window_id,
        session_factory=session_factory,
    )
    broker = TerminalBroker()
    if runtime_kind is ClientRuntime.local:
        broker.register_runtime(
            client_id,
            create_local_terminal_runtime(tmux_manager, session_factory=session_factory),
        )
    elif registry is not None:
        broker.register_runtime(client_id, RemoteRuntime(client_id=client_id, registry=registry))
    else:
        raise RuntimeError("remote runtime unavailable")

    if todo_id is not None:
        prompt = await stage_project_todo_attachments_for_prompt(
            client_id=client_id,
            todo_id=todo_id,
            prompt=prompt,
            session_factory=session_factory,
            broker=broker,
        )

    collector = _PromptOutputCollector()

    async def capture_output() -> bytes:
        return await broker.capture_output_bytes(
            client_id,
            window_id,
            runtime_window,
            history_lines=PROJECT_TODO_CAPTURE_HISTORY_LINES,
        )

    await _wait_for_agent_terminal_ready(
        runtime_window.shell_command,
        collector,
        capture_output=capture_output,
    )
    prompt_ready_snapshot = collector.last_snapshot()
    data = _command_bytes_for_prompt(runtime_window.shell_command, prompt, submit_prompt=submit_prompt)
    prompt_submitted_at = datetime.now(UTC)
    await broker.send_input_direct(client_id, window_id, runtime_window, data)
    if submit_prompt:
        followup_data = _followup_submit_bytes_for_prompt(runtime_window.shell_command)
        followup_submit_event = asyncio.Event() if followup_data else None
        followup_task = _schedule_project_todo_followup_submits(
            broker,
            client_id,
            window_id,
            runtime_window,
            followup_data,
            first_submit_event=followup_submit_event,
        )
        try:
            await _wait_for_agent_working(
                client_id=client_id,
                window_id=window_id,
                session_factory=session_factory,
                submitted_at=prompt_submitted_at,
                capture_output=capture_output,
                submitted_snapshot=prompt_ready_snapshot,
                output_signal_ready=followup_submit_event,
            )
            await _schedule_summary_after_submitted_todo_prompt(
                client_id=client_id,
                window_id=window_id,
                session_factory=session_factory,
            )
        finally:
            if followup_task is not None and not followup_task.done():
                followup_task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await followup_task


async def _wait_for_runtime_window(
    *,
    client_id: UUID,
    window_id: UUID,
    session_factory: Callable[[], object],
) -> tuple[ClientRuntime, RuntimeWindow]:
    deadline = time.monotonic() + PROJECT_TODO_RUNTIME_READY_TIMEOUT_SECONDS
    while True:
        async with session_factory() as session:
            window = await get_window_for_client(session, client_id, window_id)
            if window is not None and window.tmux_session and window.tmux_window_id:
                return ClientRuntime.local, RuntimeWindow(
                    session_id=window.tmux_session,
                    window_id=window.tmux_window_id,
                    window_index=window.tmux_window_index,
                    cwd=window.cwd,
                    shell_command=window.shell_command,
                )
            if window is not None and window.remote_session_id and window.remote_window_id:
                return ClientRuntime.remote, RuntimeWindow(
                    session_id=window.remote_session_id,
                    window_id=window.remote_window_id,
                    cwd=window.cwd,
                    shell_command=window.shell_command,
                )
        if time.monotonic() >= deadline:
            raise TimeoutError("project todo terminal runtime did not become ready")
        await asyncio.sleep(0.25)


async def _schedule_summary_after_submitted_todo_prompt(
    *,
    client_id: UUID,
    window_id: UUID,
    session_factory: Callable[[], object],
) -> None:
    try:
        async with session_factory() as session:
            window = await get_window_for_client(session, client_id, window_id)
            if window is None:
                return
            await schedule_summary_after_project_todo_dispatch(session, window)
            await session.commit()
    except Exception:
        logger.warning(
            "project todo prompt summary scheduling failed",
            extra={"client_id": str(client_id), "window_id": str(window_id)},
            exc_info=True,
        )


def _command_bytes_for_prompt(shell_command: str | None, prompt: str, *, submit_prompt: bool = True) -> bytes:
    return command_bytes_for_agent_prompt(
        shell_command,
        prompt,
        submit_prompt=submit_prompt,
        bracketed_paste_for_submit_providers=MULTILINE_PROMPT_BRACKETED_PASTE_PROVIDERS,
        error_message="project todo dispatch requires an interactive agent terminal",
    )


def _submit_bytes_for_prompt(shell_command: str | None) -> bytes:
    return agent_prompt_submit_bytes(shell_command)


def _followup_submit_bytes_for_prompt(shell_command: str | None) -> bytes | None:
    if _agent_provider_for_prompt(shell_command) in PROJECT_TODO_FOLLOWUP_SUBMIT_PROVIDERS:
        return _submit_bytes_for_prompt(shell_command)
    return None


def _schedule_project_todo_followup_submits(
    broker: TerminalBroker,
    client_id: UUID,
    window_id: UUID,
    runtime_window: RuntimeWindow,
    data: bytes | None,
    *,
    first_submit_event: asyncio.Event | None = None,
) -> asyncio.Task[None] | None:
    if not data:
        return None
    task = asyncio.create_task(
        _send_project_todo_followup_submits(
            broker,
            client_id,
            window_id,
            runtime_window,
            data,
            interval_seconds=PROJECT_TODO_FOLLOWUP_SUBMIT_INTERVAL_SECONDS,
            duration_seconds=PROJECT_TODO_FOLLOWUP_SUBMIT_DURATION_SECONDS,
            first_submit_event=first_submit_event,
        )
    )
    task.add_done_callback(_log_project_todo_followup_submit_failure)
    return task


def _log_project_todo_followup_submit_failure(task: asyncio.Task[None]) -> None:
    if task.cancelled():
        return
    with contextlib.suppress(Exception):
        exc = task.exception()
        if exc is not None:
            logger.debug(
                "project todo follow-up submit failed",
                exc_info=(type(exc), exc, exc.__traceback__),
            )


async def _send_project_todo_followup_submits(
    broker: TerminalBroker,
    client_id: UUID,
    window_id: UUID,
    runtime_window: RuntimeWindow,
    data: bytes,
    *,
    interval_seconds: float,
    duration_seconds: float,
    first_submit_event: asyncio.Event | None = None,
) -> None:
    if interval_seconds <= 0 or duration_seconds <= 0:
        if first_submit_event is not None:
            first_submit_event.set()
        return
    attempts = max(1, int(duration_seconds / interval_seconds))
    for _ in range(attempts):
        await asyncio.sleep(interval_seconds)
        try:
            await broker.send_input_direct(client_id, window_id, runtime_window, data)
        finally:
            if first_submit_event is not None and not first_submit_event.is_set():
                first_submit_event.set()


def _agent_provider_for_prompt(shell_command: str | None) -> str | None:
    return agent_provider_for_prompt(shell_command)


def _looks_like_agent_command(shell_command: str) -> bool:
    return looks_like_agent_command(shell_command)


async def _wait_for_agent_terminal_ready(
    shell_command: str | None,
    collector: "_PromptOutputCollector",
    *,
    capture_output: Callable[[], Awaitable[bytes]] | None = None,
) -> None:
    if not shell_command or not _looks_like_agent_command(shell_command):
        return
    provider = _agent_provider_for_prompt(shell_command)
    try:
        await _wait_until_agent_ready(provider, collector, capture_output=capture_output)
    except TimeoutError as exc:
        raise TimeoutError("project todo dispatch waited for the agent-client prompt, but it was not ready") from exc
    await asyncio.sleep(PROJECT_TODO_AGENT_READY_SETTLE_SECONDS)


async def _wait_for_agent_working(
    *,
    client_id: UUID,
    window_id: UUID,
    session_factory: Callable[[], object],
    submitted_at: datetime | None = None,
    capture_output: Callable[[], Awaitable[bytes]] | None = None,
    submitted_snapshot: bytes | None = None,
    output_signal_ready: asyncio.Event | None = None,
) -> None:
    deadline = time.monotonic() + PROJECT_TODO_AGENT_WORKING_TIMEOUT_SECONDS
    while True:
        output_signals_ready = output_signal_ready is None or output_signal_ready.is_set()
        async with session_factory() as session:
            status = await load_work_status(session, client_id, window_id)
            if status.state in {"WORKING", "FINISHED"}:
                return
            if output_signals_ready and submitted_at is not None and await _terminal_output_after_submission(
                session,
                client_id=client_id,
                window_id=window_id,
                submitted_at=submitted_at,
            ):
                return
        if (
            output_signals_ready
            and
            submitted_snapshot is not None
            and capture_output is not None
            and await _terminal_output_changed_after_submission(capture_output, submitted_snapshot)
        ):
            return
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError(
                "project todo dispatch submitted the prompt, but the agent did not start working"
            )
        await asyncio.sleep(min(remaining, PROJECT_TODO_AGENT_WORKING_POLL_INTERVAL_SECONDS))


async def _terminal_output_after_submission(
    session: object,
    *,
    client_id: UUID,
    window_id: UUID,
    submitted_at: datetime,
) -> bool:
    window = await get_window_for_client(session, client_id, window_id)
    output_at = getattr(window, "terminal_last_output_at", None) if window is not None else None
    return output_at is not None and _aware_utc(output_at) >= _aware_utc(submitted_at)


def _aware_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


async def _terminal_output_changed_after_submission(
    capture_output: Callable[[], Awaitable[bytes]],
    submitted_snapshot: bytes,
) -> bool:
    try:
        output = await capture_output()
    except Exception:
        logger.debug("project todo post-submit capture failed", exc_info=True)
        return False
    return bool(output and output != submitted_snapshot)


def _log_dispatch_failure(task: asyncio.Task[None]) -> None:
    if task.cancelled():
        return
    with contextlib.suppress(Exception):
        exc = task.exception()
        if exc is not None:
            logger.warning("project todo prompt dispatch failed", exc_info=(type(exc), exc, exc.__traceback__))
