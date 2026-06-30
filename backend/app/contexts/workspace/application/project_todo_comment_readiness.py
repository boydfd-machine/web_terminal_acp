from __future__ import annotations

import asyncio
import logging
import re
import shlex
import time
from collections.abc import Awaitable, Callable

from app.client_agent.agent_commands import agent_command_for_interactive_shell
from app.contexts.terminal_runtime.application.agent_prompt_input import (
    AGENT_PROMPT_MARKERS_BY_PROVIDER,
    agent_provider_for_prompt as _agent_provider_for_prompt,
    line_has_prompt_marker as _line_has_prompt_marker,
    looks_like_agent_command,
    normalize_terminal_text as _normalize_terminal_text,
)
from app.contexts.workspace.application.project_todo_prompt_readiness import (
    PROJECT_TODO_AGENT_READY_CAPTURE_INTERVAL_SECONDS,
    PROJECT_TODO_AGENT_READY_SETTLE_SECONDS,
    PROJECT_TODO_AGENT_READY_TIMEOUT_SECONDS,
    PromptOutputCollector as _PromptOutputCollector,
    agent_terminal_is_ready as _agent_terminal_is_ready,
)

logger = logging.getLogger(__name__)

_SHELL_PROMPT_PATTERNS = (
    re.compile(r"^\u279c\s+"),
    re.compile(r".+\s+git:\([^)]+\).*$"),
    re.compile(r"^[\w.-]+@[\w.-]+:.*[$#]\s*$"),
    re.compile(r"^(?:[$#]|%)\s*$"),
)
async def wait_for_comment_agent_terminal_ready(
    *,
    prompt_shell_command: str | None,
    collector: _PromptOutputCollector,
    capture_output: Callable[[], Awaitable[bytes]],
    relaunch_agent: Callable[[], Awaitable[None]],
) -> None:
    if not prompt_shell_command or not looks_like_agent_command(prompt_shell_command):
        return

    provider = _agent_provider_for_prompt(prompt_shell_command)
    await _feed_comment_ready_capture(collector, capture_output)
    if _comment_agent_should_relaunch(provider, collector.text()):
        await relaunch_agent()
        collector = _PromptOutputCollector()

    try:
        await _wait_until_comment_agent_ready(provider, collector, capture_output=capture_output)
    except TimeoutError:
        if not _comment_agent_should_relaunch(provider, collector.text()):
            raise
        await relaunch_agent()
        await _wait_until_comment_agent_ready(
            provider,
            _PromptOutputCollector(),
            capture_output=capture_output,
        )
    await asyncio.sleep(PROJECT_TODO_AGENT_READY_SETTLE_SECONDS)


def comment_agent_relaunch_bytes(prompt_shell_command: str | None, *, cwd: str | None) -> bytes:
    if not prompt_shell_command:
        return b""
    command = agent_command_for_interactive_shell(prompt_shell_command) or prompt_shell_command
    if cwd:
        command = f"cd {shlex.quote(cwd)} && {command}"
    return command.encode("utf-8") + b"\n"


async def _wait_until_comment_agent_ready(
    provider: str | None,
    collector: _PromptOutputCollector,
    *,
    capture_output: Callable[[], Awaitable[bytes]],
) -> None:
    deadline = time.monotonic() + PROJECT_TODO_AGENT_READY_TIMEOUT_SECONDS
    last_capture_at = 0.0
    while True:
        if _comment_agent_is_current_prompt(provider, collector.text()):
            return
        now = time.monotonic()
        if now - last_capture_at >= PROJECT_TODO_AGENT_READY_CAPTURE_INTERVAL_SECONDS:
            last_capture_at = now
            await _feed_comment_ready_capture(collector, capture_output)
            continue
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError(
                f"terminal output did not match within {PROJECT_TODO_AGENT_READY_TIMEOUT_SECONDS:g} seconds"
            )
        await collector.wait_for_update(min(remaining, PROJECT_TODO_AGENT_READY_CAPTURE_INTERVAL_SECONDS))


async def _feed_comment_ready_capture(
    collector: _PromptOutputCollector,
    capture_output: Callable[[], Awaitable[bytes]],
) -> None:
    try:
        snapshot = await capture_output()
    except Exception:
        logger.debug("project todo comment readiness capture failed", exc_info=True)
        return
    if snapshot:
        await collector.feed_snapshot(snapshot)


def _comment_agent_should_relaunch(provider: str | None, output: str) -> bool:
    tail = _terminal_tail(output)
    return _latest_prompt_is_shell(provider, tail) or (
        not _agent_terminal_is_ready(provider, tail) and _terminal_looks_like_shell_prompt(tail)
    )


def _comment_agent_is_current_prompt(provider: str | None, output: str) -> bool:
    tail = _terminal_tail(output)
    return _latest_prompt_is_agent(provider, tail) or (
        _agent_terminal_is_ready(provider, tail) and not _latest_prompt_is_shell(provider, tail)
    )


def _terminal_looks_like_shell_prompt(output: str) -> bool:
    return any(any(pattern.match(line) for pattern in _SHELL_PROMPT_PATTERNS) for line in _terminal_tail_lines(output))


def _latest_prompt_is_shell(provider: str | None, output: str) -> bool:
    return _latest_prompt_kind(provider, output) == "shell"


def _latest_prompt_is_agent(provider: str | None, output: str) -> bool:
    return _latest_prompt_kind(provider, output) == "agent"


def _latest_prompt_kind(provider: str | None, output: str) -> str | None:
    agent_markers = AGENT_PROMPT_MARKERS_BY_PROVIDER.get(provider, (">", "\u203a", "\u276f"))
    for line in reversed(_terminal_tail_lines(output)):
        if any(pattern.match(line) for pattern in _SHELL_PROMPT_PATTERNS):
            return "shell"
        if any(_line_has_prompt_marker(line, marker) for marker in agent_markers):
            return "agent"
    return None


def _terminal_tail(output: str, *, line_count: int = 20) -> str:
    return "\n".join(_terminal_tail_lines(output, line_count=line_count))


def _terminal_tail_lines(output: str, *, line_count: int = 20) -> list[str]:
    lines = [line.strip() for line in _normalize_terminal_text(output).splitlines() if line.strip()]
    return lines[-line_count:]
