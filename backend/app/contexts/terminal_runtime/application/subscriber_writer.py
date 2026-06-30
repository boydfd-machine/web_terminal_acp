from __future__ import annotations

import asyncio
import contextlib
from collections import deque
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from uuid import UUID

from app.contexts.terminal_runtime.domain.types import TerminalSender

TerminalStatusSender = Callable[[str], Awaitable[None]]


@dataclass
class QueuedSubscriberMessage:
    payload: bytes | str
    size: int


class BaseTerminalSubscriberWriter:
    """Bounded per-browser writer queue for terminal output/status.

    This keeps remote/local runtime output readers from waiting on slow browser
    websocket sends while still bounding memory for dead or overloaded tabs.
    """

    def __init__(
        self,
        *,
        client_id: UUID,
        window_id: UUID,
        output_sender: TerminalSender,
        status_sender: TerminalStatusSender | None,
        on_failure: Callable[["BaseTerminalSubscriberWriter", BaseException], Awaitable[None]],
        send_timeout_seconds: float,
        max_bytes: int,
        max_messages: int,
        coalesce_bytes: int,
        ack_window_bytes: int,
    ) -> None:
        self.client_id = client_id
        self.window_id = window_id
        self.output_sender = output_sender
        self.status_sender = status_sender
        self._on_failure = on_failure
        self._send_timeout_seconds = send_timeout_seconds
        self._max_bytes = max_bytes
        self._max_messages = max_messages
        self._coalesce_bytes = coalesce_bytes
        self._ack_window_bytes = ack_window_bytes
        self._queue: deque[QueuedSubscriberMessage] = deque()
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
                self._queue.append(QueuedSubscriberMessage(payload=payload, size=size))
            self._queued_bytes += size
            self._condition.notify()
        self.start()
        return True

    def _shed_queued_byte_output_locked(self) -> int:
        if not self._queue:
            return 0
        kept: deque[QueuedSubscriberMessage] = deque()
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

    async def _next_message(self) -> QueuedSubscriberMessage | None:
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
                message = QueuedSubscriberMessage(payload=head, size=len(head))
                self._queue.appendleft(QueuedSubscriberMessage(payload=tail, size=len(tail)))
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
