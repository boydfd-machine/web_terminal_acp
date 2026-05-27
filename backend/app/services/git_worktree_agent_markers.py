from __future__ import annotations

from collections.abc import Iterable
from typing import Any
from uuid import UUID

from sqlalchemy import Text, cast, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Event, EventSourceType
from app.repositories.git_worktree import list_window_git_bindings
from app.services.git_worktree_coordinator import process_worktree_registration
from app.services.runtime.client_connections import ClientConnectionRegistry
from app.services.terminal_worktree_marker import (
    WORKTREE_MARKER_PREFIX,
    ParsedWorktreeMarker,
    extract_worktree_markers,
)

_MARKER_TEXT_PREFIX = WORKTREE_MARKER_PREFIX.decode("ascii")
_MARKER_SEARCH_TEXT = "web-terminal-worktree"
_MARKER_END = "\x07"
_MAX_PAYLOAD_SCAN_NODES = 512
_MAX_PAYLOAD_SCAN_DEPTH = 8
_MAX_MARKERS_PER_PAYLOAD = 20
_MAX_AGENT_MARKER_EVENTS = 500


def extract_worktree_markers_from_agent_payload(
    payload: Any,
) -> tuple[ParsedWorktreeMarker, ...]:
    markers: list[ParsedWorktreeMarker] = []
    for value in _payload_strings(payload):
        if _MARKER_SEARCH_TEXT not in value:
            continue
        for marker_text in _marker_text_segments(value):
            _clean_data, parsed = extract_worktree_markers(marker_text.encode("utf-8"))
            markers.extend(parsed)
            if len(markers) >= _MAX_MARKERS_PER_PAYLOAD:
                return tuple(markers[:_MAX_MARKERS_PER_PAYLOAD])
    return tuple(markers)


async def materialize_agent_worktree_markers(
    session: AsyncSession,
    *,
    client_id: UUID,
    window_ids: Iterable[UUID],
    registry: ClientConnectionRegistry | None = None,
) -> set[UUID]:
    target_window_ids = tuple(dict.fromkeys(window_ids))
    if not target_window_ids:
        return set()
    existing_bindings = await list_window_git_bindings(session, target_window_ids)
    bound_window_ids = {binding.virtual_window_id for binding in existing_bindings}
    unbound_window_ids = tuple(
        window_id for window_id in target_window_ids if window_id not in bound_window_ids
    )
    if not unbound_window_ids:
        return set()
    target_window_id_set = set(unbound_window_ids)

    events = list(
        await session.scalars(
            select(Event)
            .where(
                Event.client_id == client_id,
                Event.virtual_window_id.in_(unbound_window_ids),
                Event.source_type == EventSourceType.agent_tool_record,
                cast(Event.payload_json, Text).contains(_MARKER_SEARCH_TEXT),
            )
            .order_by(Event.created_at, Event.id)
            .limit(_MAX_AGENT_MARKER_EVENTS)
        )
    )
    changed_window_ids: set[UUID] = set()
    seen_markers: set[tuple[UUID, str | None, str | None, str | None]] = set()
    for event in events:
        event_window_id = event.virtual_window_id
        if event_window_id is None or event_window_id not in target_window_id_set:
            continue
        for marker in extract_worktree_markers_from_agent_payload(event.payload_json):
            marker_window_id = _marker_window_id(marker)
            if marker_window_id != event_window_id:
                continue
            marker_key = (
                marker_window_id,
                _marker_string(marker, "worktree_root"),
                _marker_string(marker, "main_repo_root"),
                _marker_string(marker, "branch"),
            )
            if marker_key in seen_markers:
                continue
            seen_markers.add(marker_key)
            await process_worktree_registration(
                session,
                client_id=client_id,
                window_id=marker_window_id,
                marker=marker,
                registry=registry,
            )
            changed_window_ids.add(marker_window_id)
    return changed_window_ids


def _payload_strings(payload: Any) -> Iterable[str]:
    stack: list[tuple[Any, int]] = [(payload, 0)]
    visited = 0
    while stack and visited < _MAX_PAYLOAD_SCAN_NODES:
        value, depth = stack.pop()
        visited += 1
        if isinstance(value, str):
            yield value
            continue
        if depth >= _MAX_PAYLOAD_SCAN_DEPTH:
            continue
        if isinstance(value, dict):
            stack.extend((item, depth + 1) for item in value.values())
        elif isinstance(value, list | tuple):
            stack.extend((item, depth + 1) for item in value)


def _marker_text_segments(value: str) -> Iterable[str]:
    position = 0
    emitted = 0
    while emitted < _MAX_MARKERS_PER_PAYLOAD:
        marker_start = value.find(_MARKER_TEXT_PREFIX, position)
        if marker_start < 0:
            return
        marker_end = value.find(_MARKER_END, marker_start + len(_MARKER_TEXT_PREFIX))
        if marker_end < 0:
            return
        emitted += 1
        yield value[marker_start : marker_end + len(_MARKER_END)]
        position = marker_end + len(_MARKER_END)


def _marker_window_id(marker: ParsedWorktreeMarker) -> UUID | None:
    try:
        return UUID(str(marker.get("window_id")))
    except (TypeError, ValueError):
        return None


def _marker_string(marker: ParsedWorktreeMarker, key: str) -> str | None:
    value = marker.get(key)
    return value if isinstance(value, str) else None
