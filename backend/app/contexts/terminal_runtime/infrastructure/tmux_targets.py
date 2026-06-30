from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class TmuxTarget:
    session: str
    window_id: str
    window_index: str | None = None
    cwd: str | None = None
    shell_command: str | None = None
    local_window_id: UUID | str | None = None


@dataclass(frozen=True)
class TmuxAttachTarget:
    session: str


def build_attach_command(target: TmuxAttachTarget) -> list[str]:
    return ["tmux", "attach-session", "-t", target.session]
