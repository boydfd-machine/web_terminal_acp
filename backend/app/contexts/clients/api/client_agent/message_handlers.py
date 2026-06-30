# ruff: noqa: F401,F403,F405
from app.contexts.clients.api.client_agent.connection import *
from app.contexts.activity.application.agent_activity_projection import (
    event_is_agent_completion,
)
from app.contexts.activity.application.agent_event_messages import (
    managed_event_from_message,
)
from app.contexts.activity.application.agent_event_queue import (
    AgentEventQueueUnavailable,
    create_redis_client,
    enqueue_managed_agent_event,
    queue_config_from_settings,
)


def _managed_event_from_message(client_id: UUID, message: AgentMessage) -> ManagedAiEvent:
    return managed_event_from_message(client_id, message)



async def _handle_ai_event_message_with_ack_sender(
    websocket: WebSocket,
    send_ack_message,
    client_id: UUID,
    message: AgentMessage,
    redis_client=None,
) -> bool:
    try:
        if message.window_id is None:
            raise ValueError("window_id is required")
        event = _managed_event_from_message(client_id, message)
        queue_config = queue_config_from_settings()
        if queue_config is not None:
            try:
                await enqueue_managed_agent_event(event, redis_client=redis_client, config=queue_config)
                if _managed_event_requires_inline_persist(event):
                    await _persist_ai_event_inline(websocket, client_id, message, event)
                await _send_ai_event_ack_message(send_ack_message, client_id, message, ok=True)
                return True
            except AgentEventQueueUnavailable:
                logger.warning(
                    "agent event queue unavailable; persisting ai_event inline",
                    extra={
                        "client_id": str(client_id),
                        "window_id": str(message.window_id),
                        "request_id": message.request_id,
                    },
                    exc_info=True,
                )
        await _persist_ai_event_inline(websocket, client_id, message, event)
        await _send_ai_event_ack_message(send_ack_message, client_id, message, ok=True)
        return True
    except ValueError as exc:
        await _send_ai_event_ack_message(send_ack_message, client_id, message, ok=False, error=str(exc))
        return False


def _managed_event_requires_inline_persist(event: ManagedAiEvent) -> bool:
    provider = event.provider.strip()
    if provider in {"claude", "claude_code"}:
        return not _claude_sidechain_payload(event.payload)
    return True


def _claude_sidechain_payload(payload: dict) -> bool:
    if payload.get("isSidechain") is not True:
        return False
    if _payload_text(payload.get("agentId"), payload.get("subagent_id"), payload.get("subagentId")):
        return True
    metadata = payload.get("subagent")
    return isinstance(metadata, dict) and bool(
        _payload_text(metadata.get("agentId"), metadata.get("agent_id"))
    )


def _payload_text(*values: object) -> str | None:
    for value in values:
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


async def _persist_ai_event_inline(
    websocket: WebSocket,
    client_id: UUID,
    message: AgentMessage,
    event: ManagedAiEvent,
) -> None:
    if message.window_id is None:
        raise ValueError("window_id is required")
    async with SessionLocal() as session:
        row = await persist_managed_agent_event(
            session,
            event,
            registry=_connection_registry(websocket),
        )
        await _commit_session(session)
        _schedule_queued_project_todo_artifact_generations(websocket, session)
        if await index_managed_agent_event_if_ready(session, _ready_es_client(websocket), row):
            await _commit_session(session)
    resources = ["agent_record", "window", "search"]
    if event_is_agent_completion(row):
        resources.append("project_todos")
    await _ui_event_hub(websocket).publish_invalidation(
        resources,
        client_id=client_id,
        window_id=message.window_id,
        reason="ai_event",
    )


