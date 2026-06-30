from __future__ import annotations

import json
import os
import shutil
import sqlite3
import stat
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable
from uuid import UUID, uuid4

from app.client_agent.agent_commands import agent_provider_from_command, format_agent_command
from app.contexts.terminal_runtime.application.codex_clone import (
    mark_codex_cloned_home,
    rewrite_codex_home,
)
from app.platform.plugins.agent_plugins import get_agent_plugin_registry
from app.platform.plugins.agent_plugins.shared_cache import link_shared_agent_cache_items
from app.platform.plugins.agent_plugins.types import AgentPlugin

_CLONE_IGNORED_NAMES = {".tmp", "log", "shell_snapshots"}


@dataclass(frozen=True)
class CloneWindowAgentHomesResult:
    cloned_agents: tuple[str, ...]
    session_ids: dict[str, str]
    resume_commands: dict[str, str]


def remove_window_agent_homes(window_id: UUID | str, *, home: Path | None = None) -> None:
    user_home = home or Path.home()
    target_id = str(window_id)
    for plugin in get_agent_plugin_registry().all():
        root = user_home / plugin.storage.managed_root / target_id
        if root.exists() and root.is_dir() and not root.is_symlink():
            shutil.rmtree(root)
        managed_home = root.parent / ".managed-home" / target_id
        if managed_home.exists() and managed_home.is_dir() and not managed_home.is_symlink():
            shutil.rmtree(managed_home)


def clone_window_agent_homes(
    source_window_id: UUID | str,
    target_window_id: UUID | str,
    *,
    home: Path | None = None,
    source_cwd: str | None = None,
    isolate_sessions: bool = False,
) -> CloneWindowAgentHomesResult:
    user_home = home or Path.home()
    source_id = str(source_window_id)
    target_id = str(target_window_id)
    cloned_agents: list[str] = []
    session_ids: dict[str, str] = {}
    resume_commands: dict[str, str] = {}

    for plugin in get_agent_plugin_registry().all():
        source_root = user_home / plugin.storage.managed_root / source_id
        if not source_root.exists():
            continue
        target_root = user_home / plugin.storage.managed_root / target_id
        if target_root.exists():
            shutil.rmtree(target_root)
        shutil.copytree(source_root, target_root, symlinks=True, ignore=_clone_ignore)
        link_shared_agent_cache_items(plugin.agent_client_id, target_root, home=user_home)
        cloned_agents.append(plugin.agent_client_id)
        if plugin.agent_client_id == "codex":
            new_session_id = rewrite_codex_home(target_root, isolate_sessions=isolate_sessions)
            mark_codex_cloned_home(target_root, source_id)
        elif plugin.agent_client_id == "claude":
            new_session_id = _new_session_id_for_plugin(plugin, target_root, source_cwd=source_cwd)
            _rewrite_claude_code_home(target_root, new_session_id)
        elif plugin.agent_client_id == "cursor":
            new_session_id = _new_session_id_for_plugin(plugin, target_root, source_cwd=source_cwd)
            _rewrite_cursor_home(target_root, new_session_id)
        else:
            new_session_id = _new_session_id_for_plugin(plugin, target_root, source_cwd=source_cwd)

        if new_session_id:
            session_ids[plugin.agent_client_id] = new_session_id
            resume_command = _resume_command_for_plugin(plugin, new_session_id)
            if resume_command is not None:
                resume_commands[plugin.agent_client_id] = resume_command
        elif plugin.agent_client_id == "codex":
            session_ids[plugin.agent_client_id] = ""

        _refresh_managed_home_alias(plugin.agent_client_id, target_root, user_home=user_home)

    return CloneWindowAgentHomesResult(
        cloned_agents=tuple(cloned_agents),
        session_ids=session_ids,
        resume_commands=resume_commands,
    )


