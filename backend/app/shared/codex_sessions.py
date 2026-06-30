from __future__ import annotations

import re
from pathlib import Path
from typing import Any

_ROLLOUT_SESSION_ID = re.compile(
    r"^rollout-(?:(?:\d{4}-\d{2}-\d{2}T\d{2}-\d{2}-\d{2})-)?(?P<session>.+)$",
    re.IGNORECASE,
)


def codex_session_id_from_source_path(source_path: str | None) -> str | None:
    if not source_path:
        return None
    match = _ROLLOUT_SESSION_ID.match(Path(source_path).stem)
    if match is None:
        return None
    session_id = match.group("session").strip()
    return session_id or None


def codex_session_id_from_payload(payload: dict[str, Any], source_path: str | None) -> str | None:
    sidechain_session_id = _codex_sidechain_session_id(payload)
    if sidechain_session_id is not None:
        return sidechain_session_id

    source_session_id = codex_session_id_from_source_path(source_path)
    if source_session_id is not None:
        return source_session_id

    raw_id = _string_value(payload.get("trace_id")) or _string_value(payload.get("id"))
    if raw_id:
        return raw_id

    nested = payload.get("payload")
    if isinstance(nested, dict):
        nested_id = _string_value(nested.get("id"))
        if nested_id:
            return nested_id

    return None


def codex_subagent_id_from_payload(payload: dict[str, Any]) -> str | None:
    return _codex_subagent_id(payload) or _codex_subagent_id(_nested_payload(payload))


def codex_subagent_tool_use_id_from_payload(payload: dict[str, Any]) -> str | None:
    value = _string_value(payload.get("subagent_tool_use_id")) or _string_value(payload.get("subagentToolUseId"))
    if value:
        return value
    metadata = payload.get("subagent")
    if isinstance(metadata, dict):
        value = _string_value(metadata.get("tool_use_id")) or _string_value(metadata.get("toolUseId"))
        if value:
            return value
    tool_use_result = payload.get("toolUseResult")
    if isinstance(tool_use_result, dict):
        value = _string_value(tool_use_result.get("tool_use_id")) or _string_value(tool_use_result.get("toolUseId"))
        if value:
            return value
    nested = _nested_payload(payload)
    if nested:
        return codex_subagent_tool_use_id_from_payload(nested)
    return None


def codex_is_sidechain_payload(payload: dict[str, Any]) -> bool:
    return _payload_is_sidechain(payload) or _payload_is_sidechain(_nested_payload(payload))


def _string_value(value: Any) -> str | None:
    if isinstance(value, str):
        value = value.strip()
        return value or None
    if isinstance(value, (int, float, bool)):
        return str(value)
    return None


def _payload_is_sidechain(payload: dict[str, Any]) -> bool:
    return payload.get("isSidechain") is True


def _nested_payload(payload: dict[str, Any]) -> dict[str, Any]:
    nested = payload.get("payload")
    return nested if isinstance(nested, dict) else {}


def _codex_subagent_id(payload: dict[str, Any]) -> str | None:
    value = _string_value(payload.get("agentId")) or _string_value(payload.get("subagent_id")) or _string_value(
        payload.get("subagentId")
    )
    if value:
        return value
    metadata = payload.get("subagent")
    if isinstance(metadata, dict):
        value = _string_value(metadata.get("agent_id")) or _string_value(metadata.get("agentId"))
        if value:
            return value
    tool_use_result = payload.get("toolUseResult")
    if isinstance(tool_use_result, dict):
        value = _string_value(tool_use_result.get("agentId"))
        if value:
            return value
    return None


def _codex_sidechain_session_id(payload: dict[str, Any]) -> str | None:
    subagent_id = codex_subagent_id_from_payload(payload)
    if codex_is_sidechain_payload(payload) and subagent_id is not None:
        return f"agent-{subagent_id}"
    return None
