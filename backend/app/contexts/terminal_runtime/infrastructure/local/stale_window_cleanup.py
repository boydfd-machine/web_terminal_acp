from __future__ import annotations

import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from app.config import get_settings
from app.contexts.terminal_runtime.domain.types import RuntimeWindow
from app.contexts.terminal_runtime.infrastructure.tmux_manager import TmuxCommandError
from app.contexts.terminal_runtime.infrastructure.tmux_targets import TmuxTarget

Clock = Callable[[], float]
RetainWindowCheck = Callable[[object], Awaitable[bool]]


@dataclass(frozen=True)
class StaleWindowCleanupPolicy:
    cleanup_seconds: float
    clock: Clock = time.time
    retain_window: RetainWindowCheck | None = None

    @classmethod
    def from_settings(
        cls,
        *,
        cleanup_seconds: float | None = None,
        clock: Clock | None = None,
        retain_window: RetainWindowCheck | None = None,
    ) -> "StaleWindowCleanupPolicy":
        settings_seconds = get_settings().tmux_window_inactive_cleanup_seconds
        return cls(
            cleanup_seconds=settings_seconds if cleanup_seconds is None else cleanup_seconds,
            clock=clock or time.time,
            retain_window=retain_window,
        )

    async def should_recreate(
        self,
        tmux_manager: object,
        target: TmuxTarget,
        *,
        local_window_id: object | None,
    ) -> bool:
        if self.cleanup_seconds <= 0:
            return False
        activity_timestamp = await tmux_window_activity_timestamp(tmux_manager, target)
        if activity_timestamp is None:
            return False
        if self.clock() - activity_timestamp < self.cleanup_seconds:
            return False
        if local_window_id is not None and self.retain_window is not None:
            return not await self.retain_window(local_window_id)
        return True


async def ensure_local_runtime_window(
    tmux_manager: object,
    policy: StaleWindowCleanupPolicy,
    window: RuntimeWindow,
    *,
    local_window_id: object | None,
) -> RuntimeWindow:
    target = TmuxTarget(
        session=window.session_id,
        window_id=window.window_id,
        cwd=window.cwd,
        shell_command=window.shell_command,
    )
    if await tmux_manager.has_window(target):
        if local_window_id is None or not await policy.should_recreate(
            tmux_manager,
            target,
            local_window_id=local_window_id,
        ):
            return await _with_tmux_window_index(tmux_manager, target, window)
        await tmux_manager.kill_window(_target_with_local_window_id(target, local_window_id))
    elif local_window_id is None:
        raise RuntimeError(f"terminal window is missing: {window.session_id}:{window.window_id}")

    recreated = await tmux_manager.recreate_window(target, local_window_id=local_window_id)
    return RuntimeWindow(
        session_id=recreated.session,
        window_id=recreated.window_id,
        window_index=getattr(recreated, "window_index", None),
        cwd=recreated.cwd,
        shell_command=recreated.shell_command,
    )


async def _with_tmux_window_index(
    tmux_manager: object,
    target: TmuxTarget,
    window: RuntimeWindow,
) -> RuntimeWindow:
    if window.window_index is not None:
        return window
    index_reader = getattr(tmux_manager, "window_index", None)
    if not callable(index_reader):
        return window
    window_index = await index_reader(target)
    if window_index is None:
        return window
    return RuntimeWindow(
        session_id=window.session_id,
        window_id=window.window_id,
        window_index=window_index,
        cwd=window.cwd,
        shell_command=window.shell_command,
    )


async def tmux_window_activity_timestamp(tmux_manager: object, target: TmuxTarget) -> float | None:
    activity_reader = getattr(tmux_manager, "window_activity_timestamp", None)
    if callable(activity_reader):
        return await activity_reader(target)
    run = getattr(tmux_manager, "_run", None)
    if not callable(run):
        return None
    try:
        timestamp = (
            await run([
                "tmux",
                "display-message",
                "-p",
                "-t",
                f"{target.session}:{target.window_id}",
                "#{window_activity}",
            ])
        ).strip()
    except TmuxCommandError:
        return None
    try:
        return float(timestamp)
    except ValueError:
        return None


def _target_with_local_window_id(target: TmuxTarget, local_window_id: object) -> TmuxTarget:
    return TmuxTarget(
        session=target.session,
        window_id=target.window_id,
        window_index=target.window_index,
        cwd=target.cwd,
        shell_command=target.shell_command,
        local_window_id=local_window_id,
    )
