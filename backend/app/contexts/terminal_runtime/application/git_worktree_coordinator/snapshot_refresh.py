from __future__ import annotations

import os
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import inspect as sa_inspect
from sqlalchemy.ext.asyncio import AsyncSession

from app.contexts.terminal_runtime.application.client_connections import ClientConnectionRegistry
from app.contexts.terminal_runtime.domain.git_worktree_ops import (
    compact_git_worktree_snapshot,
    compute_session_diff,
    git_worktree_needs_merge_attention,
    pending_commit_from_diff,
)
from app.contexts.terminal_runtime.application.git_worktree_coordinator.landed_diff_recovery import (
    recover_landed_commit_session_diff,
)
from app.models import ClientRuntime

GitWorktreeAction = Callable[..., Awaitable[dict[str, Any] | None]]


async def refresh_run_snapshot(
    session: AsyncSession,
    run: Any,
    client_id: UUID,
    registry: ClientConnectionRegistry | None,
    client_runtime: ClientRuntime | None = None,
    *,
    git_worktree_action: GitWorktreeAction,
    local_git_worktree_action: GitWorktreeAction,
) -> bool:
    worktree_root = run.worktree_root
    if not isinstance(worktree_root, str) or not worktree_root.strip():
        return False

    snapshot_payload = {
        "worktree_root": worktree_root,
        "base_head": _snapshot_head(run.start_snapshot_json),
        "main_repo_root": (
            _snapshot_string(run.end_snapshot_json, "main_repo_root")
            or _snapshot_string(run.start_snapshot_json, "main_repo_root")
            or run.main_repo_root
        ),
        "known_head_sha": _snapshot_head(run.end_snapshot_json)
        or _snapshot_head(run.start_snapshot_json),
        "known_branch": _snapshot_string(run.end_snapshot_json, "branch")
        or _snapshot_string(run.start_snapshot_json, "branch"),
    }
    result = await git_worktree_action(
        registry,
        client_id,
        client_runtime,
        action="snapshot",
        **snapshot_payload,
    )
    if result is None and _is_local_project_worktree_path(worktree_root, run.main_repo_root):
        result = await local_git_worktree_action("snapshot", **snapshot_payload)
    snapshot = result.get("snapshot") if result and result.get("ok") else None
    if not isinstance(snapshot, dict) or not _snapshot_has_refresh_context(snapshot):
        return False

    changed = False
    start_snapshot = run.start_snapshot_json if isinstance(run.start_snapshot_json, dict) else snapshot
    compact_start_snapshot = compact_git_worktree_snapshot(start_snapshot)
    compact_end_snapshot = compact_git_worktree_snapshot(snapshot)
    snapshot_changed = False
    if not isinstance(run.start_snapshot_json, dict):
        run.start_snapshot_json = compact_start_snapshot
        snapshot_changed = True
        changed = True
    elif run.start_snapshot_json != compact_start_snapshot:
        run.start_snapshot_json = compact_start_snapshot
        snapshot_changed = True
        changed = True
    if run.end_snapshot_json != compact_end_snapshot:
        run.end_snapshot_json = compact_end_snapshot
        snapshot_changed = True
        changed = True
    session_diff = compute_session_diff(start_snapshot, snapshot)
    recovered_session_diff = await recover_landed_commit_session_diff(
        session,
        run,
        client_id=client_id,
        current_session_diff=session_diff,
        start_snapshot=start_snapshot,
        end_snapshot=snapshot,
        registry=registry,
        client_runtime=client_runtime,
        git_worktree_action=git_worktree_action,
    )
    if recovered_session_diff is not None:
        session_diff = recovered_session_diff
    session_diff_loaded = _attribute_is_loaded(run, "session_diff_json")
    if (
        snapshot_changed
        or recovered_session_diff is not None
        or (session_diff_loaded and run.session_diff_json != session_diff)
    ):
        run.session_diff_json = session_diff
        changed = True
    pending_commit = pending_commit_from_diff(session_diff)
    if run.pending_commit != pending_commit:
        run.pending_commit = pending_commit
        changed = True
    refreshed_at = datetime.now(UTC)
    if _is_tracking_run(run):
        if run.status != "completed":
            run.status = "completed"
            changed = True
        if changed or run.ended_at is None:
            run.ended_at = refreshed_at
            changed = True
    if pending_commit or git_worktree_needs_merge_attention(snapshot):
        resolved_at = None
    else:
        resolved_at = run.resolved_at or refreshed_at
    if run.resolved_at != resolved_at:
        run.resolved_at = resolved_at
        changed = True
    if changed:
        await session.flush()
    return changed


def _is_local_project_worktree_path(worktree_root: str, main_repo_root: str | None) -> bool:
    if not isinstance(main_repo_root, str) or not main_repo_root.strip():
        return False
    normalized = os.path.realpath(worktree_root)
    expected_root = os.path.join(os.path.realpath(main_repo_root), ".web-terminal-acp", "worktrees")
    try:
        if os.path.commonpath([normalized, expected_root]) != expected_root:
            return False
    except ValueError:
        return False
    return os.path.isdir(normalized) and os.path.isfile(os.path.join(normalized, ".git"))


def _is_tracking_run(run: Any) -> bool:
    return str(getattr(run, "command_sequence", "")).startswith("worktree:")


def _snapshot_head(snapshot: Any) -> str | None:
    return _snapshot_string(snapshot, "head_sha")


def _snapshot_string(snapshot: Any, key: str) -> str | None:
    if not isinstance(snapshot, dict):
        return None
    value = snapshot.get(key)
    return value if isinstance(value, str) and value.strip() else None


def _snapshot_has_refresh_context(snapshot: dict[str, Any]) -> bool:
    if snapshot.get("is_linked_worktree"):
        return True
    merge_status = _snapshot_string(snapshot, "merge_status")
    return bool(
        snapshot.get("is_linked_worktree") is False
        and _snapshot_head(snapshot)
        and _snapshot_string(snapshot, "main_repo_root")
        and merge_status in {"merged", "unmerged", "conflict"}
    )


def _attribute_is_loaded(instance: Any, name: str) -> bool:
    try:
        return name not in sa_inspect(instance).unloaded
    except Exception:
        return True
