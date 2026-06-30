from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import Boolean, cast, desc, func, literal_column, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.contexts.terminal_runtime.domain.git_worktree_ops import (
    git_worktree_merge_state,
    git_worktree_needs_merge_attention,
)
from app.models import GitWorktreeRun, ProjectTodo, ProjectTodoStatus


async def sync_project_todo_worktree_summaries_for_window(
    session: AsyncSession,
    client_id: UUID,
    window_id: UUID,
) -> bool:
    summary = await implementation_worktree_summary(session, window_id)
    if summary is None:
        return False

    todos = list(
        await session.scalars(
            select(ProjectTodo).where(
                ProjectTodo.client_id == client_id,
                ProjectTodo.assigned_window_id == window_id,
                ProjectTodo.implementation_worktree_json.is_not(None),
                ProjectTodo.status.in_(
                    [
                        ProjectTodoStatus.awaiting_review,
                        ProjectTodoStatus.done,
                    ]
                ),
            )
        )
    )
    changed = False
    for todo in todos:
        if _worktree_summary_matches(todo.implementation_worktree_json, summary):
            continue
        todo.implementation_worktree_json = summary
        changed = True
    if changed:
        await session.flush()
    return changed


async def list_project_todo_worktree_attention_targets(
    session: AsyncSession,
    *,
    limit: int = 100,
) -> list[tuple[UUID, UUID]]:
    rows = await session.execute(project_todo_worktree_attention_targets_statement(limit=limit))
    targets: list[tuple[UUID, UUID]] = []
    seen: set[tuple[UUID, UUID]] = set()
    for client_id, window_id in rows:
        if window_id is None:
            continue
        target = (client_id, window_id)
        if target in seen:
            continue
        seen.add(target)
        targets.append(target)
    return targets


def project_todo_worktree_attention_targets_statement(*, limit: int = 100):
    return (
        select(
            ProjectTodo.client_id,
            ProjectTodo.assigned_window_id,
        )
        .where(
            ProjectTodo.assigned_window_id.is_not(None),
            ProjectTodo.implementation_worktree_json.is_not(None),
            _worktree_summary_needs_merge_attention_expression(),
            ProjectTodo.status.in_(
                [literal_column("'AWAITING_REVIEW'"), literal_column("'DONE'")]
            ),
        )
        .order_by(desc(ProjectTodo.updated_at), desc(ProjectTodo.id))
        .limit(limit)
    )


def _worktree_summary_needs_merge_attention_expression():
    summary = ProjectTodo.implementation_worktree_json
    return or_(
        _worktree_summary_boolean_field(summary, "merge_attention_required").is_(True),
        _worktree_summary_text_field(summary, "merge_status").in_(
            [literal_column("'unmerged'"), literal_column("'conflict'")]
        ),
        _worktree_summary_boolean_field(summary, "merged_to_main").is_(False),
    )


def _worktree_summary_boolean_field(summary, key: str):
    return cast(_worktree_summary_text_field(summary, key), Boolean)


def _worktree_summary_text_field(summary, key: str):
    return summary.op("->>")(literal_column(f"'{key}'"))


