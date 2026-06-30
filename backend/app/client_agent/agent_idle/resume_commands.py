from __future__ import annotations

# ruff: noqa: F403,F405

import json
import sqlite3
import time
from pathlib import Path
from typing import Any

from app.client_agent.agent_idle.supervisor import *
from app.shared.codex_sessions import (
    codex_session_id_from_payload as _shared_codex_session_id_from_payload,
    codex_session_id_from_source_path as _shared_session_id_from_source_path,
)


def resume_command(record: SuspendedAgent) -> str | None:
    command_name = _resume_command_name(record.provider, record.command_name)
    if command_name is None:
        return None

    if record.provider == "claude_code":
        args = _claude_resume_args(record)
        provider_command = format_agent_command(command_name, *args)
    elif record.provider == "codex":
        provider_command = format_agent_command(command_name, "resume", record.session_id)
    elif record.provider == "cursor_cli":
        provider_command = f"{shlex.quote(command_name)} --resume {shlex.quote(record.session_id)}"
    elif record.provider == "antigravity_cli":
        provider_command = format_agent_command(command_name, "--conversation", record.session_id)
    else:
        return None

    cwd = _resume_cwd(record)
    if cwd:
        return f"cd {shlex.quote(cwd)} && WEB_TERMINAL_AUTO_RESUME=1 {provider_command}"
    return f"WEB_TERMINAL_AUTO_RESUME=1 {provider_command}"


def suspended_agent_from_process(
    session: AgentSessionRef,
    processes: tuple[AgentProcess, ...],
    *,
    project_path: str | None,
    suspended_at: float,
) -> SuspendedAgent | None:
    process = _root_agent_process(processes)
    command_name = _resume_command_name(
        session.provider,
        process.command_name if process is not None else None,
    )
    cwd = (process.cwd if process is not None else None) or project_path
    if command_name is None:
        return None
    return SuspendedAgent(
        provider=session.provider,
        session_id=session.session_id,
        command_name=command_name,
        cwd=cwd,
        source_path=session.source_path,
        last_output_at=session.last_output_at,
        suspended_at=suspended_at,
        claude_worktree_name=session.claude_worktree_name,
        claude_worktree_original_cwd=session.claude_worktree_original_cwd,
    )


async def terminate_agent_processes(processes: tuple[AgentProcess, ...]) -> None:
    pids = tuple(process.pid for process in processes)
    if not pids:
        return

    parent_map = await asyncio.to_thread(_build_parent_map)
    target_pids = await asyncio.to_thread(_descendant_pids, list(pids), parent_map)
    if not target_pids:
        target_pids = set(pids)

    await asyncio.to_thread(_signal_processes, target_pids, signal.SIGTERM)
    deadline = time.monotonic() + AGENT_TERMINATE_GRACE_SECONDS
    while time.monotonic() < deadline:
        if not any(_pid_exists(pid) for pid in target_pids):
            return
        await asyncio.sleep(0.1)
    await asyncio.to_thread(_signal_processes, target_pids, signal.SIGKILL)


def _latest_claude_session_id(path: Path) -> str | None:
    latest: str | None = None
    try:
        with path.open("rb") as handle:
            for raw_line in handle:
                try:
                    payload = json.loads(raw_line)
                except json.JSONDecodeError:
                    continue
                if isinstance(payload, dict):
                    latest = _string_value(payload.get("sessionId")) or latest
                    latest = _string_value(payload.get("session_id")) or latest
    except OSError:
        return None
    return latest


def _latest_claude_worktree_metadata(
    path: Path,
    *,
    session_id: str | None = None,
) -> tuple[str | None, str | None]:
    latest_name: str | None = None
    latest_original_cwd: str | None = None
    try:
        with path.open("rb") as handle:
            for raw_line in handle:
                try:
                    payload = json.loads(raw_line)
                except json.JSONDecodeError:
                    continue
                if not isinstance(payload, dict):
                    continue
                payload_session_id = session_id_from_payload("claude_code", payload, str(path))
                if session_id is not None and payload_session_id not in {None, session_id}:
                    continue
                worktree_name, original_cwd = _claude_worktree_metadata_from_payload(payload)
                if worktree_name is not None:
                    latest_name = worktree_name
                    latest_original_cwd = original_cwd
    except OSError:
        return None, None
    return latest_name, latest_original_cwd


def _latest_codex_session_id(path: Path) -> str | None:
    latest: str | None = None
    try:
        with path.open("rb") as handle:
            for raw_line in handle:
                try:
                    payload = json.loads(raw_line)
                except json.JSONDecodeError:
                    continue
                if isinstance(payload, dict):
                    latest = session_id_from_payload("codex", payload, str(path)) or latest
    except OSError:
        return None
    return latest or _shared_session_id_from_source_path(str(path))


def _codex_session_id_from_payload(
    payload: dict[str, Any],
    source_path: str | None = None,
) -> str | None:
    return _shared_codex_session_id_from_payload(payload, source_path)


def _claude_resume_args(record: SuspendedAgent) -> tuple[str, ...]:
    return ("--resume", record.session_id)


def _resume_cwd(record: SuspendedAgent) -> str | None:
    if record.provider == "claude_code" and record.claude_worktree_name is not None:
        return record.claude_worktree_original_cwd or record.cwd
    return record.cwd


def _claude_worktree_metadata_from_payload(payload: dict[str, Any]) -> tuple[str | None, str | None]:
    worktree_session = payload.get("worktreeSession")
    if not isinstance(worktree_session, dict):
        return None, None
    worktree_name = _valid_claude_worktree_name(
        _string_value(worktree_session.get("worktreeName"))
    )
    if worktree_name is None:
        return None, None
    return worktree_name, _string_value(worktree_session.get("originalCwd"))


