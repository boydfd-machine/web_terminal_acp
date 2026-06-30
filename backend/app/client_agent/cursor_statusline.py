from __future__ import annotations

import json
import logging
import stat
from pathlib import Path
from typing import Any
from uuid import UUID

logger = logging.getLogger(__name__)

STATUSLINE_USAGE_FILENAME = "statusline-usage.json"
STATUSLINE_WRITER_SCRIPT_NAME = "cursor-statusline-writer.sh"
STATUSLINE_TOKEN_EVENT_TYPE = "statusline_token_usage"
STATUSLINE_UPDATE_INTERVAL_MS = 500
STATUSLINE_TIMEOUT_MS = 1000

STATUSLINE_WRITER_SCRIPT = """#!/usr/bin/env bash
payload=$(cat)
[ -n "${CURSOR_DATA_DIR:-}" ] || exit 0
out="${CURSOR_DATA_DIR}/statusline-usage.json"
tmp="${out}.tmp.$$"
printf '%s\\n' "$payload" > "$tmp"
mv "$tmp" "$out"
"""


def cursor_home_for_window(window_id: UUID | str) -> Path:
    return Path.home() / ".web-terminal-acp" / "cursor-homes" / str(window_id)


def cursor_statusline_usage_path(window_id: UUID | str) -> Path:
    return cursor_home_for_window(window_id) / STATUSLINE_USAGE_FILENAME


def cursor_statusline_writer_path(window_id: UUID | str) -> Path:
    return cursor_home_for_window(window_id) / "bin" / STATUSLINE_WRITER_SCRIPT_NAME


def ensure_cursor_statusline_setup(window_id: UUID | str) -> None:
    home = cursor_home_for_window(window_id)
    if not home.exists():
        return
    _write_statusline_writer_script(cursor_statusline_writer_path(window_id))
    _merge_statusline_cli_config(home / "cli-config.json", cursor_statusline_writer_path(window_id))


def read_cursor_statusline_payload(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        parsed = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        logger.info("Unable to read Cursor statusline usage %s", path)
        return None
    return parsed if isinstance(parsed, dict) else None


def statusline_payload_fingerprint(payload: dict[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def build_cursor_statusline_token_event(
    payload: dict[str, Any],
    *,
    client_id: UUID,
    window_id: UUID,
    project_path: str | None,
    source_path: str,
) -> dict[str, Any]:
    session_id = _text(payload.get("session_id"))
    return {
        "provider": "cursor_cli",
        "type": STATUSLINE_TOKEN_EVENT_TYPE,
        "session_id": session_id,
        "session_name": _text(payload.get("session_name")),
        "model": payload.get("model") if isinstance(payload.get("model"), dict) else None,
        "context_window": payload.get("context_window")
        if isinstance(payload.get("context_window"), dict)
        else None,
        "current_usage": payload.get("current_usage")
        if isinstance(payload.get("current_usage"), dict)
        else _current_usage_from_context_window(payload),
        "agentId": session_id,
        "client_id": str(client_id),
        "virtual_window_id": str(window_id),
        "project_path": project_path,
        "source_path": source_path,
    }


def collect_cursor_statusline_watch_events(
    *,
    state,
    client_id: UUID,
    window_id: UUID,
    project_path: str | None,
) -> list[dict[str, Any]]:
    ensure_cursor_statusline_setup(window_id)
    path = cursor_statusline_usage_path(window_id)
    payload = read_cursor_statusline_payload(path)
    if payload is None:
        return []

    fingerprint = statusline_payload_fingerprint(payload)
    if state.cursor_statusline_fingerprint == fingerprint:
        return []

    state.cursor_statusline_fingerprint = fingerprint
    return [
        build_cursor_statusline_token_event(
            payload,
            client_id=client_id,
            window_id=window_id,
            project_path=project_path,
            source_path=str(path),
        )
    ]


def _write_statusline_writer_script(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(STATUSLINE_WRITER_SCRIPT, encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def _materialize_cli_config(config_path: Path) -> None:
    if not config_path.is_symlink():
        return
    try:
        content = config_path.read_text(encoding="utf-8")
    except OSError:
        logger.warning("Unable to read symlinked Cursor cli-config %s", config_path)
        return
    config_path.unlink()
    config_path.write_text(content, encoding="utf-8")


def _merge_statusline_cli_config(config_path: Path, script_path: Path) -> None:
    _materialize_cli_config(config_path)
    config: dict[str, Any] = {}
    if config_path.is_file():
        try:
            parsed = json.loads(config_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            parsed = {}
        if isinstance(parsed, dict):
            config = parsed

    desired = {
        "type": "command",
        "command": str(script_path),
        "updateIntervalMs": STATUSLINE_UPDATE_INTERVAL_MS,
        "timeoutMs": STATUSLINE_TIMEOUT_MS,
    }
    if config.get("statusLine") == desired:
        return

    config["statusLine"] = desired
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")


def _current_usage_from_context_window(payload: dict[str, Any]) -> dict[str, Any] | None:
    context_window = payload.get("context_window")
    if not isinstance(context_window, dict):
        return None
    current_usage = context_window.get("current_usage")
    return current_usage if isinstance(current_usage, dict) else None


def _text(value: Any) -> str | None:
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None
