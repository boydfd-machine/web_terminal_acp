from __future__ import annotations

import asyncio
import contextlib
import logging
import os
import pty
from uuid import UUID

from app.contexts.terminal_runtime.application.local_session import (
    LocalTerminalSession as _LocalTerminalSession,
)
from app.contexts.terminal_runtime.application.terminal_bridge import (
    ResizeControl,
    apply_pty_resize,
    attach_process_environment,
    configure_pty_slave,
)
from app.contexts.terminal_runtime.domain.types import (
    RuntimeFileEntry,
    RuntimeWindow,
    TerminalSelectionCallback,
    TerminalSender,
)
from app.contexts.terminal_runtime.infrastructure.local.stale_window_cleanup import StaleWindowCleanupPolicy, ensure_local_runtime_window
from app.contexts.terminal_runtime.infrastructure.local.output_pipe import pipe_terminal_output
from app.contexts.terminal_runtime.infrastructure.local.pty_io import _try_write_pty_input_immediately
from app.contexts.terminal_runtime.infrastructure.pty_control import (
    list_file_entries_sync as _list_file_entries_sync,
    notify_process_window_change as _notify_process_window_change,
    read_file_bytes_sync as _read_file_bytes_sync,
    run_pty_control as _run_pty_control,
    write_all_pty_input as _write_all_pty_input,
    write_file_bytes_sync as _write_file_bytes_sync,
)
from app.contexts.terminal_runtime.infrastructure.runtime_window_target import tmux_target_for_runtime_window
from app.contexts.terminal_runtime.infrastructure.tmux_manager import (
    TmuxManager,
    TmuxTarget,
    build_attach_command,
)

logger = logging.getLogger(__name__)


