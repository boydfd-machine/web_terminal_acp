from __future__ import annotations

import asyncio
import contextlib
from collections.abc import Awaitable


class ConnectionSupervisor:
    def __init__(self) -> None:
        self._tasks: dict[str, asyncio.Task] = {}

    def add_task(self, name: str, task: asyncio.Task) -> None:
        self._tasks[name] = task

    async def wait_with(
        self,
        awaitable: Awaitable,
        *,
        reconnect_message: str = "client-agent background task stopped",
    ):
        foreground = asyncio.create_task(awaitable)
        tasks = {foreground, *self._tasks.values()}
        try:
            done, _pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
            for name, task in self._tasks.items():
                if task in done:
                    await _cancel_or_consume_task(foreground)
                    await task
                    raise RuntimeError(f"{reconnect_message}: {name}")
            return await foreground
        finally:
            await _cancel_or_consume_task(foreground)

    def cancel_all(self) -> None:
        for task in self._tasks.values():
            task.cancel()

    def tasks(self) -> tuple[tuple[str, asyncio.Task], ...]:
        return tuple(self._tasks.items())


async def _cancel_or_consume_task(task: asyncio.Task) -> None:
    if not task.done():
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task
    elif not task.cancelled():
        with contextlib.suppress(Exception):
            task.exception()
