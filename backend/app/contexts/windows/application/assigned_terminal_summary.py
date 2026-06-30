from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.contexts.activity.api.schemas import GitWorktreeActivityOut
from app.contexts.activity.application.terminal_work_status import (
    TerminalWorkStatus,
    TreeWindowActivity,
    load_tree_window_activity,
    long_idle_work_status,
)
from app.contexts.activity.application.window_git_worktree_activity import git_worktree_activity_out
from app.contexts.activity.application.window_runtime_tags import runtime_tags_for_window
from app.contexts.terminal_runtime.application.git_worktree_queries import (
    latest_git_worktree_snapshots_by_window_ids,
    list_window_git_bindings,
    pending_commit_window_ids,
)
from app.models import Folder, VirtualWindow


@dataclass(frozen=True)
class AssignedTerminalSummary:
    id: UUID
    title: str
    summary: str | None
    title_tags: list[str]
    runtime_tags: list[str]
    work_status: TerminalWorkStatus
    topic_path: str | None
    git_worktree: GitWorktreeActivityOut | None
    parent_window_id: UUID | None
    root_window_id: UUID | None
    derived_mode: str | None
    created_at: datetime


async def assigned_terminal_summaries(
    session: AsyncSession,
    client_id: UUID,
    window_ids: list[UUID],
    *,
    include_activity: bool = True,
    work_statuses: dict[UUID, TerminalWorkStatus] | None = None,
) -> dict[UUID, AssignedTerminalSummary]:
    unique_window_ids = list(dict.fromkeys(window_ids))
    if not unique_window_ids:
        return {}

    windows = list(
        await session.scalars(
            select(VirtualWindow)
            .where(
                VirtualWindow.client_id == client_id,
                VirtualWindow.id.in_(unique_window_ids),
            )
            .order_by(VirtualWindow.created_at, VirtualWindow.id)
        )
    )
    if not windows:
        return {}

    loaded_window_ids = [window.id for window in windows]
    activity = (
        await load_tree_window_activity(
            session,
            client_id,
            loaded_window_ids,
            include_runtime_tags=True,
        )
        if include_activity
        else None
    )
    topic_paths = await _topic_paths_for_windows(session, client_id, loaded_window_ids)
    git_worktrees = await _git_worktree_activity_by_window(session, loaded_window_ids) if include_activity else {}
    summaries: dict[UUID, AssignedTerminalSummary] = {}
    for window in windows:
        summaries[window.id] = AssignedTerminalSummary(
            id=window.id,
            title=window.title,
            summary=window.summary,
            title_tags=window.title_tags or [],
            runtime_tags=runtime_tags_for_window(
                window,
                ai_session=activity.latest_ai_sessions.get(window.id) if activity else None,
                terminal_agent=activity.latest_terminal_agents.get(window.id) if activity else None,
            ),
            work_status=_summary_work_status(window.id, activity, work_statuses),
            topic_path=topic_paths.get(window.id),
            git_worktree=git_worktrees.get(window.id),
            parent_window_id=window.parent_window_id,
            root_window_id=window.root_window_id,
            derived_mode=window.derived_mode,
            created_at=window.created_at,
        )
    return summaries


def _summary_work_status(
    window_id: UUID,
    activity: TreeWindowActivity | None,
    work_statuses: dict[UUID, TerminalWorkStatus] | None,
) -> TerminalWorkStatus:
    if work_statuses is not None and window_id in work_statuses:
        return work_statuses[window_id]
    if activity is not None:
        return activity.work_statuses.get(window_id, long_idle_work_status())
    return long_idle_work_status()


async def _topic_paths_for_windows(
    session: AsyncSession,
    client_id: UUID,
    window_ids: list[UUID],
) -> dict[UUID, str | None]:
    rows = await session.execute(
        select(VirtualWindow.id, Folder.path)
        .outerjoin(Folder, Folder.id == VirtualWindow.folder_id)
        .where(
            VirtualWindow.client_id == client_id,
            VirtualWindow.id.in_(window_ids),
        )
    )
    return {window_id: topic_path for window_id, topic_path in rows}


async def _git_worktree_activity_by_window(
    session: AsyncSession,
    window_ids: list[UUID],
) -> dict[UUID, GitWorktreeActivityOut]:
    bindings = await list_window_git_bindings(session, window_ids)
    if not bindings:
        return {}

    bound_window_ids = [binding.virtual_window_id for binding in bindings]
    pending_window_ids = await pending_commit_window_ids(session, bound_window_ids)
    snapshots = await latest_git_worktree_snapshots_by_window_ids(session, bound_window_ids)
    return {
        binding.virtual_window_id: git_worktree_activity_out(
            binding,
            pending_commit=binding.virtual_window_id in pending_window_ids,
            snapshot=snapshots.get(binding.virtual_window_id),
        )
        for binding in bindings
    }
