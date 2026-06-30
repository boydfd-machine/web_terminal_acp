from tests.unit.test_tmux_manager_support import *

@pytest.mark.asyncio
async def test_current_window_id_reads_active_window_for_session():
    calls: list[list[str]] = []

    async def fake_run(args: list[str]) -> str:
        calls.append(args)
        return "@43\n"

    manager = TmuxManager(pool_session="web_terminal_acp_pool", default_shell="/bin/bash", runner=fake_run)

    assert await manager.current_window_id("web_terminal_view__42") == "@43"
    assert calls == [
        ["tmux", "display-message", "-p", "-t", "web_terminal_view__42", "#{window_id}"],
    ]

@pytest.mark.asyncio
async def test_has_window_returns_false_when_tmux_target_is_missing():
    async def fake_run(args: list[str]) -> str:
        raise TmuxCommandError(args, 1, "missing window")

    manager = TmuxManager(pool_session="web_terminal_acp_pool", default_shell="/bin/bash", runner=fake_run)

    assert await manager.has_window(TmuxTarget(session="web_terminal_acp_pool", window_id="@42")) is False

@pytest.mark.asyncio
async def test_has_window_returns_false_when_tmux_resolves_to_different_window():
    async def fake_run(args: list[str]) -> str:
        return "@43\n"

    manager = TmuxManager(pool_session="web_terminal_acp_pool", default_shell="/bin/bash", runner=fake_run)

    assert await manager.has_window(TmuxTarget(session="web_terminal_acp_pool", window_id="@42")) is False

@pytest.mark.asyncio
async def test_window_index_reads_existing_tmux_window_index():
    calls: list[list[str]] = []

    async def fake_run(args: list[str]) -> str:
        calls.append(args)
        return "@42\t7\n"

    manager = TmuxManager(pool_session="web_terminal_acp_pool", default_shell="/bin/bash", runner=fake_run)

    assert await manager.window_index(TmuxTarget(session="web_terminal_acp_pool", window_id="@42")) == "7"
    assert calls == [
        ["tmux", "display-message", "-p", "-t", "web_terminal_acp_pool:@42", "#{window_id}\t#{window_index}"],
    ]

@pytest.mark.asyncio
async def test_window_index_returns_none_when_tmux_resolves_to_different_window():
    async def fake_run(args: list[str]) -> str:
        return "@43\t8\n"

    manager = TmuxManager(pool_session="web_terminal_acp_pool", default_shell="/bin/bash", runner=fake_run)

    assert await manager.window_index(TmuxTarget(session="web_terminal_acp_pool", window_id="@42")) is None

@pytest.mark.asyncio
async def test_kill_window_skips_stale_tmux_target_that_resolves_to_different_window():
    calls: list[list[str]] = []

    async def fake_run(args: list[str]) -> str:
        calls.append(args)
        if args[:4] == ["tmux", "display-message", "-p", "-t"]:
            return "@43\n"
        raise AssertionError("stale target must not be killed")

    manager = TmuxManager(pool_session="web_terminal_acp_pool", default_shell="/bin/bash", runner=fake_run)

    await manager.kill_window(TmuxTarget(session="web_terminal_acp_pool", window_id="@42"))

    assert calls == [
        ["tmux", "display-message", "-p", "-t", "web_terminal_acp_pool:@42", "#{window_id}"],
    ]

@pytest.mark.asyncio
async def test_ensure_pool_is_idempotent_when_concurrent_creation_races():
    sessions: set[str] = set()
    calls: list[list[str]] = []
    create_lock = asyncio.Lock()

    async def fake_run(args: list[str]) -> str:
        calls.append(args)
        if args == ["tmux", "has-session", "-t", "web_terminal_acp_pool"]:
            if "web_terminal_acp_pool" not in sessions:
                await asyncio.sleep(0)
                raise TmuxCommandError(args, 1, "missing session")
            return ""
        if args == ["tmux", "new-session", "-d", "-s", "web_terminal_acp_pool", "/bin/bash"]:
            async with create_lock:
                if "web_terminal_acp_pool" in sessions:
                    raise TmuxCommandError(args, 1, "duplicate session")
                await asyncio.sleep(0)
                sessions.add("web_terminal_acp_pool")
            return ""
        return ""

    manager = TmuxManager(pool_session="web_terminal_acp_pool", default_shell="/bin/bash", runner=fake_run)

    await asyncio.gather(*(manager.ensure_pool() for _ in range(2)))

    assert "web_terminal_acp_pool" in sessions
    assert calls.count(["tmux", "new-session", "-d", "-s", "web_terminal_acp_pool", "/bin/bash"]) <= 2

@pytest.mark.asyncio
async def test_ensure_shadow_session_is_idempotent_when_concurrent_creation_races():
    sessions = {"web_terminal_acp_pool"}
    calls: list[list[str]] = []
    create_lock = asyncio.Lock()

    async def fake_run(args: list[str]) -> str:
        calls.append(args)
        if args == ["tmux", "has-session", "-t", "web_terminal_acp_pool"]:
            return ""
        if args == ["tmux", "has-session", "-t", "web_terminal_view__42"]:
            if "web_terminal_view__42" not in sessions:
                await asyncio.sleep(0)
                raise TmuxCommandError(args, 1, "missing session")
            return ""
        if args == ["tmux", "new-session", "-d", "-t", "web_terminal_acp_pool", "-s", "web_terminal_view__42"]:
            async with create_lock:
                if "web_terminal_view__42" in sessions:
                    raise TmuxCommandError(args, 1, "duplicate session")
                await asyncio.sleep(0)
                sessions.add("web_terminal_view__42")
            return ""
        if args in [
            ["tmux", "set-option", "-t", "web_terminal_acp_pool", "window-size", "manual"],
            ["tmux", "set-option", "-t", "web_terminal_acp_pool", "mouse", "on"],
            ["tmux", "set-option", "-t", "web_terminal_view__42", "window-size", "manual"],
            ["tmux", "set-option", "-t", "web_terminal_view__42", "mouse", "on"],
            ["tmux", "set-option", "-p", "-t", "web_terminal_view__42:@42", "allow-passthrough", "on"],
            ["tmux", "set-option", "-s", "set-clipboard", "external"],
            ["tmux", "show-options", "-s", "terminal-features"],
            ["tmux", "set-option", "-as", "terminal-features", ",xterm*:clipboard"],
        ]:
            return ""
        if args == ["tmux", "select-window", "-t", "web_terminal_view__42:@42"]:
            return ""
        raise AssertionError(f"unexpected tmux command: {args}")

    manager = TmuxManager(pool_session="web_terminal_acp_pool", default_shell="/bin/bash", runner=fake_run)

    targets = await asyncio.gather(
        *(manager.ensure_shadow_session(TmuxTarget(session="web_terminal_acp_pool", window_id="@42")) for _ in range(2))
    )

    assert targets == [TmuxAttachTarget(session="web_terminal_view__42"), TmuxAttachTarget(session="web_terminal_view__42")]
    assert "web_terminal_view__42" in sessions
    assert calls.count(["tmux", "select-window", "-t", "web_terminal_view__42:@42"]) == 2
