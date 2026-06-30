# ruff: noqa: F401

import asyncio
import contextlib
import json
from collections import deque
from dataclasses import dataclass
from datetime import UTC, datetime
import logging
import time
from typing import Any, Protocol
from uuid import UUID

from elasticsearch import AsyncElasticsearch
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, status
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db import SessionLocal
from app.client_agent.ai_events import ManagedAiEvent, managed_event_from_payload
from app.contexts.activity.application.agent_event_ingest import (
    index_managed_agent_event_if_ready,
    persist_managed_agent_event,
)
from app.contexts.activity.application.agent_work_presence import (
    touch_agent_work_presence_if_window_exists,
)
from app.contexts.clients.application.authentication import authenticate_client_token
from app.contexts.clients.application.client_lookup import get_client
from app.contexts.terminal_runtime.application.broker import TerminalBroker, terminal_status_message
from app.contexts.terminal_runtime.application.client_connections import (
    ClientConnection,
    ClientConnectionClosed,
    ClientConnectionRegistry,
)
from app.contexts.terminal_runtime.application.offline_monitor import (
    mark_remote_client_disconnected,
    reconcile_inventory,
)
from app.contexts.terminal_runtime.application.output_recorder import (
    record_terminal_command_markers,
    record_terminal_output_chunk,
)
from app.contexts.terminal_runtime.application.selection import TerminalSelectionHub
from app.contexts.terminal_runtime.application.stream_markers import TerminalStreamMarkerExtractor
from app.contexts.terminal_runtime.application.command_marker import ParsedCommandMarker
from app.contexts.terminal_runtime.application.worktree_marker import ParsedWorktreeMarker
from app.contexts.terminal_runtime.domain.protocol import (
    AgentMessage,
    TerminalPayload,
    decode_agent_message,
    encode_agent_message,
)
from app.models import Client, ClientStatus, VirtualWindow
from app.contexts.windows.application.window_lookup import get_window_for_client
from app.platform.ui_events import ui_event_hub_from_state
from app.contexts.terminal_runtime.application.git_worktree_agent_markers import extract_worktree_markers_from_agent_payload
from app.contexts.terminal_runtime.application.git_worktree_coordinator import (
    commands_need_git_worktree_tracking,
    git_worktree_agent_run_sequences,
    process_git_worktree_snapshot_refresh,
    process_terminal_commands_for_git,
    process_worktree_registration,
)
from app.contexts.workspace.application.project_todo_worktrees import (
    refresh_project_todo_worktree_summaries_for_window,
)
from app.contexts.workspace.application.project_todo_artifacts import (
    pop_project_todo_artifact_generations,
)
from app.contexts.workspace.application.summary_scheduler import (
    schedule_project_todo_artifact_generations,
)

router = APIRouter(tags=["client-agent"])
logger = logging.getLogger(__name__)
BACKGROUND_MESSAGE_QUEUE_MAX_SIZE = 5000
BACKGROUND_MESSAGE_QUEUE_WARN_SECONDS = 1.0
TERMINAL_OUTPUT_QUEUE_MAX_SIZE = BACKGROUND_MESSAGE_QUEUE_MAX_SIZE
LOW_PRIORITY_BACKGROUND_QUEUE_MAX_SIZE = 0
LOW_PRIORITY_BACKGROUND_QUEUE_WARN_SIZE = 10000
TERMINAL_OUTPUT_RECORD_BATCH_BYTES = 32 * 1024
TERMINAL_OUTPUT_RECORD_BATCH_DELAY_SECONDS = 0.02
BACKGROUND_QUEUE_DRAIN_TIMEOUT_SECONDS = 5.0


@dataclass(frozen=True)
class _TerminalOutputRecordingJob:
    client_id: UUID
    window_id: UUID
    clean_data: bytes
    commands: tuple[ParsedCommandMarker, ...]
    worktree_markers: tuple[ParsedWorktreeMarker, ...]


def _can_batch_terminal_output_recording(job: _TerminalOutputRecordingJob) -> bool:
    return bool(job.clean_data) and not job.commands and not job.worktree_markers


@dataclass(frozen=True)
class _GitWorktreeTrackingJob:
    client_id: UUID
    window_id: UUID
    commands: tuple[ParsedCommandMarker, ...] = ()
    worktree_markers: tuple[ParsedWorktreeMarker, ...] = ()


class _BackgroundMessageQueue(Protocol):
    def qsize(self) -> int: ...
    async def put(self, message: AgentMessage) -> None: ...
    async def get(self) -> AgentMessage: ...
    def task_done(self) -> None: ...
    async def join(self) -> None: ...


