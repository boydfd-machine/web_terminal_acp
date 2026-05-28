from __future__ import annotations

import asyncio
import contextlib
import json
import logging
from collections import deque
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from uuid import UUID

from app.services.runtime.types import (
    RuntimeWindow,
    TerminalRuntime,
    TerminalSelectionCallback,
    TerminalSender,
)

logger = logging.getLogger(__name__)

# Per-browser terminal subscribers get their own writer queue. This keeps the
# client-agent bulk-output worker from waiting on slow WAN websocket sends while
# still bounding memory for dead or overloaded browsers.
PUBLISH_OUTPUT_SUBSCRIBER_TIMEOUT_SECONDS = 5.0
SUBSCRIBER_WRITER_QUEUE_MAX_BYTES = 4 * 1024 * 1024
SUBSCRIBER_WRITER_QUEUE_MAX_MESSAGES = 8192
# Browser ACK keeps output bounded, but it must work like a byte window instead
# of stop-and-wait or bulk output spends most of its time waiting for round trips.
SUBSCRIBER_WRITER_COALESCE_BYTES = 128 * 1024
SUBSCRIBER_WRITER_ACK_WINDOW_BYTES = 1024 * 1024


class TerminalRuntimeUnavailable(RuntimeError):
    """Raised when no terminal runtime is registered for a client."""


TerminalStatusSender = Callable[[str], Awaitable[None]]


def terminal_status_message(
    status: str,
    *,
    reason: str | None = None,
    retry_after_ms: int | None = None,
) -> str:
    payload: dict[str, object] = {"type": "terminal_status", "status": status}
    if reason is not None:
        payload["reason"] = reason
    if retry_after_ms is not None:
        payload["retry_after_ms"] = retry_after_ms
    return json.dumps(payload, separators=(",", ":"))


@dataclass
class _QueuedSubscriberMessage:
    payload: bytes | str
    size: int


