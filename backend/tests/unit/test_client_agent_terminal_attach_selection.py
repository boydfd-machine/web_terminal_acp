from tests.unit.test_client_agent_terminal_support import *

@pytest.mark.asyncio
async def test_attach_streams_raw_tmux_pty_bytes(monkeypatch) -> None:
    calls: list[list[str]] = []
    raw_configured: list[int] = []
    subprocess_calls: list[tuple[tuple[object, ...], dict[str, object]]] = []
    received: list[bytes] = []
    sent = asyncio.Event()
    reads = [b"\x1b[31mtmux\x1b[0m"]

    async def fake_run(args: list[str]) -> str:
        calls.append(args)
        if args == ["tmux", "display-message", "-p", "-t", "client_pool:@7", "#{window_id}"]:
            return "@7\n"
        if args == ["tmux", "has-session", "-t", "web_terminal_view__7"]:
            raise RuntimeError("missing")
        return ""

    class FakeProcess:
        returncode = None

        def terminate(self) -> None:
            self.returncode = -15

        async def wait(self) -> int:
            return self.returncode or 0

    async def fake_create_subprocess_exec(*args: object, **kwargs: object) -> FakeProcess:
        subprocess_calls.append((args, kwargs))
        return FakeProcess()

    def fake_read(fd: int, size: int) -> bytes:
        assert fd == 10
        assert size == client_terminal.PTY_READ_CHUNK_BYTES
        if reads:
            return reads.pop(0)
        raise OSError

    async def sender(data: bytes) -> None:
        received.append(data)
        sent.set()

    monkeypatch.setattr(client_terminal_public_ops.pty, "openpty", lambda: (10, 11))
    monkeypatch.setattr(
        client_terminal_public_ops,
        "_configure_pty_slave",
        lambda fd: raw_configured.append(fd),
    )
    monkeypatch.setattr(client_terminal_public_ops.os, "close", lambda fd: None)
    monkeypatch.setattr(client_terminal_private_ops.os, "read", fake_read)
    monkeypatch.setattr(
        client_terminal_public_ops.asyncio,
        "create_subprocess_exec",
        fake_create_subprocess_exec,
    )

    multiplexer = ClientTerminalMultiplexer(runner=fake_run)
    multiplexer.register_window(WINDOW_ID, "client_pool", "@7")
    await multiplexer.attach(WINDOW_ID, sender)
    await asyncio.wait_for(sent.wait(), timeout=1)
    await multiplexer.detach(WINDOW_ID)

    assert received == [b"\x1b[31mtmux\x1b[0m"]
    assert calls == [
        ["tmux", "display-message", "-p", "-t", "client_pool:@7", "#{window_id}"],
        ["tmux", "has-session", "-t", "web_terminal_view__7"],
        ["tmux", "new-session", "-d", "-t", "client_pool", "-s", "web_terminal_view__7"],
        ["tmux", "set-option", "-t", "web_terminal_view__7", "window-size", "manual"],
        ["tmux", "set-option", "-t", "web_terminal_view__7", "mouse", "on"],
        ["tmux", "select-window", "-t", "web_terminal_view__7:@7"],
        ["tmux", "set-option", "-p", "-t", "web_terminal_view__7:@7", "allow-passthrough", "on"],
        ["tmux", "kill-session", "-t", "web_terminal_view__7"],
    ]
    assert not any(call[:2] == ["tmux", "pipe-pane"] for call in calls)
    assert subprocess_calls[0][0][:4] == ("tmux", "attach-session", "-t", "web_terminal_view__7")
    assert raw_configured == [11]

