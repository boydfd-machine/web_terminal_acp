import asyncio
from concurrent.futures import ThreadPoolExecutor
import contextlib
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


@pytest.mark.asyncio
async def test_attach_recreates_missing_tmux_window_before_shadow_attach(monkeypatch) -> None:
    calls: list[tuple[str, object]] = []
    received: list[bytes] = []
    sent = asyncio.Event()
    reads = [b"fresh shell"]

    class FakeTmuxManager:
        async def has_window(self, target: TmuxTarget) -> bool:
            calls.append(("has_window", target))
            return False

        async def recreate_window(self, target: TmuxTarget, *, local_window_id) -> TmuxTarget:
            calls.append(("recreate_window", (target, local_window_id)))
            return TmuxTarget(
                session=target.session,
                window_id="@9",
                cwd=target.cwd,
                shell_command=target.shell_command,
            )

        async def ensure_shadow_session(self, target: TmuxTarget, *, view_id=None):
            calls.append(("ensure_shadow_session", (target, view_id)))
            return type("AttachTarget", (), {"session": "web_terminal_view_test"})()

        async def kill_shadow_session(self, target: RuntimeWindow, *, view_id=None) -> None:
            calls.append(("kill_shadow_session", (target, view_id)))

    async def fake_create_subprocess_exec(*args: object, **kwargs: object) -> FakeProcess:
        calls.append(("create_subprocess_exec", args))
        return FakeProcess()

    def fake_read(fd: int, size: int) -> bytes:
        if reads:
            return reads.pop(0)
        raise OSError

    async def sender(data: bytes) -> None:
        received.append(data)
        sent.set()

    monkeypatch.setattr(local_runtime.pty, "openpty", lambda: (10, 11))
    monkeypatch.setattr(local_runtime, "configure_pty_slave", lambda fd: None)
    monkeypatch.setattr(local_runtime.os, "close", lambda fd: None)
    monkeypatch.setattr(local_runtime.os, "read", fake_read)
    monkeypatch.setattr(local_runtime.asyncio, "create_subprocess_exec", fake_create_subprocess_exec)

    runtime = LocalTerminalRuntime(FakeTmuxManager())
    attached_window = await runtime.attach(
        RuntimeWindow(
            session_id="web-terminal",
            window_id="@7",
            cwd="/workspace/project",
            shell_command="/bin/bash",
        ),
        sender,
        local_window_id="87654321-4321-8765-4321-876543218765",
    )
    await asyncio.wait_for(sent.wait(), timeout=1)
    await runtime.detach(attached_window)

    assert attached_window == RuntimeWindow(
        session_id="web-terminal",
        window_id="@9",
        cwd="/workspace/project",
        shell_command="/bin/bash",
    )
    assert received == [b"fresh shell"]
    assert calls[:3] == [
        (
            "has_window",
            TmuxTarget(
                session="web-terminal",
                window_id="@7",
                cwd="/workspace/project",
                shell_command="/bin/bash",
            ),
        ),
        (
            "recreate_window",
            (
                TmuxTarget(
                    session="web-terminal",
                    window_id="@7",
                    cwd="/workspace/project",
                    shell_command="/bin/bash",
                ),
                "87654321-4321-8765-4321-876543218765",
            ),
        ),
        (
            "ensure_shadow_session",
            (
                TmuxTarget(
                    session="web-terminal",
                    window_id="@9",
                    cwd="/workspace/project",
                    shell_command="/bin/bash",
                ),
                None,
            ),
        ),
    ]