class _WindowFairMessageQueue:
    def __init__(self, maxsize: int = 0) -> None:
        self._maxsize = maxsize
        self._queued_count = 0
        self._unfinished_count = 0
        self._window_queues: dict[UUID, deque[AgentMessage]] = {}
        self._windows: deque[UUID] = deque()
        self._priority_windows: deque[UUID] = deque()
        self._condition = asyncio.Condition()
        self._join_event = asyncio.Event()
        self._join_event.set()

    def qsize(self) -> int:
        return self._queued_count

    async def put(self, message: AgentMessage) -> None:
        if message.window_id is None:
            raise ValueError("window fair queue messages require window_id")
        async with self._condition:
            while self._maxsize > 0 and self._queued_count >= self._maxsize:
                await self._condition.wait()
            queue = self._window_queues.get(message.window_id)
            if queue is None:
                queue = deque()
                self._window_queues[message.window_id] = queue
                self._windows.append(message.window_id)
            queue.append(message)
            if message.payload.get("input_priority") is True:
                self._priority_windows.append(message.window_id)
            self._queued_count += 1
            self._unfinished_count += 1
            self._join_event.clear()
            self._condition.notify_all()

    async def get(self) -> AgentMessage:
        async with self._condition:
            while True:
                while self._priority_windows:
                    window_id = self._priority_windows.popleft()
                    message = self._get_for_window(
                        window_id,
                        priority_only=True,
                        requeue=False,
                    )
                    if message is not None:
                        return message
                while self._windows:
                    window_id = self._windows.popleft()
                    message = self._get_for_window(window_id)
                    if message is not None:
                        return message
                await self._condition.wait()

    def _get_for_window(
        self,
        window_id: UUID,
        *,
        priority_only: bool = False,
        requeue: bool = True,
    ) -> AgentMessage | None:
        queue = self._window_queues.get(window_id)
        if not queue:
            self._window_queues.pop(window_id, None)
            return None
        if priority_only:
            message = _pop_first_input_priority_background_message(queue)
            if message is None:
                return None
        else:
            message = queue.popleft()
        self._queued_count -= 1
        if queue and requeue:
            self._windows.append(window_id)
        elif not queue:
            self._window_queues.pop(window_id, None)
        self._condition.notify_all()
        return message

    def task_done(self) -> None:
        self._unfinished_count -= 1
        if self._unfinished_count < 0:
            self._unfinished_count = 0
            raise ValueError("task_done() called too many times")
        if self._unfinished_count == 0:
            self._join_event.set()

    async def join(self) -> None:
        await self._join_event.wait()


def _pop_first_input_priority_background_message(
    queue: deque[AgentMessage],
) -> AgentMessage | None:
    for index, message in enumerate(queue):
        if message.payload.get("input_priority") is True:
            del queue[index]
            return message
    return None


def _bearer_token(authorization: str | None) -> str | None:
    if authorization is None:
        return None
    scheme, separator, token = authorization.partition(" ")
    if separator != " " or scheme.lower() != "bearer" or not token:
        return None
    return token


def _connection_registry(websocket: WebSocket) -> ClientConnectionRegistry:
    registry = getattr(websocket.app.state, "client_connections", None)
    if registry is None:
        registry = ClientConnectionRegistry()
        websocket.app.state.client_connections = registry
    return registry


def _terminal_broker(websocket: WebSocket) -> TerminalBroker:
    broker = getattr(websocket.app.state, "terminal_broker", None)
    if broker is None:
        broker = TerminalBroker()
        websocket.app.state.terminal_broker = broker
    return broker


def _terminal_selection_hub(websocket: WebSocket) -> TerminalSelectionHub:
    hub = getattr(websocket.app.state, "terminal_selection_hub", None)
    if hub is None:
        hub = TerminalSelectionHub()
        websocket.app.state.terminal_selection_hub = hub
    return hub


def _ui_event_hub(websocket: WebSocket):
    return ui_event_hub_from_state(websocket.app.state)


def _schedule_queued_project_todo_artifact_generations(websocket: WebSocket, session: AsyncSession) -> None:
    generations = pop_project_todo_artifact_generations(session)
    if not generations:
        return
    from app.contexts.terminal_artifacts.application import schedule_terminal_artifact_generation
    from app.contexts.terminal_artifacts.application.api_service import TerminalArtifactRuntimeDeps
    from app.contexts.terminal_runtime.application.runtime_provider import get_tmux_manager

    schedule_project_todo_artifact_generations(
        generations,
        TerminalArtifactRuntimeDeps(
            session_factory=SessionLocal,
            tmux_manager=get_tmux_manager(),
            terminal_broker=_terminal_broker(websocket),
            registry=_connection_registry(websocket),
            ui_event_hub=_ui_event_hub(websocket),
            schedule_generation=schedule_terminal_artifact_generation,
        ),
    )


async def _authenticate_websocket_client(
    websocket: WebSocket,
    session: AsyncSession,
) -> Client | None:
    client_id_header = websocket.headers.get("x-client-id")
    token = _bearer_token(websocket.headers.get("authorization"))
    if client_id_header is None or token is None:
        return None

    try:
        client_id = UUID(client_id_header)
    except ValueError:
        return None

    return await authenticate_client_token(session, client_id, token)


def _mark_client_seen(client: Client) -> datetime:
    now = datetime.now(UTC)
    client.status = ClientStatus.ONLINE
    client.last_seen_at = now
    if client.connected_at is None:
        client.connected_at = now
    return now


