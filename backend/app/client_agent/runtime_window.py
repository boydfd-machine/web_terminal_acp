from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class ClientRuntimeWindow:
    remote_session_id: str
    remote_window_id: str
    local_window_id: UUID | None = None
    cwd: str | None = None
    shell_command: str | None = None
    managed_agent_tools: bool = False


@dataclass(frozen=True)
class ClientRuntimeWindowCreation:
    window: ClientRuntimeWindow
    created: bool


def parse_runtime_window_uuid(value: str) -> UUID | None:
    if not value:
        return None
    try:
        return UUID(value)
    except ValueError:
        return None
