from __future__ import annotations

import json
import re
from uuid import UUID

from app.contexts.terminal_runtime.application.runtime_provider import (
    RemoteClientUnavailable,
    RemoteRuntime,
    RemoteTerminalError,
)
from app.models import Client

REMOTE_MODEL_CONFIG_READ_MAX_BYTES = 65536


async def read_remote_window_agent_model_metadata(
    remote_runtime: RemoteRuntime,
    client: Client,
    *,
    remote_agent: str,
    window_id: UUID,
) -> dict[str, object] | None:
    install_path = client.install_path.strip() if isinstance(client.install_path, str) else ""
    if not install_path.startswith("/"):
        return None
    if remote_agent in {"claude", "claude_code"}:
        return await _read_remote_claude_model_metadata(
            remote_runtime,
            f"{install_path}/claude-code-homes/{window_id}/settings.json",
        )
    if remote_agent == "codex":
        return await _read_remote_codex_model_metadata(
            remote_runtime,
            f"{install_path}/codex-homes/{window_id}/config.toml",
        )
    return None


async def _read_remote_claude_model_metadata(
    remote_runtime: RemoteRuntime,
    settings_path: str,
) -> dict[str, object] | None:
    try:
        raw = await remote_runtime.read_file_bytes(
            settings_path, max_bytes=REMOTE_MODEL_CONFIG_READ_MAX_BYTES
        )
    except (RemoteClientUnavailable, RemoteTerminalError, ValueError):
        return None
    return _claude_model_metadata_from_settings(raw.decode("utf-8", errors="replace"))


async def _read_remote_codex_model_metadata(
    remote_runtime: RemoteRuntime,
    config_path: str,
) -> dict[str, object] | None:
    try:
        raw = await remote_runtime.read_file_bytes(
            config_path, max_bytes=REMOTE_MODEL_CONFIG_READ_MAX_BYTES
        )
    except (RemoteClientUnavailable, RemoteTerminalError, ValueError):
        return None
    return _codex_model_metadata_from_config(raw.decode("utf-8", errors="replace"))


def _claude_model_metadata_from_settings(text: str) -> dict[str, object] | None:
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return None
    env = data.get("env") if isinstance(data, dict) else None
    if not isinstance(env, dict):
        return None
    metadata: dict[str, object] = {"provider": "claude_code"}
    _set_metadata_text(
        metadata,
        "base_url",
        env.get("ANTHROPIC_BASE_URL") or env.get("CLAUDE_CODE_API_BASE_URL"),
    )
    _set_metadata_text(
        metadata,
        "model",
        env.get("ANTHROPIC_DEFAULT_SONNET_MODEL")
        or env.get("ANTHROPIC_DEFAULT_OPUS_MODEL")
        or env.get("ANTHROPIC_DEFAULT_HAIKU_MODEL"),
    )
    _set_metadata_int(metadata, "max_output_tokens", env.get("CLAUDE_CODE_MAX_OUTPUT_TOKENS"))
    _set_metadata_int(
        metadata, "auto_compact_token_limit", env.get("CLAUDE_CODE_AUTO_COMPACT_WINDOW")
    )
    return metadata if len(metadata) > 1 else None


def _codex_model_metadata_from_config(text: str) -> dict[str, object] | None:
    metadata: dict[str, object] = {"provider": "codex"}
    for line in text.splitlines():
        if line.lstrip().startswith("["):
            break
        key, value = _toml_assignment(line)
        if key is None or value is None:
            continue
        if key == "model":
            _set_metadata_text(metadata, "model", value)
        elif key == "max_output_tokens":
            _set_metadata_int(metadata, "max_output_tokens", value)
        elif key == "model_context_window":
            _set_metadata_int(metadata, "context_window", value)
        elif key == "model_auto_compact_token_limit":
            _set_metadata_int(metadata, "auto_compact_token_limit", value)
    return metadata if len(metadata) > 1 else None


def _toml_assignment(line: str) -> tuple[str | None, str | None]:
    match = re.match(r"\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*?)\s*(?:#.*)?$", line)
    if match is None:
        return None, None
    raw = match.group(2).strip()
    if len(raw) >= 2 and raw[0] == raw[-1] and raw[0] in {"'", '"'}:
        raw = raw[1:-1]
    return match.group(1), raw


def _set_metadata_text(metadata: dict[str, object], key: str, value: object) -> None:
    if isinstance(value, str) and value.strip():
        metadata[key] = value.strip()


def _set_metadata_int(metadata: dict[str, object], key: str, value: object) -> None:
    parsed = _metadata_int(value)
    if parsed is not None:
        metadata[key] = parsed


def _metadata_int(value: object) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int) and value >= 0:
        return value
    if isinstance(value, str) and value.isdigit():
        return int(value)
    return None
