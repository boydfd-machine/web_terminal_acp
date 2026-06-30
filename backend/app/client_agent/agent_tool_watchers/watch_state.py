# ruff: noqa: F401

import asyncio
import contextlib
import json
import logging
import os
import re
import sqlite3
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any
from uuid import UUID

from app.agent_plugins import get_agent_plugin_registry
from app.client_agent.agent_work_presence import (
    PRESENCE_SEND_INTERVAL_SECONDS,
    detect_agent_work_presence,
)
from app.client_agent.ai_events import ManagedAiEvent, managed_event_from_payload
from app.client_agent.antigravity_watcher import (
    antigravity_session_id_from_transcript_path,
    iter_antigravity_transcript_files,
)
from app.client_agent.codex_watcher import (
    codex_sessions_dir,
    iter_codex_session_files,
    iter_recent_codex_session_files,
    read_new_codex_events,
)
from app.client_agent.cursor_watcher import read_cursor_store_events
from app.client_agent.terminal import ClientTerminalMultiplexer
from app.client_agent.tmux_runtime import ClientTmuxRuntime
from app.services import agent_config as agent_config_service
from app.services.runtime.protocol import AgentMessage

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from app.client_agent.agent_idle import AgentIdleSupervisor
    from app.client_agent.stale_window_cleanup import ClientStaleWindowCleanup

ManagedEventSender = Callable[[AgentMessage], Awaitable[None]]
PresenceEventSender = Callable[[AgentMessage], Awaitable[None]]

AGENT_WATCH_ACTIVE_INTERVAL_SECONDS = 0.5
AGENT_WATCH_IDLE_INTERVAL_SECONDS = 2.0
AGENT_WATCH_MAX_INTERVAL_SECONDS = 5.0
AGENT_WATCH_SLOW_SCAN_SECONDS = 1.0
AGENT_WATCH_SLOW_SCAN_WARNING_INTERVAL_SECONDS = 60.0
AGENT_WATCH_DISCOVERY_INTERVAL_SECONDS = 30.0
CODEX_RECENT_DISCOVERY_INTERVAL_SECONDS = 2.0
CODEX_ACTIVE_SESSION_BOOTSTRAP_SECONDS = 10 * 60
CLAUDE_ACTIVE_SESSION_BOOTSTRAP_SECONDS = 10 * 60
CODEX_CLONE_MARKER = ".web-terminal-cloned-home"
CLAUDE_HISTORY_PENDING_RETRY_SECONDS = 2.0
AGENT_WATCH_COLLECTION_CONCURRENCY = 2
AGENT_WATCH_PROCESS_SCAN_INTERVAL_SECONDS = 30.0
_WATCH_COLLECTION_SEMAPHORE: asyncio.Semaphore | None = None
_WATCH_COLLECTION_SEMAPHORE_LOOP: asyncio.AbstractEventLoop | None = None


def ensure_cursor_window_chats_directory(window_id: UUID | str) -> None:
    from app.client_agent.cursor_statusline import ensure_cursor_statusline_setup

    root = Path.home() / ".web-terminal-acp" / "cursor-homes" / str(window_id)
    if not root.exists():
        return
    chats = root / "chats"
    if chats.is_symlink():
        chats.unlink()
    if not chats.exists():
        chats.mkdir(parents=True, exist_ok=True)
    ensure_cursor_statusline_setup(window_id)


def cursor_store_paths_for_window(window_id: UUID | str) -> list[Path]:
    root = Path.home() / ".web-terminal-acp" / "cursor-homes" / str(window_id)
    if not root.exists():
        return []
    paths: list[Path] = []
    chats = root / "chats"
    if chats.is_symlink():
        resolved_chats = chats.resolve()
        if resolved_chats.is_dir():
            paths.extend(_find_files_in_directory(resolved_chats, "store.db"))
    ensure_cursor_window_chats_directory(window_id)
    paths.extend(_find_files_without_directory_symlinks(root, "store.db"))
    return sorted(set(paths))


