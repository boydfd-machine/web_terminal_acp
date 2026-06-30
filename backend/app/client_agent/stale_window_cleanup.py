from __future__ import annotations

import asyncio
import contextlib
import heapq
import inspect
import logging
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from uuid import UUID

from app.client_agent.runtime_window import ClientRuntimeWindow

DEFAULT_STALE_WINDOW_CLEANUP_SECONDS = 3 * 60 * 60
DEFAULT_RETAIN_RECENT_LIMIT = 50
MAX_CLEANUP_SLEEP_SECONDS = 60.0

KillWindow = Callable[[UUID], Awaitable[None] | None]
Clock = Callable[[], float]
Sleep = Callable[[float], Awaitable[object]]

logger = logging.getLogger(__name__)


@dataclass
class _TrackedWindow:
    runtime_window: ClientRuntimeWindow
    last_activity_at: float
    deadline_at: float
    attached_count: int = 0


class ClientStaleWindowCleanup:
    def __init__(
        self,
        *,
        cleanup_seconds: float = DEFAULT_STALE_WINDOW_CLEANUP_SECONDS,
        retain_recent_limit: int = DEFAULT_RETAIN_RECENT_LIMIT,
        clock: Clock | None = None,
        kill_window: KillWindow,
        sleep: Sleep | None = None,
    ) -> None:
        self._cleanup_seconds = cleanup_seconds
        self._retain_recent_limit = max(0, retain_recent_limit)
        self._clock = clock or time.time
        self._kill_window = kill_window
        self._sleep = sleep or asyncio.sleep
        self._windows: dict[UUID, _TrackedWindow] = {}
        self._deadlines: list[tuple[float, int, UUID]] = []
        self._sequence = 0
        self._wakeup = asyncio.Event()
        self._task: asyncio.Task[None] | None = None
        self._closed = False

    def register_window(
        self,
        window_id: UUID,
        runtime_window: ClientRuntimeWindow,
        *,
        activity_at: float | None = None,
    ) -> None:
        at = self._activity_time(activity_at)
        existing = self._windows.get(window_id)
        attached_count = existing.attached_count if existing is not None else 0
        self._windows[window_id] = _TrackedWindow(
            runtime_window=runtime_window,
            last_activity_at=at,
            deadline_at=at + self._cleanup_seconds,
            attached_count=attached_count,
        )
        self._push_deadline(window_id)

    def unregister_window(self, window_id: UUID) -> None:
        self._windows.pop(window_id, None)
        self._wakeup.set()

    def touch_window(self, window_id: UUID, *, activity_at: float | None = None) -> None:
        tracked = self._windows.get(window_id)
        if tracked is None:
            return
        at = self._activity_time(activity_at)
        if at < tracked.last_activity_at:
            at = tracked.last_activity_at
        tracked.last_activity_at = at
        tracked.deadline_at = at + self._cleanup_seconds
        self._push_deadline(window_id)

    def attach_view(self, window_id: UUID) -> None:
        tracked = self._windows.get(window_id)
        if tracked is None:
            return
        tracked.attached_count += 1

    def detach_view(self, window_id: UUID) -> None:
        tracked = self._windows.get(window_id)
        if tracked is None:
            return
        tracked.attached_count = max(0, tracked.attached_count - 1)
        now = self._clock()
        if tracked.attached_count == 0 and tracked.last_activity_at + self._cleanup_seconds <= now:
            tracked.deadline_at = now
            self._push_deadline(window_id)
            return
        self._wakeup.set()

    def is_registered(self, window_id: UUID) -> bool:
        return window_id in self._windows

    def start(self) -> asyncio.Task[None]:
        if self._closed:
            raise RuntimeError("client stale window cleanup is closed")
        if self._task is None or self._task.done():
            self._task = asyncio.create_task(self._run())
        return self._task

    def close(self) -> None:
        self._closed = True
        self._wakeup.set()
        if self._task is not None:
            self._task.cancel()

    def next_delay(self) -> float | None:
        self._discard_stale_deadlines()
        if not self._deadlines:
            return None
        return max(0.0, self._deadlines[0][0] - self._clock())

    async def drain_expired(self) -> None:
        if self._cleanup_seconds <= 0:
            return
        now = self._clock()
        retained_window_ids = self._recently_active_window_ids()
        while True:
            self._discard_stale_deadlines()
            if not self._deadlines or self._deadlines[0][0] > now:
                return
            _deadline, _sequence, window_id = heapq.heappop(self._deadlines)
            tracked = self._windows.get(window_id)
            if tracked is None or tracked.deadline_at > now:
                continue
            if window_id in retained_window_ids or tracked.attached_count > 0:
                tracked.deadline_at = now + MAX_CLEANUP_SLEEP_SECONDS
                self._push_deadline(window_id)
                continue
            self._windows.pop(window_id, None)
            try:
                result = self._kill_window(window_id)
                if inspect.isawaitable(result):
                    await result
            except Exception:
                logger.exception("client-agent stale tmux window cleanup failed", extra={"window_id": str(window_id)})

    def _activity_time(self, activity_at: float | None) -> float:
        return self._clock() if activity_at is None else activity_at

    def _push_deadline(self, window_id: UUID) -> None:
        tracked = self._windows[window_id]
        self._sequence += 1
        heapq.heappush(self._deadlines, (tracked.deadline_at, self._sequence, window_id))
        self._wakeup.set()

    def _discard_stale_deadlines(self) -> None:
        while self._deadlines:
            deadline, _sequence, window_id = self._deadlines[0]
            tracked = self._windows.get(window_id)
            if tracked is not None and tracked.deadline_at == deadline:
                return
            heapq.heappop(self._deadlines)

    def _recently_active_window_ids(self) -> set[UUID]:
        if self._retain_recent_limit <= 0:
            return set()
        ordered = sorted(
            self._windows.items(),
            key=lambda item: item[1].last_activity_at,
            reverse=True,
        )
        return {window_id for window_id, _tracked in ordered[: self._retain_recent_limit]}

    async def _run(self) -> None:
        while True:
            await self.drain_expired()
            delay = self.next_delay()
            self._wakeup.clear()
            if delay is None:
                await self._wakeup.wait()
                continue
            await self._wait_for_wakeup_or_delay(min(delay, MAX_CLEANUP_SLEEP_SECONDS))

    async def _wait_for_wakeup_or_delay(self, delay: float) -> None:
        sleep_task = asyncio.create_task(self._sleep(delay))
        wakeup_task = asyncio.create_task(self._wakeup.wait())
        try:
            await asyncio.wait(
                {sleep_task, wakeup_task},
                return_when=asyncio.FIRST_COMPLETED,
            )
        finally:
            for task in (sleep_task, wakeup_task):
                if not task.done():
                    task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await task
