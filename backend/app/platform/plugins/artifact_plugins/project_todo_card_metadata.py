from __future__ import annotations

import re
from typing import Any

BUILTIN_PROJECT_TODO_TYPE_IDS = {
    "default",
}
TODO_TYPE_ALIASES = {
    "default": "default",
}
DEFAULT_ARTIFACT_KINDS_BY_TODO_TYPE: dict[str, list[str]] = {}
ARTIFACT_KIND_ALIASES: dict[str, str | None] = {}
SUPPORTED_PROJECT_TODO_CARD_ARTIFACT_KINDS = {
    "agent_trace_graph",
}
_SUPPORTED_ARTIFACT_KIND_BY_KEY = {
    artifact_kind.lower(): artifact_kind
    for artifact_kind in SUPPORTED_PROJECT_TODO_CARD_ARTIFACT_KINDS
}
_TODO_TYPE_PATTERN = re.compile(r"^[A-Za-z0-9_.-]+$")


def normalize_project_todo_card_type_id(value: Any) -> str:
    raw = _text(value).lower()
    mapped = TODO_TYPE_ALIASES.get(raw, raw)
    if not mapped or not _TODO_TYPE_PATTERN.match(mapped):
        return "default"
    return mapped if mapped in BUILTIN_PROJECT_TODO_TYPE_IDS else "default"


def project_todo_card_artifact_kind_candidate(value: Any) -> str | None:
    raw = _text(value)
    if not raw:
        return None
    return ARTIFACT_KIND_ALIASES.get(raw.lower(), raw)


def normalize_project_todo_card_artifact_kinds(values: list[str]) -> list[str]:
    normalized: list[str] = []
    seen: set[str] = set()
    for value in values:
        candidate = project_todo_card_artifact_kind_candidate(value)
        if candidate is None:
            continue
        canonical = _SUPPORTED_ARTIFACT_KIND_BY_KEY.get(candidate.strip().lower())
        if canonical is None or canonical.lower() in seen:
            continue
        seen.add(canonical.lower())
        normalized.append(canonical)
    return normalized


def _text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    return str(value).strip()
