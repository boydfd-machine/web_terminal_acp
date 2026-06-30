# ruff: noqa: F403,F405
from app.contexts.clients.api.client_agent.connection import *
from app.contexts.clients.api.client_agent.message_handlers import *


async def _enqueue_background_message(
    queue: _BackgroundMessageQueue,
    *,
    client_id: UUID,
    message: AgentMessage,
    queue_name: str,
) -> None:
    started_at = time.perf_counter()
    await queue.put(message)
    elapsed = time.perf_counter() - started_at
    if elapsed >= BACKGROUND_MESSAGE_QUEUE_WARN_SECONDS:
        logger.warning(
            "client-agent background queue applied backpressure",
            extra={
                "client_id": str(client_id),
                "queue_name": queue_name,
                "message_type": message.type,
                "window_id": str(message.window_id) if message.window_id else None,
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
            "client-agent background queue backlog is high",
            extra={
                "client_id": str(client_id),
                "queue_name": queue_name,
                "message_type": message.type,
                "window_id": str(message.window_id) if message.window_id else None,
                "queue_size": queue_size,
            },
        )


async def _client_agent_message_worker(
    *,
    client_id: UUID,
    queue_name: str,
    queue: _BackgroundMessageQueue,
    handler,
) -> None:
    while True:
        message = await queue.get()
        try:
            await handler(message)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception(
                "client-agent background message handler failed",
                extra={
                    "client_id": str(client_id),
                    "queue_name": queue_name,
                    "message_type": message.type,
                    "window_id": str(message.window_id) if message.window_id else None,
                },
            )
        finally:
            queue.task_done()


async def _terminal_output_recording_worker(
    *,
    client_id: UUID,
    queue: asyncio.Queue[_TerminalOutputRecordingJob],
    handler,
) -> None:
    pending_client_id: UUID | None = None
    pending_window_id: UUID | None = None
    pending_data = bytearray()
    pending_done_count = 0

    async def flush_pending() -> None:
        nonlocal pending_client_id, pending_window_id, pending_data, pending_done_count
        if pending_client_id is None or pending_window_id is None or not pending_data:
            return
        job = _TerminalOutputRecordingJob(
            client_id=pending_client_id,
            window_id=pending_window_id,
            clean_data=bytes(pending_data),
            commands=(),
            worktree_markers=(),
        )
        done_count = pending_done_count
        pending_client_id = None
        pending_window_id = None
        pending_data = bytearray()
        pending_done_count = 0
        try:
            await handler(job)
        finally:
            for _ in range(done_count):
                queue.task_done()

    async def flush_pending_and_log() -> None:
        target_window_id = pending_window_id
        try:
            await flush_pending()
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception(
                "client-agent terminal output recording handler failed",
                extra={"client_id": str(client_id), "window_id": str(target_window_id)},
            )

    while True:
        if pending_data and len(pending_data) >= TERMINAL_OUTPUT_RECORD_BATCH_BYTES:
            await flush_pending_and_log()
            continue

        try:
            if pending_data:
                job = await asyncio.wait_for(
                    queue.get(),
                    timeout=TERMINAL_OUTPUT_RECORD_BATCH_DELAY_SECONDS,
                )
            else:
                job = await queue.get()
        except asyncio.TimeoutError:
            await flush_pending_and_log()
            continue

        task_done_now = True
        try:
            if _can_batch_terminal_output_recording(job):
                if (
                    pending_window_id is not None
                    and (
                        pending_client_id != job.client_id
                        or pending_window_id != job.window_id
                        or len(pending_data) + len(job.clean_data) > TERMINAL_OUTPUT_RECORD_BATCH_BYTES
                    )
                ):
                    await flush_pending_and_log()
                pending_client_id = job.client_id
                pending_window_id = job.window_id
                pending_data.extend(job.clean_data)
                pending_done_count += 1
                task_done_now = False
                continue

            await flush_pending_and_log()
            await handler(job)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception(
                "client-agent terminal output recording handler failed",
                extra={
                    "client_id": str(client_id),
                    "window_id": str(job.window_id),
                },
            )
        finally:
            if task_done_now:
                queue.task_done()


async def _git_worktree_tracking_worker(
    *,
    client_id: UUID,
    queue: asyncio.Queue[_GitWorktreeTrackingJob],
    handler,
) -> None:
    while True:
        job = await queue.get()
        try:
            await handler(job)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception(
                "client-agent git worktree tracking handler failed",
                extra={
                    "client_id": str(client_id),
                    "window_id": str(job.window_id),
                },
            )
        finally:
            queue.task_done()


async def _wait_for_background_queues(
    *,
    client_id: UUID,
    queues: list[tuple[str, _BackgroundMessageQueue]],
    timeout_seconds: float = BACKGROUND_QUEUE_DRAIN_TIMEOUT_SECONDS,
) -> None:
    try:
        await asyncio.wait_for(
            asyncio.gather(*(queue.join() for _name, queue in queues)),
            timeout=timeout_seconds,
        )
    except asyncio.TimeoutError:
        logger.warning(
            "client-agent background queue drain timed out",
            extra={
                "client_id": str(client_id),
                "timeout_seconds": timeout_seconds,
                "queues": [
                    {"name": name, "queue_size": queue.qsize()}
                    for name, queue in queues
                ],
            },
        )


@router.websocket("/api/client-agent/bulk-ws")
async def client_agent_bulk_websocket(websocket: WebSocket) -> None:
    client_id = await _authenticate_and_mark_seen(websocket)
    if client_id is None:
        logger.warning("client-agent bulk websocket authentication failed")
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    await websocket.accept()
    marker_extractors: dict[UUID, TerminalStreamMarkerExtractor] = {}
    known_windows: set[UUID] = set()
    send_lock = asyncio.Lock()
    agent_event_queue_config = queue_config_from_settings()
    agent_event_redis_client = create_redis_client(agent_event_queue_config) if agent_event_queue_config else None
    ai_event_queue: asyncio.Queue[AgentMessage] = asyncio.Queue(
        maxsize=LOW_PRIORITY_BACKGROUND_QUEUE_MAX_SIZE
    )
    terminal_output_queue = _WindowFairMessageQueue(maxsize=TERMINAL_OUTPUT_QUEUE_MAX_SIZE)
    terminal_output_recording_queue: asyncio.Queue[_TerminalOutputRecordingJob] = asyncio.Queue(
        maxsize=LOW_PRIORITY_BACKGROUND_QUEUE_MAX_SIZE
    )
    git_worktree_tracking_queue: asyncio.Queue[_GitWorktreeTrackingJob] = asyncio.Queue(
        maxsize=LOW_PRIORITY_BACKGROUND_QUEUE_MAX_SIZE
    )

    async def send_message(message: AgentMessage) -> None:
        async with send_lock:
            await websocket.send_text(encode_agent_message(message))

    async def handle_ai_event(message: AgentMessage) -> None:
        if message.type == "agent_work_presence":
            await _handle_agent_work_presence_message(websocket, client_id, message)
            return
        persisted = await _handle_ai_event_message_with_ack_sender(
            websocket,
            send_message,
            client_id,
            message,
            agent_event_redis_client,
        )
        if persisted and queue_config_from_settings() is None:
            git_tracking_job = _git_worktree_tracking_job_from_ai_event_message(client_id, message)
            if git_tracking_job is not None:
                await git_worktree_tracking_queue.put(git_tracking_job)

    async def handle_terminal_output(message: AgentMessage) -> None:
        job = await _handle_terminal_output_message(
            websocket,
            client_id,
            message,
            marker_extractors,
            known_windows=known_windows,
        )
        if job is not None:
            await _enqueue_terminal_output_recording_job(
                terminal_output_recording_queue,
                client_id=client_id,
                job=job,
            )

    async def handle_terminal_output_recording(job: _TerminalOutputRecordingJob) -> None:
        git_tracking_job = await _record_terminal_output_job(websocket, job)
        if git_tracking_job is not None:
            await git_worktree_tracking_queue.put(git_tracking_job)

    async def handle_git_worktree_tracking(job: _GitWorktreeTrackingJob) -> None:
        registry = _connection_registry(websocket)
        changed = False
        todo_changed = False
        async with SessionLocal() as session:
            window = await session.scalar(
                select(VirtualWindow)
                .options(selectinload(VirtualWindow.client))
                .where(
                    VirtualWindow.id == job.window_id,
                    VirtualWindow.client_id == job.client_id,
                )
            )
            if window is None:
                return
            for marker in job.worktree_markers:
                if str(marker.get("window_id")) != str(job.window_id):
                    continue
                await process_worktree_registration(
                    session,
                    client_id=job.client_id,
                    window_id=job.window_id,
                    marker=marker,
                    registry=registry,
                    client_runtime=window.client.runtime if window.client is not None else None,
                )
                changed = True
            if job.commands:
                await process_terminal_commands_for_git(
                    session,
                    client_id=job.client_id,
                    window_id=job.window_id,
                    commands=list(job.commands),
                    registry=registry,
                    client_runtime=window.client.runtime if window.client is not None else None,
                )
                changed = True
            snapshot_changed = await process_git_worktree_snapshot_refresh(
                session,
                client_id=job.client_id,
                window_id=job.window_id,
                registry=registry,
                client_runtime=window.client.runtime if window.client is not None else None,
                command_sequences=git_worktree_agent_run_sequences(list(job.commands)) or None,
            )
            if snapshot_changed:
                todo_changed = await refresh_project_todo_worktree_summaries_for_window(
                    session,
                    client_id=job.client_id,
                    window_id=job.window_id,
                )
            changed = snapshot_changed or changed
            if changed:
                await session.commit()
        if changed:
            with contextlib.suppress(Exception):
                resources = ["window", "tree", "git_runs"]
                if todo_changed:
                    resources.append("project_todos")
                await _ui_event_hub(websocket).publish_invalidation(
                    resources,
                    client_id=job.client_id,
                    window_id=job.window_id,
                    reason="git_worktree",
                )

    background_workers = []

    try:
        try:
            raw_message = await websocket.receive_text()
            hello = decode_agent_message(raw_message)
        except (ValidationError, RuntimeError):
            await websocket.close(code=status.WS_1003_UNSUPPORTED_DATA)
            return
        if hello.client_id != client_id:
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return
        if hello.type != "bulk_hello":
            await websocket.close(code=status.WS_1003_UNSUPPORTED_DATA)
            return
        await send_message(AgentMessage(type="bulk_hello_ack", client_id=client_id))
        background_workers = [
            asyncio.create_task(
                _client_agent_message_worker(
                    client_id=client_id,
                    queue_name="bulk_ai_event",
                    queue=ai_event_queue,
                    handler=handle_ai_event,
                )
            ),
            asyncio.create_task(
                _client_agent_message_worker(
                    client_id=client_id,
                    queue_name="bulk_terminal_output",
                    queue=terminal_output_queue,
                    handler=handle_terminal_output,
                )
            ),
            asyncio.create_task(
                _terminal_output_recording_worker(
                    client_id=client_id,
                    queue=terminal_output_recording_queue,
                    handler=handle_terminal_output_recording,
                )
            ),
            asyncio.create_task(
                _git_worktree_tracking_worker(
                    client_id=client_id,
                    queue=git_worktree_tracking_queue,
                    handler=handle_git_worktree_tracking,
                )
            ),
        ]

        while True:
            try:
                try:
                    raw_message = await websocket.receive_text()
                except RuntimeError as exc:
                    if "WebSocket is not connected" in str(exc):
                        logger.info(
                            "client-agent bulk websocket receive stopped after close",
                            extra={"client_id": str(client_id)},
                        )
                        return
                    raise
                message = decode_agent_message(raw_message)
            except ValidationError:
                logger.warning(
                    "client-agent bulk websocket received invalid message",
                    extra={"client_id": str(client_id)},
                )
                await websocket.close(code=status.WS_1003_UNSUPPORTED_DATA)
                return

            if message.client_id != client_id:
                logger.warning(
                    "client-agent bulk websocket client_id mismatch",
                    extra={
                        "authenticated_client_id": str(client_id),
                        "message_client_id": str(message.client_id),
                        "message_type": message.type,
                    },
                )
                await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
                return

            if message.type in {"ai_event", "agent_work_presence"}:
                await _enqueue_background_message(
                    ai_event_queue,
                    client_id=client_id,
                    message=message,
                    queue_name="bulk_ai_event",
                )
                continue

            if message.type == "terminal_output":
                await _enqueue_background_message(
                    terminal_output_queue,
                    client_id=client_id,
                    message=message,
                    queue_name="bulk_terminal_output",
                )
                continue

            if message.type == "aux_terminal_output":
                await _handle_aux_terminal_output_message(websocket, client_id, message)
                continue

            logger.warning(
                "client-agent bulk websocket received unsupported message",
                extra={
                    "client_id": str(client_id),
                    "message_type": message.type,
                    "window_id": str(message.window_id) if message.window_id else None,
                },
            )
            await websocket.close(code=status.WS_1003_UNSUPPORTED_DATA)
            return
    except WebSocketDisconnect as exc:
        logger.info(
            "client-agent bulk websocket disconnected",
            extra={"client_id": str(client_id), "code": getattr(exc, "code", None)},
        )
    except Exception:
        logger.exception(
            "client-agent bulk websocket failed",
            extra={"client_id": str(client_id)},
        )
        raise
    finally:
        await _wait_for_background_queues(
            client_id=client_id,
            queues=[
                ("bulk_ai_event", ai_event_queue),
                ("bulk_terminal_output", terminal_output_queue),
                ("bulk_terminal_output_recording", terminal_output_recording_queue),
                ("bulk_git_worktree_tracking", git_worktree_tracking_queue),
            ],
        )
        for worker in background_workers:
            worker.cancel()
        for worker in background_workers:
            with contextlib.suppress(asyncio.CancelledError):
                await worker
        if agent_event_redis_client is not None:
            await agent_event_redis_client.aclose()


__all__ = [name for name in globals() if not name.startswith("__")]
