import pytest

from app.services.runtime.local import LocalTerminalRuntime
from app.contexts.terminal_runtime.infrastructure.local.stale_window_cleanup import (
    tmux_window_activity_timestamp,
)
from app.services.runtime.types import RuntimeWindow
from app.services.tmux_manager import TmuxTarget


@pytest.mark.asyncio
async def test_tmux_window_activity_timestamp_reads_tmux_window_activity() -> None:
    calls: list[list[str]] = []

    class FakeTmuxManager:
        async def _run(self, args: list[str]) -> str:
            calls.append(args)
            return "1717000000\n"

    timestamp = await tmux_window_activity_timestamp(
        FakeTmuxManager(),
        TmuxTarget(session="web_terminal_acp_pool", window_id="@42"),
    )

    assert timestamp == 1717000000.0
    assert calls == [
        [
            "tmux",
            "display-message",
            "-p",
            "-t",
            "web_terminal_acp_pool:@42",
            "#{window_activity}",
        ],
    ]


@pytest.mark.asyncio
async def test_runtime_recreates_stale_tmux_window_before_attach_or_selection() -> None:
    calls: list[tuple[str, object]] = []

    class FakeTmuxManager:
        async def has_window(self, target: TmuxTarget) -> bool:
            calls.append(("has_window", target))
            return True

        async def window_activity_timestamp(self, target: TmuxTarget) -> float:
            calls.append(("window_activity_timestamp", target))
            return 899.0

        async def kill_window(self, target: TmuxTarget) -> None:
            calls.append(("kill_window", target))

        async def recreate_window(self, target: TmuxTarget, *, local_window_id) -> TmuxTarget:
            calls.append(("recreate_window", (target, local_window_id)))
            return TmuxTarget(
                session=target.session,
                window_id="@9",
                cwd=target.cwd,
                shell_command=target.shell_command,
            )

    runtime = LocalTerminalRuntime(
        FakeTmuxManager(),
        stale_window_cleanup_seconds=100,
        stale_window_clock=lambda: 1000.0,
    )
    window = RuntimeWindow(
        session_id="web-terminal",
        window_id="@7",
        cwd="/workspace/project",
        shell_command="/bin/bash",
    )

    recreated = await runtime._ensure_runtime_window(window, local_window_id="window-1")

    target = TmuxTarget(
        session="web-terminal",
        window_id="@7",
        cwd="/workspace/project",
        shell_command="/bin/bash",
    )
    assert recreated == RuntimeWindow(
        session_id="web-terminal",
        window_id="@9",
        cwd="/workspace/project",
        shell_command="/bin/bash",
    )
    assert calls == [
        ("has_window", target),
        ("window_activity_timestamp", target),
        ("kill_window", TmuxTarget(**{**target.__dict__, "local_window_id": "window-1"})),
        ("recreate_window", (target, "window-1")),
    ]


@pytest.mark.asyncio
async def test_runtime_keeps_recent_tmux_window() -> None:
    calls: list[tuple[str, object]] = []

    class FakeTmuxManager:
        async def has_window(self, target: TmuxTarget) -> bool:
            calls.append(("has_window", target))
            return True

        async def window_activity_timestamp(self, target: TmuxTarget) -> float:
            calls.append(("window_activity_timestamp", target))
            return 950.0

        async def kill_window(self, target: TmuxTarget) -> None:
            calls.append(("kill_window", target))

        async def recreate_window(self, target: TmuxTarget, *, local_window_id) -> TmuxTarget:
            calls.append(("recreate_window", (target, local_window_id)))
            return target

    runtime = LocalTerminalRuntime(
        FakeTmuxManager(),
        stale_window_cleanup_seconds=100,
        stale_window_clock=lambda: 1000.0,
    )
    window = RuntimeWindow(session_id="web-terminal", window_id="@7")

    ensured = await runtime._ensure_runtime_window(window, local_window_id="window-1")

    assert ensured == window
    assert calls == [
        ("has_window", TmuxTarget(session="web-terminal", window_id="@7")),
        ("window_activity_timestamp", TmuxTarget(session="web-terminal", window_id="@7")),
    ]


@pytest.mark.asyncio
async def test_runtime_reads_missing_tmux_window_index_for_existing_window() -> None:
    calls: list[tuple[str, object]] = []

    class FakeTmuxManager:
        async def has_window(self, target: TmuxTarget) -> bool:
            calls.append(("has_window", target))
            return True

        async def window_index(self, target: TmuxTarget) -> str:
            calls.append(("window_index", target))
            return "4"

    runtime = LocalTerminalRuntime(FakeTmuxManager(), stale_window_cleanup_seconds=0)
    window = RuntimeWindow(session_id="web-terminal", window_id="@7")

    ensured = await runtime._ensure_runtime_window(window, local_window_id="window-1")

    assert ensured == RuntimeWindow(session_id="web-terminal", window_id="@7", window_index="4")
    assert calls == [
        ("has_window", TmuxTarget(session="web-terminal", window_id="@7")),
        ("window_index", TmuxTarget(session="web-terminal", window_id="@7")),
    ]


@pytest.mark.asyncio
async def test_runtime_keeps_stale_tmux_window_when_logical_window_is_retained() -> None:
    calls: list[tuple[str, object]] = []

    class FakeTmuxManager:
        async def has_window(self, target: TmuxTarget) -> bool:
            calls.append(("has_window", target))
            return True

        async def window_activity_timestamp(self, target: TmuxTarget) -> float:
            calls.append(("window_activity_timestamp", target))
            return 800.0

        async def kill_window(self, target: TmuxTarget) -> None:
            calls.append(("kill_window", target))

        async def recreate_window(self, target: TmuxTarget, *, local_window_id) -> TmuxTarget:
            calls.append(("recreate_window", (target, local_window_id)))
            return target

    async def retain_window(local_window_id: object) -> bool:
        calls.append(("retain_window", local_window_id))
        return local_window_id == "window-1"

    runtime = LocalTerminalRuntime(
        FakeTmuxManager(),
        stale_window_cleanup_seconds=100,
        stale_window_clock=lambda: 1000.0,
        stale_window_retain_check=retain_window,
    )
    window = RuntimeWindow(session_id="web-terminal", window_id="@7")

    ensured = await runtime._ensure_runtime_window(window, local_window_id="window-1")

    assert ensured == window
    assert calls == [
        ("has_window", TmuxTarget(session="web-terminal", window_id="@7")),
        ("window_activity_timestamp", TmuxTarget(session="web-terminal", window_id="@7")),
        ("retain_window", "window-1"),
    ]
