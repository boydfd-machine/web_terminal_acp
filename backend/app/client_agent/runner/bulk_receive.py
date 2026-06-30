from __future__ import annotations

import asyncio
import contextlib
import logging
from typing import Protocol
from uuid import UUID

from app.services.runtime.protocol import AgentMessage, decode_agent_message

logger = logging.getLogger(__name__)


class WebSocketReceiver(Protocol):
    async def recv(self) -> str:
        raise NotImplementedError


def start_bulk_receive_task(
    bulk_websocket: WebSocketReceiver,
    client_id: UUID,
) -> asyncio.Task[None]:
    return asyncio.create_task(_bulk_receive_loop(bulk_websocket, client_id))


async def receive_control_message(
    control_websocket: WebSocketReceiver,
    bulk_receive_task: asyncio.Task[None],
) -> AgentMessage:
    control_recv_task = asyncio.create_task(control_websocket.recv())
    try:
        done, _pending = await asyncio.wait(
            {control_recv_task, bulk_receive_task},
            return_when=asyncio.FIRST_COMPLETED,
        )
        if bulk_receive_task in done:
            await _cancel_or_consume_task(control_recv_task)
            await bulk_receive_task
            raise RuntimeError("bulk websocket receive loop stopped")
        return decode_agent_message(await control_recv_task)
    finally:
        await _cancel_or_consume_task(control_recv_task)


async def _cancel_or_consume_task(task: asyncio.Task) -> None:
    if not task.done():
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task
    elif not task.cancelled():
        with contextlib.suppress(Exception):
            task.exception()


async def _bulk_receive_loop(
    bulk_websocket: WebSocketReceiver,
    client_id: UUID,
) -> None:
    while True:
        message = decode_agent_message(await bulk_websocket.recv())
        _handle_bulk_message(message, client_id)


def _handle_bulk_message(message: AgentMessage, client_id: UUID) -> None:
    if message.client_id != client_id:
        raise RuntimeError("bulk websocket client_id mismatch")
    if message.type == "ai_event_ack":
        if message.payload.get("ok") is False:
            logger.warning(
                "client-agent bulk websocket received failed ai_event_ack",
                extra={
                    "client_id": str(client_id),
                    "window_id": str(message.window_id) if message.window_id is not None else None,
                    "request_id": message.request_id,
                    "error": message.payload.get("error"),
                },
            )
        return
    raise RuntimeError(f"unexpected bulk websocket message: {message.type}")
