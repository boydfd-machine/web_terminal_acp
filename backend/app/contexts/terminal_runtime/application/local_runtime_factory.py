from __future__ import annotations

from app.contexts.terminal_runtime.application.stale_window_protection import (
    SessionFactory,
    recent_active_tmux_window_retain_check,
)
from app.contexts.terminal_runtime.infrastructure.local import LocalTerminalRuntime
from app.contexts.terminal_runtime.infrastructure.tmux_manager import TmuxManager


def create_local_terminal_runtime(
    tmux_manager: TmuxManager,
    *,
    session_factory: SessionFactory,
) -> LocalTerminalRuntime:
    return LocalTerminalRuntime(
        tmux_manager,
        stale_window_retain_check=recent_active_tmux_window_retain_check(session_factory),
    )
