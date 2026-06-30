from __future__ import annotations

import logging
from collections import defaultdict
from pathlib import Path

from app.client_agent.tmux_runtime import ClientTmuxRuntime

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


async def active_non_shell_processes_for_runtime_window(
    runtime: ClientTmuxRuntime,
    *,
    remote_session_id: str,
    remote_window_id: str,
) -> list[str]:
    target = f"{remote_session_id}:{remote_window_id}"
    foreground_cmd = await _pane_current_command(runtime, target)
    if foreground_cmd and not _is_shell_or_agent_command_name(foreground_cmd):
        return [foreground_cmd]

    processes = await _pane_descendant_cmdlines(runtime, target)
    return [
        cmdline
        for cmdline in processes
        if cmdline and not _is_shell_or_agent_command_name(_command_name(cmdline))
    ]


async def _pane_current_command(runtime: ClientTmuxRuntime, target: str) -> str | None:
    try:
        output = await runtime._run(
            [
                "tmux",
                "display-message",
                "-p",
                "-t",
                target,
                "#{pane_current_command}",
            ]
        )
    except Exception:
        logger.debug("remote pane_current_command query failed", exc_info=True)
        return None
    return output.strip() or None


async def _pane_descendant_cmdlines(runtime: ClientTmuxRuntime, target: str) -> list[str]:
    try:
        output = await runtime._run(
            [
                "tmux",
                "list-panes",
                "-t",
                target,
                "-F",
                "#{pane_pid}",
            ]
        )
    except Exception:
        logger.debug("remote list-panes query failed", exc_info=True)
        return []
    pane_pids = [int(line.strip()) for line in output.splitlines() if line.strip().isdigit()]
    if not pane_pids:
        return []

    parent_map = _build_parent_map()
    cmdlines: list[str] = []
    for pid in sorted(_descendant_pids(pane_pids, parent_map)):
        cmdline = _cmdline_for_pid(pid)
        if cmdline:
            cmdlines.append(cmdline)
    return cmdlines


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
