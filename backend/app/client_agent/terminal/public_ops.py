from __future__ import annotations

import asyncio
import contextlib
import os
import pty
from uuid import UUID

from app.services.runtime.protocol import TerminalPayload

from .common import (
    DIRECT_INPUT_SUBMIT_DELAY_SECONDS,
    SelectionSender,
    TerminalSender,
    _apply_pty_resize,
    _attach_process_environment,
    _AttachedTerminal,
    _configure_pty_slave,
    _notify_process_window_change,
    _RemoteTarget,
    _run_pty_control,
    _try_write_pty_input_immediately,
    _write_all_pty_input,
)
from .direct_input import send_direct_input_to_tmux
from .keys import _attachment_key


class ClientTerminalPublicOps:
    def is_registered(self, window_id: UUID | str) -> bool:
        return str(window_id) in self._windows

    def tmux_target_for(self, window_id: UUID | str) -> str | None:
        target = self._windows.get(str(window_id))
        if target is None:
            return None
        return target.tmux_target

    def registered_remote_window(self, window_id: UUID | str) -> tuple[str, str] | None:
        target = self._windows.get(str(window_id))
        if target is None:
            return None
        return target.remote_session_id, target.remote_window_id

    def register_window(
        self,
        window_id: UUID | str,
        remote_session_id: str,
        remote_window_id: str,
    ) -> None:
        self._windows[str(window_id)] = _RemoteTarget(
            remote_session_id=remote_session_id,
            remote_window_id=remote_window_id,
        )

    def unregister_window(self, window_id: UUID | str) -> None:
        self._windows.pop(str(window_id), None)

    async def select_pool_window(self, window_id: UUID | str) -> None:
        target = self._target_for(window_id)
        await self._run(["tmux", "select-window", "-t", target.tmux_target])

    async def send_input(
        self,
        window_id: UUID | str,
        data: bytes,
        *,
        view_id: UUID | str | None = None,
    ) -> None:
        attached = self._attached_terminal_for(window_id, view_id=view_id)
        # PTY master read and write use independent kernel buffers, so writes here
        # remain responsive even while output drain is back-pressured by the bulk
        # writer queue.
        written = _try_write_pty_input_immediately(attached.master_fd, data)
        if written >= len(data):
            return
        await _run_pty_control(_write_all_pty_input, attached.master_fd, data[written:])

    async def send_input_direct(self, window_id: UUID | str, data: bytes) -> None:
        target = self._target_for(window_id)
        await send_direct_input_to_tmux(
            tmux_target=target.tmux_target,
            data=data,
            run=self._run,
            run_with_stdin=self._run_with_stdin,
            sleep=asyncio.sleep,
            submit_delay_seconds=DIRECT_INPUT_SUBMIT_DELAY_SECONDS,
        )

    async def resize(
        self,
        window_id: UUID | str,
        *,
        cols: int,
        rows: int,
        view_id: UUID | str | None = None,
    ) -> None:
        key = _attachment_key(window_id, view_id)
        attached = self._attached_terminal_for(window_id, view_id=view_id)
        size = (cols, rows)
        if attached.size == size:
            return
        await _run_pty_control(_apply_pty_resize, attached.master_fd, cols=cols, rows=rows)
        _notify_process_window_change(attached.process)
        attached.size = size
        previous_resize_task = attached.resize_task
        if previous_resize_task is not None and not previous_resize_task.done():
            previous_resize_task.cancel()
        attached.resize_task = None
        if self._can_resize_shared_shadow_window(window_id, key):
            target = self._target_for(window_id, view_id=view_id)
            attached.resize_task = asyncio.create_task(
                self._sync_shadow_window_size(target, cols=cols, rows=rows)
            )

    async def select_window(
        self,
        window_id: UUID | str,
        *,
        view_id: UUID | str | None = None,
    ) -> None:
        attached = self._attached_terminal_for(window_id, view_id=view_id)
        target = self._target_for(window_id, view_id=view_id)
        resize_task = attached.resize_task
        if resize_task is not None and not resize_task.done():
            resize_task.cancel()
        attached.resize_task = None
        if not await self._has_tmux_window(target):
            raise RuntimeError(f"tmux window is missing: {target.tmux_target}")
        await self._run(["tmux", "select-window", "-t", f"{target.shadow_session}:{target.remote_window_id}"])
        await self.select_pool_window(window_id)
        key = _attachment_key(window_id, view_id)
        if attached.size is not None and self._can_resize_shared_shadow_window(window_id, key):
            await self._run([
                "tmux",
                "resize-window",
                "-t",
                f"{target.shadow_session}:{target.remote_window_id}",
                "-x",
                str(attached.size[0]),
                "-y",
                str(attached.size[1]),
            ])
        self._attachment_windows[key] = str(window_id)
        if not self._can_resize_shared_shadow_window(window_id, key):
            self._cancel_resize_tasks_for_window(window_id)

    async def attach(
        self,
        window_id: UUID | str,
        sender: TerminalSender,
        *,
        view_id: UUID | str | None = None,
    ) -> None:
        await self.attach_with_selection(window_id, sender, view_id=view_id)

    async def attach_with_selection(
        self,
        window_id: UUID | str,
        sender: TerminalSender,
        selection_sender: SelectionSender | None = None,
        view_id: UUID | str | None = None,
    ) -> None:
        key = _attachment_key(window_id, view_id)
        target = self._target_for(window_id, view_id=view_id)
        async with self._lock:
            existing = self._attached.get(key)
            if existing is not None and existing.task is not None and not existing.task.done():
                return
            self._attached.pop(key, None)
            self._attachment_windows.pop(key, None)

            await self._ensure_shadow_session(target)
            master_fd, slave_fd = pty.openpty()
            try:
                try:
                    _configure_pty_slave(slave_fd)
                    process = await asyncio.create_subprocess_exec(
                        "tmux",
                        "attach-session",
                        "-t",
                        target.shadow_session,
                        stdin=slave_fd,
                        stdout=slave_fd,
                        stderr=slave_fd,
                        close_fds=True,
                        env=_attach_process_environment(),
                    )
                except Exception:
                    with contextlib.suppress(OSError):
                        os.close(master_fd)
                    raise
            finally:
                with contextlib.suppress(OSError):
                    os.close(slave_fd)

            attached = _AttachedTerminal(
                master_fd=master_fd,
                process=process,
                shadow_session=target.shadow_session,
            )
            attached.task = asyncio.create_task(self._pipe_output(key, attached, sender))
            if selection_sender is not None:
                attached.selection_task = asyncio.create_task(
                    self._watch_active_window(key, target, selection_sender)
                )
            self._attached[key] = attached
            self._attachment_windows[key] = str(window_id)
            if not self._can_resize_shared_shadow_window(window_id, key):
                self._cancel_resize_tasks_for_window(window_id)

    async def remove_window(self, window_id: UUID | str) -> None:
        detached_keys = [
            key
            for key, attached_window_id in tuple(self._attachment_windows.items())
            if attached_window_id == str(window_id)
        ]
        if not detached_keys:
            detached_keys = [_attachment_key(window_id)]
        for key in detached_keys:
            await self._detach_attachment_key(key)
        self._windows.pop(str(window_id), None)

    async def detach(self, window_id: UUID | str, *, view_id: UUID | str | None = None) -> None:
        await self._detach_attachment_key(_attachment_key(window_id, view_id))

    async def _detach_attachment_key(self, key: str) -> None:
        async with self._lock:
            attached = self._attached.get(key)
        if attached is None:
            return

        task = attached.task
        if task is not None and not task.done():
            task.cancel()
        await self._cleanup_attachment(key, attached)
        if task is not None:
            with contextlib.suppress(asyncio.CancelledError):
                await task

    async def close(self) -> None:
        for key in tuple(self._attached):
            await self._detach_attachment_key(key)

    async def capture_output(
        self,
        window_id: UUID | str,
        *,
        view_id: UUID | str | None = None,
    ) -> TerminalPayload:
        output = await self.capture_output_bytes(window_id, view_id=view_id)
        return TerminalPayload.from_bytes(UUID(str(window_id)), output)

    async def capture_output_bytes(
        self,
        window_id: UUID | str,
        *,
        view_id: UUID | str | None = None,
        history_lines: int | None = None,
    ) -> bytes:
        target = self._target_for(window_id, view_id=view_id)
        capture_target = (
            f"{target.shadow_session}:{target.remote_window_id}"
            if view_id is not None
            else target.tmux_target
        )
        command = ["tmux", "capture-pane", "-p", "-t", capture_target]
        if history_lines is not None and history_lines > 0:
            command.extend(["-S", f"-{history_lines}"])
        output = await self._run(command)
        return output.encode("utf-8", errors="surrogateescape")

    def _can_resize_shared_shadow_window(self, window_id: UUID | str, key: str) -> bool:
        target_window_id = str(window_id)
        for other_key, attached_window_id in self._attachment_windows.items():
            if other_key == key or attached_window_id != target_window_id:
                continue
            if self._is_live_attachment(other_key):
                return False
        return True

    def _is_live_attachment(self, key: str) -> bool:
        attached = self._attached.get(key)
        return attached is not None and attached.task is not None and not attached.task.done()

    def _cancel_resize_tasks_for_window(self, window_id: UUID | str) -> None:
        target_window_id = str(window_id)
        for key, attached_window_id in tuple(self._attachment_windows.items()):
            if attached_window_id != target_window_id:
                continue
            attached = self._attached.get(key)
            if attached is None:
                continue
            resize_task = attached.resize_task
            if resize_task is not None and not resize_task.done():
                resize_task.cancel()
            attached.resize_task = None