def _find_files_in_directory(root: Path, file_name: str) -> list[Path]:
    if not root.is_dir():
        return []
    return sorted(
        path
        for path in root.rglob(file_name)
        if path.is_file()
    )


def _find_files_without_directory_symlinks(root: Path, file_name: str) -> list[Path]:
    paths: list[Path] = []
    visited_dirs: set[tuple[int, int]] = set()
    for current_root, dir_names, file_names in os.walk(root, followlinks=False):
        current_path = Path(current_root)
        try:
            stat = current_path.stat()
        except OSError:
            dir_names[:] = []
            continue
        dir_key = (stat.st_dev, stat.st_ino)
        if dir_key in visited_dirs:
            dir_names[:] = []
            continue
        visited_dirs.add(dir_key)
        if file_name in file_names:
            path = current_path / file_name
            if path.is_file():
                paths.append(path)
    return sorted(paths)


def claude_code_home_for_window(window_id: UUID | str) -> Path:
    return Path.home() / ".web-terminal-acp" / "claude-code-homes" / str(window_id)


def claude_code_projects_dir(window_id: UUID | str) -> Path:
    return claude_code_home_for_window(window_id) / "projects"


def claude_code_history_file(window_id: UUID | str) -> Path:
    return claude_code_home_for_window(window_id) / "history.jsonl"


def iter_claude_code_jsonl_files(window_id: UUID | str) -> list[Path]:
    root = claude_code_projects_dir(window_id)
    if not root.exists():
        return []
    return sorted(path for path in root.rglob("*.jsonl") if path.is_file())


def iter_claude_code_transcript_files_for_session(window_id: UUID | str, session_id: str) -> list[Path]:
    root = claude_code_projects_dir(window_id)
    if not root.exists():
        return []
    return sorted(path for path in root.rglob(f"{session_id}.jsonl") if path.is_file())


def _global_codex_sessions_dir() -> Path:
    return Path.home() / ".codex" / "sessions"


def _global_claude_code_projects_dir() -> Path:
    return Path.home() / ".claude" / "projects"


def _relative_to(path: Path, root: Path) -> Path | None:
    try:
        return path.relative_to(root)
    except ValueError:
        return None


def _same_file(left: Path, right: Path) -> bool:
    with contextlib.suppress(OSError):
        return left.samefile(right)
    return False


def _hardlink_file_to_global(source: Path, target: Path) -> None:
    if target.exists() or target.is_symlink():
        if not _same_file(source, target):
            logger.debug(
                "skipping agent session global hardlink because target already exists",
                extra={"source_path": str(source), "target_path": str(target)},
            )
        return

    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        os.link(source, target)
    except FileExistsError:
        return
    except FileNotFoundError:
        return
    except OSError:
        logger.warning(
            "failed to hardlink agent session into global home",
            exc_info=True,
            extra={"source_path": str(source), "target_path": str(target)},
        )


def sync_codex_session_file_to_global(window_id: UUID | str, path: Path) -> None:
    relative_path = _relative_to(path, codex_sessions_dir(window_id))
    if relative_path is None:
        return
    _hardlink_file_to_global(path, _global_codex_sessions_dir() / relative_path)


def sync_claude_code_transcript_file_to_global(window_id: UUID | str, path: Path) -> None:
    relative_path = _relative_to(path, claude_code_projects_dir(window_id))
    if relative_path is None:
        return
    _hardlink_file_to_global(path, _global_claude_code_projects_dir() / relative_path)


def _claude_subagent_meta_path(path: Path) -> Path | None:
    if path.parent.name != "subagents" or not path.name.startswith("agent-") or path.suffix != ".jsonl":
        return None
    return path.with_suffix(".meta.json")


def _read_claude_subagent_meta(path: Path) -> dict[str, Any] | None:
    meta_path = _claude_subagent_meta_path(path)
    if meta_path is None or not meta_path.is_file():
        return None
    try:
        parsed = json.loads(meta_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeDecodeError):
        return None
    return parsed if isinstance(parsed, dict) else None


def _subagent_id_from_path(path: Path) -> str | None:
    if path.parent.name != "subagents" or not path.name.startswith("agent-") or path.suffix != ".jsonl":
        return None
    return path.stem.removeprefix("agent-") or None


