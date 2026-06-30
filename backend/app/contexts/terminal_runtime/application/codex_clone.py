from __future__ import annotations

import json
import re
import sqlite3
from pathlib import Path
from typing import Any, Callable
from uuid import uuid4

CODEX_CLONE_MARKER = ".web-terminal-cloned-home"

_CODEX_ROLLOUT_SESSION_ID = re.compile(
    r"(?P<prefix>rollout-[^.]*-)(?P<session>[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})(?P<suffix>\.jsonl)$",
    re.IGNORECASE,
)


def rewrite_codex_home(root: Path, *, isolate_sessions: bool = False) -> str | None:
    _ = isolate_sessions
    session_id = _latest_codex_thread_id(root) or _latest_codex_session_file_id(root)
    if session_id:
        _retarget_codex_rollout_paths(root)
        return session_id

    session_id = str(uuid4())
    rewritten = False
    sessions_dir = root / "sessions"
    if sessions_dir.exists():
        for path in sorted(sessions_dir.rglob("*.jsonl")):
            if not path.is_file() or path.is_symlink():
                continue
            target_path = _codex_target_session_path(path, session_id)
            _rewrite_jsonl_file(path, target_path, _rewrite_codex_payload(session_id))
            rewritten = True
    return session_id if rewritten else None


def mark_codex_cloned_home(root: Path, source_window_id: str) -> None:
    try:
        (root / CODEX_CLONE_MARKER).write_text(
            json.dumps({"source_window_id": source_window_id}) + "\n",
            encoding="utf-8",
        )
    except OSError:
        return


def _latest_codex_thread_id(root: Path) -> str | None:
    for path in sorted(root.glob("state_*.sqlite"), reverse=True):
        if path.is_symlink() or not path.is_file():
            continue
        try:
            conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        except sqlite3.Error:
            continue
        try:
            row = conn.execute(
                "select id from threads where archived = 0 order by updated_at desc, id desc limit 1"
            ).fetchone()
        except sqlite3.Error:
            row = None
        finally:
            conn.close()
        if row is not None and isinstance(row[0], str) and row[0].strip():
            return row[0]
    return None


def _latest_codex_session_file_id(root: Path) -> str | None:
    sessions_dir = root / "sessions"
    if not sessions_dir.exists():
        return None
    paths = sorted(
        (
            path
            for path in sessions_dir.rglob("*.jsonl")
            if path.is_file() and not path.is_symlink()
        ),
        key=_path_mtime,
        reverse=True,
    )
    for path in paths:
        match = _CODEX_ROLLOUT_SESSION_ID.match(path.name)
        if match is not None:
            return match.group("session")
    return None


def _retarget_codex_rollout_paths(root: Path) -> None:
    session_paths_by_name = _codex_session_paths_by_name(root)
    for path in sorted(root.glob("state_*.sqlite")):
        if path.is_symlink() or not path.is_file():
            continue
        try:
            conn = sqlite3.connect(path)
        except sqlite3.Error:
            continue
        try:
            rows = conn.execute("select id, rollout_path from threads").fetchall()
            with conn:
                for thread_id, rollout_path in rows:
                    if not isinstance(thread_id, str) or not isinstance(rollout_path, str):
                        continue
                    target_path = _retargeted_codex_rollout_path(
                        root, rollout_path, session_paths_by_name
                    )
                    if target_path is None or target_path == rollout_path:
                        continue
                    conn.execute(
                        "UPDATE threads SET rollout_path = ? WHERE id = ?",
                        (target_path, thread_id),
                    )
        except sqlite3.Error:
            continue
        finally:
            conn.close()


def _codex_session_paths_by_name(root: Path) -> dict[str, Path]:
    sessions_dir = root / "sessions"
    if not sessions_dir.exists():
        return {}
    return {
        path.name: path
        for path in sorted(sessions_dir.rglob("*.jsonl"))
        if path.is_file() and not path.is_symlink()
    }


def _retargeted_codex_rollout_path(
    root: Path,
    rollout_path: str,
    session_paths_by_name: dict[str, Path],
) -> str | None:
    path = Path(rollout_path)
    target_path = session_paths_by_name.get(path.name)
    if target_path is None:
        return None
    try:
        target_path.relative_to(root)
    except ValueError:
        return None
    return str(target_path)


def _codex_target_session_path(path: Path, new_session_id: str) -> Path:
    match = _CODEX_ROLLOUT_SESSION_ID.match(path.name)
    if match is None:
        return path
    return path.with_name(f"{match.group('prefix')}{new_session_id}{match.group('suffix')}")


def _rewrite_codex_payload(new_session_id: str):
    def rewrite(payload: dict[str, Any]) -> dict[str, Any]:
        nested = payload.get("payload")
        if isinstance(nested, dict):
            nested["id"] = new_session_id
        return payload

    return rewrite


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
