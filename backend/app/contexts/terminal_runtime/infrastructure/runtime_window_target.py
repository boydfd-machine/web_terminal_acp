from __future__ import annotations

from app.contexts.terminal_runtime.domain.types import RuntimeWindow
from app.contexts.terminal_runtime.infrastructure.tmux_targets import TmuxTarget


def tmux_target_for_runtime_window(window: RuntimeWindow) -> TmuxTarget:
    return TmuxTarget(
        session=window.session_id,
        window_id=window.window_id,
        window_index=window.window_index,
        cwd=window.cwd,
        shell_command=window.shell_command,
    )
