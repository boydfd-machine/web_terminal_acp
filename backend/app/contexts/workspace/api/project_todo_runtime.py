from __future__ import annotations

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.contexts.terminal_artifacts.application import schedule_terminal_artifact_generation
from app.contexts.terminal_artifacts.application.api_service import TerminalArtifactRuntimeDeps
from app.contexts.terminal_runtime.application.broker import TerminalBroker
from app.contexts.terminal_runtime.application.connection_registry import client_connection_registry_from_state
from app.contexts.terminal_runtime.application.runtime_provider import TmuxManager
from app.db import SessionLocal
from app.platform.ui_events import ui_event_hub_from_state


def background_session_factory_for(session: AsyncSession):
    bind = getattr(session, "bind", None)
    if bind is None:
        return SessionLocal
    return async_sessionmaker(bind, expire_on_commit=False, class_=AsyncSession)


def terminal_broker_from_state(request: Request) -> TerminalBroker:
    broker = getattr(request.app.state, "terminal_broker", None)
    if broker is None:
        broker = TerminalBroker()
        request.app.state.terminal_broker = broker
    return broker


def artifact_runtime_deps(
    request: Request,
    tmux_manager: TmuxManager,
    session: AsyncSession,
) -> TerminalArtifactRuntimeDeps:
    return TerminalArtifactRuntimeDeps(
        session_factory=background_session_factory_for(session),
        tmux_manager=tmux_manager,
        terminal_broker=terminal_broker_from_state(request),
        registry=client_connection_registry_from_state(request.app.state),
        ui_event_hub=ui_event_hub_from_state(request.app.state),
        schedule_generation=schedule_terminal_artifact_generation,
    )
