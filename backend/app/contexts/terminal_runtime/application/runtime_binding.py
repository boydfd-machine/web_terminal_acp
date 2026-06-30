from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Literal

from app.models import VirtualWindow
from app.contexts.terminal_runtime.domain.types import RuntimeWindow

RuntimeWindowScope = Literal["local", "remote"]


@dataclass(frozen=True)
class RuntimeWindowBinding:
    runtime_window: RuntimeWindow
    scope: RuntimeWindowScope

    @classmethod
    def from_virtual_window(cls, window: VirtualWindow) -> "RuntimeWindowBinding | None":
        if window.tmux_session is not None and window.tmux_window_id is not None:
            return cls(
                RuntimeWindow(
                    session_id=window.tmux_session,
                    window_id=window.tmux_window_id,
                    window_index=window.tmux_window_index,
                    cwd=window.cwd,
                    shell_command=window.shell_command,
                ),
                "local",
            )
        if window.remote_session_id is not None and window.remote_window_id is not None:
            return cls(
                RuntimeWindow(
                    session_id=window.remote_session_id,
                    window_id=window.remote_window_id,
                    cwd=window.cwd,
                    shell_command=window.shell_command,
                ),
                "remote",
            )
        return None

    @property
    def is_local_window(self) -> bool:
        return self.scope == "local"

    @property
    def is_remote_window(self) -> bool:
        return self.scope == "remote"

    def with_runtime_window(self, runtime_window: RuntimeWindow) -> "RuntimeWindowBinding":
        return replace(self, runtime_window=runtime_window)

    def runtime_persistence_fields(self) -> dict[str, str | None]:
        if self.is_local_window:
            return {
                "tmux_session": self.runtime_window.session_id,
                "tmux_window_id": self.runtime_window.window_id,
                "tmux_window_index": self.runtime_window.window_index,
                "remote_session_id": None,
                "remote_window_id": None,
                "cwd": self.runtime_window.cwd,
                "shell_command": self.runtime_window.shell_command,
            }
        return {
            "tmux_session": None,
            "tmux_window_id": None,
            "tmux_window_index": None,
            "remote_session_id": self.runtime_window.session_id,
            "remote_window_id": self.runtime_window.window_id,
            "cwd": self.runtime_window.cwd,
            "shell_command": self.runtime_window.shell_command,
        }
