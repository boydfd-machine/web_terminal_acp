from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.contexts.terminal_artifacts.application.generation_service import (
    TerminalBroker,
    TmuxManager,
    ClientConnectionRegistry,
    _create_ephemeral_window as _artifact_create_ephemeral_window,
    _resolve_source_agent_command as _artifact_resolve_source_agent_command,
    _runtime_window_for_ephemeral as _artifact_runtime_window_for_ephemeral,
    _run_artifact_prompt as _artifact_run_prompt,
    _cleanup_ephemeral_window as _artifact_cleanup_ephemeral_window,
    _artifact_terminal_retention_seconds,
    _wait_before_ephemeral_window_cleanup,
)
from app.contexts.terminal_runtime.application.runtime_provider import RemoteRuntime
from app.models import Client, VirtualWindow
from app.contexts.terminal_runtime.domain.types import RuntimeWindow

logger = logging.getLogger(__name__)


@dataclass
class AgentTaskSpec:
    """Spec for running a one-shot agent task in an ephemeral terminal."""

    prompt: str
    source_window_id: UUID
    is_complete: Callable[[str], bool]
    timeout_seconds: float
    title: str
    output_path: str | None = None
    derived_context_extras: dict = field(default_factory=dict)
    source_agent_command: str | None = None


@dataclass
class AgentTaskResult:
    output: str
    ephemeral_window_id: UUID
    started_at: datetime
    finished_at: datetime


async def run_agent_task(
    session: AsyncSession,
    spec: AgentTaskSpec,
    *,
    client_id: UUID,
    session_factory: Callable[[], object],
    terminal_broker: TerminalBroker | None,
    tmux_manager: TmuxManager,
    registry: ClientConnectionRegistry | None,
    before_send: Callable[[TerminalBroker], Awaitable[None]] | None = None,
    cleanup_ephemeral: bool = True,
    ephemeral_retention_seconds: float | None = None,
) -> AgentTaskResult:
    """Spawn an ephemeral window, send a prompt to its agent, wait for the
    is_complete predicate to match, then return the collected output.

    Reuses the artifact terminal execution pipeline; output is read from a
    /tmp file (when output_path is provided) or scraped from the terminal.
    """
    client = await session.get(Client, client_id)
    if client is None:
        raise ValueError("client not found")
    source_window = await _get_window_for_client(session, client_id, spec.source_window_id)
    if source_window is None:
        raise ValueError("source window not found")

    started_at = datetime.now()
    ephemeral_window_id: UUID | None = None
    ephemeral_runtime_window: RuntimeWindow | None = None
    cleanup_cancelled = False
    try:
        resolved_command = spec.source_agent_command or await _artifact_resolve_source_agent_command(
            session, source_window
        )
        ephemeral_window = await _artifact_create_ephemeral_window(
            session,
            client,
            source_window,
            None,
            source_agent_command=resolved_command,
            tmux_manager=tmux_manager,
            registry=registry,
            window_title=spec.title,
            derived_context_extras=spec.derived_context_extras,
        )
        ephemeral_window_id = ephemeral_window.id
        ephemeral_runtime_window = _artifact_runtime_window_for_ephemeral(ephemeral_window)
        await session.commit()

        runtime_window = ephemeral_runtime_window
        output = await _artifact_run_prompt(
            client,
            source_window,
            ephemeral_window,
            runtime_window,
            spec.prompt,
            output_path=spec.output_path,
            source_agent_command=resolved_command,
            is_complete=spec.is_complete,
            session_factory=session_factory,
            terminal_broker=terminal_broker,
            tmux_manager=tmux_manager,
            registry=registry,
            timeout_seconds=spec.timeout_seconds,
            before_send=before_send,
        )
        return AgentTaskResult(
            output=output,
            ephemeral_window_id=ephemeral_window_id,
            started_at=started_at,
            finished_at=datetime.now(),
        )
    except BaseException:
        cleanup_ephemeral = True
        raise
    finally:
        if ephemeral_window_id is not None and cleanup_ephemeral:
            try:
                if ephemeral_retention_seconds is None or ephemeral_retention_seconds > 0:
                    await _wait_before_ephemeral_window_cleanup(ephemeral_retention_seconds)
            except BaseException:
                cleanup_cancelled = True
            try:
                await _artifact_cleanup_ephemeral_window(
                    client_id,
                    ephemeral_window_id,
                    session_factory=session_factory,
                    tmux_manager=tmux_manager,
                    registry=registry,
                    runtime_window=ephemeral_runtime_window,
                )
            except Exception:
                logger.debug("agent task ephemeral cleanup failed", exc_info=True)
            if cleanup_cancelled:
                pass


async def _get_window_for_client(
    session: AsyncSession, client_id: UUID, window_id: UUID
) -> VirtualWindow | None:
    from app.contexts.windows.application.window_lookup import get_window_for_client

    return await get_window_for_client(session, client_id, window_id)
