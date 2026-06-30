from __future__ import annotations

import asyncio
from datetime import datetime
from time import monotonic
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import load_only

from app.contexts.activity.api.schemas import (
    ClientWindowsActivityOut,
    GitWorktreeActivityOut,
    WindowActivityOut,
)
from app.contexts.activity.application.terminal_work_status import (
    load_tree_window_activity,
    long_idle_work_status,
    to_work_status_out,
)
from app.contexts.activity.application.window_git_worktree_activity import git_worktree_activity_out
from app.contexts.activity.application.window_runtime_tags import runtime_tags_for_window
from app.contexts.workspace.application.folder_access import (
    window_project_path_expression,
    window_visible_at_expression,
)
from app.contexts.workspace.application.project_todo_titles import assigned_todo_titles_by_window
from app.models import VirtualWindow
from app.contexts.terminal_runtime.application.git_worktree_queries import (
    latest_git_worktree_snapshots_by_window_ids,
    list_window_git_bindings,
    pending_commit_window_ids,
)
from app.platform import cache_backend

_ACTIVITY_CACHE_TTL_SECONDS = 10.0
_ACTIVITY_CACHE_REDIS_TTL_SECONDS = 60
_activity_cache: dict[tuple[UUID, bool, tuple[UUID, ...]], tuple[float, ClientWindowsActivityOut]] = {}
_activity_builds: dict[tuple[UUID, bool, tuple[UUID, ...]], asyncio.Future[ClientWindowsActivityOut]] = {}


def clear_client_windows_activity_cache(client_id: UUID | None = None) -> None:
    if client_id is None:
        _activity_cache.clear()
        cache_backend.clear_namespace("window-activity")
        return
    stale_keys = [key for key in _activity_cache if key[0] == client_id]
    for key in stale_keys:
        _activity_cache.pop(key, None)
    cache_backend.delete_indexed(
        "window-activity",
        {"client-window-activity"},
        client_id=str(client_id),
    )


async def clear_client_windows_activity_cache_async(client_id: UUID | None = None) -> None:
    if client_id is None:
        _activity_cache.clear()
        await cache_backend.clear_namespace_async("window-activity")
        return
    stale_keys = [key for key in _activity_cache if key[0] == client_id]
    for key in stale_keys:
        _activity_cache.pop(key, None)
    await cache_backend.delete_indexed_async(
        "window-activity",
        {"client-window-activity"},
        client_id=str(client_id),
    )


def _begin_activity_build(
    cache_key: tuple[UUID, bool, tuple[UUID, ...]],
) -> asyncio.Future[ClientWindowsActivityOut] | None:
    future = _activity_builds.get(cache_key)
    if future is not None:
        return future
    loop = asyncio.get_running_loop()
    _activity_builds[cache_key] = loop.create_future()
    return None


def _finish_activity_build(
    cache_key: tuple[UUID, bool, tuple[UUID, ...]],
    *,
    result: ClientWindowsActivityOut | None,
    error: BaseException | None = None,
) -> None:
    future = _activity_builds.pop(cache_key, None)
    if future is None or future.done():
        return
    if error is None and result is not None:
        future.set_result(result)
        return
    failure = error if error is not None else RuntimeError("activity cache build failed")
    future.set_exception(failure)
    future.add_done_callback(lambda completed: completed.exception())