@pytest.mark.asyncio
async def test_resize_ignores_repeated_dimensions(monkeypatch) -> None:
    resizes: list[tuple[int, int, int]] = []
    shadow_resizes: list[tuple[RuntimeWindow, int, int]] = []
    keepalive = asyncio.create_task(asyncio.sleep(10))
    window = RuntimeWindow(session_id="web-terminal", window_id="@7")

    def fake_resize(fd: int, control) -> None:
        resizes.append((fd, control.cols, control.rows))

    class FakeTmuxManager:
        async def resize_shadow_window(
            self,
            target_window: RuntimeWindow,
            *,
            cols: int,
            rows: int,
            view_id=None,
        ) -> None:
            shadow_resizes.append((target_window, cols, rows))

    monkeypatch.setattr(local_runtime, "apply_pty_resize", fake_resize)
    runtime = LocalTerminalRuntime(FakeTmuxManager())
    runtime._sessions[(window.session_id, window.window_id)] = _LocalTerminalSession(
        master_fd=123,
        process=object(),
        task=keepalive,
    )
    try:
        await runtime.resize(window, cols=80, rows=24)
        await runtime.resize(window, cols=80, rows=24)
        await runtime.resize(window, cols=81, rows=24)
    finally:
        keepalive.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await keepalive

    assert resizes == [(123, 80, 24), (123, 81, 24)]
    assert shadow_resizes == [(window, 80, 24), (window, 81, 24)]


@pytest.mark.asyncio
async def test_send_input_is_not_blocked_by_default_executor_starvation(monkeypatch) -> None:
    writes: list[tuple[int, bytes]] = []
    keepalive = asyncio.create_task(asyncio.sleep(10))
    default_executor = ThreadPoolExecutor(max_workers=1)
    default_worker_started = threading.Event()
    release_default_worker = threading.Event()
    window = RuntimeWindow(session_id="web-terminal", window_id="@7")

    def occupy_default_executor() -> None:
        default_worker_started.set()
        release_default_worker.wait(timeout=5)

    def fake_write(fd: int, data: bytes) -> int:
        writes.append((fd, data))
        return len(data)

    monkeypatch.setattr(local_runtime.os, "write", fake_write)
    loop = asyncio.get_running_loop()
    loop.set_default_executor(default_executor)
    default_worker_task = loop.run_in_executor(None, occupy_default_executor)

    runtime = LocalTerminalRuntime(object())
    runtime._sessions[(window.session_id, window.window_id)] = _LocalTerminalSession(
        master_fd=123,
        process=object(),
        task=keepalive,
    )
    try:
        deadline = loop.time() + 1
        while not default_worker_started.is_set():
            if loop.time() > deadline:
                raise AssertionError("default executor worker did not start")
            await asyncio.sleep(0.01)

        await asyncio.wait_for(
            runtime.send_input(window, b"hello terminal\r"),
            timeout=0.5,
        )
    finally:
        release_default_worker.set()
        with contextlib.suppress(asyncio.CancelledError):
            await default_worker_task
        default_executor.shutdown(wait=True)
        keepalive.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await keepalive

    assert writes == [(123, b"hello terminal\r")]


@pytest.mark.asyncio
async def test_resize_returns_before_shadow_tmux_resize_completes(monkeypatch) -> None:
    resizes: list[tuple[int, int, int]] = []
    shadow_resize_started = asyncio.Event()
    release_shadow_resize = asyncio.Event()
    keepalive = asyncio.create_task(asyncio.sleep(10))
    window = RuntimeWindow(session_id="web-terminal", window_id="@7")

    def fake_resize(fd: int, control) -> None:
        resizes.append((fd, control.cols, control.rows))

    class FakeTmuxManager:
        async def resize_shadow_window(
            self,
            target_window: RuntimeWindow,
            *,
            cols: int,
            rows: int,
            view_id=None,
        ) -> None:
            shadow_resize_started.set()
            await release_shadow_resize.wait()

    monkeypatch.setattr(local_runtime, "apply_pty_resize", fake_resize)
    runtime = LocalTerminalRuntime(FakeTmuxManager())
    runtime._sessions[(window.session_id, window.window_id)] = _LocalTerminalSession(
        master_fd=123,
        process=object(),
        task=keepalive,
    )
    try:
        resize_task = asyncio.create_task(runtime.resize(window, cols=80, rows=24))
        await asyncio.wait_for(shadow_resize_started.wait(), timeout=1)

        assert resize_task.done(), "resize must not block input behind shadow tmux resize"
    finally:
        release_shadow_resize.set()
        await asyncio.wait_for(resize_task, timeout=1)
        keepalive.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await keepalive

    assert resizes == [(123, 80, 24)]


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