@pytest.mark.skipif(shutil.which("tmux") is None, reason="tmux is required")
@pytest.mark.asyncio
async def test_tmux_attach_stream_preserves_managed_shell_command_markers() -> None:
    session = f"wt_marker_unit_{os.getpid()}_{int(time.time() * 1000)}"
    env = {**os.environ, "TERM": "xterm-256color"}
    managed_shell = build_managed_shell_command(
        shell="/bin/bash",
        client_id="12345678-1234-5678-1234-567812345678",
        window_id=WINDOW_ID,
        server_url="http://127.0.0.1:8000",
        project_path="/tmp",
    ).command

    subprocess.run(["tmux", "kill-session", "-t", session], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=env)
    try:
        subprocess.run(
            ["tmux", "new-session", "-d", "-s", session, "-x", "80", "-y", "24", managed_shell],
            check=True,
            env=env,
        )
        subprocess.run(
            ["tmux", "set-option", "-t", session, "allow-passthrough", "on"],
            check=True,
            env=env,
        )
        master_fd, slave_fd = pty.openpty()
        process = subprocess.Popen(
            ["tmux", "attach-session", "-t", session],
            stdin=slave_fd,
            stdout=slave_fd,
            stderr=slave_fd,
            close_fds=True,
            env=env,
        )
        os.close(slave_fd)
        try:
            output = bytearray()
            sent = False
            deadline = time.monotonic() + 5
            while time.monotonic() < deadline and b"web-terminal-command" not in output:
                readable, _, _ = select.select([master_fd], [], [], 0.05)
                if readable:
                    try:
                        chunk = os.read(master_fd, 65536)
                    except OSError as exc:
                        if exc.errno == errno.EIO:
                            break
                        raise
                    output.extend(chunk)
                    if not sent and (b"$ " in output or b"# " in output):
                        os.write(master_fd, b"echo tmux-marker-test\n")
                        sent = True
                elif not sent and time.monotonic() > deadline - 3:
                    os.write(master_fd, b"echo tmux-marker-test\n")
                    sent = True

            assert sent is True
            assert b"web-terminal-command" in output
        finally:
            process.terminate()
            with contextlib.suppress(subprocess.TimeoutExpired):
                process.wait(timeout=1)
            os.close(master_fd)
    finally:
        subprocess.run(["tmux", "kill-session", "-t", session], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=env)

@pytest.mark.skipif(shutil.which("tmux") is None, reason="tmux is required")
@pytest.mark.asyncio
async def test_tmux_literal_send_keys_command_reaches_shell_hook_and_history(tmp_path) -> None:
    session = f"wt_send_keys_unit_{os.getpid()}_{int(time.time() * 1000)}"
    env = {**os.environ, "TERM": "xterm-256color"}
    history_path = tmp_path / "history.txt"
    managed_shell = build_managed_shell_command(
        shell="/bin/bash",
        client_id="12345678-1234-5678-1234-567812345678",
        window_id=WINDOW_ID,
        server_url="http://127.0.0.1:8000",
        project_path="/tmp",
    ).command
    agent_command = "echo WT_SEND_KEYS_HISTORY_TOKEN"
    history_command = f"fc -ln -2 > {shlex.quote(str(history_path))}"

    subprocess.run(["tmux", "kill-session", "-t", session], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=env)
    try:
        subprocess.run(
            ["tmux", "new-session", "-d", "-s", session, "-x", "80", "-y", "24", managed_shell],
            check=True,
            env=env,
        )
        subprocess.run(
            ["tmux", "set-option", "-t", session, "allow-passthrough", "on"],
            check=True,
            env=env,
        )
        master_fd, slave_fd = pty.openpty()
        process = subprocess.Popen(
            ["tmux", "attach-session", "-t", session],
            stdin=slave_fd,
            stdout=slave_fd,
            stderr=slave_fd,
            close_fds=True,
            env=env,
        )
        os.close(slave_fd)
        try:
            output = bytearray()
            sent_agent = False
            sent_history = False
            deadline = time.monotonic() + 8
            while time.monotonic() < deadline:
                readable, _, _ = select.select([master_fd], [], [], 0.05)
                if readable:
                    try:
                        chunk = os.read(master_fd, 65536)
                    except OSError as exc:
                        if exc.errno == errno.EIO:
                            break
                        raise
                    output.extend(chunk)
                if not sent_agent and (b"$ " in output or b"# " in output):
                    subprocess.run(["tmux", "send-keys", "-l", "-t", session, "--", agent_command], check=True, env=env)
                    subprocess.run(["tmux", "send-keys", "-t", session, "Enter"], check=True, env=env)
                    sent_agent = True
                if sent_agent and not sent_history and b"WT_SEND_KEYS_HISTORY_TOKEN" in output:
                    subprocess.run(["tmux", "send-keys", "-l", "-t", session, "--", history_command], check=True, env=env)
                    subprocess.run(["tmux", "send-keys", "-t", session, "Enter"], check=True, env=env)
                    sent_history = True
                if sent_history and history_path.exists() and b"web-terminal-command" in output:
                    break

            assert sent_agent is True
            assert sent_history is True
            assert b"web-terminal-command" in output
            assert agent_command in history_path.read_text(encoding="utf-8")
        finally:
            process.terminate()
            with contextlib.suppress(subprocess.TimeoutExpired):
                process.wait(timeout=1)
            os.close(master_fd)
    finally:
        subprocess.run(["tmux", "kill-session", "-t", session], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=env)