def clone_resume_command(
    shell_command: str | None,
    clone_result: CloneWindowAgentHomesResult,
) -> str | None:
    if not shell_command:
        return None
    provider = agent_provider_from_command(shell_command)
    if provider is None:
        return None
    plugin = get_agent_plugin_registry().by_provider(provider)
    resume_commands = getattr(clone_result, "resume_commands", None)
    if not isinstance(resume_commands, dict):
        return None
    return resume_commands.get(plugin.agent_client_id)


def _clone_ignore(_directory: str, names: list[str]) -> set[str]:
    ignored: set[str] = set()
    directory = Path(_directory)
    for name in names:
        if name in _CLONE_IGNORED_NAMES:
            ignored.add(name)
            continue
        if _is_runtime_special_file(directory / name):
            ignored.add(name)
    return ignored


def _is_runtime_special_file(path: Path) -> bool:
    try:
        mode = path.lstat().st_mode
    except OSError:
        return True
    return not (stat.S_ISDIR(mode) or stat.S_ISREG(mode) or stat.S_ISLNK(mode))


def _resume_command_for_plugin(plugin: AgentPlugin, session_id: str) -> str | None:
    command_name = plugin.command.default_command
    if plugin.agent_client_id == "codex":
        return format_agent_command(command_name, "resume", session_id)
    if plugin.agent_client_id == "claude":
        return format_agent_command(command_name, "--resume", session_id)
    if plugin.agent_client_id == "cursor":
        return format_agent_command(command_name, "--resume", session_id)
    if plugin.agent_client_id == "antigravity":
        return format_agent_command(command_name, "--conversation", session_id)
    return None


def _new_session_id_for_plugin(
    plugin: AgentPlugin,
    target_root: Path,
    *,
    source_cwd: str | None,
) -> str:
    if plugin.agent_client_id == "antigravity":
        existing_id = _antigravity_resume_conversation_id(target_root, source_cwd=source_cwd)
        if existing_id:
            return existing_id
    return str(uuid4())


def _refresh_managed_home_alias(agent: str, managed_root: Path, *, user_home: Path) -> None:
    plugin = get_agent_plugin_registry().by_agent_id(agent)
    home_root = managed_root.parent / ".managed-home" / managed_root.name
    alias_path = Path(plugin.storage.managed_home_alias or plugin.storage.user_root)
    if alias_path.is_absolute() or ".." in alias_path.parts:
        return
    target = home_root / alias_path
    if target.exists() or target.is_symlink():
        if target.is_symlink():
            target.unlink()
        elif target.is_dir():
            shutil.rmtree(target)
        else:
            target.unlink()
    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        target.symlink_to(managed_root)
    except OSError:
        shutil.copytree(managed_root, target, symlinks=True, dirs_exist_ok=True)


def _rewrite_claude_code_home(root: Path, new_session_id: str) -> None:
    projects_dir = root / "projects"
    if projects_dir.exists():
        for path in sorted(projects_dir.rglob("*.jsonl")):
            if not path.is_file() or path.is_symlink():
                continue
            target_path = path
            if path.parent.name != "subagents":
                target_path = path.with_name(f"{new_session_id}.jsonl")
            _rewrite_jsonl_file(path, target_path, _rewrite_claude_payload(new_session_id))
    history = root / "history.jsonl"
    if history.is_file() and not history.is_symlink():
        _rewrite_jsonl_file(history, history, _rewrite_claude_payload(new_session_id))


def _rewrite_claude_payload(new_session_id: str):
    def rewrite(payload: dict[str, Any]) -> dict[str, Any]:
        if "sessionId" in payload:
            payload["sessionId"] = new_session_id
        return payload

    return rewrite


def _rewrite_cursor_home(root: Path, new_session_id: str) -> None:
    for store in _find_files_without_directory_symlinks(root, "store.db"):
        if store.is_symlink():
            continue
        _rewrite_cursor_store(store, new_session_id)


