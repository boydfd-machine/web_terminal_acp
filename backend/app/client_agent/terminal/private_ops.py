from __future__ import annotations

import asyncio
import contextlib
import os
from uuid import UUID

from .common import (
    PTY_DRAIN_BUFFER_MAX_BYTES,
    PTY_OUTPUT_SEND_CHUNK_BYTES,
    PTY_READ_CHUNK_BYTES,
    SELECTION_POLL_INTERVAL_SECONDS,
    SelectionSender,
    TerminalSender,
    _AttachedTerminal,
    _RemoteTarget,
    logger,
)
from .keys import _attachment_key


class ClientTerminalPrivateOps:
    async def _ensure_shadow_session(self, target: _RemoteTarget) -> None:
        if not await self._has_tmux_window(target):
            raise RuntimeError(f"tmux window is missing: {target.tmux_target}")
        try:
            await self._run(["tmux", "has-session", "-t", target.shadow_session])
        except RuntimeError:
            await self._run(
                [
                    "tmux",
                    "new-session",
                    "-d",
                    "-t",
                    target.remote_session_id,
                    "-s",
                    target.shadow_session,
                ]
            )
        with contextlib.suppress(RuntimeError):
            await self._run(["tmux", "set-option", "-t", target.shadow_session, "window-size", "manual"])
        with contextlib.suppress(RuntimeError):
            await self._run(["tmux", "set-option", "-t", target.shadow_session, "mouse", "on"])
        await self._run(["tmux", "select-window", "-t", f"{target.shadow_session}:{target.remote_window_id}"])
        with contextlib.suppress(RuntimeError):
            await self._run(
                [
                    "tmux",
                    "set-option",
                    "-p",
                    "-t",
                    f"{target.shadow_session}:{target.remote_window_id}",
                    "allow-passthrough",
                    "on",
                ]
            )

    async def _has_tmux_window(self, target: _RemoteTarget) -> bool:
        try:
            window_id = (
                await self._run(
                    [
                        "tmux",
                        "display-message",
                        "-p",
                        "-t",
                        target.tmux_target,
                        "#{window_id}",
                    ]
                )
            ).strip()
        except RuntimeError:
            return False
        return window_id == target.remote_window_id

    async def _current_window_id(self, shadow_session: str) -> str:
        return (
            await self._run(
                [
                    "tmux",
                    "display-message",
                    "-p",
                    "-t",
                    shadow_session,
                    "#{window_id}",
                ]
            )
        ).strip()

    def _local_window_id_for_remote(
        self,
        remote_session_id: str,
        remote_window_id: str,
    ) -> UUID | None:
        for local_window_id, target in self._windows.items():
            if (
                target.remote_session_id == remote_session_id
                and target.remote_window_id == remote_window_id
            ):
                return UUID(local_window_id)
        return None

    async def _run(self, args: list[str]) -> str:
        if self._runner is not None:
            return await self._runner(args)

        process = await asyncio.create_subprocess_exec(
            *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await process.communicate()
        if process.returncode != 0:
            error_text = stderr.decode(errors="replace").strip()
            raise RuntimeError(f"tmux command failed ({process.returncode}): {' '.join(args)}: {error_text}")
        return stdout.decode(errors="replace")

    async def _run_with_stdin(self, args: list[str], stdin: bytes) -> str:
        if self._runner is not None:
            return await self._runner(args)

        process = await asyncio.create_subprocess_exec(
            *args,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await process.communicate(stdin)
        if process.returncode != 0:
            error_text = stderr.decode(errors="replace").strip()
            raise RuntimeError(f"tmux command failed ({process.returncode}): {' '.join(args)}: {error_text}")
        return stdout.decode(errors="replace")

    async def _sync_shadow_window_size(
        self,
        target: _RemoteTarget,
        *,
        cols: int,
        rows: int,
    ) -> None:
        try:
            await self._run([
                "tmux",
                "resize-window",
                "-t",
                f"{target.shadow_session}:{target.remote_window_id}",
                "-x",
                str(cols),
                "-y",
                str(rows),
            ])
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception(
                "failed to resize client-agent shadow tmux window",
                extra={
                    "remote_session_id": target.remote_session_id,
                    "remote_window_id": target.remote_window_id,
                    "view_id": target.view_id,
                    "cols": cols,
                    "rows": rows,
                },
            )

    async def _kill_shadow_session(self, shadow_session: str) -> None:
        try:
            await self._run(["tmux", "kill-session", "-t", shadow_session])
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception(
                "failed to kill client-agent shadow tmux session",
                extra={"shadow_session": shadow_session},
            )

    def _target_for(
        self,
        window_id: UUID | str,
        *,
        view_id: UUID | str | None = None,
    ) -> _RemoteTarget:
        key = str(window_id)
        try:
            target = self._windows[key]
        except KeyError as exc:
            raise KeyError(f"window is not registered with tmux multiplexer: {key}") from exc
        if view_id is None:
            return target
        return _RemoteTarget(
            remote_session_id=target.remote_session_id,
            remote_window_id=target.remote_window_id,
            view_id=str(view_id),
        )

    def _attached_terminal_for(
        self,
        window_id: UUID | str,
        *,
        view_id: UUID | str | None = None,
    ) -> _AttachedTerminal:
        key = _attachment_key(window_id, view_id)
        attached = self._attached.get(key)
        if attached is None or attached.task is None or attached.task.done():
            raise RuntimeError(f"terminal window is not attached: {key}")
        return attached

    async def _pipe_output(
        self,
        window_id: str,
        attached: _AttachedTerminal,
        sender: TerminalSender,
    ) -> None:
        # Streams the fully-rendered tmux output (status bar, pane borders,
        # popups, copy-mode overlays, etc.) from the attached PTY master back to
        # the server, while keeping the PTY itself drained at all times.
        #
        # A naive `read -> await sender(data)` loop blocks the PTY whenever the
        # downstream is slow (saturated bulk writer queue, slow server, ...).
        # That stalls tmux's event loop because the PTY master's output buffer
        # fills up; tmux can then no longer process input from the same PTY, so
        # `os.write(master_fd, ...)` for the user's keystrokes starts blocking
        # too. Because the control WebSocket recv loop awaits `send_input`, the
        # whole client agent freezes for as long as the bulk path is congested.
        #
        # To avoid that, we split the work between two cooperative tasks:
        #
        #   * The reader sub-task is a tight loop that copies PTY bytes into an
        #     in-memory coalescing buffer. It never awaits the sender, so tmux
        #     always has a consumer for its output and stays responsive.
        #   * The drainer (this coroutine) atomically swaps the buffer out and
        #     forwards it through the bulk-writer sender. If the sender stalls,
        #     only the drainer waits; the reader keeps emptying the PTY into
        #     the buffer. If the buffer ever exceeds the configured cap, the
        #     reader drops the oldest bytes (logging a warning) instead of
        #     blocking tmux.
        attached.output_eof = False
        attached.output_event.clear()
        attached.output_buffer.clear()

        async def reader_loop() -> None:
            try:
                while True:
                    try:
                        data = await asyncio.to_thread(
                            os.read, attached.master_fd, PTY_READ_CHUNK_BYTES
                        )
                    except OSError:
                        return
                    if not data:
                        return
                    attached.output_buffer.extend(data)
                    if len(attached.output_buffer) > PTY_DRAIN_BUFFER_MAX_BYTES:
                        overflow = (
                            len(attached.output_buffer) - PTY_DRAIN_BUFFER_MAX_BYTES
                        )
                        del attached.output_buffer[:overflow]
                        logger.warning(
                            "client-agent PTY output buffer overflowed; "
                            "dropped oldest bytes to keep tmux responsive",
                            extra={
                                "window_id": window_id,
                                "dropped_bytes": overflow,
                                "buffer_bytes": len(attached.output_buffer),
                            },
                        )
                    attached.output_event.set()
            finally:
                attached.output_eof = True
                attached.output_event.set()

        reader_task = asyncio.create_task(reader_loop())
        attached.reader_task = reader_task
        try:
            while True:
                # `bytes(buffer)` followed by `buffer.clear()` runs as a single
                # synchronous block (no awaits in between), so the reader task,
                # which lives on the same event loop, cannot append concurrently
                # and no bytes can be lost during the swap.
                if attached.output_buffer:
                    chunk = bytes(attached.output_buffer)
                    attached.output_buffer.clear()
                    try:
                        for index in range(0, len(chunk), PTY_OUTPUT_SEND_CHUNK_BYTES):
                            await sender(chunk[index : index + PTY_OUTPUT_SEND_CHUNK_BYTES])
                    except Exception:
                        return
                    continue
                if attached.output_eof:
                    return
                # Clear the event before waiting so that any subsequent reader
                # append (and matching `set()`) is observed by `wait()`. Because
                # both reader and drainer execute on the same event loop, no
                # event/buffer state can change between this `clear` and the
                # next `await`.
                attached.output_event.clear()
                if attached.output_buffer or attached.output_eof:
                    continue
                await attached.output_event.wait()
        finally:
            if not reader_task.done():
                reader_task.cancel()
                with contextlib.suppress(asyncio.CancelledError, Exception):
                    await reader_task
            attached.reader_task = None
            await self._cleanup_attachment(window_id, attached)

    async def _watch_active_window(
        self,
        key: str,
        target: _RemoteTarget,
        selection_sender: SelectionSender,
    ) -> None:
        last_window_id = target.remote_window_id
        while True:
            await asyncio.sleep(SELECTION_POLL_INTERVAL_SECONDS)
            try:
                active_window_id = await self._current_window_id(target.shadow_session)
            except Exception:
                return
            if active_window_id == last_window_id:
                continue
            last_window_id = active_window_id
            local_window_id = self._local_window_id_for_remote(
                target.remote_session_id,
                active_window_id,
            )
            if local_window_id is not None:
                async with self._lock:
                    if key not in self._attached:
                        return
                    self._attachment_windows[key] = str(local_window_id)
                await selection_sender(local_window_id)

    async def _cleanup_attachment(self, window_id: str, attached: _AttachedTerminal) -> None:
        async with self._lock:
            if attached.cleanup_started:
                return
            attached.cleanup_started = True
            if self._attached.get(window_id) is attached:
                self._attached.pop(window_id, None)
                self._attachment_windows.pop(window_id, None)

        with contextlib.suppress(OSError):
            os.close(attached.master_fd)
        if attached.process.returncode is None:
            with contextlib.suppress(ProcessLookupError):
                attached.process.terminate()
            with contextlib.suppress(asyncio.TimeoutError):
                await asyncio.wait_for(attached.process.wait(), timeout=2)
            if attached.process.returncode is None:
                with contextlib.suppress(ProcessLookupError):
                    attached.process.kill()
                await attached.process.wait()
        selection_task = attached.selection_task
        if selection_task is not None and selection_task is not asyncio.current_task():
            selection_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await selection_task
        resize_task = attached.resize_task
        if resize_task is not None and resize_task is not asyncio.current_task():
            resize_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await resize_task
        await self._kill_shadow_session(attached.shadow_session)