@pytest.mark.asyncio
async def test_watch_active_window_emits_selection_when_shadow_session_changes(
    monkeypatch,
) -> None:
    calls: list[list[str]] = []
    selected: list[UUID] = []
    current_window = ["@7"]
    second_selection = asyncio.Event()
    release_read = threading.Event()

    async def fake_run(args: list[str]) -> str:
        calls.append(args)
        if args == ["tmux", "display-message", "-p", "-t", "client_pool:@7", "#{window_id}"]:
            return "@7\n"
        if args == ["tmux", "display-message", "-p", "-t", "client_pool:@8", "#{window_id}"]:
            return "@8\n"
        if args == ["tmux", "has-session", "-t", "web_terminal_view__7"]:
            return ""
        if args == ["tmux", "display-message", "-p", "-t", "web_terminal_view__7", "#{window_id}"]:
            return current_window[0]
        return ""

    class FakeProcess:
        returncode = None

        def terminate(self) -> None:
            self.returncode = -15

        async def wait(self) -> int:
            return self.returncode or 0

    async def fake_create_subprocess_exec(*args: object, **kwargs: object) -> FakeProcess:
        return FakeProcess()

    def fake_read(fd: int, size: int) -> bytes:
        release_read.wait(timeout=5)
        raise OSError

    async def sender(_data: bytes) -> None:
        return None

    async def selection_sender(window_id: UUID) -> None:
        selected.append(window_id)
        if window_id == OTHER_WINDOW_ID:
            second_selection.set()

    monkeypatch.setattr(client_terminal_public_ops.pty, "openpty", lambda: (10, 11))
    monkeypatch.setattr(client_terminal_public_ops, "_configure_pty_slave", lambda fd: None)
    monkeypatch.setattr(client_terminal_public_ops.os, "close", lambda fd: None)
    monkeypatch.setattr(client_terminal_private_ops.os, "read", fake_read)
    monkeypatch.setattr(client_terminal_private_ops, "SELECTION_POLL_INTERVAL_SECONDS", 0.01)
    monkeypatch.setattr(
        client_terminal_public_ops.asyncio,
        "create_subprocess_exec",
        fake_create_subprocess_exec,
    )

    multiplexer = ClientTerminalMultiplexer(runner=fake_run)
    multiplexer.register_window(WINDOW_ID, "client_pool", "@7")
    multiplexer.register_window(OTHER_WINDOW_ID, "client_pool", "@8")

    await multiplexer.attach_with_selection(WINDOW_ID, sender, selection_sender=selection_sender)
    try:
        await asyncio.sleep(0.05)
        current_window[0] = "@8"
        await asyncio.wait_for(second_selection.wait(), timeout=2)
    finally:
        release_read.set()
        await multiplexer.detach(WINDOW_ID)

    assert selected == [OTHER_WINDOW_ID]
    assert not any(call[:2] == ["tmux", "pipe-pane"] for call in calls)
    assert ["tmux", "display-message", "-p", "-t", "web_terminal_view__7", "#{window_id}"] in calls