async def implementation_worktree_summary(
    session: AsyncSession,
    window_id: UUID,
) -> dict[str, Any] | None:
    runs = list(
        await session.scalars(
            select(GitWorktreeRun)
            .where(GitWorktreeRun.virtual_window_id == window_id)
            .order_by(
                desc(
                    func.coalesce(
                        GitWorktreeRun.resolved_at,
                        GitWorktreeRun.ended_at,
                        GitWorktreeRun.started_at,
                    )
                ),
                desc(GitWorktreeRun.id),
            )
            .limit(100)
        )
    )
    if not runs:
        return None

    commits: list[dict[str, Any]] = []
    files: dict[str, dict[str, Any]] = {}
    seen_commits: set[str] = set()
    latest_run = runs[0]
    has_changes = False
    pending_commit = False

    for run in runs:
        pending_commit = pending_commit or bool(run.pending_commit)
        diff = run.session_diff_json if isinstance(run.session_diff_json, dict) else {}
        has_changes = has_changes or bool(diff.get("has_changes"))
        for commit in _safe_dicts(diff.get("commits")):
            sha = _string_value(commit.get("sha"))
            if sha is None or sha in seen_commits:
                continue
            seen_commits.add(sha)
            commits.append(_commit_summary(commit))
        for file_entry in _safe_dicts(diff.get("files")):
            path = _string_value(file_entry.get("path"))
            if path is None:
                continue
            files.setdefault(path, _file_summary(file_entry))

    latest_diff = (
        latest_run.session_diff_json if isinstance(latest_run.session_diff_json, dict) else {}
    )
    latest_end = (
        latest_run.end_snapshot_json if isinstance(latest_run.end_snapshot_json, dict) else {}
    )
    latest_start = (
        latest_run.start_snapshot_json if isinstance(latest_run.start_snapshot_json, dict) else {}
    )
    latest_merge_snapshot = next(
        (
            run.end_snapshot_json
            for run in runs
            if isinstance(run.end_snapshot_json, dict)
        ),
        None,
    )
    merge_state = git_worktree_merge_state(latest_merge_snapshot)
    return {
        "window_id": str(window_id),
        "main_repo_root": (
            _first_string(latest_end, latest_start, key="main_repo_root")
            or latest_run.main_repo_root
        ),
        "worktree_root": (
            _first_string(latest_end, latest_start, key="worktree_root")
            or latest_run.worktree_root
        ),
        "branch": _first_string(latest_end, latest_start, key="branch"),
        "start_head": latest_diff.get("start_head"),
        "end_head": latest_diff.get("end_head") or latest_end.get("head_sha"),
        "has_changes": has_changes,
        "pending_commit": pending_commit,
        "merge_attention_required": git_worktree_needs_merge_attention(latest_merge_snapshot),
        **merge_state,
        "runs_total": len(runs),
        "commits": commits,
        "files": list(files.values()),
        "diff_runs": [_diff_run_summary(run) for run in runs if _run_has_commit_diff(run)],
        "captured_at": datetime.now(UTC).isoformat(),
    }


def _worktree_summary_matches(current: Any, updated: dict[str, Any]) -> bool:
    if not isinstance(current, dict):
        return False
    return _summary_without_capture(current) == _summary_without_capture(updated)


def _summary_without_capture(summary: dict[str, Any]) -> dict[str, Any]:
    return {
        key: value
        for key, value in summary.items()
        if key != "captured_at"
    }


def _safe_dicts(value: object) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _commit_summary(commit: dict[str, Any]) -> dict[str, Any]:
    return {
        "sha": commit.get("sha"),
        "short_sha": commit.get("short_sha"),
        "subject": commit.get("subject"),
        "author_name": commit.get("author_name"),
        "authored_at": commit.get("authored_at"),
        "files": [_file_summary(file_entry) for file_entry in _safe_dicts(commit.get("files"))],
    }


def _file_summary(file_entry: dict[str, Any]) -> dict[str, Any]:
    return {
        "path": file_entry.get("path"),
        "old_path": file_entry.get("old_path"),
        "status": file_entry.get("status"),
        "additions": file_entry.get("additions"),
        "deletions": file_entry.get("deletions"),
    }


def _diff_run_summary(run: GitWorktreeRun) -> dict[str, Any]:
    return {
        "id": str(run.id),
        "virtual_window_id": str(run.virtual_window_id),
        "command_sequence": run.command_sequence,
        "agent_provider": run.agent_provider,
        "status": run.status,
        "run_type": "tracking" if str(run.command_sequence).startswith("worktree:") else "agent",
        "worktree_root": run.worktree_root,
        "main_repo_root": run.main_repo_root,
        "discovery_method": run.discovery_method,
        "start_snapshot_json": run.start_snapshot_json,
        "end_snapshot_json": run.end_snapshot_json,
        "session_diff_json": run.session_diff_json,
        "pending_commit": run.pending_commit,
        "resolved_at": _datetime_iso(run.resolved_at),
        "started_at": _datetime_iso(run.started_at),
        "ended_at": _datetime_iso(run.ended_at),
    }


def _run_has_commit_diff(run: GitWorktreeRun) -> bool:
    diff = run.session_diff_json if isinstance(run.session_diff_json, dict) else {}
    return any(_safe_dicts(commit.get("files")) for commit in _safe_dicts(diff.get("commits")))


def _datetime_iso(value: datetime | None) -> str | None:
    return value.isoformat() if isinstance(value, datetime) else None


def _first_string(*values: dict[str, Any], key: str) -> str | None:
    for value in values:
        string = _string_value(value.get(key))
        if string is not None:
            return string
    return None


def _string_value(value: object) -> str | None:
    return value if isinstance(value, str) and value.strip() else None
