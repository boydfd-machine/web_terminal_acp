from tests.unit.test_tmux_manager_support import *

def test_shadow_session_name_is_stable():
    assert shadow_session_name("@42") == "web_terminal_view__42"

def test_shadow_session_name_sanitizes_unsafe_characters():
    assert shadow_session_name("pane:../weird id") == "web_terminal_view_pane____weird_id"

def test_shadow_session_name_prefers_view_id_when_present():
    assert shadow_session_name("@42", "view:one") == "web_terminal_view_view_one"

def test_build_attach_command_targets_shadow_session():
    target = TmuxAttachTarget(session="web_terminal_view__42")
    command = build_attach_command(target)
    assert command == ["tmux", "attach-session", "-t", "web_terminal_view__42"]

@pytest.mark.asyncio
async def test_capture_window_can_include_history_lines():
    calls: list[list[str]] = []

    async def fake_run(args: list[str]) -> str:
        calls.append(args)
        return "history\n"

    manager = TmuxManager(pool_session="web_terminal_acp_pool", default_shell="/bin/bash", runner=fake_run)
    target = TmuxTarget(session="web_terminal_acp_pool", window_id="@42")

    output = await manager.capture_window(target, history_lines=5000)

    assert output == "history\n"
    assert calls == [["tmux", "capture-pane", "-p", "-t", "web_terminal_acp_pool:@42", "-S", "-5000"]]

def test_mountinfo_bind_path_pairs_uses_mount_root_as_host_path():
    pairs = tmux_manager._mountinfo_bind_path_pairs(
        [
            (
                "2662 2549 254:1 /srv/workspace "
                "/workspace rw,relatime - ext4 /dev/vda1 rw,discard,errors=remount-ro"
            ),
            "1 0 0:1 / /proc rw,nosuid,nodev,noexec,relatime - proc proc rw",
        ]
    )

    assert pairs == [("/srv/workspace", "/workspace")]

@pytest.mark.asyncio
async def test_create_window_uses_pool_and_returns_tmux_target():
    calls: list[list[str]] = []

    async def fake_run(args: list[str]) -> str:
        calls.append(args)
        if args[:3] == ["tmux", "new-window", "-P"]:
            return "@42\t7\n"
        return ""

    manager = TmuxManager(pool_session="web_terminal_acp_pool", default_shell="/bin/bash", runner=fake_run)

    target = await manager.create_window("/tmp/project", "/bin/zsh")

    assert target == TmuxTarget(
        session="web_terminal_acp_pool",
        window_id="@42",
        window_index="7",
        cwd="/tmp/project",
        shell_command="/bin/zsh",
    )
    assert calls == [
        ["tmux", "has-session", "-t", "web_terminal_acp_pool"],
        ["tmux", "set-option", "-t", "web_terminal_acp_pool", "window-size", "manual"],
        ["tmux", "set-option", "-t", "web_terminal_acp_pool", "mouse", "on"],
        ["tmux", "set-option", "-s", "set-clipboard", "external"],
        ["tmux", "show-options", "-s", "terminal-features"],
        ["tmux", "set-option", "-as", "terminal-features", ",xterm*:clipboard"],
        ["tmux", "new-window", "-P", "-F", "#{window_id}\t#{window_index}", "-t", "web_terminal_acp_pool", "-c", "/tmp/project", "/bin/zsh"],
        ["tmux", "set-option", "-p", "-t", "web_terminal_acp_pool:@42", "allow-passthrough", "on"],
        ["tmux", "select-window", "-t", "web_terminal_acp_pool:@42"],
        ["tmux", "display-message", "-p", "-t", "web_terminal_acp_pool:@42", "#{pane_current_path}"],
    ]

