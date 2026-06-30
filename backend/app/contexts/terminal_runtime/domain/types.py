from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Literal, Protocol
from uuid import UUID

TerminalSender = Callable[[bytes], Awaitable[None]]


@dataclass(frozen=True)
class RuntimeWindow:
    session_id: str
    window_id: str
    window_index: str | None = None
    cwd: str | None = None
    shell_command: str | None = None


@dataclass(frozen=True)
class RuntimeFileEntry:
    name: str
    path: str
    kind: Literal["file", "directory"]
    size: int | None = None
    mtime: float | None = None


TerminalSelectionCallback = Callable[[RuntimeWindow], Awaitable[None]]


class TerminalRuntime(Protocol):
    async def create_window(
        self,
        cwd: str | None = None,
        shell_command: str | None = None,
        *,
        window_id: object | None = None,
        agent_ops_token: str | None = None,
    ) -> RuntimeWindow:
        """Create a terminal window in this runtime."""

    async def attach(
        self,
        window: RuntimeWindow,
        sender: TerminalSender,
        *,
        local_window_id: object | None = None,
        selection_callback: TerminalSelectionCallback | None = None,
        view_id: UUID | str | None = None,
        allow_missing_window_recreate: bool = False,
    ) -> RuntimeWindow | None:
        """Attach runtime output for a window to a sender."""

    async def detach(
        self,
        window: RuntimeWindow,
        *,
        local_window_id: object | None = None,
        view_id: UUID | str | None = None,
    ) -> None:
        """Detach runtime output and clean up resources for a window."""

    async def send_input(
        self,
        window: RuntimeWindow,
        data: bytes,
        *,
        local_window_id: object | None = None,
        view_id: UUID | str | None = None,
    ) -> None:
        """Send terminal input bytes to a runtime window."""

    async def send_input_direct(
        self,
        window: RuntimeWindow,
        data: bytes,
        *,
        local_window_id: object | None = None,
    ) -> None:
        """Send input bytes directly to the base runtime window."""

    async def resize(
        self,
        window: RuntimeWindow,
        *,
        cols: int,
        rows: int,
        local_window_id: object | None = None,
        view_id: UUID | str | None = None,
    ) -> None:
        """Resize a runtime window."""

    async def capture_output_bytes(
        self,
        window: RuntimeWindow,
        *,
        local_window_id: object | None = None,
        view_id: UUID | str | None = None,
        history_lines: int | None = None,
    ) -> bytes:
        """Capture the current visible terminal output for a runtime window."""

    async def read_file_bytes(self, path: str, *, max_bytes: int | None = None) -> bytes:
        """Read a file from the runtime host."""

    async def list_file_entries(self, path: str) -> list[RuntimeFileEntry]:
        """List direct child entries from a directory on the runtime host."""

    async def write_file_bytes(self, path: str, data: bytes, *, overwrite: bool = True) -> None:
        """Write file bytes on the runtime host."""

    async def select_window(
        self,
        current_window: RuntimeWindow,
        next_window: RuntimeWindow,
        *,
        local_window_id: object,
        view_id: UUID | str | None = None,
        allow_missing_window_recreate: bool = False,
    ) -> RuntimeWindow | None:
        """Switch an existing runtime view to another window."""
