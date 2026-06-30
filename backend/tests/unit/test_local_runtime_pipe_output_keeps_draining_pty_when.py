import asyncio
from concurrent.futures import ThreadPoolExecutor
import contextlib
import signal
import threading

import pytest

import app.services.runtime.local as local_runtime
from app.services.runtime.local import LocalTerminalRuntime, _LocalTerminalSession
from app.services.runtime.types import RuntimeWindow
from app.services.tmux_manager import TmuxTarget


class FakeProcess:
    returncode = None

    def terminate(self) -> None:
        self.returncode = -15

    async def wait(self) -> int:
        return self.returncode or 0


class FakeAttachedProcess:
    returncode = None

    def __init__(self) -> None:
        self.signals: list[int] = []

    def send_signal(self, signal_number: int) -> None:
        self.signals.append(signal_number)

@pytest.mark.asyncio
async def test_pipe_output_keeps_draining_pty_when_sender_is_backpressured(monkeypatch) -> None:
    first_send_started = asyncio.Event()
    release_first_send = asyncio.Event()
    second_read = threading.Event()
    received: list[bytes] = []
    reads = [b"first", b"second"]
    window = RuntimeWindow(session_id="web-terminal", window_id="@7")

    class FakeProcess:
        returncode = 0

    session = _LocalTerminalSession(master_fd=123, process=FakeProcess())

    def fake_read(fd: int, size: int) -> bytes:
        assert fd == 123
        assert size == local_runtime.PTY_READ_CHUNK_BYTES
        if reads:
            data = reads.pop(0)
            if data == b"second":
                second_read.set()
            return data
        raise OSError

    async def blocked_sender(data: bytes) -> None:
        received.append(data)
        first_send_started.set()
        await release_first_send.wait()

    monkeypatch.setattr(local_runtime.os, "read", fake_read)
    monkeypatch.setattr(local_runtime.os, "close", lambda fd: None)

    runtime = LocalTerminalRuntime(object())
    output_task = asyncio.create_task(
        runtime._pipe_output((window.session_id, window.window_id), session, blocked_sender)
    )
    try:
        await asyncio.wait_for(first_send_started.wait(), timeout=1)
        assert second_read.wait(timeout=1), "PTY reader should keep draining while sender is blocked"
    finally:
        release_first_send.set()
        await asyncio.wait_for(output_task, timeout=1)

    assert received == [b"first", b"second"]

@pytest.mark.asyncio
async def test_pipe_output_uses_event_loop_fd_reader_for_prompt_output() -> None:
    received: list[bytes] = []
    window = RuntimeWindow(session_id="web-terminal", window_id="@7")
    read_fd, write_fd = local_runtime.os.pipe()

    class FakeProcess:
        returncode = 0

        def terminate(self) -> None:
            self.returncode = -15

        async def wait(self) -> int:
            return self.returncode or 0

    session = _LocalTerminalSession(master_fd=read_fd, process=FakeProcess())

    async def sender(data: bytes) -> None:
        received.append(data)

    runtime = LocalTerminalRuntime(object())
    output_task = asyncio.create_task(
        runtime._pipe_output((window.session_id, window.window_id), session, sender)
    )
    try:
        local_runtime.os.write(write_fd, b"prompt")
        deadline = asyncio.get_event_loop().time() + 1
        while received != [b"prompt"]:
            if asyncio.get_event_loop().time() > deadline:
                raise AssertionError(f"event-loop fd reader did not deliver output: {received!r}")
            await asyncio.sleep(0.01)
    finally:
        with contextlib.suppress(OSError):
            local_runtime.os.close(write_fd)
        output_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await output_task

    assert session.reader_task is None