@pytest.mark.asyncio
async def test_select_window_switches_view_shadow_session_without_new_attach() -> None:
    calls: list[list[str]] = []
    view_id = UUID("aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee")
    keepalive = asyncio.create_task(asyncio.sleep(10))

    async def fake_run(args: list[str]) -> str:
        calls.append(args)
        if args == ["tmux", "display-message", "-p", "-t", "client_pool:@8", "#{window_id}"]:
            return "@8\n"
        return ""

    class FakeProcess:
        returncode = None

        def send_signal(self, signal_number: int) -> None:
            return None

    multiplexer = ClientTerminalMultiplexer(runner=fake_run)
    multiplexer.register_window(WINDOW_ID, "client_pool", "@7")
    multiplexer.register_window(OTHER_WINDOW_ID, "client_pool", "@8")
    multiplexer._attached[str(view_id)] = _AttachedTerminal(
        master_fd=123,
        process=FakeProcess(),
        shadow_session="web_terminal_view_view_one",
        task=keepalive,
        size=(120, 40),
    )
    try:
        await multiplexer.select_window(OTHER_WINDOW_ID, view_id=view_id)
    finally:
        keepalive.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await keepalive

    assert calls == [
        ["tmux", "display-message", "-p", "-t", "client_pool:@8", "#{window_id}"],
        ["tmux", "select-window", "-t", f"web_terminal_view_{view_id}:@8"],
        ["tmux", "select-window", "-t", "client_pool:@8"],
        ["tmux", "resize-window", "-t", f"web_terminal_view_{view_id}:@8", "-x", "120", "-y", "40"],
    ]

@pytest.mark.asyncio
async def test_attach_fails_before_shadow_attach_when_registered_tmux_window_is_missing() -> None:
    calls: list[list[str]] = []

    async def fake_run(args: list[str]) -> str:
        calls.append(args)
        if args == ["tmux", "display-message", "-p", "-t", "client_pool:@7", "#{window_id}"]:
            raise RuntimeError("missing window")
        return ""

    async def sender(_data: bytes) -> None:
        return None

    multiplexer = ClientTerminalMultiplexer(runner=fake_run)
    multiplexer.register_window(WINDOW_ID, "client_pool", "@7")

    with pytest.raises(RuntimeError, match="tmux window is missing"):
        await multiplexer.attach(WINDOW_ID, sender)

    assert calls == [["tmux", "display-message", "-p", "-t", "client_pool:@7", "#{window_id}"]]

@pytest.mark.asyncio
async def test_attach_fails_when_registered_tmux_target_resolves_to_different_window() -> None:
    calls: list[list[str]] = []

    async def fake_run(args: list[str]) -> str:
        calls.append(args)
        if args == ["tmux", "display-message", "-p", "-t", "client_pool:@7", "#{window_id}"]:
            return "@8\n"
        return ""

    async def sender(_data: bytes) -> None:
        return None

    multiplexer = ClientTerminalMultiplexer(runner=fake_run)
    multiplexer.register_window(WINDOW_ID, "client_pool", "@7")

    with pytest.raises(RuntimeError, match="tmux window is missing"):
        await multiplexer.attach(WINDOW_ID, sender)

    assert calls == [["tmux", "display-message", "-p", "-t", "client_pool:@7", "#{window_id}"]]

@pytest.mark.asyncio
async def test_remove_window_detaches_matching_view_attachment(monkeypatch) -> None:
    closed: list[int] = []
    terminated: list[bool] = []
    view_id = UUID("aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee")
    keepalive = asyncio.create_task(asyncio.sleep(10))

    class FakeProcess:
        returncode = None

        def terminate(self) -> None:
            terminated.append(True)
            self.returncode = -15

        async def wait(self) -> int:
            return self.returncode or 0

    monkeypatch.setattr(client_terminal_private_ops.os, "close", lambda fd: closed.append(fd))

    calls: list[list[str]] = []

    async def fake_run(args: list[str]) -> str:
        calls.append(args)
        return ""

    multiplexer = ClientTerminalMultiplexer(runner=fake_run)
    multiplexer.register_window(WINDOW_ID, "client_pool", "@7")
    multiplexer.register_window(OTHER_WINDOW_ID, "client_pool", "@8")
    multiplexer._attached[str(view_id)] = _AttachedTerminal(
        master_fd=123,
        process=FakeProcess(),
        shadow_session="web_terminal_view_view_one",
        task=keepalive,
    )
    multiplexer._attachment_windows[str(view_id)] = str(OTHER_WINDOW_ID)

    await multiplexer.remove_window(OTHER_WINDOW_ID)

    assert closed == [123]
    assert terminated == [True]
    assert str(view_id) not in multiplexer._attached
    assert str(view_id) not in multiplexer._attachment_windows
    assert not multiplexer.is_registered(OTHER_WINDOW_ID)
    assert ["tmux", "kill-session", "-t", "web_terminal_view_view_one"] in calls
