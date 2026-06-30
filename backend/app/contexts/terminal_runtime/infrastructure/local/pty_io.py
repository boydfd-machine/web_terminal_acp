# ruff: noqa: F401,F821
"""Executed into the local runtime package globals."""

import asyncio
import contextlib
import logging
import os
import pty
import select
from uuid import UUID

from app.contexts.terminal_runtime.application.local_session import LocalTerminalSession as _LocalTerminalSession
from app.contexts.terminal_runtime.infrastructure.pty_control import (
    PTY_DRAIN_BUFFER_MAX_BYTES,
    PTY_FAST_INPUT_MAX_BYTES,
    PTY_READ_CHUNK_BYTES,
    list_file_entries_sync as _list_file_entries_sync,
    notify_process_window_change as _notify_process_window_change,
    read_file_bytes_sync as _read_file_bytes_sync,
    run_pty_control as _run_pty_control,
    write_all_pty_input as _write_all_pty_input,
    write_file_bytes_sync as _write_file_bytes_sync,
)
from app.contexts.terminal_runtime.domain.types import (
    RuntimeFileEntry,
    RuntimeWindow,
    TerminalSelectionCallback,
    TerminalSender,
)
from app.contexts.terminal_runtime.application.terminal_bridge import (
    ResizeControl,
    apply_pty_resize,
    attach_process_environment,
    configure_pty_slave,
)
from app.contexts.terminal_runtime.infrastructure.tmux_manager import TmuxManager, TmuxTarget, build_attach_command

logger = logging.getLogger(__name__)


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
