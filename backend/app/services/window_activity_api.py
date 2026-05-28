from __future__ import annotations

from time import monotonic
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import load_only

from app.models import VirtualWindow
from app.repositories.git_worktree import list_window_git_bindings, pending_commit_window_ids
from app.schemas import ClientWindowsActivityOut, GitWorktreeActivityOut, WindowActivityOut
from app.services.terminal_work_status import (
    load_tree_window_activity,
    long_idle_work_status,
    to_work_status_out,
)
from app.services.window_runtime_tags import runtime_tags_for_window

_ACTIVITY_CACHE_TTL_SECONDS = 10.0
_activity_cache: dict[tuple[UUID, bool, tuple[UUID, ...]], tuple[float, ClientWindowsActivityOut]] = {}


def clear_client_windows_activity_cache(client_id: UUID | None = None) -> None:
    if client_id is None:
        _activity_cache.clear()
        return
    stale_keys = [key for key in _activity_cache if key[0] == client_id]
    for key in stale_keys:
        _activity_cache.pop(key, None)


async def load_client_windows_activity(
    session: AsyncSession,
    client_id: UUID,
    *,
    include_runtime_tags: bool = False,
) -> ClientWindowsActivityOut:
    window_ids = list(
        await session.scalars(
            select(VirtualWindow.id)
            .where(
                VirtualWindow.client_id == client_id,
                VirtualWindow.folder_id.is_not(None),
            )
            .order_by(VirtualWindow.id)
        )
    )
    if not window_ids:
        return ClientWindowsActivityOut()

    cache_key = (client_id, include_runtime_tags, tuple(window_ids))
    now = monotonic()
    cached = _activity_cache.get(cache_key)
    if cached is not None and now - cached[0] <= _ACTIVITY_CACHE_TTL_SECONDS:
        return cached[1]

    activity = await load_tree_window_activity(
        session,
        client_id,
        window_ids,
        include_runtime_tags=include_runtime_tags,
    )
    windows = list(
        await session.scalars(
            select(VirtualWindow)
            .options(load_only(VirtualWindow.id, VirtualWindow.cwd))
            .where(VirtualWindow.id.in_(window_ids))
        )
    )
    windows_by_id = {window.id: window for window in windows}
    git_worktrees = await _load_git_worktree_activity(session, window_ids)

    items: list[WindowActivityOut] = []
    for window_id in window_ids:
        window = windows_by_id.get(window_id)
        if window is None:
            continue
        work_status = activity.work_statuses.get(window_id, long_idle_work_status())
        if include_runtime_tags:
            runtime_tags = runtime_tags_for_window(
                window,
                ai_session=activity.latest_ai_sessions.get(window_id),
                terminal_agent=activity.latest_terminal_agents.get(window_id),
            )
        else:
            runtime_tags = runtime_tags_for_window(window)
        git_worktree = git_worktrees.get(window_id)
        items.append(
            WindowActivityOut(
                window_id=window_id,
                work_status=to_work_status_out(work_status),
                runtime_tags=runtime_tags,
                last_agent_task_completed_at=activity.last_agent_task_completed_at.get(
                    window_id
                ),
                git_worktree=git_worktree,
            )
        )
    result = ClientWindowsActivityOut(windows=items)
    _activity_cache[cache_key] = (now, result)
    return result


async def _load_git_worktree_activity(
    session: AsyncSession,
    window_ids: list[UUID],
) -> dict[UUID, GitWorktreeActivityOut]:
    bindings = await list_window_git_bindings(session, window_ids)
    if not bindings:
        return {}

    pending_window_ids = await pending_commit_window_ids(
        session,
        [binding.virtual_window_id for binding in bindings],
    )
    return {
        binding.virtual_window_id: GitWorktreeActivityOut(
            worktree_root=binding.worktree_root,
            main_repo_root=binding.main_repo_root,
            branch=binding.branch,
            pending_commit=binding.virtual_window_id in pending_window_ids,
        )
        for binding in bindings
    }
