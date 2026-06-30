from __future__ import annotations

import asyncio
import contextlib
import fcntl
import logging
import os
import re
import select
import signal
import struct
import termios
import tty
from concurrent.futures import ThreadPoolExecutor
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from functools import partial
from uuid import UUID

Runner = Callable[[list[str]], Awaitable[str]]
TerminalSender = Callable[[bytes], Awaitable[None]]
SelectionSender = Callable[[UUID], Awaitable[None]]
DIRECT_INPUT_SUBMIT_DELAY_SECONDS = 0.1

logger = logging.getLogger(__name__)

PTY_READ_CHUNK_BYTES = 65536
PTY_OUTPUT_SEND_CHUNK_BYTES = 4 * 1024
PTY_FAST_INPUT_MAX_BYTES = 256
PTY_CONTROL_EXECUTOR_MAX_WORKERS = 8
SELECTION_POLL_INTERVAL_SECONDS = 0.25
# Maximum size of the in-memory coalescing buffer that decouples PTY reads from
# the bulk-writer sender. When the downstream send path back-pressures (slow
# server, slow bulk WebSocket, browser stall, ...), bytes accumulate here. The
# PTY itself is always drained so tmux keeps making forward progress and user
# input remains responsive. Beyond this limit the oldest bytes are dropped so a
# pathological burst cannot grow memory without bound; in practice this only
# triggers when the downstream is many MB behind, at which point the user can
# refresh the window to recover the live frame from tmux.
PTY_DRAIN_BUFFER_MAX_BYTES = 16 * 1024 * 1024
PTY_CONTROL_EXECUTOR = ThreadPoolExecutor(
    max_workers=PTY_CONTROL_EXECUTOR_MAX_WORKERS,
    thread_name_prefix="web-terminal-pty-control",
)


def _shadow_session_name(window_id: str, view_id: str | None = None) -> str:
    value = view_id or window_id
    sanitized = re.sub(r"[^A-Za-z0-9_-]", "_", value)
    return f"web_terminal_view_{sanitized}"


def _apply_pty_resize(master_fd: int, *, cols: int, rows: int) -> None:
    fcntl.ioctl(master_fd, termios.TIOCSWINSZ, struct.pack("HHHH", rows, cols, 0, 0))


def _notify_process_window_change(process: asyncio.subprocess.Process) -> None:
    if process.returncode is not None:
        return
    with contextlib.suppress(ProcessLookupError):
        process.send_signal(signal.SIGWINCH)


def _configure_pty_slave(slave_fd: int) -> None:
    tty.setraw(slave_fd, termios.TCSANOW)


def _attach_process_environment() -> dict[str, str]:
    return {**os.environ, "TERM": "xterm-256color"}


async def _run_pty_control(func, /, *args, **kwargs):
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(
        PTY_CONTROL_EXECUTOR,
        partial(func, *args, **kwargs),
    )


def _try_write_pty_input_immediately(master_fd: int, data: bytes) -> int:
    if not data or len(data) > PTY_FAST_INPUT_MAX_BYTES:
        return 0
    try:
        _, writable, _ = select.select([], [master_fd], [], 0)
    except (OSError, ValueError):
        return 0
    if not writable:
        return 0
    try:
        return os.write(master_fd, data)
    except (BlockingIOError, InterruptedError, OSError):
        return 0


def _write_all_pty_input(master_fd: int, data: bytes) -> None:
    remaining = memoryview(data)
    while remaining:
        written = os.write(master_fd, remaining)
        if written <= 0:
            raise BlockingIOError("PTY input write made no progress")
        remaining = remaining[written:]


@dataclass(frozen=True)
class _RemoteTarget:
    remote_session_id: str
    remote_window_id: str
    view_id: str | None = None

    @property
    def tmux_target(self) -> str:
        return f"{self.remote_session_id}:{self.remote_window_id}"

    @property
    def shadow_session(self) -> str:
        return _shadow_session_name(self.remote_window_id, self.view_id)


@dataclass
class _AttachedTerminal:
    master_fd: int
    process: asyncio.subprocess.Process
    shadow_session: str
    task: asyncio.Task[None] | None = None
    selection_task: asyncio.Task[None] | None = None
    cleanup_started: bool = False
    size: tuple[int, int] | None = None
    # Coalescing buffer that decouples the PTY read loop from the downstream
    # sender. The reader appends here without ever awaiting on the sender; the
    # drainer task copies the contents out (atomically, between awaits) and
    # forwards them via the bulk-writer. See `_pipe_output` for details.
    output_buffer: bytearray = field(default_factory=bytearray)
    output_event: asyncio.Event = field(default_factory=asyncio.Event)
    output_eof: bool = False
    reader_task: asyncio.Task[None] | None = None
    resize_task: asyncio.Task[None] | None = None


__all__ = [name for name in globals() if not name.startswith("__")]
