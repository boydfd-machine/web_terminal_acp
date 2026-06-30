from __future__ import annotations

from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.orm import load_only

from app.models import GitWorktreeRun


def runs_for_refresh_query(
    window_id: UUID,
    command_sequences: set[str] | None,
    include_tracking_run: bool,
    include_unresolved_runs: bool,
):
    query = (
        select(GitWorktreeRun)
        .options(
            load_only(
                GitWorktreeRun.id,
                GitWorktreeRun.client_id,
                GitWorktreeRun.virtual_window_id,
                GitWorktreeRun.command_sequence,
                GitWorktreeRun.agent_provider,
                GitWorktreeRun.status,
                GitWorktreeRun.main_repo_root,
                GitWorktreeRun.worktree_root,
                GitWorktreeRun.discovery_method,
                GitWorktreeRun.start_snapshot_json,
                GitWorktreeRun.end_snapshot_json,
                GitWorktreeRun.pending_commit,
                GitWorktreeRun.resolved_at,
                GitWorktreeRun.started_at,
                GitWorktreeRun.ended_at,
            )
        )
        .where(
            GitWorktreeRun.virtual_window_id == window_id,
            GitWorktreeRun.worktree_root.is_not(None),
        )
    )
    predicates = []
    if command_sequences:
        predicates.append(GitWorktreeRun.command_sequence.in_(command_sequences))
    if include_tracking_run:
        predicates.append(GitWorktreeRun.command_sequence.like("worktree:%"))
    if include_unresolved_runs:
        predicates.append(GitWorktreeRun.resolved_at.is_(None))
    if not predicates:
        predicates.append(GitWorktreeRun.command_sequence.like("worktree:%"))
    return query.where(predicates[0] if len(predicates) == 1 else or_(*predicates))
