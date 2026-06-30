# ruff: noqa: F403,F405
from app.contexts.clients.api.client_agent.connection import *
from app.contexts.clients.api.client_agent.bulk_websocket import *
from app.contexts.clients.api.client_agent.message_handlers import *


@router.websocket("/api/client-agent/ws")
async def client_agent_websocket(websocket: WebSocket) -> None:
    client_id = await _authenticate_and_mark_seen(websocket)
    if client_id is None:
        logger.warning("client-agent websocket authentication failed")
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    await websocket.accept()
    connection = ClientConnection(websocket=websocket, client_id=client_id)
    registry = _connection_registry(websocket)
    terminal_selection_queue: asyncio.Queue[AgentMessage] = asyncio.Queue(
        maxsize=BACKGROUND_MESSAGE_QUEUE_MAX_SIZE
    )

    async def handle_terminal_selection(message: AgentMessage) -> None:
        await _handle_terminal_selection_message(websocket, client_id, message)

    background_workers = [
        asyncio.create_task(
            _client_agent_message_worker(
                client_id=client_id,
                queue_name="terminal_selection",
                queue=terminal_selection_queue,
                handler=handle_terminal_selection,
            )
        ),
    ]

    await registry.register(connection)
    logger.info("client-agent websocket connected", extra={"client_id": str(client_id)})

    try:
        while True:
            try:
                try:
                    raw_message = await websocket.receive_text()
                except RuntimeError as exc:
                    if "WebSocket is not connected" in str(exc):
                        logger.info(
                            "client-agent websocket receive stopped after close",
                            extra={"client_id": str(client_id)},
                        )
                        return
                    raise
                message = decode_agent_message(raw_message)
            except ValidationError:
                logger.warning(
                    "client-agent websocket received invalid message",
                    extra={"client_id": str(client_id)},
                )
                await websocket.close(code=status.WS_1003_UNSUPPORTED_DATA)
                return

            if message.client_id != client_id:
                logger.warning(
                    "client-agent websocket client_id mismatch",
                    extra={
                        "authenticated_client_id": str(client_id),
                        "message_client_id": str(message.client_id),
                        "message_type": message.type,
                    },
                )
                await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
                return

            if connection.resolve(message):
                connection.mark_seen()
                continue

            if message.type == "hello":
                marked_seen = await _best_effort_mark_client_seen_with_metadata(
                    client_id,
                    message.payload,
                    message_type=message.type,
                )
                if marked_seen is False:
                    await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
                    return
                if marked_seen is True:
                    await _ui_event_hub(websocket).publish_debounced_invalidation(
                        ("clients", client_id),
                        ["clients"],
                        client_id=client_id,
                        reason="client_hello",
                        delay_seconds=1.0,
                    )
                connection.mark_seen()
                await connection.send(AgentMessage(type="hello_ack", client_id=client_id))
                continue

            if message.type == "heartbeat":
                marked_seen = await _best_effort_mark_client_seen_with_metadata(
                    client_id,
                    message.payload,
                    message_type=message.type,
                )
                if marked_seen is False:
                    await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
                    return
                if marked_seen is True:
                    await _ui_event_hub(websocket).publish_debounced_invalidation(
                        ("clients", client_id),
                        ["clients"],
                        client_id=client_id,
                        reason="client_heartbeat",
                        delay_seconds=1.0,
                    )
                connection.mark_seen()
                await connection.send(AgentMessage(type="heartbeat_ack", client_id=client_id))
                continue

            if message.type == "inventory":
                inventory_handled = await _best_effort_handle_inventory_message(
                    websocket,
                    client_id,
                    message,
                )
                if inventory_handled is False:
                    await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
                    return
                connection.mark_seen()
                continue

            if message.type in {"ai_event", "terminal_output", "aux_terminal_output"}:
                logger.warning(
                    "client-agent bulk message received on control websocket",
                    extra={
                        "client_id": str(client_id),
                        "message_type": message.type,
                        "window_id": str(message.window_id) if message.window_id else None,
                    },
                )
                await websocket.close(code=status.WS_1003_UNSUPPORTED_DATA)
                return

            if message.type == "terminal_selection":
                connection.mark_seen()
                await _enqueue_background_message(
                    terminal_selection_queue,
                    client_id=client_id,
                    message=message,
                    queue_name="terminal_selection",
                )
                continue

            if message.type == "terminal_error":
                connection.mark_seen()
                logger.warning(
                    "client-agent terminal error",
                    extra={
                        "client_id": str(client_id),
                        "window_id": str(message.window_id) if message.window_id else None,
                        "error_message": message.payload.get("message"),
                    },
                )
                await _handle_terminal_error_message(websocket, client_id, message)
                continue
    except WebSocketDisconnect as exc:
        logger.info(
            "client-agent websocket disconnected",
            extra={"client_id": str(client_id), "code": getattr(exc, "code", None)},
        )
    except ClientConnectionClosed:
        logger.info(
            "client-agent websocket send stopped after close",
            extra={"client_id": str(client_id)},
        )
    except Exception:
        logger.exception(
            "client-agent websocket failed",
            extra={"client_id": str(client_id)},
        )
        raise
    finally:
        await _wait_for_background_queues(
            client_id=client_id,
            queues=[("terminal_selection", terminal_selection_queue)],
        )
        for worker in background_workers:
            worker.cancel()
        for worker in background_workers:
            with contextlib.suppress(asyncio.CancelledError):
                await worker
        await registry.unregister(connection)
        connection.abort()
        if registry.get(client_id) is None:
            changed = await _best_effort_mark_client_disconnected_by_id(client_id)
            if changed:
                await _ui_event_hub(websocket).publish_invalidation(
                    ["clients", "tree", "window"],
                    client_id=client_id,
                    reason="client_disconnected",
                )
            logger.warning(
                "client-agent websocket removed last connection",
                extra={"client_id": str(client_id), "marked_offline": changed},
            )
            await _terminal_broker(websocket).clear_client(
                client_id,
                status_message=terminal_status_message(
                    "unavailable",
                    reason="client_offline",
                    retry_after_ms=5000,
                ),
            )


__all__ = [name for name in globals() if not name.startswith("__")]
