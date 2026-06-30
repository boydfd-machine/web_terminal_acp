from __future__ import annotations

import logging
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from uuid import UUID

from app.models import Client, ClientRuntime, VirtualWindow
from app.contexts.terminal_runtime.domain.types import RuntimeWindow
from app.contexts.terminal_runtime.infrastructure.tmux_manager import TmuxManager
from app.contexts.terminal_runtime.infrastructure.tmux_targets import TmuxTarget

logger = logging.getLogger(__name__)


SHELL_COMMAND_NAMES = frozenset({"bash", "zsh", "sh", "fish", "dash", "ksh", "tcsh", "csh"})
AGENT_COMMAND_NAMES = frozenset(
    {
        "claude",
        "codex",
        "cursor",
        "cursor-agent",
        "agent",
        "agy",
        "agy-p",
        "antigravity-cli",
    }
)


@dataclass(frozen=True)
class PaneProcess:
    pid: int
    cmdline: str
    cwd: str | None


async def pane_has_active_non_shell_process(
    client: Client,
    window: VirtualWindow,
    *,
    tmux_manager: TmuxManager,
    remote_runtime: object | None = None,
) -> tuple[bool, list[str]]:
    """检查 todo 关联 window 的 tmux pane 里是否有非 shell 的活跃进程。

    本地 client：直接 tmux 命令 + /proc。
    远程 client：通过 client-agent 在远端 tmux pane 执行等价查询。
    """
    if client.runtime is not ClientRuntime.local:
        if remote_runtime is None:
            return False, []
        if not window.remote_session_id or not window.remote_window_id:
            return False, []
        try:
            processes = await remote_runtime.active_processes(
                RuntimeWindow(
                    session_id=window.remote_session_id,
                    window_id=window.remote_window_id,
                    cwd=window.cwd,
                    shell_command=window.shell_command,
                ),
                local_window_id=window.id,
            )
        except Exception:
            logger.debug("remote process liveness query failed", exc_info=True)
            return False, []
        active = [str(process) for process in processes if str(process).strip()]
        return bool(active), active
    if not window.tmux_session or not window.tmux_window_id:
        return False, []
    target = TmuxTarget(
        session=window.tmux_session,
        window_id=window.tmux_window_id,
        local_window_id=window.id,
    )
    foreground_cmd = await _pane_current_command(tmux_manager, target)
    active_processes: list[PaneProcess] = []
    if foreground_cmd and not _is_shell_or_agent_command_name(foreground_cmd):
        return True, [foreground_cmd]
    active_processes = await _pane_descendant_processes(tmux_manager, target)
    non_shell = [
        p for p in active_processes
        if p.cmdline and not _is_shell_or_agent_command_name(_command_name(p.cmdline))
    ]
    if non_shell:
        return True, [p.cmdline for p in non_shell]
    return False, [p.cmdline for p in active_processes]


def _target_string(target: TmuxTarget) -> str:
    return f"{target.session}:{target.window_id}"


async def _pane_current_command(tmux_manager: TmuxManager, target: TmuxTarget) -> str | None:
    try:
        output = await tmux_manager._run(
            [
                "tmux",
                "display-message",
                "-p",
                "-t",
                _target_string(target),
                "#{pane_current_command}",
            ]
        )
    except Exception:
        logger.debug("pane_current_command query failed", exc_info=True)
        return None
    return output.strip() or None


async def _pane_descendant_processes(tmux_manager: TmuxManager, target: TmuxTarget) -> list[PaneProcess]:
    try:
        output = await tmux_manager._run(
            [
                "tmux",
                "list-panes",
                "-t",
                _target_string(target),
                "-F",
                "#{pane_pid}",
            ]
        )
    except Exception:
        logger.debug("list-panes query failed", exc_info=True)
        return []
    pane_pids = [int(line.strip()) for line in output.splitlines() if line.strip().isdigit()]
    if not pane_pids:
        return []
    parent_map = _build_parent_map()
    watched_pids = _descendant_pids(pane_pids, parent_map)
    processes: list[PaneProcess] = []
    for pid in sorted(watched_pids):
        cmdline = _cmdline_for_pid(pid)
        if not cmdline:
            continue
        processes.append(PaneProcess(pid=pid, cmdline=cmdline, cwd=_cwd_for_pid(pid)))
    return processes


def _build_parent_map() -> dict[int, int]:
    parent_map: dict[int, int] = {}
    proc_root = Path("/proc")
    try:
        entries = list(proc_root.iterdir())
    except OSError:
        return parent_map
    for entry in entries:
        if not entry.name.isdigit():
            continue
        pid = int(entry.name)
        try:
            status_text = (entry / "status").read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for line in status_text.splitlines():
            if line.startswith("PPid:"):
                parts = line.split()
                if len(parts) >= 2 and parts[1].isdigit():
                    parent_map[pid] = int(parts[1])
                break
    return parent_map


def _descendant_pids(root_pids: list[int], parent_map: dict[int, int]) -> set[int]:
    children: dict[int, list[int]] = defaultdict(list)
    for pid, ppid in parent_map.items():
        children[ppid].append(pid)
    seen: set[int] = set()
    stack = list(root_pids)
    while stack:
        pid = stack.pop()
        if pid in seen:
            continue
        seen.add(pid)
        stack.extend(children.get(pid, []))
    return seen


def _cmdline_for_pid(pid: int) -> str:
    try:
        raw = (Path("/proc") / str(pid) / "cmdline").read_bytes()
    except OSError:
        return ""
    return raw.replace(b"\0", b" ").decode(errors="replace").strip()


def _cwd_for_pid(pid: int) -> str | None:
    try:
        return str((Path("/proc") / str(pid) / "cwd").resolve())
    except OSError:
        return None


def _command_name(cmdline: str) -> str:
    tokens = cmdline.split()
    if not tokens:
        return ""
    return Path(tokens[0]).name.lower()


def _is_shell_command_name(name: str) -> bool:
    return name.lower() in SHELL_COMMAND_NAMES


def _is_agent_command_name(name: str) -> bool:
    return name.lower() in AGENT_COMMAND_NAMES


def _is_shell_or_agent_command_name(name: str) -> bool:
    return _is_shell_command_name(name) or _is_agent_command_name(name)