@pytest.mark.asyncio
async def test_create_window_maps_host_bind_mount_path_and_returns_actual_cwd(monkeypatch):
    calls: list[list[str]] = []

    monkeypatch.setattr(
        tmux_manager,
        "_docker_bind_mount_path_pairs",
        lambda: [("/srv/workspace", "/workspace")],
    )

    async def fake_run(args: list[str]) -> str:
        calls.append(args)
        if args[:3] == ["tmux", "new-window", "-P"]:
            return "@42\n"
        if args == [
            "tmux",
            "display-message",
            "-p",
            "-t",
            "web_terminal_acp_pool:@42",
            "#{pane_current_path}",
        ]:
            return "/workspace/web_terminal_acp\n"
        return ""

    manager = TmuxManager(pool_session="web_terminal_acp_pool", default_shell="/bin/bash", runner=fake_run)

    target = await manager.create_window(
        "/srv/workspace/web_terminal_acp",
        None,
    )

    assert target.cwd == "/workspace/web_terminal_acp"
    new_window_call = next(call for call in calls if call[:3] == ["tmux", "new-window", "-P"])
    assert new_window_call[-2:] == ["/workspace/web_terminal_acp", "/bin/bash"]

@pytest.mark.asyncio
async def test_create_window_launches_direct_agent_inside_default_shell_with_literal_send_keys(tmp_path):
    calls: list[list[str]] = []

    async def fake_run(args: list[str]) -> str:
        calls.append(args)
        if args[:3] == ["tmux", "new-window", "-P"]:
            return "@42\n"
        return ""

    manager = TmuxManager(
        pool_session="web_terminal_acp_pool",
        default_shell="/bin/bash",
        launcher_dir=tmp_path / "launchers",
        runner=fake_run,
    )

    target = await manager.create_window(
        "/tmp/project",
        "claude --resume claude-session",
        window_id="87654321-4321-8765-4321-876543218765",
    )

    assert target.shell_command == "claude --resume claude-session"
    new_window_call = next(call for call in calls if call[:3] == ["tmux", "new-window", "-P"])
    launcher_path = tmp_path / "launchers" / "87654321-4321-8765-4321-876543218765.sh"
    assert new_window_call[-1] == f"exec {launcher_path}"
    launcher_text = launcher_path.read_text(encoding="utf-8")
    assert "exec /bin/bash --rcfile" in launcher_text
    assert "claude --dangerously-skip-permissions --resume claude-session" not in new_window_call[-1]
    assert [
        "tmux",
        "send-keys",
        "-l",
        "-t",
        "web_terminal_acp_pool:@42",
        "--",
        "claude --dangerously-skip-permissions --resume claude-session",
    ] in calls
    assert ["tmux", "send-keys", "-t", "web_terminal_acp_pool:@42", "Enter"] in calls

@pytest.mark.asyncio
async def test_send_input_direct_sends_literal_text_and_enter_after_yield(monkeypatch) -> None:
    calls: list[list[str]] = []
    sleep_calls: list[float] = []
    original_sleep = asyncio.sleep

    async def fake_sleep(delay: float) -> None:
        sleep_calls.append(delay)
        await original_sleep(0)

    monkeypatch.setattr(tmux_manager.asyncio, "sleep", fake_sleep)

    async def fake_run(args: list[str]) -> str:
        calls.append(args)
        return ""

    manager = TmuxManager(pool_session="web_terminal_acp_pool", default_shell="/bin/bash", runner=fake_run)

    await manager.send_input_direct(
        TmuxTarget(session="web_terminal_acp_pool", window_id="@42"),
        b"artifact prompt\n",
    )

    assert calls == [
        ["tmux", "send-keys", "-l", "-t", "web_terminal_acp_pool:@42", "--", "artifact prompt"],
        ["tmux", "send-keys", "-t", "web_terminal_acp_pool:@42", "Enter"],
    ]
    assert sleep_calls == [tmux_manager.DIRECT_INPUT_SUBMIT_DELAY_SECONDS]

