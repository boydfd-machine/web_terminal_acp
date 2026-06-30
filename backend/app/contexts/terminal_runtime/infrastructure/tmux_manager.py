from __future__ import annotations

import asyncio
import contextlib
import os
import re
from collections.abc import Awaitable, Callable, Iterable
from pathlib import Path
from typing import ClassVar, Protocol
from uuid import UUID

from app.client_agent.agent_commands import agent_command_for_interactive_shell
from app.config import get_settings
from app.models import LOCAL_CLIENT_ID
from app.contexts.terminal_runtime.infrastructure import tmux_paths
from app.contexts.terminal_runtime.infrastructure.managed_shell_launcher import ManagedShellLauncherStore
from app.contexts.terminal_runtime.infrastructure.tmux_direct_input import send_direct_input_to_tmux
from app.contexts.terminal_runtime.infrastructure.tmux_targets import TmuxAttachTarget, TmuxTarget, build_attach_command

Runner = Callable[[list[str]], Awaitable[str]]
DIRECT_INPUT_SUBMIT_DELAY_SECONDS = 0.1


class TmuxWindowTarget(Protocol):
    window_id: str


def shadow_session_name(window_id: str, view_id: str | None = None) -> str:
    value = view_id or window_id
    sanitized = re.sub(r"[^A-Za-z0-9_-]", "_", value)
    return f"web_terminal_view_{sanitized}"


def _mountinfo_bind_path_pairs(lines: Iterable[str]) -> list[tuple[str, str]]:
    return tmux_paths.mountinfo_bind_path_pairs(lines)


def _docker_bind_mount_path_pairs() -> list[tuple[str, str]]:
    return tmux_paths.docker_bind_mount_path_pairs()


def _map_host_path_to_container_path(path: str) -> str:
    return tmux_paths.map_host_path_to_container_path(path, _docker_bind_mount_path_pairs())


def get_tmux_manager() -> "TmuxManager":
    return TmuxManager()


class TmuxCommandError(RuntimeError):
    def __init__(self, args: list[str], returncode: int, stderr: str):
        self.args_list = args
        self.returncode = returncode
        self.stderr = stderr
        super().__init__(f"tmux command failed ({returncode}): {' '.join(args)}: {stderr.strip()}")


