# ruff: noqa: F401
import asyncio

from pathlib import Path

from uuid import UUID

import pytest

import app.client_agent.runner as client_agent_runner

from app.client_agent.config import ClientAgentConfig

from app.services.agent_config import AgentConfig, AgentConfigItem, AgentConfigSection

from app.services.agent_profiles import AgentProfile

from app.client_agent.runner import (
    _handle_agent_message,
    _run_cleanup_step,
    _should_restore_agent_tool_watcher,
)

from app.client_agent.runtime_window import ClientRuntimeWindow, ClientRuntimeWindowCreation

from app.services.runtime.protocol import AgentMessage, TerminalPayload

WINDOW_ID = UUID("87654321-4321-8765-4321-876543218765")

VIEW_ID = UUID("aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee")

async def handle_message_for_test(
    writer,
    bulk_writer,
    config,
    runtime,
    terminal,
    supervisor,
    watcher,
    attach_snapshot_tasks,
    terminal_view_window_ids,
    message: AgentMessage,
    *,
    install_builtin_mcp=None,
    stale_window_cleanup=None,
) -> bool:
    original_install = client_agent_runner.agent_config_service.install_builtin_mcp_for_window
    client_agent_runner.agent_config_service.install_builtin_mcp_for_window = (
        install_builtin_mcp or (lambda **_kwargs: None)
    )
    try:
        return await _handle_agent_message(
            writer,
            bulk_writer,
            config,
            runtime,
            terminal,
            supervisor,
            watcher,
            FakeAuxTerminal(),
            attach_snapshot_tasks,
            set(),
            asyncio.Semaphore(1),
            terminal_view_window_ids,
            message,
            stale_window_cleanup=stale_window_cleanup,
        )
    finally:
        client_agent_runner.agent_config_service.install_builtin_mcp_for_window = original_install

class FakeWriter:
    def __init__(self) -> None:
        self.messages: list[AgentMessage] = []

    async def send(self, message: AgentMessage) -> None:
        self.messages.append(message)

class FakeBulkWriter:
    def __init__(self) -> None:
        self.terminal_messages: list[AgentMessage] = []

    async def send_terminal_output(self, message: AgentMessage) -> None:
        self.terminal_messages.append(message)
        return None

    async def send_ai_event(self, message: AgentMessage) -> None:
        return None

class FakeRuntime:
    def __init__(
        self,
        calls: list[str] | None = None,
        *,
        window_exists: bool = True,
        recreation_created: bool = True,
        pane_current_command: str = "bash",
        agent_processes_running: bool = False,
        window_activity_timestamp: float | None = None,
    ) -> None:
        self.calls = calls
        self.server_url = "https://control.example.com"
        self.default_shell = "/bin/bash"
        self.window_exists = window_exists
        self.recreation_created = recreation_created
        self.pane_current_command = pane_current_command
        self.agent_processes_running = agent_processes_running
        self._window_activity_timestamp = window_activity_timestamp
        self.recreated: list[UUID] = []
        self.recreate_shell_commands: list[str | None] = []
        self.create_shell_commands: list[str | None] = []
        self.killed: list[UUID] = []
        self.has_window_calls: list[tuple[str, str | None]] = []
        self.tmux_run_calls: list[list[str]] = []

    async def create_window(self, window_id, *, cwd=None, shell_command=None, agent_ops_token=None):
        if self.calls is not None:
            self.calls.append("create_window")
        self.create_shell_commands.append(shell_command)
        return ClientRuntimeWindow(
            remote_session_id="pool",
            remote_window_id="@9",
            local_window_id=window_id,
            cwd=cwd,
            shell_command=shell_command,
            managed_agent_tools=True,
        )

    async def kill_window(self, window_id) -> None:
        if self.calls is not None:
            self.calls.append("kill_window")
        self.killed.append(window_id)

    async def has_window(self, remote_window_id: str, *, remote_session_id: str | None = None) -> bool:
        self.has_window_calls.append((remote_window_id, remote_session_id))
        return self.window_exists

    async def window_activity_timestamp(self, remote_window_id, *, remote_session_id=None):
        return self._window_activity_timestamp

    async def _run(self, args: list[str]) -> str:
        self.tmux_run_calls.append(args)
        if args[:4] == ["tmux", "list-panes", "-t", "pool:@9"]:
            return "123\n" if self.agent_processes_running else ""
        if args[:4] == ["tmux", "display-message", "-p", "-t"]:
            return f"{self.pane_current_command}\n"
        return ""

    async def recreate_window(
        self,
        window_id: UUID,
        *,
        cwd: str | None = None,
        shell_command: str | None = None,
    ) -> ClientRuntimeWindow:
        return (
            await self.recreate_window_with_status(
                window_id,
                cwd=cwd,
                shell_command=shell_command,
            )
        ).window

    async def recreate_window_with_status(
        self,
        window_id: UUID,
        *,
        cwd: str | None = None,
        shell_command: str | None = None,
    ) -> ClientRuntimeWindowCreation:
        self.recreated.append(window_id)
        self.recreate_shell_commands.append(shell_command)
        return ClientRuntimeWindowCreation(
            window=ClientRuntimeWindow(
                remote_session_id="pool",
                remote_window_id="@9",
                local_window_id=window_id,
                cwd=cwd,
                shell_command=shell_command,
                managed_agent_tools=True,
            ),
            created=self.recreation_created,
        )

    async def recreate_stale_window_with_status(
        self,
        window_id: UUID,
        *,
        remote_session_id: str,
        remote_window_id: str,
        cwd: str | None = None,
        shell_command: str | None = None,
    ) -> ClientRuntimeWindowCreation:
        self.killed.append(window_id)
        return await self.recreate_window_with_status(
            window_id,
            cwd=cwd,
            shell_command=shell_command,
        )