async def _handle_ai_event_message(
    websocket: WebSocket,
    connection: ClientConnection,
    client_id: UUID,
    message: AgentMessage,
) -> None:
    try:
        await _handle_ai_event_message_with_ack_sender(
            websocket,
            connection.send,
            client_id,
            message,
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


def _git_worktree_tracking_job_from_ai_event_message(
    client_id: UUID,
    message: AgentMessage,
) -> _GitWorktreeTrackingJob | None:
    if message.window_id is None:
        return None
    markers = extract_worktree_markers_from_agent_payload(message.payload)
    if not markers and not _agent_payload_can_change_worktree(message.payload):
        return None
    return _GitWorktreeTrackingJob(
        client_id=client_id,
        window_id=message.window_id,
        worktree_markers=markers,
    )


def _agent_payload_can_change_worktree(payload: Any) -> bool:
    stack: list[tuple[Any, int]] = [(payload, 0)]
    visited = 0
    while stack and visited < 128:
        value, depth = stack.pop()
        visited += 1
        if isinstance(value, dict):
            payload_type = value.get("type")
            if payload_type == "function_call_output":
                return True
            if depth < 6:
                stack.extend((item, depth + 1) for item in value.values())
        elif isinstance(value, list | tuple) and depth < 6:
            stack.extend((item, depth + 1) for item in value)
    return False


async def _handle_agent_work_presence_message(
    websocket: WebSocket,
    client_id: UUID,
    message: AgentMessage,
) -> None:
    if message.window_id is None:
        raise ValueError("window_id is required")
    providers = message.payload.get("providers")
    reasons = message.payload.get("reasons")
    if not isinstance(providers, list) or not isinstance(reasons, list):
        raise ValueError("providers and reasons must be lists")
    provider_values = [str(value) for value in providers]
    reason_values = [str(value) for value in reasons]

    async with SessionLocal() as session:
        event = await touch_agent_work_presence_if_window_exists(
            session,
            client_id=client_id,
            window_id=message.window_id,
            providers=provider_values,
            reasons=reason_values,
        )
        if event is None:
            logger.debug(
                "ignoring agent work presence for missing window",
                extra={
                    "client_id": str(client_id),
                    "window_id": str(message.window_id),
                },
            )
            return
        await _commit_session(session)
    await _ui_event_hub(websocket).publish_invalidation(
        ["window"],
        client_id=client_id,
        window_id=message.window_id,
        reason="agent_work_presence",
    )


def _extract_terminal_output_bytes(
    message: AgentMessage,
    marker_extractors: dict[UUID, TerminalStreamMarkerExtractor] | None,
) -> tuple[bytes, tuple[ParsedCommandMarker, ...], tuple[ParsedWorktreeMarker, ...]] | None:
    if message.window_id is None:
        return None

    payload = TerminalPayload.model_validate(message.payload)
    if payload.window_id != message.window_id:
        return None

    data = payload.to_bytes()
    if marker_extractors is None:
        from app.contexts.terminal_runtime.application.command_marker import extract_command_markers
        from app.contexts.terminal_runtime.application.worktree_marker import extract_worktree_markers

        clean_data, commands = extract_command_markers(data)
        clean_data, worktrees = extract_worktree_markers(clean_data)
    else:
        clean_data, commands, worktrees = marker_extractors.setdefault(
            _marker_extractor_key(message),
            TerminalStreamMarkerExtractor(),
        ).feed(data)
    return clean_data, tuple(commands), tuple(worktrees)


def _marker_extractor_key(message: AgentMessage) -> UUID:
    if message.window_id is None:
        raise ValueError("window_id is required")
    return _message_view_id(message) or message.window_id


def _message_view_id(message: AgentMessage) -> UUID | None:
    value = message.payload.get("view_id")
    if value is None:
        return None
    try:
        return UUID(str(value))
    except ValueError:
        return None


async def _window_belongs_to_client(client_id: UUID, window_id: UUID) -> bool:
    async with SessionLocal() as session:
        result = await session.execute(
            select(VirtualWindow.id).where(
                VirtualWindow.id == window_id,
                VirtualWindow.client_id == client_id,
            ).limit(1)
        )
        return result.scalar_one_or_none() is not None


async def _display_terminal_output_message(
    websocket: WebSocket,
    client_id: UUID,
    message: AgentMessage,
    marker_extractors: dict[UUID, TerminalStreamMarkerExtractor] | None = None,
    *,
    known_windows: set[UUID] | None = None,
) -> _TerminalOutputRecordingJob | None:
    if message.window_id is None:
        return None
    if known_windows is not None:
        if message.window_id not in known_windows:
            if not await _window_belongs_to_client(client_id, message.window_id):
                return None
            known_windows.add(message.window_id)
    elif not await _window_belongs_to_client(client_id, message.window_id):
        return None

    extracted = _extract_terminal_output_bytes(message, marker_extractors)
    if extracted is None:
        return None

    clean_data, commands, worktree_markers = extracted
    job = None
    if message.payload.get("is_snapshot") is not True and (
        clean_data or commands or worktree_markers
    ):
        job = _TerminalOutputRecordingJob(
            client_id=client_id,
            window_id=message.window_id,
            clean_data=clean_data,
            commands=commands,
            worktree_markers=worktree_markers,
        )
    if clean_data:
        try:
            await _terminal_broker(websocket).publish_output(
                client_id,
                _message_view_id(message) or message.window_id,
                clean_data,
            )
        except Exception:
            logger.exception("terminal output publish failed")
    return job


async def _record_terminal_output_job(
    websocket: WebSocket,
    job: _TerminalOutputRecordingJob,
) -> _GitWorktreeTrackingJob | None:
    async with SessionLocal() as session:
        window = await get_window_for_client(session, job.client_id, job.window_id)
        if window is None:
            return None
        command_events = await record_terminal_command_markers(
            session,
            job.client_id,
            job.window_id,
            list(job.commands),
        )
        if command_events:
            with contextlib.suppress(Exception):
                await _ui_event_hub(websocket).publish_invalidation(
                    ["agent_record", "command_history", "window", "search"],
                    client_id=job.client_id,
                    window_id=job.window_id,
                    reason="terminal_command",
                )
        output_recorded = False
        if job.clean_data:
            output_recorded = await record_terminal_output_chunk(
                session,
                job.client_id,
                job.window_id,
                job.clean_data,
                _ready_es_client(websocket),
            )
        if output_recorded:
            with contextlib.suppress(Exception):
                await _ui_event_hub(websocket).publish_debounced_invalidation(
                    ("terminal_output", job.client_id, job.window_id),
                    ["window", "search"],
                    client_id=job.client_id,
                    window_id=job.window_id,
                    reason="terminal_output",
                    delay_seconds=1.0,
                )
    if job.worktree_markers or commands_need_git_worktree_tracking(list(job.commands)):
        return _GitWorktreeTrackingJob(
            client_id=job.client_id,
            window_id=job.window_id,
            commands=job.commands,
            worktree_markers=job.worktree_markers,
        )
    return None


async def _handle_terminal_output_message(
    websocket: WebSocket,
    client_id: UUID,
    message: AgentMessage,
    marker_extractors: dict[UUID, TerminalStreamMarkerExtractor] | None = None,
    *,
    known_windows: set[UUID] | None = None,
) -> _TerminalOutputRecordingJob | None:
    return await _display_terminal_output_message(
        websocket,
        client_id,
        message,
        marker_extractors,
        known_windows=known_windows,
    )


async def _handle_aux_terminal_output_message(
    websocket: WebSocket,
    client_id: UUID,
    message: AgentMessage,
) -> None:
    if message.window_id is None:
        return
    if not await _window_belongs_to_client(client_id, message.window_id):
        return
    payload = TerminalPayload.model_validate(message.payload)
    view_id = _message_view_id(message)
    if view_id is None:
        return
    await _terminal_broker(websocket).publish_output(
        client_id,
        view_id,
        payload.to_bytes(),
    )


async def _handle_terminal_selection_message(
    websocket: WebSocket,
    client_id: UUID,
    message: AgentMessage,
) -> None:
    if message.window_id is None:
        return
    view_id = _message_view_id(message)

    async with SessionLocal() as session:
        window = await get_window_for_client(session, client_id, message.window_id)
        if window is None:
            return

    selection_message = {
        "type": "terminal_selection",
        "client_id": str(client_id),
        "window_id": str(message.window_id),
    }
    if view_id is not None:
        selection_message["view_id"] = str(view_id)
        await _terminal_broker(websocket).publish_status(
            client_id,
            view_id,
            json.dumps(selection_message, separators=(",", ":")),
        )
        return

    await _terminal_selection_hub(websocket).publish(client_id, message.window_id)


async def _handle_terminal_error_message(
    websocket: WebSocket,
    client_id: UUID,
    message: AgentMessage,
) -> None:
    if message.window_id is None:
        return
    await _terminal_broker(websocket).publish_status(
        client_id,
        _message_view_id(message) or message.window_id,
        terminal_status_message("error", reason="runtime_error"),
    )


async def _enqueue_terminal_output_recording_job(
    queue: asyncio.Queue[_TerminalOutputRecordingJob],
    *,
    client_id: UUID,
    job: _TerminalOutputRecordingJob,
) -> None:
    started_at = time.perf_counter()
    await queue.put(job)
    elapsed = time.perf_counter() - started_at
    if elapsed >= BACKGROUND_MESSAGE_QUEUE_WARN_SECONDS:
        logger.warning(
            "client-agent terminal output recording queue applied backpressure",
            extra={
                "client_id": str(client_id),
                "window_id": str(job.window_id),
                "queue_size": queue.qsize(),
                "elapsed_seconds": round(elapsed, 3),
            },
        )
    queue_size = queue.qsize()
    if (
        LOW_PRIORITY_BACKGROUND_QUEUE_WARN_SIZE > 0
        and queue_size >= LOW_PRIORITY_BACKGROUND_QUEUE_WARN_SIZE
        and queue_size % LOW_PRIORITY_BACKGROUND_QUEUE_WARN_SIZE == 0
    ):
        logger.warning(
            "client-agent terminal output recording queue backlog is high",
            extra={
                "client_id": str(client_id),
                "window_id": str(job.window_id),
                "queue_size": queue_size,
            },
        )


__all__ = [name for name in globals() if not name.startswith("__")]
