from tests.unit.test_client_agent_terminal_support import *

@pytest.mark.asyncio
async def test_send_input_direct_sends_literal_text_to_base_tmux_window(monkeypatch) -> None:
    calls: list[list[str]] = []
    sleep_calls: list[float] = []
    original_sleep = asyncio.sleep

    async def fake_sleep(delay: float) -> None:
        sleep_calls.append(delay)
        await original_sleep(0)

    monkeypatch.setattr(client_terminal.asyncio, "sleep", fake_sleep)

    async def fake_run(args: list[str]) -> str:
        calls.append(args)
        return ""

    multiplexer = ClientTerminalMultiplexer(runner=fake_run)
    multiplexer.register_window(WINDOW_ID, "client_pool", "@7")

    await multiplexer.send_input_direct(WINDOW_ID, b"artifact prompt\n")

    assert calls == [
        ["tmux", "send-keys", "-l", "-t", "client_pool:@7", "--", "artifact prompt"],
        ["tmux", "send-keys", "-t", "client_pool:@7", "Enter"],
    ]
    assert sleep_calls == [client_terminal.DIRECT_INPUT_SUBMIT_DELAY_SECONDS]

@pytest.mark.asyncio
async def test_send_input_direct_does_not_delay_plain_newline(monkeypatch) -> None:
    calls: list[list[str]] = []
    sleep_calls: list[float] = []

    async def fake_sleep(delay: float) -> None:
        sleep_calls.append(delay)

    async def fake_run(args: list[str]) -> str:
        calls.append(args)
        return ""

    monkeypatch.setattr(client_terminal.asyncio, "sleep", fake_sleep)
    multiplexer = ClientTerminalMultiplexer(runner=fake_run)
    multiplexer.register_window(WINDOW_ID, "client_pool", "@7")

    await multiplexer.send_input_direct(WINDOW_ID, b"\n")

    assert calls == [["tmux", "send-keys", "-t", "client_pool:@7", "Enter"]]
    assert sleep_calls == []


@pytest.mark.asyncio
async def test_send_input_direct_keeps_bracketed_paste_atomic(monkeypatch) -> None:
    """Multi-line bracketed-paste payloads must be sent as ONE literal chunk
    followed by a single Enter. Splitting the paste body line-by-line and
    pressing Enter between lines breaks the bracketed paste protocol for
    agents like Claude Code: the first Enter submits the partial prompt
    and the remaining lines + END marker leak into the next turn.

    Reproduces the say hi dispatch regression on code-server-direct where
    broker.send_input_direct delivered the prompt but Claude never received
    it - because the multi-line paste was split into per-line send-keys
    calls, and the Enter keys between lines were treated as submit.
    """
    calls: list[list[str]] = []
    sleep_calls: list[float] = []
    original_sleep = asyncio.sleep

    async def fake_sleep(delay: float) -> None:
        sleep_calls.append(delay)
        await original_sleep(0)

    monkeypatch.setattr(client_terminal.asyncio, "sleep", fake_sleep)

    async def fake_run(args: list[str]) -> str:
        calls.append(args)
        return ""

    multiplexer = ClientTerminalMultiplexer(runner=fake_run)
    multiplexer.register_window(WINDOW_ID, "client_pool", "@7")

    # b"\x1b[200~" + multi-line prompt + b"\x1b[201~" + b"\n" - matches what
    # command_bytes_for_agent_prompt produces for claude_code dispatch.
    paste_bytes = (
        b"\x1b[200~You are assigned to complete this project todo.\n"
        b"Project path: /home/coder\n"
        b"Todo: say-hi\n"
        b"Context:\n"
        b"just say hi\x1b[201~\n"
    )
    await multiplexer.send_input_direct(WINDOW_ID, paste_bytes)

    # The whole bracketed paste body (including embedded newlines and both
    # C0 markers) must be sent as a single literal chunk, then exactly one
    # Enter to submit.
    assert len(calls) == 2, f"expected 2 calls (literal + Enter), got {calls}"
    assert calls[0][:5] == ["tmux", "send-keys", "-l", "-t", "client_pool:@7"]
    sent_literal = calls[0][-1]
    assert sent_literal.startswith("\x1b[200~"), "literal must keep paste start marker"
    assert sent_literal.endswith("\x1b[201~"), "literal must keep paste end marker"
    assert "Project path: /home/coder" in sent_literal, "must keep embedded lines intact"
    assert calls[1] == ["tmux", "send-keys", "-t", "client_pool:@7", "Enter"]
    assert sleep_calls == [client_terminal.DIRECT_INPUT_SUBMIT_DELAY_SECONDS]