@pytest.mark.asyncio
async def test_create_window_launches_proxychains_cursor_inside_default_shell(tmp_path):
    calls: list[list[str]] = []

    async def fake_run(args: list[str]) -> str:
        calls.append(args)
        if args[:3] == ["tmux", "new-window", "-P"]:
            return "@42\n"
        return ""

    manager = TmuxManager(
        pool_session="web_terminal_acp_pool",
        default_shell="/bin/bash",
        launcher_dir=tmp_path / "launchers",
        runner=fake_run,
    )

    target = await manager.create_window(
        "/tmp/project",
        "proxychains4 -q agent",
        window_id="87654321-4321-8765-4321-876543218765",
    )

    assert target.shell_command == "proxychains4 -q agent"
    new_window_call = next(call for call in calls if call[:3] == ["tmux", "new-window", "-P"])
    launcher_path = tmp_path / "launchers" / "87654321-4321-8765-4321-876543218765.sh"
    assert new_window_call[-1] == f"exec {launcher_path}"
    assert [
        "tmux",
        "send-keys",
        "-l",
        "-t",
        "web_terminal_acp_pool:@42",
        "--",
        "proxychains4 -q agent",
    ] in calls
    assert ["tmux", "send-keys", "-t", "web_terminal_acp_pool:@42", "Enter"] in calls

@pytest.mark.asyncio
async def test_create_window_uses_short_launcher_script_for_managed_shell(tmp_path):
    calls: list[list[str]] = []

    async def fake_run(args: list[str]) -> str:
        calls.append(args)
        if args[:3] == ["tmux", "new-window", "-P"]:
            return "@42\n"
        return ""

    manager = TmuxManager(
        pool_session="web_terminal_acp_pool",
        default_shell="/bin/bash",
        server_url="https://control.example.com/with space/it's-ok",
        launcher_dir=tmp_path / "launchers",
        runner=fake_run,
    )

    await manager.create_window(
        "/tmp/project",
        "/bin/bash",
        window_id="87654321-4321-8765-4321-876543218765",
    )

    new_window_call = next(call for call in calls if call[:3] == ["tmux", "new-window", "-P"])
    launcher_command = new_window_call[-1]
    launcher_path = tmp_path / "launchers" / "87654321-4321-8765-4321-876543218765.sh"
    assert launcher_command == f"exec {launcher_path}"
    assert len(launcher_command) < 200
    launcher_text = launcher_path.read_text(encoding="utf-8")
    assert launcher_text.startswith("#!/bin/sh\n")
    assert "WEB_TERMINAL_WINDOW_ID=87654321-4321-8765-4321-876543218765" in launcher_text
    assert "WEB_TERMINAL_PROJECT_PATH=/tmp/project" in launcher_text
    assert "exec /bin/bash" in launcher_text

@pytest.mark.asyncio
async def test_recreate_window_reuses_window_metadata_with_managed_shell(tmp_path):
    calls: list[list[str]] = []

    async def fake_run(args: list[str]) -> str:
        calls.append(args)
        if args[:3] == ["tmux", "new-window", "-P"]:
            return "@43\n"
        return ""

    manager = TmuxManager(
        pool_session="web_terminal_acp_pool",
        default_shell="/bin/bash",
        server_url="https://control.example.com",
        launcher_dir=tmp_path / "launchers",
        runner=fake_run,
    )
    target = await manager.recreate_window(
        TmuxTarget(
            session="web_terminal_acp_pool",
            window_id="@42",
            cwd="/tmp/project",
            shell_command="/bin/zsh",
        ),
        local_window_id="87654321-4321-8765-4321-876543218765",
    )

    assert target == TmuxTarget(
        session="web_terminal_acp_pool",
        window_id="@43",
        cwd="/tmp/project",
        shell_command="/bin/zsh",
        local_window_id="87654321-4321-8765-4321-876543218765",
    )
    new_window_call = next(call for call in calls if call[:3] == ["tmux", "new-window", "-P"])
    assert new_window_call[:9] == [
        "tmux",
        "new-window",
        "-P",
        "-F",
        "#{window_id}\t#{window_index}",
        "-t",
        "web_terminal_acp_pool",
        "-c",
        "/tmp/project",
    ]
    launcher_path = tmp_path / "launchers" / "87654321-4321-8765-4321-876543218765.sh"
    assert new_window_call[-1] == f"exec {launcher_path}"
    assert "WEB_TERMINAL_WINDOW_ID=87654321-4321-8765-4321-876543218765" in launcher_path.read_text(
        encoding="utf-8"
    )

