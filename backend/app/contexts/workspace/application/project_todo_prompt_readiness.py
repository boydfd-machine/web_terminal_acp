from __future__ import annotations

import asyncio
import contextlib
import logging
import time
from collections.abc import Awaitable, Callable

from app.contexts.terminal_runtime.application.agent_prompt_input import (
    AGENT_PROMPT_MARKERS_BY_PROVIDER,
    GENERIC_AGENT_PROMPT_MARKERS,
    normalize_terminal_text,
    terminal_has_prompt_marker,
)

PROJECT_TODO_AGENT_READY_TIMEOUT_SECONDS = 90.0
PROJECT_TODO_AGENT_READY_SETTLE_SECONDS = 0.2
PROJECT_TODO_AGENT_READY_CAPTURE_INTERVAL_SECONDS = 0.5
PROJECT_TODO_OUTPUT_MAX_BYTES = 512 * 1024

logger = logging.getLogger(__name__)


class PromptOutputCollector:
    def __init__(self) -> None:
        self._buffer = bytearray()
        self._updated = asyncio.Event()
        self._last_snapshot: bytes | None = None

    async def feed(self, data: bytes) -> None:
        if not data:
            return
        self._buffer.extend(data)
        if len(self._buffer) > PROJECT_TODO_OUTPUT_MAX_BYTES:
            del self._buffer[: len(self._buffer) - PROJECT_TODO_OUTPUT_MAX_BYTES]
        self._updated.set()

    async def feed_snapshot(self, data: bytes) -> None:
        if not data or self._buffer.endswith(data):
            if data:
                self._last_snapshot = data
            return
        self._last_snapshot = data
        await self.feed(data)

    async def wait_for_update(self, timeout_seconds: float) -> None:
        self._updated.clear()
        with contextlib.suppress(asyncio.TimeoutError):
            await asyncio.wait_for(self._updated.wait(), timeout=timeout_seconds)

    def text(self) -> str:
        return self._buffer.decode("utf-8", errors="replace")

    def last_snapshot(self) -> bytes | None:
        return self._last_snapshot


async def wait_until_agent_ready(
    provider: str | None,
    collector: PromptOutputCollector,
    *,
    capture_output: Callable[[], Awaitable[bytes]] | None,
) -> None:
    deadline = time.monotonic() + PROJECT_TODO_AGENT_READY_TIMEOUT_SECONDS
    last_capture_at = 0.0
    while True:
        if agent_terminal_is_ready(provider, collector.text()):
            return
        now = time.monotonic()
        if capture_output is not None and now - last_capture_at >= PROJECT_TODO_AGENT_READY_CAPTURE_INTERVAL_SECONDS:
            last_capture_at = now
            await feed_ready_capture(collector, capture_output)
            continue
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError(
                f"terminal output did not match within {PROJECT_TODO_AGENT_READY_TIMEOUT_SECONDS:g} seconds"
            )
        await collector.wait_for_update(min(remaining, PROJECT_TODO_AGENT_READY_CAPTURE_INTERVAL_SECONDS))


async def feed_ready_capture(
    collector: PromptOutputCollector,
    capture_output: Callable[[], Awaitable[bytes]],
) -> None:
    try:
        snapshot = await capture_output()
    except Exception:
        logger.debug("project todo readiness capture failed", exc_info=True)
        return
    if snapshot:
        await collector.feed_snapshot(snapshot)


def agent_terminal_is_ready(provider: str | None, output: str) -> bool:
    text = normalize_terminal_text(output)
    if provider == "codex":
        return ("OpenAI Codex" in text or ">_ Codex" in text) and terminal_has_prompt_marker(
            text,
            AGENT_PROMPT_MARKERS_BY_PROVIDER["codex"],
        )
    if provider == "claude_code":
        return "Claude Code" in text and terminal_has_prompt_marker(
            text,
            AGENT_PROMPT_MARKERS_BY_PROVIDER["claude_code"],
        )
    if provider == "cursor_cli":
        return (
            any(label in text for label in ("Cursor Agent", "Cursor CLI", "cursor-agent"))
            and terminal_has_prompt_marker(text, AGENT_PROMPT_MARKERS_BY_PROVIDER["cursor_cli"])
        )
    if provider == "antigravity_cli":
        return "Antigravity" in text and terminal_has_prompt_marker(
            text,
            AGENT_PROMPT_MARKERS_BY_PROVIDER["antigravity_cli"],
        )
    return terminal_has_prompt_marker(text, GENERIC_AGENT_PROMPT_MARKERS)