def _valid_claude_worktree_name(value: str | None) -> str | None:
    if value is None or "/" in value or "\\" in value:
        return None
    return value


def _cursor_session_id(path: Path) -> str | None:
    meta = _cursor_store_meta(path)
    raw_id = _string_value(meta.get("agentId")) or _string_value(meta.get("chatId"))
    if raw_id:
        return raw_id
    parent_name = path.parent.name
    return parent_name if parent_name else None


def _cursor_store_meta(path: Path) -> dict[str, Any]:
    try:
        conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    except sqlite3.DatabaseError:
        return {}
    try:
        row = conn.execute("select value from meta order by key limit 1").fetchone()
    except sqlite3.DatabaseError:
        return {}
    finally:
        conn.close()
    if row is None:
        return {}

    value = row[0]
    try:
        if isinstance(value, bytes):
            value = value.decode("utf-8")
        if not isinstance(value, str):
            return {}
        decoded = json.loads(bytes.fromhex(value).decode("utf-8"))
    except (TypeError, ValueError, UnicodeDecodeError, json.JSONDecodeError):
        return {}
    return decoded if isinstance(decoded, dict) else {}


def _event_output_time(source_path: str | None) -> float:
    if source_path:
        return _path_mtime(Path(source_path))
    return time.time()


def _path_mtime(path: Path) -> float:
    try:
        return path.stat().st_mtime
    except OSError:
        return time.time()


def _session_id_from_path(source_path: str | None) -> str | None:
    return _shared_session_id_from_source_path(source_path)


def _newer_session(
    current: AgentSessionRef | None,
    candidate: AgentSessionRef,
) -> AgentSessionRef:
    if current is None or candidate.last_output_at >= current.last_output_at:
        return candidate
    return current


def _merge_session_metadata(
    current: AgentSessionRef | None,
    candidate: AgentSessionRef,
) -> AgentSessionRef:
    if (
        current is None
        or current.provider != candidate.provider
        or current.session_id != candidate.session_id
    ):
        return candidate
    claude_worktree_name = candidate.claude_worktree_name or current.claude_worktree_name
    claude_worktree_original_cwd = (
        candidate.claude_worktree_original_cwd or current.claude_worktree_original_cwd
    )
    if (
        claude_worktree_name == candidate.claude_worktree_name
        and claude_worktree_original_cwd == candidate.claude_worktree_original_cwd
    ):
        return candidate
    return AgentSessionRef(
        provider=candidate.provider,
        session_id=candidate.session_id,
        source_path=candidate.source_path,
        last_output_at=candidate.last_output_at,
        claude_worktree_name=claude_worktree_name,
        claude_worktree_original_cwd=claude_worktree_original_cwd,
    )


def _string_value(value: Any) -> str | None:
    if isinstance(value, str):
        value = value.strip()
        return value or None
    if isinstance(value, (int, float, bool)):
        return str(value)
    return None


def _claude_local_command_payload(payload: dict[str, Any]) -> bool:
    if _string_value(payload.get("type")) != "user":
        return False

    message = payload.get("message")
    if not isinstance(message, dict):
        return False
    role = _string_value(message.get("role"))
    if role not in {None, "user"}:
        return False

    content = _string_value(message.get("content"))
    if content is None:
        return payload.get("isMeta") is True

    stripped = content.lstrip()
    return payload.get("isMeta") is True or any(
        stripped.startswith(prefix) for prefix in _CLAUDE_LOCAL_COMMAND_PREFIXES
    )


def _root_agent_process(processes: tuple[AgentProcess, ...]) -> AgentProcess | None:
    return min(processes, key=lambda process: process.pid) if processes else None


def _resume_command_name(provider: str, detected_command: str | None) -> str | None:
    detected_command = detected_command or ""
    commands = _provider_commands().get(provider, set())
    if detected_command in commands:
        return detected_command
    return _default_commands().get(provider)


def _default_commands() -> dict[str, str]:
    return {
        plugin.provider_id: plugin.command.default_command
        for plugin in get_agent_plugin_registry().all()
    }


def _provider_commands() -> dict[str, set[str]]:
    return {
        plugin.provider_id: set(plugin.command.command_names)
        for plugin in get_agent_plugin_registry().all()
    }


def _suspended_agent_from_dict(value: dict[str, Any]) -> SuspendedAgent | None:
    provider = _string_value(value.get("provider"))
    session_id = _string_value(value.get("session_id"))
    command_name = _string_value(value.get("command_name"))
    if provider is None or session_id is None or command_name is None:
        return None
    return SuspendedAgent(
        provider=provider,
        session_id=session_id,
        command_name=command_name,
        cwd=_string_value(value.get("cwd")),
        source_path=_string_value(value.get("source_path")),
        last_output_at=float(value.get("last_output_at") or 0),
        suspended_at=float(value.get("suspended_at") or 0),
        claude_worktree_name=_valid_claude_worktree_name(
            _string_value(value.get("claude_worktree_name"))
        ),
        claude_worktree_original_cwd=_string_value(value.get("claude_worktree_original_cwd")),
    )


def _signal_processes(pids: set[int], sig: int) -> None:
    current_pid = os.getpid()
    for pid in sorted(pids, reverse=True):
        if pid <= 1 or pid == current_pid:
            continue
        try:
            os.kill(pid, sig)
        except ProcessLookupError:
            continue
        except PermissionError:
            logger.debug("cannot signal agent process", extra={"pid": pid, "signal": sig})


def _pid_exists(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True


__all__ = [name for name in globals() if not name.startswith("__")]