class TmuxManager:
    _session_locks: ClassVar[dict[str, asyncio.Lock]] = {}

    def __init__(
        self,
        pool_session: str | None = None,
        default_shell: str | None = None,
        server_url: str | None = None,
        launcher_dir: Path | None = None,
        runner: Runner | None = None,
    ) -> None:
        settings = get_settings()
        self.pool_session = pool_session or settings.tmux_pool_session
        self.default_shell = default_shell or settings.default_shell
        self.server_url = server_url or f"http://{settings.app_host}:{settings.app_port}"
        self.launcher_dir = launcher_dir or Path.home() / ".web-terminal-acp" / "launchers"
        self._managed_shell_launchers = ManagedShellLauncherStore(self.launcher_dir, self.server_url)
        self._runner = runner
        self._clipboard_configured = False
        self._clipboard_lock = asyncio.Lock()

    async def _run(self, args: list[str]) -> str:
        if self._runner is not None:
            return await self._runner(args)

        process = await asyncio.create_subprocess_exec(
            *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout, stderr = await process.communicate()
        except asyncio.CancelledError:
            with contextlib.suppress(ProcessLookupError):
                process.kill()
            with contextlib.suppress(Exception):
                await process.wait()
            raise
        if process.returncode != 0:
            raise TmuxCommandError(args, process.returncode, stderr.decode(errors="replace"))
        return stdout.decode(errors="replace")

    async def _run_with_stdin(self, args: list[str], stdin: bytes) -> str:
        if self._runner is not None:
            return await self._runner(args)

        process = await asyncio.create_subprocess_exec(
            *args,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout, stderr = await process.communicate(stdin)
        except asyncio.CancelledError:
            with contextlib.suppress(ProcessLookupError):
                process.kill()
            with contextlib.suppress(Exception):
                await process.wait()
            raise
        if process.returncode != 0:
            raise TmuxCommandError(args, process.returncode, stderr.decode(errors="replace"))
        return stdout.decode(errors="replace")

    @classmethod
    def _lock_for_session(cls, session_name: str) -> asyncio.Lock:
        lock = cls._session_locks.get(session_name)
        if lock is None:
            lock = asyncio.Lock()
            cls._session_locks[session_name] = lock
        return lock

    async def _has_session(self, session_name: str) -> bool:
        try:
            await self._run(["tmux", "has-session", "-t", session_name])
        except TmuxCommandError:
            return False
        return True

    async def _create_session_idempotently(
        self, session_name: str, command: list[str]
    ) -> None:
        if await self._has_session(session_name):
            return

        async with self._lock_for_session(session_name):
            if await self._has_session(session_name):
                return
            try:
                await self._run(command)
            except TmuxCommandError:
                if await self._has_session(session_name):
                    return
                raise

    async def ensure_pool(self) -> None:
        await self._create_session_idempotently(
            self.pool_session,
            ["tmux", "new-session", "-d", "-s", self.pool_session, self.default_shell],
        )
        await self._ensure_terminal_session_options(self.pool_session)
        await self._ensure_clipboard_support()

    async def _ensure_terminal_session_options(self, session_name: str) -> None:
        with contextlib.suppress(TmuxCommandError):
            await self._run(["tmux", "set-option", "-t", session_name, "window-size", "manual"])
        with contextlib.suppress(TmuxCommandError):
            await self._run(["tmux", "set-option", "-t", session_name, "mouse", "on"])

    async def _ensure_pane_passthrough(self, tmux_target: str) -> None:
        with contextlib.suppress(TmuxCommandError):
            await self._run(["tmux", "set-option", "-p", "-t", tmux_target, "allow-passthrough", "on"])

    async def _ensure_clipboard_support(self) -> None:
        if self._clipboard_configured:
            return

        async with self._clipboard_lock:
            if self._clipboard_configured:
                return

            with contextlib.suppress(TmuxCommandError):
                await self._run(["tmux", "set-option", "-s", "set-clipboard", "external"])
            terminal_features = ""
            with contextlib.suppress(TmuxCommandError):
                terminal_features = await self._run(["tmux", "show-options", "-s", "terminal-features"])
            if "clipboard" not in terminal_features:
                with contextlib.suppress(TmuxCommandError):
                    await self._run(
                        ["tmux", "set-option", "-as", "terminal-features", ",xterm*:clipboard"]
                    )
            self._clipboard_configured = True

    async def create_window(
        self,
        cwd: str | None,
        shell_command: str | None,
        *,
        client_id: UUID | str = LOCAL_CLIENT_ID,
        window_id: UUID | str | None = None,
        agent_ops_token: str | None = None,
    ) -> TmuxTarget:
        await self.ensure_pool()
        requested_cwd = cwd or os.getcwd()
        effective_cwd = _map_host_path_to_container_path(requested_cwd)
        effective_shell = shell_command or self.default_shell
        interactive_agent_command = (
            agent_command_for_interactive_shell(shell_command)
            if shell_command is not None
            else None
        )
        command = [
            "tmux",
            "new-window",
            "-P",
            "-F",
            "#{window_id}\t#{window_index}",
            "-t",
            self.pool_session,
        ]
        command.extend(["-c", effective_cwd])
        shell = self.default_shell if interactive_agent_command is not None else effective_shell
        if window_id is not None:
            shell = self.managed_shell_launcher_command(
                client_id=client_id,
                window_id=window_id,
                shell=shell,
                project_path=effective_cwd,
                agent_ops_token=agent_ops_token,
            )
        command.append(shell)
        try:
            tmux_window_id, tmux_window_index = _parse_new_window_output(await self._run(command))
        except Exception:
            if window_id is not None:
                self._remove_managed_shell_launcher(window_id)
            raise
        await self._ensure_pane_passthrough(f"{self.pool_session}:{tmux_window_id}")
        try:
            await self.select_window(TmuxTarget(session=self.pool_session, window_id=tmux_window_id))
        except TmuxCommandError as exc:
            if not _is_missing_tmux_window_error(exc, tmux_window_id):
                raise
            interactive_agent_command = None
            recovery_shell = self.default_shell
            if window_id is not None:
                recovery_shell = self.managed_shell_launcher_command(
                    client_id=client_id,
                    window_id=window_id,
                    shell=self.default_shell,
                    project_path=effective_cwd,
                    agent_ops_token=agent_ops_token,
                )
            tmux_window_id, tmux_window_index = _parse_new_window_output(
                await self._run(
                    [
                        "tmux",
                        "new-window",
                        "-P",
                        "-F",
                        "#{window_id}\t#{window_index}",
                        "-t",
                        self.pool_session,
                        "-c",
                        effective_cwd,
                        recovery_shell,
                    ]
                )
            )
            await self._ensure_pane_passthrough(f"{self.pool_session}:{tmux_window_id}")
            await self.select_window(TmuxTarget(session=self.pool_session, window_id=tmux_window_id))
        if interactive_agent_command is not None:
            await self._send_literal_command(
                f"{self.pool_session}:{tmux_window_id}", interactive_agent_command
            )
        effective_cwd = await self.window_cwd(
            TmuxTarget(session=self.pool_session, window_id=tmux_window_id),
            fallback=effective_cwd,
        )
        return TmuxTarget(
            session=self.pool_session,
            window_id=tmux_window_id,
            window_index=tmux_window_index,
            cwd=effective_cwd,
            shell_command=effective_shell,
            local_window_id=window_id,
        )

    def managed_shell_launcher_command(
        self,
        *,
        client_id: UUID | str,
        window_id: UUID | str,
        shell: str,
        project_path: str | None = None,
        agent_ops_token: str | None = None,
    ) -> str:
        return self._managed_shell_launchers.command(
            client_id=client_id,
            window_id=window_id,
            shell=shell,
            project_path=project_path,
            agent_ops_token=agent_ops_token,
        )

    def _remove_managed_shell_launcher(self, window_id: UUID | str) -> None:
        self._managed_shell_launchers.remove(window_id)

    async def _send_literal_command(self, tmux_target: str, command: str) -> None:
        await self._run(["tmux", "send-keys", "-l", "-t", tmux_target, "--", command])
        await asyncio.sleep(DIRECT_INPUT_SUBMIT_DELAY_SECONDS)
        await self._run(["tmux", "send-keys", "-t", tmux_target, "Enter"])

    async def send_input_direct(self, target: TmuxTarget, data: bytes) -> None:
        await send_direct_input_to_tmux(
            tmux_target=f"{target.session}:{target.window_id}",
            data=data,
            run=self._run,
            run_with_stdin=self._run_with_stdin,
            sleep=asyncio.sleep,
            submit_delay_seconds=DIRECT_INPUT_SUBMIT_DELAY_SECONDS,
        )

    async def recreate_window(
        self,
        target: TmuxTarget,
        *,
        local_window_id: UUID | str,
    ) -> TmuxTarget:
        return await self.create_window(
            target.cwd,
            target.shell_command,
            client_id=LOCAL_CLIENT_ID,
            window_id=local_window_id,
        )

    async def select_window(self, target: TmuxWindowTarget) -> None:
        session_name = (
            getattr(target, "session", None)
            or getattr(target, "session_id", None)
            or self.pool_session
        )
        await self._run(["tmux", "select-window", "-t", f"{session_name}:{target.window_id}"])

    async def ensure_shadow_session(
        self,
        target: TmuxTarget,
        *,
        view_id: str | None = None,
    ) -> TmuxAttachTarget:
        await self.ensure_pool()
        shadow_session = shadow_session_name(target.window_id, view_id)
        await self._create_session_idempotently(
            shadow_session,
            ["tmux", "new-session", "-d", "-t", target.session, "-s", shadow_session],
        )
        await self._ensure_terminal_session_options(shadow_session)
        await self._run(["tmux", "select-window", "-t", f"{shadow_session}:{target.window_id}"])
        await self._ensure_pane_passthrough(f"{shadow_session}:{target.window_id}")
        return TmuxAttachTarget(session=shadow_session)

    async def kill_shadow_session(
        self,
        target: TmuxWindowTarget,
        *,
        view_id: str | None = None,
    ) -> None:
        with contextlib.suppress(TmuxCommandError):
            await self._run([
                "tmux",
                "kill-session",
                "-t",
                shadow_session_name(target.window_id, view_id),
            ])

    async def resize_shadow_window(
        self,
        target: TmuxWindowTarget,
        *,
        cols: int,
        rows: int,
        view_id: str | None = None,
    ) -> None:
        await self._run([
            "tmux",
            "resize-window",
            "-t",
            f"{shadow_session_name(target.window_id, view_id)}:{target.window_id}",
            "-x",
            str(cols),
            "-y",
            str(rows),
        ])

    async def select_shadow_window(
        self,
        target: TmuxWindowTarget,
        *,
        view_id: str,
    ) -> None:
        await self._run(
            [
                "tmux",
                "select-window",
                "-t",
                f"{shadow_session_name(target.window_id, view_id)}:{target.window_id}",
            ]
        )

    async def current_window_id(self, session_name: str) -> str:
        return (
            await self._run(
                ["tmux", "display-message", "-p", "-t", session_name, "#{window_id}"]
            )
        ).strip()

    async def has_window(self, target: TmuxTarget) -> bool:
        try:
            window_id = (
                await self._run([
                    "tmux",
                    "display-message",
                    "-p",
                    "-t",
                    f"{target.session}:{target.window_id}",
                    "#{window_id}",
                ])
            ).strip()
        except TmuxCommandError:
            return False
        return window_id == target.window_id

    async def window_index(self, target: TmuxTarget) -> str | None:
        try:
            window_id, window_index = _parse_new_window_output(
                await self._run([
                    "tmux",
                    "display-message",
                    "-p",
                    "-t",
                    f"{target.session}:{target.window_id}",
                    "#{window_id}\t#{window_index}",
                ])
            )
        except TmuxCommandError:
            return None
        if window_id != target.window_id:
            return None
        return window_index

    async def window_cwd(self, target: TmuxTarget, *, fallback: str | None = None) -> str | None:
        try:
            cwd = (
                await self._run([
                    "tmux",
                    "display-message",
                    "-p",
                    "-t",
                    f"{target.session}:{target.window_id}",
                    "#{pane_current_path}",
                ])
            ).strip()
        except TmuxCommandError:
            return fallback
        return cwd or fallback

    async def kill_window(self, target: TmuxTarget) -> None:
        if not await self.has_window(target):
            if target.local_window_id is not None:
                self._remove_managed_shell_launcher(target.local_window_id)
            return
        await self._run([
            "tmux",
            "kill-window",
            "-t",
            f"{target.session}:{target.window_id}",
        ])
        if target.local_window_id is not None:
            self._remove_managed_shell_launcher(target.local_window_id)

    async def capture_window(self, target: TmuxTarget, *, history_lines: int | None = None) -> str:
        command = [
            "tmux",
            "capture-pane",
            "-p",
            "-t",
            f"{target.session}:{target.window_id}",
        ]
        if history_lines is not None and history_lines > 0:
            command.extend(["-S", f"-{history_lines}"])
        return await self._run(command)


def _is_missing_tmux_window_error(exc: BaseException, window_id: str) -> bool:
    message = str(exc)
    return f"can't find window: {window_id}" in message or re.search(r"can't find window: @\d+", message) is not None


def _parse_new_window_output(output: str) -> tuple[str, str | None]:
    first_line = output.strip().splitlines()[0] if output.strip() else ""
    window_id, separator, window_index = first_line.partition("\t")
    return window_id.strip(), window_index.strip() if separator and window_index.strip() else None
