from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from contextlib import AbstractAsyncContextManager

from sqlalchemy.ext.asyncio import AsyncSession

from app.contexts.terminal_artifacts.application import schedule_terminal_artifact_generation
from app.contexts.terminal_artifacts.application.api_service import TerminalArtifactRuntimeDeps
from app.contexts.terminal_runtime.application.broker import TerminalBroker
from app.contexts.terminal_runtime.application.client_connections import ClientConnectionRegistry
from app.contexts.terminal_runtime.application.runtime_provider import TmuxManager
from app.contexts.workspace.application.project_todo_artifacts import (
    claim_pending_project_todo_artifact_generations,
    schedule_project_todo_requested_artifacts,
)
from app.platform.ui_events import UiEventHub

logger = logging.getLogger(__name__)

SessionFactory = Callable[[], AbstractAsyncContextManager[AsyncSession]]
ARTIFACT_DISPATCH_COMPENSATION_INTERVAL_SECONDS = 5.0
ARTIFACT_DISPATCH_COMPENSATION_BATCH_SIZE = 25


async def process_artifact_dispatch_compensation_once(
    session_factory: SessionFactory,
    *,
    tmux_manager: TmuxManager,
    terminal_broker: TerminalBroker,
    registry: ClientConnectionRegistry,
    ui_event_hub: UiEventHub,
    limit: int = ARTIFACT_DISPATCH_COMPENSATION_BATCH_SIZE,
) -> int:
    async with session_factory() as session:
        generations = await claim_pending_project_todo_artifact_generations(session, limit=limit)
        if not generations:
            await session.commit()
            return 0
        await session.commit()

    schedule_project_todo_requested_artifacts(
        generations,
        TerminalArtifactRuntimeDeps(
            session_factory=session_factory,
            tmux_manager=tmux_manager,
            terminal_broker=terminal_broker,
            registry=registry,
            ui_event_hub=ui_event_hub,
            schedule_generation=schedule_terminal_artifact_generation,
        ),
    )
    return len(generations)


async def run_artifact_dispatch_compensation_loop(
    session_factory: SessionFactory,
    *,
    tmux_manager: TmuxManager,
    terminal_broker: TerminalBroker,
    registry: ClientConnectionRegistry,
    ui_event_hub: UiEventHub,
    interval_seconds: float = ARTIFACT_DISPATCH_COMPENSATION_INTERVAL_SECONDS,
) -> None:
    while True:
        try:
            await process_artifact_dispatch_compensation_once(
                session_factory,
                tmux_manager=tmux_manager,
                terminal_broker=terminal_broker,
                registry=registry,
                ui_event_hub=ui_event_hub,
            )
        except Exception:
            logger.exception("failed to compensate terminal artifact dispatches")
        await asyncio.sleep(interval_seconds)