def _claude_subagent_result_index(window_id: UUID | str) -> dict[str, list[dict[str, str]]]:
    root = claude_code_projects_dir(window_id)
    if not root.exists():
        return {}
    matches: dict[str, list[dict[str, str]]] = {}
    for meta_path in sorted(root.rglob("subagents/agent-*.meta.json")):
        try:
            parsed = json.loads(meta_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError, UnicodeDecodeError):
            continue
        if not isinstance(parsed, dict):
            continue
        tool_use_id = parsed.get("toolUseId")
        if not isinstance(tool_use_id, str) or not tool_use_id.strip():
            continue
        agent_id = meta_path.stem.removeprefix("agent-").removesuffix(".meta")
        if not agent_id:
            continue
        matches.setdefault(tool_use_id.strip(), []).append(
            {
                "agent_id": agent_id,
                "tool_use_id": tool_use_id.strip(),
                "source_path": str(meta_path.with_name(f"agent-{agent_id}.jsonl")),
            }
        )
    return matches


def _initial_process_scan_delay(window_id: UUID, interval_seconds: float) -> float:
    if interval_seconds <= 0:
        return 0.0
    interval_ms = max(1, int(interval_seconds * 1000))
    stagger_seconds = (window_id.int % interval_ms) / 1000.0
    return min(AGENT_WATCH_IDLE_INTERVAL_SECONDS, interval_seconds) + stagger_seconds


@dataclass
class AgentToolWatcherState:
    codex_offsets: dict[Path, int] = field(default_factory=dict)
    codex_session_files: list[Path] = field(default_factory=list)
    codex_session_files_refreshed_at: float = 0.0
    codex_recent_session_files_refreshed_at: float = 0.0
    claude_code_offsets: dict[Path, int] = field(default_factory=dict)
    claude_code_jsonl_files: list[Path] = field(default_factory=list)
    claude_code_jsonl_files_refreshed_at: float = 0.0
    claude_code_history_offset: int = 0
    claude_code_history_session_ids: set[str] = field(default_factory=set)
    claude_code_pending_history_session_ids: set[str] = field(default_factory=set)
    claude_code_pending_history_scanned_at: float = 0.0
    claude_code_history_jsonl_files: set[Path] = field(default_factory=set)
    cursor_store_paths: list[Path] = field(default_factory=list)
    cursor_seen_blob_ids: dict[Path, set[str]] = field(default_factory=dict)
    cursor_last_rowids: dict[Path, int] = field(default_factory=dict)
    cursor_discovery_started: bool = False
    cursor_statusline_fingerprint: str | None = None
    antigravity_offsets: dict[Path, int] = field(default_factory=dict)
    antigravity_transcript_files: list[Path] = field(default_factory=list)
    antigravity_transcript_files_refreshed_at: float = 0.0
    antigravity_subagent_targets: dict[str, dict[str, str]] = field(default_factory=dict)


def _agent_tool_collectors(namespace: dict[str, object] | None = None) -> tuple[tuple[str, str], ...]:
    lookup = globals() if namespace is None else namespace
    collectors: list[tuple[str, str]] = []
    for plugin in get_agent_plugin_registry().all():
        collector_name = plugin.watch_collector_name
        if collector_name is None:
            continue
        if not collector_name.isidentifier() or not callable(lookup.get(collector_name)):
            raise ValueError(
                f"agent plugin {plugin.agent_client_id!r} has invalid watch collector {collector_name!r}"
            )
        collectors.append((plugin.provider_id, collector_name))
    return tuple(collectors)


@dataclass
class AgentToolWatchWindow:
    window_id: UUID
    project_path: str | None
    providers: frozenset[str] | None = None
    state: AgentToolWatcherState = field(default_factory=AgentToolWatcherState)
    initialized: bool = False
    sleep_seconds: float = AGENT_WATCH_IDLE_INTERVAL_SECONDS
    next_event_scan_at: float = 0.0
    next_process_scan_at: float = 0.0
    next_slow_scan_warning_at: float = 0.0