async def load_client_windows_activity(
    session: AsyncSession,
    client_id: UUID,
    *,
    include_runtime_tags: bool = False,
    visible_since: datetime | None = None,
    project_path: str | None = None,
) -> ClientWindowsActivityOut:
    filters = [
        VirtualWindow.client_id == client_id,
        VirtualWindow.folder_id.is_not(None),
    ]
    if visible_since is not None:
        filters.append(window_visible_at_expression() >= visible_since)
    if project_path is not None:
        filters.append(window_project_path_expression() == project_path)

    window_ids = list(
        await session.scalars(
            select(VirtualWindow.id)
            .where(*filters)
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
    redis_cached = await _redis_activity_cache_async(cache_key)
    if redis_cached is not None and now - redis_cached[0] <= _ACTIVITY_CACHE_TTL_SECONDS:
        return redis_cached[1]

    active_build = _begin_activity_build(cache_key)
    if active_build is not None:
        return await active_build

    error: BaseException | None = None
    result: ClientWindowsActivityOut | None = None
    try:
        result = await _build_client_windows_activity(
            session,
            client_id,
            window_ids,
            include_runtime_tags=include_runtime_tags,
        )
        if not await _store_redis_activity_cache_async(cache_key, now, result):
            _activity_cache[cache_key] = (now, result)
        return result
    except BaseException as exc:
        error = exc
        raise
    finally:
        _finish_activity_build(cache_key, result=result, error=error)


async def _build_client_windows_activity(
    session: AsyncSession,
    client_id: UUID,
    window_ids: list[UUID],
    *,
    include_runtime_tags: bool,
) -> ClientWindowsActivityOut:
    activity = await load_tree_window_activity(
        session,
        client_id,
        window_ids,
        include_runtime_tags=include_runtime_tags,
    )
    windows = list(
        await session.scalars(
            select(VirtualWindow)
            .options(
                load_only(
                    VirtualWindow.id,
                    VirtualWindow.cwd,
                    VirtualWindow.parent_window_id,
                    VirtualWindow.root_window_id,
                    VirtualWindow.derived_mode,
                )
            )
            .where(VirtualWindow.id.in_(window_ids))
        )
    )
    windows_by_id = {window.id: window for window in windows}
    git_worktrees = await _load_git_worktree_activity(session, window_ids)
    todo_titles = await assigned_todo_titles_by_window(session, window_ids, client_id=client_id)

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
        agent_task_status = activity.last_agent_task_status.get(window_id)
        items.append(
            WindowActivityOut(
                window_id=window_id,
                work_status=to_work_status_out(work_status),
                runtime_tags=runtime_tags,
                last_agent_task_completed_at=activity.last_agent_task_completed_at.get(
                    window_id
                ),
                last_agent_task_status=agent_task_status.state if agent_task_status is not None else None,
                last_agent_task_status_at=(
                    agent_task_status.occurred_at if agent_task_status is not None else None
                ),
                git_worktree=git_worktree,
                todo_title=todo_titles.get(window_id),
                parent_window_id=window.parent_window_id,
                root_window_id=window.root_window_id,
                derived_mode=window.derived_mode,
            )
        )
    return ClientWindowsActivityOut(windows=items)


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
    snapshots = await latest_git_worktree_snapshots_by_window_ids(
        session,
        [binding.virtual_window_id for binding in bindings],
    )
    return {
        binding.virtual_window_id: git_worktree_activity_out(
            binding,
            pending_commit=binding.virtual_window_id in pending_window_ids,
            snapshot=snapshots.get(binding.virtual_window_id),
        )
        for binding in bindings
    }


def _redis_activity_cache(
    cache_key: tuple[UUID, bool, tuple[UUID, ...]],
) -> tuple[float, ClientWindowsActivityOut] | None:
    cached = cache_backend.get_json("window-activity", cache_key)
    if cached is None:
        return None
    try:
        cached_at = float(cached["created_at"])
        payload = cached["payload"]
        return cached_at, ClientWindowsActivityOut.model_validate(payload)
    except (KeyError, TypeError, ValueError):
        cache_backend.delete_keys([cache_backend.cache_key("window-activity", cache_key)])
        return None


async def _redis_activity_cache_async(
    cache_key: tuple[UUID, bool, tuple[UUID, ...]],
) -> tuple[float, ClientWindowsActivityOut] | None:
    cached = await cache_backend.get_json_async("window-activity", cache_key)
    if cached is None:
        return None
    try:
        cached_at = float(cached["created_at"])
        payload = cached["payload"]
        return cached_at, ClientWindowsActivityOut.model_validate(payload)
    except (KeyError, TypeError, ValueError):
        await cache_backend.delete_keys_async([cache_backend.cache_key("window-activity", cache_key)])
        return None


def _store_redis_activity_cache(
    cache_key: tuple[UUID, bool, tuple[UUID, ...]],
    created_at: float,
    payload: ClientWindowsActivityOut,
) -> bool:
    client_id = cache_key[0]
    return cache_backend.set_indexed_json(
        "window-activity",
        cache_key,
        {
            "created_at": created_at,
            "client_id": str(client_id),
            "payload": payload.model_dump(mode="json"),
        },
        resources=frozenset({"client-window-activity"}),
        client_id=str(client_id),
        ttl_seconds=_ACTIVITY_CACHE_REDIS_TTL_SECONDS,
    )


async def _store_redis_activity_cache_async(
    cache_key: tuple[UUID, bool, tuple[UUID, ...]],
    created_at: float,
    payload: ClientWindowsActivityOut,
) -> bool:
    client_id = cache_key[0]
    return await cache_backend.set_indexed_json_async(
        "window-activity",
        cache_key,
        {
            "created_at": created_at,
            "client_id": str(client_id),
            "payload": payload.model_dump(mode="json"),
        },
        resources=frozenset({"client-window-activity"}),
        client_id=str(client_id),
        ttl_seconds=_ACTIVITY_CACHE_REDIS_TTL_SECONDS,
    )