def _client_metadata_text(payload: dict[str, Any], key: str, max_length: int) -> str | None:
    value = payload.get(key)
    if not isinstance(value, str):
        return None
    value = value.strip()
    if not value:
        return None
    return value[:max_length]


def _apply_client_reported_metadata(client: Client, payload: dict[str, Any]) -> None:
    hostname = _client_metadata_text(payload, "hostname", 255)
    version = _client_metadata_text(payload, "version", 64)
    if hostname is not None:
        client.hostname = hostname
    if version is not None:
        client.version = version


async def _authenticate_and_mark_seen(websocket: WebSocket) -> UUID | None:
    async with SessionLocal() as session:
        client = await _authenticate_websocket_client(websocket, session)
        if client is None:
            return None
        client_id = client.id
        _mark_client_seen(client)
        await session.commit()
        await _ui_event_hub(websocket).publish_debounced_invalidation(
            ("clients", client_id),
            ["clients"],
            client_id=client_id,
            reason="client_seen",
            delay_seconds=1.0,
        )
        return client_id


async def _mark_client_seen_with_metadata(client_id: UUID, payload: dict[str, Any]) -> bool:
    async with SessionLocal() as session:
        client = await get_client(session, client_id)
        if client is None:
            return False
        _mark_client_seen(client)
        _apply_client_reported_metadata(client, payload)
        await session.commit()
        return True


async def _mark_client_disconnected_by_id(client_id: UUID) -> bool:
    async with SessionLocal() as session:
        changed = await mark_remote_client_disconnected(session, client_id)
        await session.commit()
        return changed


async def _best_effort_mark_client_seen_with_metadata(
    client_id: UUID,
    payload: dict[str, Any],
    *,
    message_type: str,
) -> bool | None:
    try:
        return await _mark_client_seen_with_metadata(client_id, payload)
    except Exception:
        logger.warning(
            "client-agent seen update failed; keeping control websocket open",
            extra={"client_id": str(client_id), "message_type": message_type},
            exc_info=True,
        )
        return None


async def _best_effort_handle_inventory_message(
    websocket: WebSocket,
    client_id: UUID,
    message: AgentMessage,
) -> bool | None:
    try:
        return await _handle_inventory_message(websocket, client_id, message)
    except Exception:
        logger.warning(
            "client-agent inventory update failed; keeping control websocket open",
            extra={"client_id": str(client_id)},
            exc_info=True,
        )
        return None


async def _best_effort_mark_client_disconnected_by_id(client_id: UUID) -> bool:
    try:
        return await _mark_client_disconnected_by_id(client_id)
    except Exception:
        logger.warning(
            "client-agent offline update failed during websocket cleanup",
            extra={"client_id": str(client_id)},
            exc_info=True,
        )
        return False


async def _handle_inventory_message(websocket: WebSocket, client_id: UUID, message: AgentMessage) -> bool:
    inventory = message.payload.get("tmux_windows", message.payload.get("windows", []))
    if not isinstance(inventory, list):
        inventory = []

    async with SessionLocal() as session:
        client = await get_client(session, client_id)
        if client is None:
            return False
        _mark_client_seen(client)
        changed_count = await reconcile_inventory(session, client_id, inventory)
        await session.commit()
        await _ui_event_hub(websocket).publish_invalidation(
            ["clients"],
            client_id=client_id,
            reason="client_inventory_seen",
        )
        if changed_count:
            await _ui_event_hub(websocket).publish_invalidation(
                ["tree", "window"],
                client_id=client_id,
                reason="client_inventory",
            )
        return True


def _ready_es_client(websocket: WebSocket) -> AsyncElasticsearch | None:
    if getattr(websocket.app.state, "es_indexes_ready", False) is not True:
        return None
    return getattr(websocket.app.state, "es_client", None)


async def _commit_session(session) -> None:
    await session.commit()


async def _send_ai_event_ack_message(
    send_message,
    client_id: UUID,
    message: AgentMessage,
    *,
    ok: bool,
    error: str | None = None,
) -> None:
    if message.request_id is None:
        return
    payload: dict[str, Any] = {"ok": ok}
    if error is not None:
        payload["error"] = error
    await send_message(
        AgentMessage(
            type="ai_event_ack",
            client_id=client_id,
            window_id=message.window_id,
            request_id=message.request_id,
            payload=payload,
        )
    )


async def _send_ai_event_ack(
    connection: ClientConnection,
    client_id: UUID,
    message: AgentMessage,
    *,
    ok: bool,
    error: str | None = None,
) -> None:
    try:
        await _send_ai_event_ack_message(
            connection.send,
            client_id,
            message,
            ok=ok,
            error=error,
        )
    except (ClientConnectionClosed, RuntimeError):
        logger.debug(
            "skipped ai_event ack because client-agent connection is closed",
            extra={
                "client_id": str(client_id),
                "window_id": str(message.window_id) if message.window_id else None,
                "request_id": message.request_id,
            },
        )


__all__ = [name for name in globals() if not name.startswith("__")]
