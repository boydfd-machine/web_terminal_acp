from __future__ import annotations

import asyncio
import contextlib
import os
import select
import signal
from concurrent.futures import ThreadPoolExecutor
from functools import partial

from app.contexts.terminal_runtime.domain.types import RuntimeFileEntry

PTY_READ_CHUNK_BYTES = 65536
PTY_FAST_INPUT_MAX_BYTES = 256
PTY_CONTROL_EXECUTOR_MAX_WORKERS = 8
PTY_DRAIN_BUFFER_MAX_BYTES = 16 * 1024 * 1024
PTY_CONTROL_EXECUTOR = ThreadPoolExecutor(
    max_workers=PTY_CONTROL_EXECUTOR_MAX_WORKERS,
    thread_name_prefix="web-terminal-local-pty-control",
)


async def run_pty_control(func, /, *args, **kwargs):
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(
        PTY_CONTROL_EXECUTOR,
        partial(func, *args, **kwargs),
    )


def try_write_pty_input_immediately(master_fd: int, data: bytes) -> int:
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


def write_all_pty_input(master_fd: int, data: bytes) -> None:
    remaining = memoryview(data)
    while remaining:
        written = os.write(master_fd, remaining)
        if written <= 0:
            raise BlockingIOError("PTY input write made no progress")
        remaining = remaining[written:]


def notify_process_window_change(process: asyncio.subprocess.Process) -> None:
    if process.returncode is not None:
        return
    with contextlib.suppress(ProcessLookupError):
        process.send_signal(signal.SIGWINCH)


def read_file_bytes_sync(path: str, max_bytes: int | None) -> bytes:
    with open(path, "rb") as handle:
        if max_bytes is None or max_bytes <= 0:
            return handle.read()
        return handle.read(max_bytes + 1)


def list_file_entries_sync(path: str) -> list[RuntimeFileEntry]:
    entries: list[RuntimeFileEntry] = []
    with os.scandir(path) as iterator:
        for entry in iterator:
            try:
                stat_result = entry.stat(follow_symlinks=False)
                is_dir = entry.is_dir(follow_symlinks=False)
                is_file = entry.is_file(follow_symlinks=False)
            except OSError:
                continue
            if not is_dir and not is_file:
                continue
            entries.append(
                RuntimeFileEntry(
                    name=entry.name,
                    path=entry.path,
                    kind="directory" if is_dir else "file",
                    size=None if is_dir else stat_result.st_size,
                    mtime=stat_result.st_mtime,
                )
            )
    return sorted(entries, key=lambda item: (item.kind != "directory", item.name.lower(), item.name))


def write_file_bytes_sync(path: str, data: bytes, overwrite: bool) -> None:
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    flags = os.O_WRONLY | os.O_CREAT
    flags |= os.O_TRUNC if overwrite else os.O_EXCL
    fd = os.open(path, flags, 0o644)
    with os.fdopen(fd, "wb") as handle:
        handle.write(data)
