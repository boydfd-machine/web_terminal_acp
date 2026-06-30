from __future__ import annotations

from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.contexts.terminal_runtime.application import process_liveness as pl
from app.contexts.terminal_runtime.domain.types import RuntimeWindow
from app.contexts.terminal_runtime.infrastructure.tmux_targets import TmuxTarget
from app.models import Client, ClientRuntime, VirtualWindow, WindowStatus


def _make_local_client() -> Client:
    return Client(
        id=uuid4(),
        name="local",
        runtime=ClientRuntime.local,
        owner_user_id="owner-1",
    )


def _make_window() -> VirtualWindow:
    return VirtualWindow(
        id=uuid4(),
        client_id=uuid4(),
        title="Terminal",
        status=WindowStatus.active,
        tmux_session="session-1",
        tmux_window_id="@1",
    )


def test_command_name_extracts_basename() -> None:
    assert pl._command_name("/usr/bin/node dev-server.js") == "node"
    assert pl._command_name("python3 -m http.server") == "python3"
    assert pl._command_name("") == ""


def test_is_shell_command_name_matches_common_shells() -> None:
    assert pl._is_shell_command_name("bash") is True
    assert pl._is_shell_command_name("ZSH") is True
    assert pl._is_shell_command_name("node") is False
    assert pl._is_shell_command_name("python") is False


def test_descendant_pids_walks_parent_map() -> None:
    parent_map = {2: 1, 3: 2, 4: 2, 5: 4}
    result = pl._descendant_pids([1], parent_map)
    assert result == {1, 2, 3, 4, 5}


def test_descendant_pids_handles_cycles() -> None:
    parent_map = {2: 1, 1: 2}
    result = pl._descendant_pids([1], parent_map)
    assert result == {1, 2}


def test_target_string_uses_session_and_window_id() -> None:
    target = TmuxTarget(session="sess", window_id="@5")
    assert pl._target_string(target) == "sess:@5"


@pytest.mark.asyncio
async def test_remote_client_returns_false() -> None:
    client = _make_local_client()
    client.runtime = ClientRuntime.remote
    window = _make_window()
    tmux_manager = object()
    has_active, processes = await pl.pane_has_active_non_shell_process(
        client, window, tmux_manager=tmux_manager  # type: ignore[arg-type]
    )
    assert has_active is False
    assert processes == []


@pytest.mark.asyncio
async def test_remote_client_queries_remote_runtime_for_active_processes() -> None:
    client = _make_local_client()
    client.runtime = ClientRuntime.remote
    window = _make_window()
    window.tmux_session = None
    window.tmux_window_id = None
    window.remote_session_id = "remote-session"
    window.remote_window_id = "@9"
    remote_runtime = AsyncMock()
    remote_runtime.active_processes.return_value = ["sleep 120"]

    has_active, processes = await pl.pane_has_active_non_shell_process(
        client,
        window,
        tmux_manager=object(),  # type: ignore[arg-type]
        remote_runtime=remote_runtime,
    )

    assert has_active is True
    assert processes == ["sleep 120"]
    remote_runtime.active_processes.assert_awaited_once_with(
        RuntimeWindow(
            session_id=window.remote_session_id,
            window_id=window.remote_window_id,
            cwd=window.cwd,
            shell_command=window.shell_command,
        ),
        local_window_id=window.id,
    )


@pytest.mark.asyncio
async def test_remote_client_without_remote_runtime_binding_returns_false() -> None:
    client = _make_local_client()
    client.runtime = ClientRuntime.remote
    window = _make_window()
    window.tmux_session = "stale-local-session"
    window.tmux_window_id = "@1"
    window.remote_session_id = None
    window.remote_window_id = None
    remote_runtime = AsyncMock()

    has_active, processes = await pl.pane_has_active_non_shell_process(
        client,
        window,
        tmux_manager=object(),  # type: ignore[arg-type]
        remote_runtime=remote_runtime,
    )

    assert has_active is False
    assert processes == []
    remote_runtime.active_processes.assert_not_called()


@pytest.mark.asyncio
async def test_window_without_tmux_session_returns_false() -> None:
    client = _make_local_client()
    window = _make_window()
    window.tmux_session = None
    tmux_manager = object()
    has_active, _ = await pl.pane_has_active_non_shell_process(
        client, window, tmux_manager=tmux_manager  # type: ignore[arg-type]
    )
    assert has_active is False


@pytest.mark.asyncio
async def test_foreground_non_shell_triggers_active(monkeypatch) -> None:
    client = _make_local_client()
    window = _make_window()

    async def fake_run(args):
        return "node"

    class FakeTmuxManager:
        async def _run(self, args):
            return await fake_run(args)

    has_active, processes = await pl.pane_has_active_non_shell_process(
        client, window, tmux_manager=FakeTmuxManager()  # type: ignore[arg-type]
    )
    assert has_active is True
    assert processes == ["node"]


@pytest.mark.asyncio
async def test_foreground_shell_falls_through_to_descendants(monkeypatch) -> None:
    client = _make_local_client()
    window = _make_window()

    class FakeTmuxManager:
        async def _run(self, args):
            if "display-message" in args:
                return "bash"
            if "list-panes" in args:
                return "12345"
            return ""

    async def fake_descendants(_manager, _target):
        return [
            pl.PaneProcess(pid=12345, cmdline="bash", cwd="/tmp"),
            pl.PaneProcess(pid=12346, cmdline="npm run dev", cwd="/tmp/proj"),
        ]

    monkeypatch.setattr(pl, "_pane_descendant_processes", fake_descendants)

    has_active, processes = await pl.pane_has_active_non_shell_process(
        client, window, tmux_manager=FakeTmuxManager()  # type: ignore[arg-type]
    )
    assert has_active is True
    assert "npm run dev" in processes


@pytest.mark.asyncio
async def test_foreground_agent_cli_falls_through_to_background_descendants(monkeypatch) -> None:
    client = _make_local_client()
    window = _make_window()

    class FakeTmuxManager:
        async def _run(self, args):
            if "display-message" in args:
                return "claude"
            if "list-panes" in args:
                return "12345"
            return ""

    async def fake_descendants(_manager, _target):
        return [
            pl.PaneProcess(pid=12345, cmdline="claude --dangerously-skip-permissions", cwd="/tmp"),
            pl.PaneProcess(pid=12346, cmdline="sleep 120", cwd="/tmp/proj"),
        ]

    monkeypatch.setattr(pl, "_pane_descendant_processes", fake_descendants)

    has_active, processes = await pl.pane_has_active_non_shell_process(
        client, window, tmux_manager=FakeTmuxManager()  # type: ignore[arg-type]
    )
    assert has_active is True
    assert processes == ["sleep 120"]
