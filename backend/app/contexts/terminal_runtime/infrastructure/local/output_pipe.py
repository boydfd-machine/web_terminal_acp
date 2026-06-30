from __future__ import annotations

import asyncio
import contextlib
import logging
import os
from collections.abc import Awaitable, Callable

from app.contexts.terminal_runtime.application.local_session import (
    LocalTerminalSession as _LocalTerminalSession,
)
from app.contexts.terminal_runtime.domain.types import TerminalSender
from app.contexts.terminal_runtime.infrastructure.pty_control import (
    PTY_DRAIN_BUFFER_MAX_BYTES,
    PTY_READ_CHUNK_BYTES,
)

logger = logging.getLogger(__name__)


async def pipe_terminal_output(
    key: tuple[str, str],
    session: _LocalTerminalSession,
    sender: TerminalSender,
    cleanup_session: Callable[[tuple[str, str], _LocalTerminalSession], Awaitable[None]],
) -> None:
    session.output_eof = False
    session.output_event.clear()
    session.output_buffer.clear()
    loop = asyncio.get_running_loop()
    reader_installed = False

    def read_ready() -> None:
        while True:
            try:
                data = os.read(session.master_fd, PTY_READ_CHUNK_BYTES)
            except BlockingIOError:
                return
            except OSError:
                session.output_eof = True
                session.output_event.set()
                return
            if not data:
                session.output_eof = True
                session.output_event.set()
                return
            _append_output_chunk(key, session, data)

    try:
        os.set_blocking(session.master_fd, False)
        loop.add_reader(session.master_fd, read_ready)
        reader_installed = True
    except (AttributeError, NotImplementedError, OSError):
        with contextlib.suppress(OSError):
            os.set_blocking(session.master_fd, True)
        reader_installed = False

    reader_task = None if reader_installed else asyncio.create_task(_reader_loop(key, session))
    session.reader_task = reader_task
    try:
        while True:
            if session.output_buffer:
                chunk = bytes(session.output_buffer)
                session.output_buffer.clear()
                try:
                    await sender(chunk)
                except Exception:
                    logger.exception("terminal output sender failed")
                    return
                continue
            if session.output_eof:
                return
            session.output_event.clear()
            if session.output_buffer or session.output_eof:
                continue
            await session.output_event.wait()
    finally:
        if reader_installed:
            loop.remove_reader(session.master_fd)
        if reader_task is not None and not reader_task.done():
            reader_task.cancel()
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await reader_task
        session.reader_task = None
        await cleanup_session(key, session)


async def _reader_loop(key: tuple[str, str], session: _LocalTerminalSession) -> None:
    try:
        while True:
            try:
                data = await asyncio.to_thread(
                    os.read,
                    session.master_fd,
                    PTY_READ_CHUNK_BYTES,
                )
            except OSError:
                return
            if not data:
                return
            _append_output_chunk(key, session, data)
    finally:
        session.output_eof = True
        session.output_event.set()


def _append_output_chunk(
    key: tuple[str, str],
    session: _LocalTerminalSession,
    data: bytes,
) -> None:
    session.output_buffer.extend(data)
    if len(session.output_buffer) > PTY_DRAIN_BUFFER_MAX_BYTES:
        overflow = len(session.output_buffer) - PTY_DRAIN_BUFFER_MAX_BYTES
        del session.output_buffer[:overflow]
        logger.warning(
            "local terminal PTY output buffer overflowed; dropped oldest bytes",
            extra={
                "session_id": key[0],
                "view_id": key[1],
                "dropped_bytes": overflow,
                "buffer_bytes": len(session.output_buffer),
            },
        )
    session.output_event.set()


__all__ = [name for name in globals() if not name.startswith("__")]
