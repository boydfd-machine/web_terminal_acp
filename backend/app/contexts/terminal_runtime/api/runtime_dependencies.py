# ruff: noqa: F401
from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import time
from uuid import UUID

from elasticsearch import AsyncElasticsearch
from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect, status

from app.auth import require_websocket_auth
from app.db import SessionLocal
from app.models import LOCAL_CLIENT_ID, VirtualWindow, WindowStatus
from app.contexts.clients.application.client_lookup import get_client
from app.contexts.windows.application.window_lookup import get_window_for_client
from app.contexts.windows.application.window_lookup import get_window_for_local_tmux_target
from app.contexts.windows.application.window_lookup import patch_runtime_window
from app.platform.ui_events import ui_event_hub_from_state
from app.contexts.terminal_runtime.api.local_recording_routes import (
    LocalTerminalOutputRecorder,
    LocalTerminalOutputRecorderDependencies,
    LocalTerminalOutputRecordJob,
)
from app.contexts.terminal_runtime.application.broker import (
    TerminalBroker,
    TerminalRuntimeUnavailable,
    terminal_status_message,
)
from app.contexts.terminal_runtime.application.client_connections import ClientConnectionRegistry
from app.contexts.terminal_runtime.application.local_runtime_factory import create_local_terminal_runtime
from app.contexts.terminal_runtime.application.runtime_provider import (
    RemoteClientUnavailable,
    RemoteRuntime,
    RemoteTerminalError,
)
from app.contexts.terminal_runtime.domain.types import RuntimeWindow
from app.contexts.terminal_runtime.application.terminal_bridge import OutputAckControl, ResizeControl, SelectWindowControl, parse_text_input
from app.contexts.terminal_runtime.application.runtime_binding import RuntimeWindowBinding
from app.contexts.terminal_runtime.application.stream_markers import TerminalStreamMarkerExtractor
from app.contexts.terminal_runtime.application.git_worktree_coordinator import (
    commands_need_git_worktree_tracking,
    git_worktree_agent_run_sequences,
    process_git_worktree_snapshot_refresh,
    process_terminal_commands_for_git,
    process_worktree_registration,
)
from app.contexts.terminal_runtime.application.output_recorder import (
    record_terminal_command_markers,
    record_terminal_output_chunk,
)
from app.contexts.terminal_runtime.application.selection import TerminalSelectionHub
from app.contexts.terminal_runtime.application.runtime_provider import TmuxCommandError, TmuxManager, get_tmux_manager
from app.contexts.workspace.application.project_todo_worktrees import (
    refresh_project_todo_worktree_summaries_for_window,
)

logger = logging.getLogger(__name__)
router = APIRouter(tags=["terminal"])
REMOTE_RECONNECT_RETRY_AFTER_MS = 5000
RUNTIME_START_RETRY_AFTER_MS = 500
REMOTE_ATTACH_REQUEST_TIMEOUT_SECONDS = 2.0
ATTACH_SNAPSHOT_GRACE_SECONDS = 0.5
LOCAL_OUTPUT_RECORD_BATCH_BYTES = 32 * 1024
LOCAL_OUTPUT_RECORD_BATCH_DELAY_SECONDS = 0.02

def mark_window_error(window: VirtualWindow) -> None:
    window.status = WindowStatus.error


def mark_window_active(window: VirtualWindow) -> None:
    window.status = WindowStatus.active


def mark_window_disconnected(window: VirtualWindow) -> None:
    window.status = WindowStatus.disconnected


def _ready_es_client(websocket: WebSocket) -> AsyncElasticsearch | None:
    if getattr(websocket.app.state, "es_indexes_ready", False) is not True:
        return None
    return getattr(websocket.app.state, "es_client", None)


def _client_connection_registry(websocket: WebSocket) -> ClientConnectionRegistry:
    registry = getattr(websocket.app.state, "client_connections", None)
    if registry is None:
        registry = ClientConnectionRegistry()
        websocket.app.state.client_connections = registry
    return registry


def _terminal_broker(websocket: WebSocket, tmux_manager: TmuxManager) -> TerminalBroker:
    broker = getattr(websocket.app.state, "terminal_broker", None)
    if broker is None:
        broker = TerminalBroker()
        websocket.app.state.terminal_broker = broker

    if broker.runtime_for(LOCAL_CLIENT_ID) is None:
        local_runtime = getattr(websocket.app.state, "local_terminal_runtime", None)
        if local_runtime is None:
            local_runtime = create_local_terminal_runtime(tmux_manager, session_factory=SessionLocal)
            websocket.app.state.local_terminal_runtime = local_runtime
        broker.register_runtime(LOCAL_CLIENT_ID, local_runtime)
    return broker


def _terminal_selection_hub(websocket: WebSocket) -> TerminalSelectionHub:
    hub = getattr(websocket.app.state, "terminal_selection_hub", None)
    if hub is None:
        hub = TerminalSelectionHub()
        websocket.app.state.terminal_selection_hub = hub
    return hub


def _ui_event_hub(websocket: WebSocket):
    return ui_event_hub_from_state(websocket.app.state)


def _runtime_window_binding_from_virtual_window(window: VirtualWindow) -> RuntimeWindowBinding | None:
    return RuntimeWindowBinding.from_virtual_window(window)


async def _send_text_if_connected(websocket: WebSocket, data: str) -> bool:
    try:
        await websocket.send_text(data)
    except (RuntimeError, WebSocketDisconnect):
        return False
    return True


async def _close_websocket_if_connected(websocket: WebSocket, *, code: int = 1000) -> None:
    with contextlib.suppress(Exception):
        await websocket.close(code=code)


async def _send_text_and_close(websocket: WebSocket, data: str, *, code: int = 1000) -> None:
    await _send_text_if_connected(websocket, data)
    await _close_websocket_if_connected(websocket, code=code)


async def _persist_runtime_window(
    client_id: UUID,
    window_id: UUID,
    binding: RuntimeWindowBinding,
) -> None:
    async with SessionLocal() as session:
        await patch_runtime_window(
            session,
            client_id,
            window_id,
            **binding.runtime_persistence_fields(),
        )
        with contextlib.suppress(Exception):
            await session.commit()


async def _mark_window_error(client_id: UUID, window_id: UUID) -> None:
    async with SessionLocal() as session:
        window = await get_window_for_client(session, client_id, window_id)
        if window is not None:
            mark_window_error(window)
            with contextlib.suppress(Exception):
                await session.commit()


async def _mark_window_active(client_id: UUID, window_id: UUID) -> None:
    async with SessionLocal() as session:
        window = await get_window_for_client(session, client_id, window_id)
        if window is not None and window.status is not WindowStatus.active:
            mark_window_active(window)
            with contextlib.suppress(Exception):
                await session.commit()


async def _mark_window_disconnected(client_id: UUID, window_id: UUID) -> None:
    async with SessionLocal() as session:
        window = await get_window_for_client(session, client_id, window_id)
        if window is not None and window.status is not WindowStatus.disconnected:
            mark_window_disconnected(window)
            with contextlib.suppress(Exception):
                await session.commit()


async def _local_runtime_window_to_virtual_window_id(
    client_id: UUID,
    runtime_window: RuntimeWindow,
) -> UUID | None:
    async with SessionLocal() as session:
        window = await get_window_for_local_tmux_target(
            session,
            client_id,
            tmux_session=runtime_window.session_id,
            tmux_window_id=runtime_window.window_id,
        )
        return window.id if window is not None else None
