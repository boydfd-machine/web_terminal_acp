from __future__ import annotations

import pytest

from app.client_agent import process_liveness


@pytest.mark.asyncio
async def test_foreground_shell_returns_background_descendant(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeRuntime:
        async def _run(self, args: list[str]) -> str:
            if "display-message" in args:
                return "bash\n"
            if "list-panes" in args:
                return "100\n"
            return ""

    monkeypatch.setattr(process_liveness, "_build_parent_map", lambda: {101: 100, 102: 101})
    monkeypatch.setattr(
        process_liveness,
        "_cmdline_for_pid",
        lambda pid: {100: "bash", 101: "sleep 120", 102: "bash"}.get(pid, ""),
    )

    active = await process_liveness.active_non_shell_processes_for_runtime_window(
        FakeRuntime(),  # type: ignore[arg-type]
        remote_session_id="pool",
        remote_window_id="@9",
    )

    assert active == ["sleep 120"]


@pytest.mark.asyncio
async def test_foreground_non_shell_short_circuits_descendant_scan(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeRuntime:
        async def _run(self, args: list[str]) -> str:
            if "display-message" in args:
                return "node\n"
            raise AssertionError("descendant scan should not run for foreground work")

    active = await process_liveness.active_non_shell_processes_for_runtime_window(
        FakeRuntime(),  # type: ignore[arg-type]
        remote_session_id="pool",
        remote_window_id="@9",
    )

    assert active == ["node"]


@pytest.mark.asyncio
async def test_foreground_agent_cli_returns_background_descendant(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeRuntime:
        async def _run(self, args: list[str]) -> str:
            if "display-message" in args:
                return "claude\n"
            if "list-panes" in args:
                return "100\n"
            return ""

    monkeypatch.setattr(process_liveness, "_build_parent_map", lambda: {101: 100, 102: 101})
    monkeypatch.setattr(
        process_liveness,
        "_cmdline_for_pid",
        lambda pid: {100: "claude --dangerously-skip-permissions", 101: "sleep 120", 102: "zsh"}.get(pid, ""),
    )

    active = await process_liveness.active_non_shell_processes_for_runtime_window(
        FakeRuntime(),  # type: ignore[arg-type]
        remote_session_id="pool",
        remote_window_id="@9",
    )

    assert active == ["sleep 120"]