def _rewrite_cursor_store(path: Path, new_session_id: str) -> None:
    conn = sqlite3.connect(path)
    try:
        with conn:
            meta_rows = list(conn.execute("select key, value from meta"))
            for key, value in meta_rows:
                meta = _decode_cursor_meta(value)
                if meta is None:
                    continue
                meta["agentId"] = new_session_id
                if "latestRootBlobId" in meta and isinstance(meta["latestRootBlobId"], str):
                    meta["latestRootBlobId"] = _clone_id(meta["latestRootBlobId"], new_session_id)
                conn.execute(
                    "update meta set value = ? where key = ?", (_encode_cursor_meta(meta), key)
                )
            blob_rows = list(conn.execute("select id, data from blobs"))
            for blob_id, data in blob_rows:
                new_blob_id = _clone_id(str(blob_id), new_session_id)
                conn.execute("update blobs set id = ? where id = ?", (new_blob_id, blob_id))
                rewritten_data = _rewrite_cursor_blob_data(data, new_session_id)
                if rewritten_data is not None:
                    conn.execute(
                        "update blobs set data = ? where id = ?", (rewritten_data, new_blob_id)
                    )
    finally:
        conn.close()


def _decode_cursor_meta(value: Any) -> dict[str, Any] | None:
    try:
        if isinstance(value, bytes):
            value = value.decode("utf-8")
        if not isinstance(value, str):
            return None
        decoded = json.loads(bytes.fromhex(value).decode("utf-8"))
    except (TypeError, ValueError, UnicodeDecodeError, json.JSONDecodeError):
        return None
    return decoded if isinstance(decoded, dict) else None


def _encode_cursor_meta(value: dict[str, Any]) -> str:
    return json.dumps(value, separators=(",", ":")).encode("utf-8").hex()


def _rewrite_cursor_blob_data(data: Any, new_session_id: str) -> bytes | None:
    original_type = type(data)
    if isinstance(data, memoryview):
        data = data.tobytes()
    if isinstance(data, str):
        raw = data.encode("utf-8")
    elif isinstance(data, bytes):
        raw = data
    else:
        return None
    try:
        parsed = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None
    if not isinstance(parsed, dict):
        return None
    parsed["agentId"] = new_session_id
    encoded = json.dumps(parsed, separators=(",", ":")).encode("utf-8")
    return encoded if original_type is not str else encoded.decode("utf-8").encode("utf-8")


def _antigravity_resume_conversation_id(root: Path, *, source_cwd: str | None) -> str | None:
    cached = _antigravity_cached_conversation_id(root, source_cwd=source_cwd)
    if cached:
        return cached
    brain = root / "brain"
    if not brain.exists():
        return None
    session_dirs = sorted(
        (path for path in brain.iterdir() if path.is_dir() and not path.is_symlink()),
        key=lambda path: _path_mtime(path),
        reverse=True,
    )
    for session_dir in session_dirs:
        session_id = session_dir.name.strip()
        if session_id:
            return session_id
    return None


def _antigravity_cached_conversation_id(root: Path, *, source_cwd: str | None) -> str | None:
    cache_path = root / "cache" / "last_conversations.json"
    try:
        parsed = json.loads(cache_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None
    if not isinstance(parsed, dict):
        return None
    if source_cwd:
        value = parsed.get(source_cwd)
        if isinstance(value, str) and value.strip():
            return value.strip()
    for value in parsed.values():
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _path_mtime(path: Path) -> float:
    try:
        return path.stat().st_mtime
    except OSError:
        return 0.0


def _rewrite_jsonl_file(
    path: Path,
    target_path: Path,
    rewrite: Callable[[dict[str, Any]], dict[str, Any]],
) -> None:
    rows: list[str] = []
    try:
        raw_lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeDecodeError):
        return
    for line in raw_lines:
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            rows.append(line)
            continue
        if isinstance(payload, dict):
            payload = rewrite(payload)
        rows.append(json.dumps(payload, separators=(",", ":"), ensure_ascii=False))
    target_path.parent.mkdir(parents=True, exist_ok=True)
    target_path.write_text("\n".join(rows) + ("\n" if rows else ""), encoding="utf-8")
    if target_path != path:
        path.unlink(missing_ok=True)


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


def _clone_id(value: str, new_session_id: str) -> str:
    return f"{new_session_id}:{value}"
