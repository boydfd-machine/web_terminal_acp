from __future__ import annotations

import re
from collections.abc import Awaitable, Callable, Iterable
from typing import Any
from uuid import UUID

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.contexts.terminal_runtime.domain.git_worktree_ops import compute_session_diff
from app.models import ClientRuntime, Event, EventSourceType

GitWorktreeAction = Callable[..., Awaitable[dict[str, Any] | None]]

_SHA_PATTERN = r"([0-9a-fA-F]{7,40})"
_LANDED_COMMIT_PATTERNS = (
    re.compile(rf"\bcommit\s*[`:= ]+\s*`?{_SHA_PATTERN}`?", re.IGNORECASE),
    re.compile(rf"\bHEAD\s*=\s*`?{_SHA_PATTERN}`?", re.IGNORECASE),
    re.compile(rf"\bmain\s+fast-forwarded\s+to\s+`?{_SHA_PATTERN}`?", re.IGNORECASE),
    re.compile(rf"\bfast-forwarding\s+main\s+to\s+\S+@{_SHA_PATTERN}\b", re.IGNORECASE),
)
_MAX_EVENT_SCAN = 200
_MAX_PAYLOAD_SCAN_NODES = 512
_MAX_PAYLOAD_SCAN_DEPTH = 8


async def recover_landed_commit_session_diff(
    session: AsyncSession,
    run: Any,
    *,
    client_id: UUID,
    current_session_diff: dict[str, Any],
    start_snapshot: dict[str, Any],
    end_snapshot: dict[str, Any],
    registry: Any,
    client_runtime: ClientRuntime | None,
    git_worktree_action: GitWorktreeAction,
) -> dict[str, Any] | None:
    if not _needs_landed_diff_recovery(run, current_session_diff, start_snapshot, end_snapshot):
        return None

    base_head = _snapshot_string(start_snapshot, "head_sha")
    main_repo_root = (
        _snapshot_string(end_snapshot, "main_repo_root")
        or _snapshot_string(start_snapshot, "main_repo_root")
        or _string_value(getattr(run, "main_repo_root", None))
    )
    if not base_head or not main_repo_root:
        return None

    branch = (
        _snapshot_string(end_snapshot, "branch")
        or _snapshot_string(start_snapshot, "branch")
        or _string_value(getattr(run, "branch", None))
    )
    current_heads = {
        value
        for value in (
            _snapshot_string(start_snapshot, "head_sha"),
            _snapshot_string(end_snapshot, "head_sha"),
        )
        if value
    }
    for sha in await landed_commit_candidates(session, client_id, run.virtual_window_id):
        if sha in current_heads:
            continue
        snapshot = await _capture_landed_commit_snapshot(
            registry,
            client_id,
            client_runtime,
            git_worktree_action=git_worktree_action,
            main_repo_root=main_repo_root,
            base_head=base_head,
            head_sha=sha,
            branch=branch,
        )
        if not snapshot or not _snapshot_commits(snapshot):
            continue
        recovered = compute_session_diff(start_snapshot, snapshot)
        if not recovered.get("commits"):
            continue
        recovered["recovered_from_landed_commit"] = True
        recovered["recovered_landed_commit_sha"] = sha
        return recovered
    return None


async def landed_commit_candidates(
    session: AsyncSession,
    client_id: UUID,
    window_id: UUID,
) -> list[str]:
    payloads = list(
        await session.scalars(
            select(Event.payload_json)
            .where(
                Event.client_id == client_id,
                Event.virtual_window_id == window_id,
                Event.source_type == EventSourceType.agent_tool_record,
            )
            .order_by(desc(Event.created_at), desc(Event.id))
            .limit(_MAX_EVENT_SCAN)
        )
    )
    candidates: list[str] = []
    seen: set[str] = set()
    for payload in payloads:
        for value in _payload_strings(payload):
            for sha in _candidate_shas(value):
                normalized = sha.lower()
                if normalized in seen:
                    continue
                seen.add(normalized)
                candidates.append(normalized)
    return candidates


def _needs_landed_diff_recovery(
    run: Any,
    session_diff: dict[str, Any],
    start_snapshot: dict[str, Any],
    end_snapshot: dict[str, Any],
) -> bool:
    if not str(getattr(run, "command_sequence", "")).startswith("worktree:"):
        return False
    if session_diff.get("has_changes"):
        return False
    if session_diff.get("commits") or session_diff.get("files"):
        return False
    return _snapshot_is_merged(start_snapshot) or _snapshot_is_merged(end_snapshot)


async def _capture_landed_commit_snapshot(
    registry: Any,
    client_id: UUID,
    client_runtime: ClientRuntime | None,
    *,
    git_worktree_action: GitWorktreeAction,
    main_repo_root: str,
    base_head: str,
    head_sha: str,
    branch: str | None,
) -> dict[str, Any] | None:
    result = await git_worktree_action(
        registry,
        client_id,
        client_runtime,
        action="snapshot",
        worktree_root=main_repo_root,
        base_head=base_head,
        main_repo_root=main_repo_root,
        known_head_sha=head_sha,
        known_branch=branch,
    )
    snapshot = result.get("snapshot") if result and result.get("ok") else None
    return snapshot if isinstance(snapshot, dict) else None


def _candidate_shas(value: str) -> Iterable[str]:
    for pattern in _LANDED_COMMIT_PATTERNS:
        for match in pattern.finditer(value):
            yield match.group(1)


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


def _snapshot_commits(snapshot: dict[str, Any]) -> list[dict[str, Any]]:
    commits = snapshot.get("commits")
    if not isinstance(commits, list):
        return []
    return [commit for commit in commits if isinstance(commit, dict)]


def _snapshot_is_merged(snapshot: dict[str, Any]) -> bool:
    return snapshot.get("merged_to_main") is True or snapshot.get("merge_status") == "merged"


def _snapshot_string(snapshot: dict[str, Any], key: str) -> str | None:
    value = snapshot.get(key)
    return value if isinstance(value, str) and value.strip() else None


def _string_value(value: Any) -> str | None:
    return value if isinstance(value, str) and value.strip() else None