class _TerminalSubscriberWriter:
    def __init__(
        self,
        *,
        client_id: UUID,
        window_id: UUID,
        output_sender: TerminalSender,
        status_sender: TerminalStatusSender | None,
        on_failure: Callable[["_TerminalSubscriberWriter", BaseException], Awaitable[None]],
        send_timeout_seconds: float | None = None,
        max_bytes: int | None = None,
        max_messages: int | None = None,
        coalesce_bytes: int | None = None,
        ack_window_bytes: int | None = None,
    ) -> None:
        self.client_id = client_id
        self.window_id = window_id
        self.output_sender = output_sender
        self.status_sender = status_sender
        self._on_failure = on_failure
        self._send_timeout_seconds = send_timeout_seconds or PUBLISH_OUTPUT_SUBSCRIBER_TIMEOUT_SECONDS
        self._max_bytes = max_bytes or SUBSCRIBER_WRITER_QUEUE_MAX_BYTES
        self._max_messages = max_messages or SUBSCRIBER_WRITER_QUEUE_MAX_MESSAGES
        self._coalesce_bytes = coalesce_bytes or SUBSCRIBER_WRITER_COALESCE_BYTES
        self._ack_window_bytes = ack_window_bytes or SUBSCRIBER_WRITER_ACK_WINDOW_BYTES
        self._queue: deque[_QueuedSubscriberMessage] = deque()
        self._queued_bytes = 0
        self._condition = asyncio.Condition()
        self._closed = False
        self._ack_enabled = False
        self._in_flight_bytes = 0
        self._in_flight_frames: deque[int] = deque()
        self._task: asyncio.Task[None] | None = None

    def start(self) -> None:
        if self._task is None or self._task.done():
            self._task = asyncio.create_task(self._run())

    async def enqueue_output(self, data: bytes) -> bool:
        return await self._enqueue(data)

    async def enqueue_status(self, message: str) -> bool:
        return await self._enqueue(message)

    async def close(self) -> None:
        async with self._condition:
            if self._closed:
                return
            self._closed = True
            self._in_flight_bytes = 0
            self._in_flight_frames.clear()
            self._queue.clear()
            self._queued_bytes = 0
            self._condition.notify_all()
        task = self._task
        if task is not None and task is not asyncio.current_task() and not task.done():
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task

    async def _enqueue(self, payload: bytes | str) -> bool:
        size = len(payload) if isinstance(payload, bytes) else len(payload.encode("utf-8"))
        if size > self._max_bytes:
            return False
        async with self._condition:
            if self._closed:
                return False
            if (
                len(self._queue) >= self._max_messages
                or self._queued_bytes + size > self._max_bytes
            ):
                if self._ack_enabled and isinstance(payload, bytes):
                    self._shed_queued_byte_output_locked()
                if (
                    len(self._queue) >= self._max_messages
                    or self._queued_bytes + size > self._max_bytes
                ):
                    return False
            if (
                not self._ack_enabled
                and isinstance(payload, bytes)
                and self._queue
                and isinstance(self._queue[-1].payload, bytes)
                and self._queue[-1].size + size <= self._coalesce_bytes
            ):
                self._queue[-1].payload += payload
                self._queue[-1].size += size
            else:
                self._queue.append(_QueuedSubscriberMessage(payload=payload, size=size))
            self._queued_bytes += size
            self._condition.notify()
        self.start()
        return True

    def _shed_queued_byte_output_locked(self) -> int:
        if not self._queue:
            return 0
        kept: deque[_QueuedSubscriberMessage] = deque()
        dropped_bytes = 0
        for message in self._queue:
            if isinstance(message.payload, bytes):
                dropped_bytes += message.size
            else:
                kept.append(message)
        if dropped_bytes:
            self._queue = kept
            self._queued_bytes -= dropped_bytes
            self._condition.notify_all()
        return dropped_bytes

    async def output_ack(self, bytes_acked: int | None = None) -> None:
        async with self._condition:
            was_ack_enabled = self._ack_enabled
            self._ack_enabled = True
            if bytes_acked is None:
                if was_ack_enabled and self._in_flight_frames:
                    released_bytes = self._in_flight_frames.popleft()
                    self._in_flight_bytes = max(0, self._in_flight_bytes - released_bytes)
                else:
                    self._in_flight_bytes = 0
                    self._in_flight_frames.clear()
            else:
                released_bytes = max(0, bytes_acked)
                self._in_flight_bytes = max(0, self._in_flight_bytes - released_bytes)
                while released_bytes > 0 and self._in_flight_frames:
                    frame_bytes = self._in_flight_frames[0]
                    if released_bytes < frame_bytes:
                        self._in_flight_frames[0] = frame_bytes - released_bytes
                        break
                    released_bytes -= frame_bytes
                    self._in_flight_frames.popleft()
                if self._in_flight_bytes == 0:
                    self._in_flight_frames.clear()
            self._condition.notify_all()

    def _send_window_full_locked(self) -> bool:
        if not self._ack_enabled or not self._queue:
            return False
        if not isinstance(self._queue[0].payload, bytes):
            return False
        return self._in_flight_bytes >= self._ack_window_bytes

    async def _next_message(self) -> _QueuedSubscriberMessage | None:
        async with self._condition:
            while (not self._queue or self._send_window_full_locked()) and not self._closed:
                await self._condition.wait()
            if not self._queue:
                return None
            message = self._queue.popleft()
            self._queued_bytes -= message.size
            if isinstance(message.payload, bytes) and self._ack_enabled:
                remaining_window = max(1, self._ack_window_bytes - self._in_flight_bytes)
                frame_budget = min(self._coalesce_bytes, remaining_window)
            else:
                frame_budget = self._coalesce_bytes
            if isinstance(message.payload, bytes) and self._ack_enabled and message.size > frame_budget:
                payload = message.payload
                head = payload[:frame_budget]
                tail = payload[frame_budget:]
                message = _QueuedSubscriberMessage(payload=head, size=len(head))
                self._queue.appendleft(_QueuedSubscriberMessage(payload=tail, size=len(tail)))
                self._queued_bytes += len(tail)
            elif isinstance(message.payload, bytes):
                chunks = [message.payload]
                while (
                    self._queue
                    and isinstance(self._queue[0].payload, bytes)
                    and message.size + self._queue[0].size <= frame_budget
                ):
                    next_message = self._queue.popleft()
                    self._queued_bytes -= next_message.size
                    chunks.append(next_message.payload)
                    message.size += next_message.size
                if len(chunks) > 1:
                    message.payload = b"".join(chunks)
            if isinstance(message.payload, bytes) and self._ack_enabled:
                self._in_flight_bytes += message.size
                self._in_flight_frames.append(message.size)
            return message

    async def _run(self) -> None:
        try:
            while True:
                message = await self._next_message()
                if message is None:
                    return
                sender = self.output_sender if isinstance(message.payload, bytes) else self.status_sender
                if sender is None:
                    continue
                await asyncio.wait_for(
                    sender(message.payload),  # type: ignore[arg-type]
                    timeout=self._send_timeout_seconds,
                )
        except asyncio.CancelledError:
            raise
        except BaseException as exc:
            async with self._condition:
                self._closed = True
                self._in_flight_bytes = 0
                self._in_flight_frames.clear()
                self._queue.clear()
                self._queued_bytes = 0
                self._condition.notify_all()
            await self._on_failure(self, exc)