class BlockingCreateRuntime(FakeRuntime):
    def __init__(
        self,
        calls: list[str],
        started: asyncio.Event,
        should_continue: asyncio.Event,
    ) -> None:
        super().__init__(calls)
        self.started = started
        self.should_continue = should_continue

    async def create_window(self, window_id, *, cwd=None, shell_command=None, agent_ops_token=None):
        if self.calls is not None:
            self.calls.append("create_window")
        self.started.set()
        await self.should_continue.wait()
        return ClientRuntimeWindow(
            remote_session_id="pool",
            remote_window_id="@9",
            local_window_id=window_id,
            cwd=cwd,
            managed_agent_tools=True,
        )

class FakeTerminal:
    def __init__(self, calls: list[str]) -> None:
        self.calls = calls
        self.capture_kwargs = []
        self.registered_remote_windows: dict[str, tuple[str, str]] = {}

    def registered_remote_window(self, window_id) -> tuple[str, str] | None:
        return self.registered_remote_windows.get(str(window_id))

    def register_window(self, window_id, remote_session_id, remote_window_id) -> None:
        self.registered_remote_windows[str(window_id)] = (remote_session_id, remote_window_id)
        self.calls.append("register_window")

    def unregister_window(self, window_id) -> None:
        self.registered_remote_windows.pop(str(window_id), None)
        self.calls.append("unregister_window")

    async def attach_with_selection(self, *args, **kwargs) -> None:
        self.calls.append("attach_with_selection")

    async def select_window(self, *args, **kwargs) -> None:
        self.calls.append("select_window")

    async def capture_output_bytes(self, *args, **kwargs) -> bytes:
        self.calls.append("capture_output_bytes")
        self.capture_kwargs.append(kwargs)
        return b"current screen"

    async def send_input_direct(self, *args, **kwargs) -> None:
        self.calls.append("send_input_direct")

    async def remove_window(self, window_id) -> None:
        self.calls.append("remove_window")

class FakeIdleSupervisor:
    def __init__(self, calls: list[str]) -> None:
        self.calls = calls
        self.resume_calls: list[tuple[UUID, bool]] = []
        self.resumable_session = False

    def attach_view(self, view_id: UUID, window_id: UUID) -> None:
        self.calls.append("attach_view")

    def detach_view(self, view_id: UUID) -> None:
        self.calls.append("detach_view")

    def remove_window(self, window_id: UUID) -> None:
        self.calls.append("remove_window_supervisor")

    def register_window(self, window_id: UUID, project_path: str | None) -> None:
        self.calls.append("register_window_supervisor")

    def has_resumable_session(self, window_id: UUID, *, project_path: str | None = None) -> bool:
        return self.resumable_session

    async def resume_window(self, window_id: UUID, *, allow_latest_session: bool = False) -> None:
        self.calls.append("resume_window")
        self.resume_calls.append((window_id, allow_latest_session))

class FakeAgentToolWatcher:
    def __init__(self, calls: list[str]) -> None:
        self.calls = calls
        self.watched: list[tuple[UUID, str | None] | tuple[UUID, str | None, frozenset[str] | None]] = []
        self.removed: list[UUID] = []

    def watch_window(
        self,
        window_id: UUID,
        project_path: str | None,
        *,
        providers: frozenset[str] | None = None,
    ) -> None:
        self.calls.append("watch_window")
        if providers is None:
            self.watched.append((window_id, project_path))
        else:
            self.watched.append((window_id, project_path, providers))

    def remove_window(self, window_id: UUID) -> None:
        self.calls.append("unwatch_window")
        self.removed.append(window_id)

class FakeAuxTerminal:
    def __init__(self) -> None:
        self.calls: list[tuple[str, object]] = []
        self.attach_sender = None

    async def ensure_terminal(self, aux_terminal_id: str, *, cwd=None, shell_command=None):
        self.calls.append(("ensure_terminal", aux_terminal_id))
        return type(
            "AuxTarget",
            (),
            {
                "aux_terminal_id": aux_terminal_id,
                "cwd": cwd,
                "shell_command": shell_command,
            },
        )()

    async def attach(self, aux_terminal_id: str, sender, *, view_id) -> None:
        self.calls.append(("attach", aux_terminal_id))
        self.attach_sender = sender

    async def detach(self, aux_terminal_id: str, *, view_id) -> None:
        self.calls.append(("detach", aux_terminal_id))

    async def send_input(self, aux_terminal_id: str, data: bytes, *, view_id) -> None:
        self.calls.append(("send_input", data))

    async def resize(self, aux_terminal_id: str, *, cols: int, rows: int, view_id) -> None:
        self.calls.append(("resize", (cols, rows)))

    async def kill(self, aux_terminal_id: str) -> None:
        self.calls.append(("kill", aux_terminal_id))

__all__ = [name for name in globals() if not name.startswith("__")]
