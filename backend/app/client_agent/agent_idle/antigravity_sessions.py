from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from uuid import UUID

from app.client_agent.antigravity_watcher import (
    antigravity_home_for_window,
    antigravity_session_id_from_transcript_path,
    iter_antigravity_transcript_files,
)


@dataclass(frozen=True)
class AntigravitySessionData:
    session_id: str
    source_path: str
    last_output_at: float


def antigravity_session_id_from_payload(
    payload: dict[str, Any],
    source_path: str | None,
) -> str | None:
    if payload.get("isSidechain") is True:
        return None

    session_id = _string_value(payload.get("session_id")) or _string_value(
        payload.get("conversationId")
    )
    if session_id:
        return session_id.removeprefix("agent-") or None

    if source_path:
        return antigravity_session_id_from_transcript_path(Path(source_path))
    return None


def latest_antigravity_session_data(
    window_id: UUID,
    *,
    project_path: str | None = None,
) -> AntigravitySessionData | None:
    paths = _transcript_paths_by_session(window_id)
    cached_session_id = _cached_conversation_id(
        antigravity_home_for_window(window_id),
        source_cwd=project_path,
    )
    if cached_session_id:
        cached_path = paths.get(cached_session_id)
        if cached_path is not None:
            return _session_data(cached_session_id, cached_path)

    latest: AntigravitySessionData | None = None
    for session_id, path in paths.items():
        candidate = _session_data(session_id, path)
        if latest is None or candidate.last_output_at >= latest.last_output_at:
            latest = candidate
    return latest


def _transcript_paths_by_session(window_id: UUID) -> dict[str, Path]:
    paths: dict[str, Path] = {}
    for path in iter_antigravity_transcript_files(window_id):
        session_id = antigravity_session_id_from_transcript_path(path)
        if session_id:
            paths[session_id] = path
    return paths


def _session_data(session_id: str, path: Path) -> AntigravitySessionData:
    return AntigravitySessionData(
        session_id=session_id,
        source_path=str(path),
        last_output_at=_path_mtime(path),
    )


def _cached_conversation_id(root: Path, *, source_cwd: str | None) -> str | None:
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


def _string_value(value: Any) -> str | None:
    if isinstance(value, str):
        value = value.strip()
        return value or None
    if isinstance(value, (int, float, bool)):
        return str(value)
    return None