@pytest.mark.asyncio
async def test_ensure_pool_creates_missing_pool_session():
    calls: list[list[str]] = []

    async def fake_run(args: list[str]) -> str:
        calls.append(args)
        if args == ["tmux", "has-session", "-t", "web_terminal_acp_pool"]:
            raise TmuxCommandError(args, 1, "missing session")
        return ""

    manager = TmuxManager(pool_session="web_terminal_acp_pool", default_shell="/bin/bash", runner=fake_run)

    await manager.ensure_pool()

    assert calls == [
        ["tmux", "has-session", "-t", "web_terminal_acp_pool"],
        ["tmux", "has-session", "-t", "web_terminal_acp_pool"],
        ["tmux", "new-session", "-d", "-s", "web_terminal_acp_pool", "/bin/bash"],
        ["tmux", "set-option", "-t", "web_terminal_acp_pool", "window-size", "manual"],
        ["tmux", "set-option", "-t", "web_terminal_acp_pool", "mouse", "on"],
        ["tmux", "set-option", "-s", "set-clipboard", "external"],
        ["tmux", "show-options", "-s", "terminal-features"],
        ["tmux", "set-option", "-as", "terminal-features", ",xterm*:clipboard"],
    ]

@pytest.mark.asyncio
async def test_ensure_shadow_session_groups_to_pool_and_selects_window():
    calls: list[list[str]] = []

    async def fake_run(args: list[str]) -> str:
        calls.append(args)
        if args == ["tmux", "has-session", "-t", "web_terminal_view__42"]:
            raise TmuxCommandError(args, 1, "missing session")
        return ""

    manager = TmuxManager(pool_session="web_terminal_acp_pool", default_shell="/bin/bash", runner=fake_run)

    attach_target = await manager.ensure_shadow_session(
        TmuxTarget(session="web_terminal_acp_pool", window_id="@42")
    )

    assert attach_target == TmuxAttachTarget(session="web_terminal_view__42")
    assert calls == [
        ["tmux", "has-session", "-t", "web_terminal_acp_pool"],
        ["tmux", "set-option", "-t", "web_terminal_acp_pool", "window-size", "manual"],
        ["tmux", "set-option", "-t", "web_terminal_acp_pool", "mouse", "on"],
        ["tmux", "set-option", "-s", "set-clipboard", "external"],
        ["tmux", "show-options", "-s", "terminal-features"],
        ["tmux", "set-option", "-as", "terminal-features", ",xterm*:clipboard"],
        ["tmux", "has-session", "-t", "web_terminal_view__42"],
        ["tmux", "has-session", "-t", "web_terminal_view__42"],
        ["tmux", "new-session", "-d", "-t", "web_terminal_acp_pool", "-s", "web_terminal_view__42"],
        ["tmux", "set-option", "-t", "web_terminal_view__42", "window-size", "manual"],
        ["tmux", "set-option", "-t", "web_terminal_view__42", "mouse", "on"],
        ["tmux", "select-window", "-t", "web_terminal_view__42:@42"],
        ["tmux", "set-option", "-p", "-t", "web_terminal_view__42:@42", "allow-passthrough", "on"],
    ]

@pytest.mark.asyncio
async def test_kill_shadow_session_removes_view_session():
    calls: list[list[str]] = []

    async def fake_run(args: list[str]) -> str:
        calls.append(args)
        return ""

    manager = TmuxManager(pool_session="web_terminal_acp_pool", default_shell="/bin/bash", runner=fake_run)

    await manager.kill_shadow_session(
        TmuxTarget(session="web_terminal_acp_pool", window_id="@42"),
        view_id="view:one",
    )

    assert calls == [["tmux", "kill-session", "-t", "web_terminal_view_view_one"]]

@pytest.mark.asyncio
async def test_has_window_returns_true_when_tmux_target_exists():
    calls: list[list[str]] = []

    async def fake_run(args: list[str]) -> str:
        calls.append(args)
        return "@42\n"

    manager = TmuxManager(pool_session="web_terminal_acp_pool", default_shell="/bin/bash", runner=fake_run)

    assert await manager.has_window(TmuxTarget(session="web_terminal_acp_pool", window_id="@42")) is True
    assert calls == [
        ["tmux", "display-message", "-p", "-t", "web_terminal_acp_pool:@42", "#{window_id}"],
    ]
