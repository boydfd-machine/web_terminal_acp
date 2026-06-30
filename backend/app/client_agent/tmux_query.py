from __future__ import annotations

import re
from collections.abc import Awaitable, Callable

Runner = Callable[[list[str]], Awaitable[str]]


async def tmux_has_window(
    run: Runner,
    session_id: str,
    remote_window_id: str,
) -> bool:
    try:
        window_id = (
            await run(
                [
                    "tmux",
                    "display-message",
                    "-p",
                    "-t",
                    f"{session_id}:{remote_window_id}",
                    "#{window_id}",
                ]
            )
        ).strip()
    except RuntimeError:
        return False
    return window_id == remote_window_id


async def tmux_window_activity_timestamp(
    run: Runner,
    session_id: str,
    remote_window_id: str,
) -> float | None:
    try:
        timestamp = (
            await run(
                [
                    "tmux",
                    "display-message",
                    "-p",
                    "-t",
                    f"{session_id}:{remote_window_id}",
                    "#{window_activity}",
                ]
            )
        ).strip()
    except RuntimeError:
        return None
    try:
        return float(timestamp)
    except ValueError:
        return None


def is_missing_tmux_window_error(exc: BaseException, remote_window_id: str) -> bool:
    message = str(exc)
    return (
        f"can't find window: {remote_window_id}" in message
        or re.search(r"can't find window: @\d+", message) is not None
    )