class LocalTerminalRuntime:
    def __init__(
        self,
        tmux_manager: TmuxManager,
        *,
        stale_window_cleanup_seconds: float | None = None,
        stale_window_clock=None,
        stale_window_retain_check=None,
    ) -> None:
        self._tmux_manager = tmux_manager
        self._sessions: dict[tuple[str, str], _LocalTerminalSession] = {}
        self._lock = asyncio.Lock()
        self._stale_window_policy = StaleWindowCleanupPolicy.from_settings(
            cleanup_seconds=stale_window_cleanup_seconds,
            clock=stale_window_clock,
            retain_window=stale_window_retain_check,
        )

    async def create_window(
        self,
        cwd: str | None = None,
        shell_command: str | None = None,
        *,
        window_id: object | None = None,
        agent_ops_token: str | None = None,
    ) -> RuntimeWindow:
        target = await self._tmux_manager.create_window(
            cwd,
            shell_command,
            window_id=window_id,
            agent_ops_token=agent_ops_token,
        )
        if isinstance(target, RuntimeWindow):
            return target
        return RuntimeWindow(
            session_id=target.session,
            window_id=target.window_id,
            window_index=getattr(target, "window_index", None),
            cwd=target.cwd,
            shell_command=target.shell_command,
        )

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
        window = await self._ensure_runtime_window(window, local_window_id=local_window_id)
        key = _attachment_key(window, view_id)
        async with self._lock:
            existing = self._sessions.get(key)
            if existing is not None and not existing.task.done():
                return window
            self._sessions.pop(key, None)

            attach_target = await self._tmux_manager.ensure_shadow_session(
                TmuxTarget(
                    session=window.session_id,
                    window_id=window.window_id,
                    cwd=window.cwd,
                    shell_command=window.shell_command,
                ),
                view_id=str(view_id) if view_id is not None else None,
            )
            master_fd, slave_fd = pty.openpty()
            try:
                try:
                    configure_pty_slave(slave_fd)
                    process = await asyncio.create_subprocess_exec(
                        *build_attach_command(attach_target),
                        stdin=slave_fd,
                        stdout=slave_fd,
                        stderr=slave_fd,
                        close_fds=True,
                        env=attach_process_environment(),
                    )
                except Exception:
                    with contextlib.suppress(OSError):
                        os.close(master_fd)
                    raise
            finally:
                with contextlib.suppress(OSError):
                    os.close(slave_fd)

            session = _LocalTerminalSession(
                master_fd=master_fd,
                process=process,
                shadow_window_id=window.window_id,
                shadow_view_id=str(view_id) if view_id is not None else None,
            )
            session.task = asyncio.create_task(self._pipe_output(key, session, sender))
            if selection_callback is not None:
                session.selection_task = asyncio.create_task(
                    self._watch_active_window(window, attach_target.session, selection_callback)
                )
            self._sessions[key] = session
            if not self._can_resize_shared_shadow_window(window, key):
                self._cancel_resize_tasks_for_window(window)
        return window

    async def detach(
        self,
        window: RuntimeWindow,
        *,
        local_window_id: object | None = None,
        view_id: UUID | str | None = None,
    ) -> None:
        key = _attachment_key(window, view_id)
        async with self._lock:
            session = self._sessions.get(key)
        if session is None:
            return

        task = session.task
        if task is not None and not task.done():
            task.cancel()
        await self._cleanup_session(key, session)
        if task is not None:
            with contextlib.suppress(asyncio.CancelledError):
                await task

    async def send_input(
        self,
        window: RuntimeWindow,
        data: bytes,
        *,
        local_window_id: object | None = None,
        view_id: UUID | str | None = None,
    ) -> None:
        session = self._session_for(window, view_id=view_id)
        written = _try_write_pty_input_immediately(session.master_fd, data)
        if written >= len(data):
            return
        await _run_pty_control(_write_all_pty_input, session.master_fd, data[written:])

    async def send_input_direct(
        self,
        window: RuntimeWindow,
        data: bytes,
        *,
        local_window_id: object | None = None,
    ) -> None:
        window = await self._ensure_runtime_window(window, local_window_id=local_window_id)
        await self._tmux_manager.send_input_direct(
            tmux_target_for_runtime_window(window),
            data,
        )

    async def resize(
        self,
        window: RuntimeWindow,
        *,
        cols: int,
        rows: int,
        local_window_id: object | None = None,
        view_id: UUID | str | None = None,
    ) -> None:
        key = _attachment_key(window, view_id)
        session = self._session_for(window, view_id=view_id)
        size = (cols, rows)
        if session.size == size:
            return
        await _run_pty_control(
            apply_pty_resize,
            session.master_fd,
            ResizeControl(cols=cols, rows=rows),
        )
        _notify_process_window_change(session.process)
        session.size = size
        previous_resize_task = session.resize_task
        if previous_resize_task is not None and not previous_resize_task.done():
            previous_resize_task.cancel()
        session.resize_task = None
        if self._can_resize_shared_shadow_window(window, key):
            session.resize_task = asyncio.create_task(self._sync_shadow_window_size(
                window,
                cols=cols,
                rows=rows,
                view_id=str(view_id) if view_id is not None else None,
            ))

    async def capture_output_bytes(
        self,
        window: RuntimeWindow,
        *,
        local_window_id: object | None = None,
        view_id: UUID | str | None = None,
        history_lines: int | None = None,
    ) -> bytes:
        window = await self._ensure_runtime_window(window, local_window_id=local_window_id)
        output = await self._tmux_manager.capture_window(
            tmux_target_for_runtime_window(window),
            history_lines=history_lines,
        )
        return output.encode("utf-8", errors="surrogateescape")

    async def read_file_bytes(self, path: str, *, max_bytes: int | None = None) -> bytes:
        return await _run_pty_control(_read_file_bytes_sync, path, max_bytes)

    async def list_file_entries(self, path: str) -> list[RuntimeFileEntry]:
        return await _run_pty_control(_list_file_entries_sync, path)

    async def write_file_bytes(self, path: str, data: bytes, *, overwrite: bool = True) -> None:
        await _run_pty_control(_write_file_bytes_sync, path, data, overwrite)

    async def select_window(
        self,
        current_window: RuntimeWindow,
        next_window: RuntimeWindow,
        *,
        local_window_id: object,
        view_id: UUID | str | None = None,
        allow_missing_window_recreate: bool = False,
    ) -> RuntimeWindow | None:
        next_window = await self._ensure_runtime_window(
            next_window,
            local_window_id=local_window_id,
        )
        session = self._session_for(current_window, view_id=view_id)
        resize_task = session.resize_task
        if resize_task is not None and not resize_task.done():
            resize_task.cancel()
        session.resize_task = None
        await self._tmux_manager.select_shadow_window(
            next_window,
            view_id=str(view_id) if view_id is not None else next_window.window_id,
        )
        await self._tmux_manager.select_window(next_window)
        size = session.size
        key = _attachment_key(current_window, view_id)
        if size is not None and self._can_resize_shared_shadow_window(next_window, key):
            await self._tmux_manager.resize_shadow_window(
                next_window,
                cols=size[0],
                rows=size[1],
                view_id=str(view_id) if view_id is not None else None,
            )
        session.shadow_window_id = next_window.window_id
        if not self._can_resize_shared_shadow_window(next_window, key):
            self._cancel_resize_tasks_for_window(next_window)
        return next_window

    async def _ensure_runtime_window(
        self,
        window: RuntimeWindow,
        *,
        local_window_id: object | None,
    ) -> RuntimeWindow:
        return await ensure_local_runtime_window(
            self._tmux_manager,
            self._stale_window_policy,
            window,
            local_window_id=local_window_id,
        )

    def _session_for(
        self,
        window: RuntimeWindow,
        *,
        view_id: UUID | str | None = None,
    ) -> _LocalTerminalSession:
        key = _attachment_key(window, view_id)
        session = self._sessions.get(key)
        if session is None or session.task is None or session.task.done():
            raise RuntimeError(f"terminal window is not attached: {window.session_id}:{window.window_id}")
        return session

    async def _pipe_output(
        self,
        key: tuple[str, str],
        session: _LocalTerminalSession,
        sender: TerminalSender,
    ) -> None:
        await pipe_terminal_output(key, session, sender, self._cleanup_session)

    async def _watch_active_window(
        self,
        window: RuntimeWindow,
        shadow_session: str,
        selection_callback: TerminalSelectionCallback,
    ) -> None:
        last_window_id = window.window_id
        while True:
            await asyncio.sleep(0.25)
            try:
                active_window_id = await self._tmux_manager.current_window_id(shadow_session)
            except Exception:
                return
            if active_window_id == last_window_id:
                continue
            last_window_id = active_window_id
            await selection_callback(
                RuntimeWindow(session_id=window.session_id, window_id=active_window_id)
            )

    async def _sync_shadow_window_size(
        self,
        window: RuntimeWindow,
        *,
        cols: int,
        rows: int,
        view_id: str | None,
    ) -> None:
        try:
            await self._tmux_manager.resize_shadow_window(
                window,
                cols=cols,
                rows=rows,
                view_id=view_id,
            )
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception(
                "failed to resize local shadow tmux window",
                extra={
                    "session_id": window.session_id,
                    "window_id": window.window_id,
                    "view_id": view_id,
                    "cols": cols,
                    "rows": rows,
                },
            )

    def _can_resize_shared_shadow_window(self, window: RuntimeWindow, key: tuple[str, str]) -> bool:
        return not any(
            other_key != key
            and session.shadow_window_id == window.window_id
            and session.task is not None
            and not session.task.done()
            for other_key, session in tuple(self._sessions.items())
        )

    def _cancel_resize_tasks_for_window(self, window: RuntimeWindow) -> None:
        for session in tuple(self._sessions.values()):
            if session.shadow_window_id != window.window_id:
                continue
            resize_task = session.resize_task
            if resize_task is not None and not resize_task.done():
                resize_task.cancel()
            session.resize_task = None

    async def _cleanup_session(
        self,
        key: tuple[str, str],
        session: _LocalTerminalSession,
    ) -> None:
        async with self._lock:
            if session.cleanup_started:
                return
            session.cleanup_started = True
            current = self._sessions.get(key)
            if current is session:
                self._sessions.pop(key, None)

        with contextlib.suppress(OSError):
            os.close(session.master_fd)
        if session.process.returncode is None:
            with contextlib.suppress(ProcessLookupError):
                session.process.terminate()
            with contextlib.suppress(asyncio.TimeoutError):
                await asyncio.wait_for(session.process.wait(), timeout=2)
            if session.process.returncode is None:
                with contextlib.suppress(ProcessLookupError):
                    session.process.kill()
                await session.process.wait()
        selection_task = session.selection_task
        if selection_task is not None and selection_task is not asyncio.current_task():
            selection_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await selection_task
        resize_task = session.resize_task
        if resize_task is not None and resize_task is not asyncio.current_task():
            resize_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await resize_task
        if session.shadow_window_id is not None:
            with contextlib.suppress(Exception):
                await self._tmux_manager.kill_shadow_session(
                    RuntimeWindow(session_id=key[0], window_id=session.shadow_window_id),
                    view_id=session.shadow_view_id,
                )


def _attachment_key(window: RuntimeWindow, view_id: UUID | str | None) -> tuple[str, str]:
    return (window.session_id, str(view_id) if view_id is not None else window.window_id)
