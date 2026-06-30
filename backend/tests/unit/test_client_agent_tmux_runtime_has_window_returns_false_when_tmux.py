import asyncio

from uuid import UUID

import pytest

from app.client_agent.runtime_window import ClientRuntimeWindow
from app.client_agent.tmux_runtime import ClientTmuxRuntime


CLIENT_ID = UUID("12345678-1234-5678-1234-567812345678")
WINDOW_ID = UUID("87654321-4321-8765-4321-876543218765")

@pytest.mark.asyncio
async def test_has_window_returns_false_when_tmux_resolves_different_remote_window() -> None:
    async def fake_run(args: list[str]) -> str:
        return "@10\n"

    runtime = ClientTmuxRuntime(
        client_id=CLIENT_ID,
        server_url="https://control.example.com",
        pool_session="client_pool",
        runner=fake_run,
    )

    assert not await runtime.has_window("@9")

@pytest.mark.asyncio
async def test_kill_window_skips_stale_remote_tmux_target() -> None:
    calls: list[list[str]] = []

    async def fake_run(args: list[str]) -> str:
        calls.append(args)
        if args[:4] == ["tmux", "has-session", "-t", "client_pool"]:
            return ""
        if args[:4] == ["tmux", "list-windows", "-t", "client_pool"]:
            return f"@9\t{WINDOW_ID}\t/tmp\t1\n"
        if args[:4] == ["tmux", "display-message", "-p", "-t"]:
            return "@10\n"
        if args[:2] == ["tmux", "kill-window"]:
            raise AssertionError("stale target must not be killed")
        return ""

    runtime = ClientTmuxRuntime(
        client_id=CLIENT_ID,
        server_url="https://control.example.com",
        pool_session="client_pool",
        runner=fake_run,
    )

    await runtime.kill_window(WINDOW_ID)

    assert calls[-1] == ["tmux", "display-message", "-p", "-t", "client_pool:@9", "#{window_id}"]
    assert not any(call[:2] == ["tmux", "kill-window"] for call in calls)

@pytest.mark.asyncio
async def test_kill_window_waits_for_in_progress_create_before_scanning_tmux(tmp_path) -> None:
    calls: list[list[str]] = []
    set_window_id_started = asyncio.Event()
    release_set_window_id = asyncio.Event()
    window_id_option_set = False

    async def fake_run(args: list[str]) -> str:
        nonlocal window_id_option_set
        calls.append(args)
        if args[:3] == ["tmux", "new-window", "-P"]:
            return "@9\n"
        if args == [
            "tmux",
            "set-option",
            "-w",
            "-t",
            "client_pool:@9",
            "@web-terminal-window-id",
            str(WINDOW_ID),
        ]:
            set_window_id_started.set()
            await release_set_window_id.wait()
            window_id_option_set = True
            return ""
        if args[:4] == ["tmux", "list-windows", "-t", "client_pool"]:
            local_id = str(WINDOW_ID) if window_id_option_set else ""
            return f"@9\t{local_id}\t/tmp\t1\n"
        if args[:4] == ["tmux", "display-message", "-p", "-t"]:
            return "@9\n"
        return ""

    runtime = ClientTmuxRuntime(
        client_id=CLIENT_ID,
        server_url="https://control.example.com",
        pool_session="client_pool",
        default_shell="/bin/bash",
        launcher_dir=tmp_path / "launchers",
        runner=fake_run,
    )

    create_task = asyncio.create_task(runtime.create_window(WINDOW_ID, cwd="/tmp"))
    await asyncio.wait_for(set_window_id_started.wait(), timeout=1)

    kill_task = asyncio.create_task(runtime.kill_window(WINDOW_ID))
    await asyncio.sleep(0)

    assert not kill_task.done()

    release_set_window_id.set()
    await create_task
    await kill_task

    kill_calls = [call for call in calls if call[:2] == ["tmux", "kill-window"]]
    assert kill_calls == [["tmux", "kill-window", "-t", "client_pool:@9"]]

@pytest.mark.asyncio
async def test_kill_window_before_queued_create_prevents_later_tmux_creation(tmp_path) -> None:
    calls: list[list[str]] = []

    async def fake_run(args: list[str]) -> str:
        calls.append(args)
        if args[:4] == ["tmux", "list-windows", "-t", "client_pool"]:
            return ""
        if args[:3] == ["tmux", "new-window", "-P"]:
            raise AssertionError("cancelled window must not create tmux window")
        return ""

    runtime = ClientTmuxRuntime(
        client_id=CLIENT_ID,
        server_url="https://control.example.com",
        pool_session="client_pool",
        default_shell="/bin/bash",
        launcher_dir=tmp_path / "launchers",
        runner=fake_run,
    )

    await runtime.kill_window(WINDOW_ID)

    with pytest.raises(RuntimeError, match="window creation was cancelled"):
        await runtime.create_window(WINDOW_ID, cwd="/tmp")

    assert not any(call[:3] == ["tmux", "new-window", "-P"] for call in calls)
