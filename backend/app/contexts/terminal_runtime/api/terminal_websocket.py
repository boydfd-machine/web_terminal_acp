from __future__ import annotations

import json
import time
from uuid import UUID

from fastapi import Depends, WebSocket, WebSocketDisconnect, status

from app.auth import require_websocket_auth, require_websocket_client_access, websocket_auth_subprotocol
from app.contexts.terminal_runtime.api.runtime_dependencies import (
    ATTACH_SNAPSHOT_GRACE_SECONDS,
    LOCAL_OUTPUT_RECORD_BATCH_BYTES,
    LOCAL_OUTPUT_RECORD_BATCH_DELAY_SECONDS,
    REMOTE_ATTACH_REQUEST_TIMEOUT_SECONDS,
    REMOTE_RECONNECT_RETRY_AFTER_MS,
    RUNTIME_START_RETRY_AFTER_MS,
    LocalTerminalOutputRecordJob,
    LocalTerminalOutputRecorder,
    LocalTerminalOutputRecorderDependencies,
    RemoteClientUnavailable,
    RemoteRuntime,
    RemoteTerminalError,
    RuntimeWindow,
    SessionLocal,
    TerminalRuntimeUnavailable,
    TerminalStreamMarkerExtractor,
    TmuxCommandError,
    TmuxManager,
    WindowStatus,
    _client_connection_registry,
    _close_websocket_if_connected,
    _local_runtime_window_to_virtual_window_id,
    _mark_window_active,
    _mark_window_disconnected,
    _mark_window_error,
    _persist_runtime_window,
    _ready_es_client,
    _runtime_window_binding_from_virtual_window,
    _send_text_and_close,
    _send_text_if_connected,
    _terminal_broker,
    _ui_event_hub,
    commands_need_git_worktree_tracking,
    get_tmux_manager,
    get_window_for_client,
    git_worktree_agent_run_sequences,
    process_git_worktree_snapshot_refresh,
    process_terminal_commands_for_git,
    process_worktree_registration,
    record_terminal_command_markers,
    record_terminal_output_chunk,
    refresh_project_todo_worktree_summaries_for_window,
    router,
    terminal_status_message,
)
from app.contexts.terminal_runtime.application.terminal_bridge import (
    OutputAckControl,
    ResizeControl,
    SelectWindowControl,
    parse_text_input,
)


def _truthy_query_param(value: object) -> bool:
    return isinstance(value, str) and value.lower() in {"1", "true", "yes", "on"}