@pytest.mark.asyncio
async def test_send_input_writes_raw_bytes_to_attached_pty(monkeypatch) -> None:
    writes: list[tuple[int, bytes]] = []
    keepalive = asyncio.create_task(asyncio.sleep(10))

    def fake_write(fd: int, data: bytes) -> int:
        writes.append((fd, data))
        return len(data)

    monkeypatch.setattr(client_terminal.os, "write", fake_write)
    multiplexer = ClientTerminalMultiplexer()
    multiplexer._attached[str(WINDOW_ID)] = _AttachedTerminal(
        master_fd=123,
        process=object(),
        shadow_session="web_terminal_view__7",
        task=keepalive,
    )
    try:
        await multiplexer.send_input(WINDOW_ID, b"hello terminal\r")
    finally:
        keepalive.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await keepalive

    assert writes == [(123, b"hello terminal\r")]

@pytest.mark.asyncio
async def test_send_input_is_not_blocked_by_default_executor_starvation(monkeypatch) -> None:
    writes: list[tuple[int, bytes]] = []
    keepalive = asyncio.create_task(asyncio.sleep(10))
    default_executor = ThreadPoolExecutor(max_workers=1)
    default_worker_started = threading.Event()
    release_default_worker = threading.Event()

    def occupy_default_executor() -> None:
        default_worker_started.set()
        release_default_worker.wait(timeout=5)

    def fake_write(fd: int, data: bytes) -> int:
        writes.append((fd, data))
        return len(data)

    monkeypatch.setattr(client_terminal.os, "write", fake_write)
    loop = asyncio.get_running_loop()
    loop.set_default_executor(default_executor)
    default_worker_task = loop.run_in_executor(None, occupy_default_executor)

    multiplexer = ClientTerminalMultiplexer()
    multiplexer._attached[str(WINDOW_ID)] = _AttachedTerminal(
        master_fd=123,
        process=object(),
        shadow_session="web_terminal_view__7",
        task=keepalive,
    )
    try:
        deadline = loop.time() + 1
        while not default_worker_started.is_set():
            if loop.time() > deadline:
                raise AssertionError("default executor worker did not start")
            await asyncio.sleep(0.01)

        await asyncio.wait_for(
            multiplexer.send_input(WINDOW_ID, b"hello terminal\r"),
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
async def test_small_send_input_uses_immediate_writable_pty_fast_path(monkeypatch) -> None:
    writes: list[tuple[int, bytes]] = []
    control_calls: list[tuple[object, ...]] = []
    keepalive = asyncio.create_task(asyncio.sleep(10))

    def fake_select(read_list, write_list, error_list, timeout):
        assert read_list == []
        assert write_list == [123]
        assert error_list == []
        assert timeout == 0
        return [], [123], []

    def fake_write(fd: int, data: bytes) -> int:
        writes.append((fd, bytes(data)))
        return len(data)

    async def fake_run_pty_control(*args) -> None:
        control_calls.append(args)

    monkeypatch.setattr(client_terminal.select, "select", fake_select)
    monkeypatch.setattr(client_terminal.os, "write", fake_write)
    monkeypatch.setattr(client_terminal, "_run_pty_control", fake_run_pty_control)

    multiplexer = ClientTerminalMultiplexer()
    multiplexer._attached[str(WINDOW_ID)] = _AttachedTerminal(
        master_fd=123,
        process=object(),
        shadow_session="web_terminal_view__7",
        task=keepalive,
    )
    try:
        await multiplexer.send_input(WINDOW_ID, b"x")
    finally:
        keepalive.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await keepalive

    assert writes == [(123, b"x")]
    assert control_calls == []

@pytest.mark.asyncio
async def test_send_input_falls_back_to_executor_when_pty_is_not_immediately_writable(monkeypatch) -> None:
    writes: list[tuple[int, bytes]] = []
    keepalive = asyncio.create_task(asyncio.sleep(10))

    def fake_select(_read_list, _write_list, _error_list, _timeout):
        return [], [], []

    def fake_write(fd: int, data: bytes) -> int:
        writes.append((fd, bytes(data)))
        return len(data)

    monkeypatch.setattr(client_terminal.select, "select", fake_select)
    monkeypatch.setattr(client_terminal.os, "write", fake_write)

    multiplexer = ClientTerminalMultiplexer()
    multiplexer._attached[str(WINDOW_ID)] = _AttachedTerminal(
        master_fd=123,
        process=object(),
        shadow_session="web_terminal_view__7",
        task=keepalive,
    )
    try:
        await multiplexer.send_input(WINDOW_ID, b"x")
    finally:
        keepalive.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await keepalive

    assert writes == [(123, b"x")]

@pytest.mark.asyncio
async def test_resize_applies_dimensions_to_attached_pty_and_shadow_tmux_window(monkeypatch) -> None:
    resizes: list[tuple[int, int, int]] = []
    signals: list[int] = []
    calls: list[list[str]] = []
    keepalive = asyncio.create_task(asyncio.sleep(10))

    class FakeProcess:
        returncode = None

        def send_signal(self, signal_number: int) -> None:
            signals.append(signal_number)

    def fake_resize(fd: int, *, cols: int, rows: int) -> None:
        resizes.append((fd, cols, rows))

    async def fake_run(args: list[str]) -> str:
        calls.append(args)
        return ""

    monkeypatch.setattr(client_terminal, "_apply_pty_resize", fake_resize)
    multiplexer = ClientTerminalMultiplexer(runner=fake_run)
    multiplexer.register_window(WINDOW_ID, "client_pool", "@7")
    multiplexer._attached[str(WINDOW_ID)] = _AttachedTerminal(
        master_fd=123,
        process=FakeProcess(),
        shadow_session="web_terminal_view__7",
        task=keepalive,
    )
    try:
        await multiplexer.resize(WINDOW_ID, cols=41, rows=44)
    finally:
        keepalive.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await keepalive

    assert resizes == [(123, 41, 44)]
    assert signals == [client_terminal.signal.SIGWINCH]
    assert calls == [["tmux", "resize-window", "-t", "web_terminal_view__7:@7", "-x", "41", "-y", "44"]]

@pytest.mark.asyncio
async def test_resize_does_not_resize_shared_tmux_window_with_multiple_live_views(monkeypatch) -> None:
    view_one = UUID("aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee")
    view_two = UUID("bbbbbbbb-cccc-dddd-eeee-ffffffffffff")
    resizes: list[tuple[int, int, int]] = []
    signals: list[int] = []
    calls: list[list[str]] = []
    keepalive_one = asyncio.create_task(asyncio.sleep(10))
    keepalive_two = asyncio.create_task(asyncio.sleep(10))

    class FakeProcess:
        returncode = None

        def send_signal(self, signal_number: int) -> None:
            signals.append(signal_number)

    def fake_resize(fd: int, *, cols: int, rows: int) -> None:
        resizes.append((fd, cols, rows))

    async def fake_run(args: list[str]) -> str:
        calls.append(args)
        return ""

    monkeypatch.setattr(client_terminal, "_apply_pty_resize", fake_resize)
    multiplexer = ClientTerminalMultiplexer(runner=fake_run)
    multiplexer.register_window(WINDOW_ID, "client_pool", "@7")
    multiplexer._attached[str(view_one)] = _AttachedTerminal(
        master_fd=123,
        process=FakeProcess(),
        shadow_session=f"web_terminal_view_{view_one}",
        task=keepalive_one,
    )
    multiplexer._attached[str(view_two)] = _AttachedTerminal(
        master_fd=456,
        process=FakeProcess(),
        shadow_session=f"web_terminal_view_{view_two}",
        task=keepalive_two,
    )
    multiplexer._attachment_windows[str(view_one)] = str(WINDOW_ID)
    multiplexer._attachment_windows[str(view_two)] = str(WINDOW_ID)
    try:
        await multiplexer.resize(WINDOW_ID, cols=41, rows=44, view_id=view_one)
    finally:
        keepalive_one.cancel()
        keepalive_two.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await keepalive_one
        with contextlib.suppress(asyncio.CancelledError):
            await keepalive_two

    assert resizes == [(123, 41, 44)]
    assert signals == [client_terminal.signal.SIGWINCH]
    assert calls == []

@pytest.mark.asyncio
async def test_resize_ignores_repeated_dimensions(monkeypatch) -> None:
    resizes: list[tuple[int, int, int]] = []
    signals: list[int] = []
    calls: list[list[str]] = []
    keepalive = asyncio.create_task(asyncio.sleep(10))

    class FakeProcess:
        returncode = None

        def send_signal(self, signal_number: int) -> None:
            signals.append(signal_number)

    def fake_resize(fd: int, *, cols: int, rows: int) -> None:
        resizes.append((fd, cols, rows))

    async def fake_run(args: list[str]) -> str:
        calls.append(args)
        return ""

    monkeypatch.setattr(client_terminal, "_apply_pty_resize", fake_resize)
    multiplexer = ClientTerminalMultiplexer(runner=fake_run)
    multiplexer.register_window(WINDOW_ID, "client_pool", "@7")
    multiplexer._attached[str(WINDOW_ID)] = _AttachedTerminal(
        master_fd=123,
        process=FakeProcess(),
        shadow_session="web_terminal_view__7",
        task=keepalive,
    )
    try:
        await multiplexer.resize(WINDOW_ID, cols=41, rows=44)
        await multiplexer.resize(WINDOW_ID, cols=41, rows=44)
        await multiplexer.resize(WINDOW_ID, cols=42, rows=44)
    finally:
        keepalive.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await keepalive

    assert resizes == [(123, 41, 44), (123, 42, 44)]
    assert signals == [client_terminal.signal.SIGWINCH, client_terminal.signal.SIGWINCH]
    assert calls == [
        ["tmux", "resize-window", "-t", "web_terminal_view__7:@7", "-x", "41", "-y", "44"],
        ["tmux", "resize-window", "-t", "web_terminal_view__7:@7", "-x", "42", "-y", "44"],
    ]

@pytest.mark.asyncio
async def test_resize_returns_before_shadow_tmux_resize_completes(monkeypatch) -> None:
    writes: list[tuple[int, bytes]] = []
    resizes: list[tuple[int, int, int]] = []
    shadow_resize_started = asyncio.Event()
    release_shadow_resize = asyncio.Event()
    keepalive = asyncio.create_task(asyncio.sleep(10))

    class FakeProcess:
        returncode = None

        def send_signal(self, signal_number: int) -> None:
            return None

    def fake_resize(fd: int, *, cols: int, rows: int) -> None:
        resizes.append((fd, cols, rows))

    def fake_write(fd: int, data: bytes) -> int:
        writes.append((fd, data))
        return len(data)

    async def fake_run(args: list[str]) -> str:
        if args[:2] == ["tmux", "resize-window"]:
            shadow_resize_started.set()
            await release_shadow_resize.wait()
        return ""

    monkeypatch.setattr(client_terminal, "_apply_pty_resize", fake_resize)
    monkeypatch.setattr(client_terminal.os, "write", fake_write)
    multiplexer = ClientTerminalMultiplexer(runner=fake_run)
    multiplexer.register_window(WINDOW_ID, "client_pool", "@7")
    multiplexer._attached[str(WINDOW_ID)] = _AttachedTerminal(
        master_fd=123,
        process=FakeProcess(),
        shadow_session="web_terminal_view__7",
        task=keepalive,
    )
    try:
        resize_task = asyncio.create_task(multiplexer.resize(WINDOW_ID, cols=100, rows=30))
        await asyncio.wait_for(shadow_resize_started.wait(), timeout=1)

        assert resize_task.done(), "resize must not block input behind shadow tmux resize"
        await multiplexer.send_input(WINDOW_ID, b"x")
    finally:
        release_shadow_resize.set()
        await asyncio.wait_for(resize_task, timeout=1)
        keepalive.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await keepalive

    assert resizes == [(123, 100, 30)]
    assert writes == [(123, b"x")]

@pytest.mark.asyncio
async def test_capture_output_returns_terminal_payload_with_base64_output() -> None:
    calls: list[list[str]] = []

    async def fake_run(args: list[str]) -> str:
        calls.append(args)
        return "line one\nline two\n"

    multiplexer = ClientTerminalMultiplexer(runner=fake_run)
    multiplexer.register_window(WINDOW_ID, "client_pool", "@7")

    payload = await multiplexer.capture_output(WINDOW_ID)

    assert payload.window_id == WINDOW_ID
    assert payload.to_bytes() == b"line one\nline two\n"
    assert calls == [["tmux", "capture-pane", "-p", "-t", "client_pool:@7"]]

@pytest.mark.asyncio
async def test_capture_output_bytes_can_include_history_lines() -> None:
    calls: list[list[str]] = []

    async def fake_run(args: list[str]) -> str:
        calls.append(args)
        return "history\n"

    multiplexer = ClientTerminalMultiplexer(runner=fake_run)
    multiplexer.register_window(WINDOW_ID, "client_pool", "@7")

    output = await multiplexer.capture_output_bytes(WINDOW_ID, history_lines=5000)

    assert output == b"history\n"
    assert calls == [["tmux", "capture-pane", "-p", "-t", "client_pool:@7", "-S", "-5000"]]