class TerminalBroker:
    def __init__(self) -> None:
        self._runtimes: dict[UUID, TerminalRuntime] = {}
        self._subscribers: dict[tuple[UUID, UUID], dict[TerminalSender, _TerminalSubscriberWriter]] = {}
        self._status_subscribers: dict[tuple[UUID, UUID], dict[TerminalStatusSender, _TerminalSubscriberWriter]] = {}
        self._attachments: dict[tuple[UUID, UUID], RuntimeWindow] = {}
        self._attachment_window_ids: dict[tuple[UUID, UUID], UUID] = {}
        self._detaches: dict[tuple[UUID, UUID], asyncio.Task[None]] = {}
        self._lock = asyncio.Lock()

    def register_runtime(self, client_id: UUID, runtime: TerminalRuntime) -> None:
        self._runtimes[client_id] = runtime

    def runtime_for(self, client_id: UUID) -> TerminalRuntime | None:
        return self._runtimes.get(client_id)

    async def subscribe(
        self,
        client_id: UUID,
        window_id: UUID,
        sender: TerminalSender,
        status_sender: TerminalStatusSender | None = None,
    ) -> None:
        existing_writers: list[_TerminalSubscriberWriter] = []
        writer = _TerminalSubscriberWriter(
            client_id=client_id,
            window_id=window_id,
            output_sender=sender,
            status_sender=status_sender,
            on_failure=self._handle_subscriber_writer_failure,
        )
        async with self._lock:
            key = (client_id, window_id)
            existing = self._subscribers.get(key, {}).get(sender)
            if existing is not None:
                existing_writers.append(existing)
            if status_sender is not None:
                existing_status = self._status_subscribers.get(key, {}).get(status_sender)
                if existing_status is not None and existing_status not in existing_writers:
                    existing_writers.append(existing_status)
            for existing_writer in existing_writers:
                self._remove_writer_locked(key, existing_writer)
            self._subscribers.setdefault(key, {})[sender] = writer
            if status_sender is not None:
                self._status_subscribers.setdefault(key, {})[status_sender] = writer
        for existing in existing_writers:
            await existing.close()

    async def unsubscribe(
        self,
        client_id: UUID,
        window_id: UUID,
        sender: TerminalSender,
        status_sender: TerminalStatusSender | None = None,
    ) -> None:
        key = (client_id, window_id)
        detach_task: asyncio.Task[None] | None = None
        writers_to_close: list[_TerminalSubscriberWriter] = []
        async with self._lock:
            writer = self._subscribers.get(key, {}).get(sender)
            if writer is not None:
                self._remove_writer_locked(key, writer)
                writers_to_close.append(writer)

            status_writer = (
                self._status_subscribers.get(key, {}).get(status_sender)
                if status_sender is not None
                else None
            )
            if status_writer is not None:
                self._remove_writer_locked(key, status_writer)
                if status_writer not in writers_to_close:
                    writers_to_close.append(status_writer)

            if key not in self._subscribers and key not in self._status_subscribers:
                self._subscribers.pop(key, None)
                self._status_subscribers.pop(key, None)
                runtime_window = self._attachments.pop(key, None)
                local_window_id = self._attachment_window_ids.pop(key, window_id)
                runtime = self._runtimes.get(client_id)
                if runtime_window is not None and runtime is not None:
                    detach_task = asyncio.create_task(
                        runtime.detach(
                            runtime_window,
                            local_window_id=local_window_id,
                            view_id=window_id,
                        )
                    )
                    self._detaches[key] = detach_task

        for writer in writers_to_close:
            await writer.close()

        if detach_task is not None:
            with contextlib.suppress(Exception):
                await detach_task
            async with self._lock:
                if self._detaches.get(key) is detach_task:
                    self._detaches.pop(key, None)

    async def publish_output(self, client_id: UUID, window_id: UUID, data: bytes) -> None:
        async with self._lock:
            writers = tuple(self._subscribers.get((client_id, window_id), {}).values())

        if not writers:
            return

        failed_writers: list[_TerminalSubscriberWriter] = []
        for writer in writers:
            if await writer.enqueue_output(data):
                continue
            failed_writers.append(writer)
            logger.warning(
                "broker dropping terminal output subscriber with full queue",
                extra={
                    "client_id": str(client_id),
                    "window_id": str(window_id),
                },
            )

        for writer in failed_writers:
            await self._drop_subscriber_writer(writer)

    async def publish_view_output(self, client_id: UUID, view_id: UUID, data: bytes) -> None:
        await self.publish_output(client_id, view_id, data)

    async def acknowledge_output(
        self,
        client_id: UUID,
        window_id: UUID,
        sender: TerminalSender,
        bytes_acked: int | None = None,
    ) -> None:
        async with self._lock:
            writer = self._subscribers.get((client_id, window_id), {}).get(sender)
        if writer is not None:
            await writer.output_ack(bytes_acked)

    async def publish_status(self, client_id: UUID, window_id: UUID, message: str) -> None:
        async with self._lock:
            writers = tuple(self._status_subscribers.get((client_id, window_id), {}).values())

        if not writers:
            return

        failed_writers: list[_TerminalSubscriberWriter] = []
        for writer in writers:
            if await writer.enqueue_status(message):
                continue
            failed_writers.append(writer)
            logger.warning(
                "broker dropping terminal status subscriber with full queue",
                extra={
                    "client_id": str(client_id),
                    "window_id": str(window_id),
                },
            )

        for writer in failed_writers:
            await self._drop_subscriber_writer(writer)

    async def clear_client(
        self,
        client_id: UUID,
        *,
        status_message: str | None = None,
    ) -> None:
        async with self._lock:
            for key in tuple(self._attachments):
                if key[0] == client_id:
                    self._attachments.pop(key, None)
                    self._attachment_window_ids.pop(key, None)
            subscriber_keys = [
                key for key in self._status_subscribers
                if key[0] == client_id and self._status_subscribers.get(key)
            ]

        if status_message is not None:
            for _, window_id in subscriber_keys:
                await self.publish_status(client_id, window_id, status_message)

    async def attach(
        self,
        client_id: UUID,
        window_id: UUID,
        runtime_window: RuntimeWindow,
        output_callback: TerminalSender | None = None,
        selection_callback: TerminalSelectionCallback | None = None,
        view_id: UUID | None = None,
    ) -> RuntimeWindow:
        runtime = self._require_runtime(client_id)
        attachment_id = view_id or window_id
        key = (client_id, attachment_id)
        while True:
            async with self._lock:
                existing_attachment = self._attachments.get(key)
                if existing_attachment is not None:
                    return existing_attachment
                detach_task = self._detaches.get(key)
            if detach_task is None:
                break
            with contextlib.suppress(Exception):
                await detach_task

        sender = output_callback or (lambda data: self.publish_output(client_id, attachment_id, data))
        attached_window = await runtime.attach(
            runtime_window,
            sender,
            local_window_id=window_id,
            selection_callback=selection_callback,
            view_id=attachment_id,
        )
        effective_runtime_window = attached_window or runtime_window
        async with self._lock:
            self._attachments[key] = effective_runtime_window
            self._attachment_window_ids[key] = window_id
        return effective_runtime_window

    async def send_input(
        self,
        client_id: UUID,
        window_id: UUID,
        runtime_window: RuntimeWindow,
        data: bytes,
        view_id: UUID | None = None,
    ) -> None:
        runtime = self._require_runtime(client_id)
        await runtime.send_input(
            runtime_window,
            data,
            local_window_id=window_id,
            view_id=view_id or window_id,
        )

    async def resize(
        self,
        client_id: UUID,
        window_id: UUID,
        runtime_window: RuntimeWindow,
        *,
        cols: int,
        rows: int,
        view_id: UUID | None = None,
    ) -> None:
        runtime = self._require_runtime(client_id)
        await runtime.resize(
            runtime_window,
            cols=cols,
            rows=rows,
            local_window_id=window_id,
            view_id=view_id or window_id,
        )

    async def select_window(
        self,
        client_id: UUID,
        view_id: UUID,
        current_window_id: UUID,
        current_runtime_window: RuntimeWindow,
        next_window_id: UUID,
        next_runtime_window: RuntimeWindow,
    ) -> RuntimeWindow:
        runtime = self._require_runtime(client_id)
        key = (client_id, view_id)
        selected_window = await runtime.select_window(
            current_runtime_window,
            next_runtime_window,
            local_window_id=next_window_id,
            view_id=view_id,
        )
        effective_runtime_window = selected_window or next_runtime_window
        async with self._lock:
            if key in self._attachments:
                self._attachments[key] = effective_runtime_window
                self._attachment_window_ids[key] = next_window_id
        return effective_runtime_window

    def _require_runtime(self, client_id: UUID) -> TerminalRuntime:
        runtime = self._runtimes.get(client_id)
        if runtime is None:
            raise TerminalRuntimeUnavailable(f"no terminal runtime registered for client: {client_id}")
        return runtime

    async def _handle_subscriber_writer_failure(
        self,
        writer: _TerminalSubscriberWriter,
        error: BaseException,
    ) -> None:
        if isinstance(error, asyncio.TimeoutError):
            logger.warning(
                "broker dropping terminal subscriber that timed out",
                extra={
                    "client_id": str(writer.client_id),
                    "window_id": str(writer.window_id),
                    "timeout_seconds": PUBLISH_OUTPUT_SUBSCRIBER_TIMEOUT_SECONDS,
                },
            )
        await self._drop_subscriber_writer(writer)

    async def _drop_subscriber_writer(self, writer: _TerminalSubscriberWriter) -> None:
        detach_task: asyncio.Task[None] | None = None
        async with self._lock:
            key = (writer.client_id, writer.window_id)
            self._remove_writer_locked(key, writer)

            if key not in self._subscribers and key not in self._status_subscribers:
                self._subscribers.pop(key, None)
                self._status_subscribers.pop(key, None)
                runtime_window = self._attachments.pop(key, None)
                local_window_id = self._attachment_window_ids.pop(key, writer.window_id)
                runtime = self._runtimes.get(writer.client_id)
                if runtime_window is not None and runtime is not None:
                    detach_task = asyncio.create_task(
                        runtime.detach(
                            runtime_window,
                            local_window_id=local_window_id,
                            view_id=writer.window_id,
                        )
                    )
                    self._detaches[key] = detach_task

        await writer.close()
        if detach_task is not None:
            with contextlib.suppress(Exception):
                await detach_task
            async with self._lock:
                key = (writer.client_id, writer.window_id)
                if self._detaches.get(key) is detach_task:
                    self._detaches.pop(key, None)

    def _remove_writer_locked(
        self,
        key: tuple[UUID, UUID],
        writer: _TerminalSubscriberWriter,
    ) -> None:
        subscribers = self._subscribers.get(key)
        if subscribers is not None:
            for sender, candidate in tuple(subscribers.items()):
                if candidate is writer:
                    subscribers.pop(sender, None)
            if not subscribers:
                self._subscribers.pop(key, None)

        status_subscribers = self._status_subscribers.get(key)
        if status_subscribers is not None:
            for sender, candidate in tuple(status_subscribers.items()):
                if candidate is writer:
                    status_subscribers.pop(sender, None)
            if not status_subscribers:
                self._status_subscribers.pop(key, None)