@router.websocket("/api/clients/{client_id}/terminal/{window_id}")
async def terminal_websocket(
    websocket: WebSocket,
    client_id: UUID,
    window_id: UUID,
    tmux_manager: TmuxManager = Depends(get_tmux_manager),
) -> None:
    if not await require_websocket_auth(websocket):
        return
    if not await require_websocket_client_access(websocket, client_id):
        return

    subprotocol = websocket_auth_subprotocol(websocket)
    query_params = getattr(websocket, "query_params", {})
    view_id_text = query_params.get("view_id")
    try:
        view_id = UUID(view_id_text) if view_id_text else window_id
    except ValueError:
        await _close_websocket_if_connected(websocket, code=status.WS_1008_POLICY_VIOLATION)
        return
    allow_initial_missing_window_recreate = _truthy_query_param(
        query_params.get("allow_missing_window_recreate")
    )

    async with SessionLocal() as session:
        window = await get_window_for_client(session, client_id, window_id)
        if window is None:
            await _close_websocket_if_connected(websocket, code=status.WS_1008_POLICY_VIOLATION)
            return
        binding = _runtime_window_binding_from_virtual_window(window)
        if binding is None:
            await websocket.accept(subprotocol=subprotocol)
            if window.status is WindowStatus.disconnected:
                await _send_text_and_close(
                    websocket,
                    terminal_status_message(
                        "unavailable",
                        reason="client_offline",
                        retry_after_ms=REMOTE_RECONNECT_RETRY_AFTER_MS,
                    ),
                    code=1013,
                )
                return
            if window.status is WindowStatus.error:
                await _send_text_and_close(
                    websocket,
                    terminal_status_message("error", reason="runtime_start_failed"),
                    code=status.WS_1011_INTERNAL_ERROR,
                )
                return
            await _send_text_and_close(
                websocket,
                terminal_status_message(
                    "reconnecting",
                    reason="runtime_starting",
                    retry_after_ms=RUNTIME_START_RETRY_AFTER_MS,
                ),
                code=1013,
            )
            return
        if window.status is WindowStatus.disconnected and not binding.is_remote_window:
            await websocket.accept(subprotocol=subprotocol)
            await _send_text_and_close(
                websocket,
                terminal_status_message(
                    "unavailable",
                    reason="client_offline",
                    retry_after_ms=REMOTE_RECONNECT_RETRY_AFTER_MS,
                ),
            )
            return

    broker = _terminal_broker(websocket, tmux_manager)
    if binding.is_remote_window:
        registry = _client_connection_registry(websocket)
        connection = registry.get(client_id)
        if connection is None or getattr(connection, "closed", False):
            await _mark_window_disconnected(client_id, window_id)
            await websocket.accept(subprotocol=subprotocol)
            await _send_text_and_close(
                websocket,
                terminal_status_message(
                    "unavailable",
                    reason="client_offline",
                    retry_after_ms=REMOTE_RECONNECT_RETRY_AFTER_MS,
                ),
                code=1013,
            )
            return
        remote_runtime = RemoteRuntime(
            client_id=client_id,
            registry=registry,
            request_timeout=REMOTE_ATTACH_REQUEST_TIMEOUT_SECONDS,
        )
        broker.register_runtime(client_id, remote_runtime)

    marker_extractor = TerminalStreamMarkerExtractor()
    current_window_id = window_id
    current_binding = binding
    browser_input_seen = False
    attach_started_at = time.monotonic()
    local_output_recorder = LocalTerminalOutputRecorder(
        LocalTerminalOutputRecorderDependencies(
            client_id=client_id,
            session_factory=SessionLocal,
            ready_es_client=lambda: _ready_es_client(websocket),
            ui_event_hub=lambda: _ui_event_hub(websocket),
            record_command_markers=record_terminal_command_markers,
            record_output_chunk=record_terminal_output_chunk,
            commands_need_git_worktree_tracking=commands_need_git_worktree_tracking,
            git_worktree_agent_run_sequences=git_worktree_agent_run_sequences,
            process_git_worktree_snapshot_refresh=process_git_worktree_snapshot_refresh,
            process_terminal_commands_for_git=process_terminal_commands_for_git,
            process_worktree_registration=process_worktree_registration,
            refresh_project_todo_worktree_summaries_for_window=refresh_project_todo_worktree_summaries_for_window,
        ),
        batch_bytes=LOCAL_OUTPUT_RECORD_BATCH_BYTES,
        batch_delay_seconds=LOCAL_OUTPUT_RECORD_BATCH_DELAY_SECONDS,
    )

    async def publish_selection(selected_runtime_window: RuntimeWindow) -> None:
        nonlocal current_window_id, current_binding, marker_extractor
        selected_window_id = await _local_runtime_window_to_virtual_window_id(
            client_id,
            selected_runtime_window,
        )
        if selected_window_id is None:
            return
        current_window_id = selected_window_id
        current_binding = current_binding.with_runtime_window(selected_runtime_window)
        marker_extractor = TerminalStreamMarkerExtractor()
        await _send_text_if_connected(websocket, json.dumps({
            "type": "terminal_selection",
            "client_id": str(client_id),
            "window_id": str(selected_window_id),
            "view_id": str(view_id),
        }, separators=(",", ":")))

    async def record_and_publish_output(data: bytes) -> None:
        target_window_id = current_window_id
        clean_data, commands, worktree_markers = marker_extractor.feed(data)
        is_attach_snapshot = (
            bool(commands or worktree_markers or clean_data)
            and not browser_input_seen
            and time.monotonic() - attach_started_at <= ATTACH_SNAPSHOT_GRACE_SECONDS
        )
        if clean_data:
            await broker.publish_view_output(client_id, view_id, clean_data)
        if (commands or worktree_markers or clean_data) and not is_attach_snapshot:
            local_output_recorder.queue(
                LocalTerminalOutputRecordJob(
                    target_window_id,
                    clean_data,
                    commands,
                    worktree_markers,
                    is_attach_snapshot=is_attach_snapshot,
                )
            )

    async def select_active_window(
        next_window_id: UUID,
        *,
        allow_missing_window_recreate: bool = False,
    ) -> bool:
        nonlocal current_window_id, current_binding
        nonlocal marker_extractor, attach_started_at, browser_input_seen
        if next_window_id == current_window_id:
            return True
        async with SessionLocal() as session:
            next_window = await get_window_for_client(session, client_id, next_window_id)
            if next_window is None:
                return False
            next_binding = _runtime_window_binding_from_virtual_window(next_window)
            if next_binding is None:
                return False

        selected_runtime_window = await broker.select_window(
            client_id,
            view_id,
            current_window_id,
            current_binding.runtime_window,
            next_window_id,
            next_binding.runtime_window,
            allow_missing_window_recreate=allow_missing_window_recreate,
        )
        if selected_runtime_window != next_binding.runtime_window:
            next_binding = next_binding.with_runtime_window(selected_runtime_window)
            await _persist_runtime_window(
                client_id,
                next_window_id,
                next_binding,
            )
        current_window_id = next_window_id
        current_binding = next_binding
        marker_extractor = TerminalStreamMarkerExtractor()
        attach_started_at = time.monotonic()
        browser_input_seen = False
        await _mark_window_active(client_id, next_window_id)
        await _send_text_if_connected(websocket, json.dumps({
            "type": "terminal_selection",
            "client_id": str(client_id),
            "window_id": str(next_window_id),
            "view_id": str(view_id),
        }, separators=(",", ":")))
        return True

    await websocket.accept(subprotocol=subprotocol)
    output_sender = websocket.send_bytes
    await broker.subscribe(client_id, view_id, output_sender, websocket.send_text)
    try:
        try:
            attached_runtime_window = await broker.attach(
                client_id,
                window_id,
                binding.runtime_window,
                output_callback=record_and_publish_output if binding.is_local_window else None,
                selection_callback=publish_selection if binding.is_local_window else None,
                view_id=view_id,
                allow_missing_window_recreate=allow_initial_missing_window_recreate,
            )
            if attached_runtime_window is not None and attached_runtime_window != binding.runtime_window:
                binding = binding.with_runtime_window(attached_runtime_window)
                current_binding = binding
                await _persist_runtime_window(
                    client_id,
                    window_id,
                    binding,
                )
        except RemoteClientUnavailable:
            await _mark_window_disconnected(client_id, window_id)
            await _send_text_and_close(
                websocket,
                terminal_status_message(
                    "unavailable",
                    reason="client_offline",
                    retry_after_ms=REMOTE_RECONNECT_RETRY_AFTER_MS,
                ),
                code=1013,
            )
            return
        except (TerminalRuntimeUnavailable, TmuxCommandError, RemoteTerminalError, RuntimeError):
            await _mark_window_error(client_id, window_id)
            await _send_text_and_close(
                websocket,
                terminal_status_message("error", reason="attach_failed"),
                code=status.WS_1011_INTERNAL_ERROR,
            )
            return
        await _mark_window_active(client_id, window_id)
        await _send_text_if_connected(websocket, terminal_status_message("connected"))

        while True:
            message = await websocket.receive()
            if message.get("type") == "websocket.disconnect":
                return
            if message.get("bytes") is not None:
                try:
                    browser_input_seen = True
                    await broker.send_input(
                        client_id,
                        current_window_id,
                        current_binding.runtime_window,
                        message["bytes"],
                        view_id=view_id,
                    )
                except RemoteClientUnavailable:
                    await _mark_window_disconnected(client_id, current_window_id)
                    await broker.clear_client(
                        client_id,
                        status_message=terminal_status_message(
                            "unavailable",
                            reason="client_offline",
                            retry_after_ms=REMOTE_RECONNECT_RETRY_AFTER_MS,
                        ),
                    )
                    await _close_websocket_if_connected(websocket, code=1013)
                    return
                continue
            if message.get("text") is not None:
                action = parse_text_input(message["text"])
                if isinstance(action, SelectWindowControl):
                    try:
                        if not await select_active_window(
                            action.window_id,
                            allow_missing_window_recreate=action.allow_missing_window_recreate,
                        ):
                            await _send_text_if_connected(
                                websocket,
                                terminal_status_message("error", reason="select_failed")
                            )
                    except RemoteClientUnavailable:
                        await _mark_window_disconnected(client_id, current_window_id)
                        await broker.clear_client(
                            client_id,
                            status_message=terminal_status_message(
                                "unavailable",
                                reason="client_offline",
                                retry_after_ms=REMOTE_RECONNECT_RETRY_AFTER_MS,
                            ),
                        )
                        await _close_websocket_if_connected(websocket, code=1013)
                        return
                    except (TerminalRuntimeUnavailable, TmuxCommandError, RemoteTerminalError, RuntimeError):
                        await _send_text_if_connected(
                            websocket,
                            terminal_status_message("error", reason="select_failed")
                        )
                elif isinstance(action, ResizeControl):
                    try:
                        await broker.resize(
                            client_id,
                            current_window_id,
                            current_binding.runtime_window,
                            cols=action.cols,
                            rows=action.rows,
                            view_id=view_id,
                        )
                    except RemoteClientUnavailable:
                        await _mark_window_disconnected(client_id, current_window_id)
                        await broker.clear_client(
                            client_id,
                            status_message=terminal_status_message(
                                "unavailable",
                                reason="client_offline",
                                retry_after_ms=REMOTE_RECONNECT_RETRY_AFTER_MS,
                            ),
                        )
                        await _close_websocket_if_connected(websocket, code=1013)
                        return
                elif isinstance(action, OutputAckControl):
                    await broker.acknowledge_output(
                        client_id,
                        view_id,
                        output_sender,
                        bytes_acked=action.bytes_acked,
                    )
                elif isinstance(action, bytes):
                    browser_input_seen = True
                    try:
                        await broker.send_input(
                            client_id,
                            current_window_id,
                            current_binding.runtime_window,
                            action,
                            view_id=view_id,
                        )
                    except RemoteClientUnavailable:
                        await _mark_window_disconnected(client_id, current_window_id)
                        await broker.clear_client(
                            client_id,
                            status_message=terminal_status_message(
                                "unavailable",
                                reason="client_offline",
                                retry_after_ms=REMOTE_RECONNECT_RETRY_AFTER_MS,
                            ),
                        )
                        await _close_websocket_if_connected(websocket, code=1013)
                        return
    except WebSocketDisconnect:
        return
    except RemoteClientUnavailable:
        await _mark_window_disconnected(client_id, current_window_id)
        await _close_websocket_if_connected(websocket, code=1013)
        return
    finally:
        await broker.unsubscribe(client_id, view_id, output_sender, websocket.send_text)
