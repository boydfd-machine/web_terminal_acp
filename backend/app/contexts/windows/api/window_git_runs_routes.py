from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import Depends, Query, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.contexts.terminal_runtime.application.connection_registry import client_connection_registry_from_state
from app.contexts.terminal_runtime.application.git_worktree_agent_markers import materialize_agent_worktree_markers
from app.contexts.terminal_runtime.application.git_worktree_coordinator import process_git_worktree_snapshot_refresh
from app.contexts.terminal_runtime.application.git_worktree_queries import get_window_git_binding, list_git_worktree_runs
from app.contexts.windows.api.git_worktree_run_projection import to_git_worktree_run_out
from app.contexts.windows.api.response_projection import router
from app.contexts.windows.api.window_lifecycle_routes import _require_window_for_agent_record
from app.contexts.windows.api.schemas import GitWorktreeRunListOut
from app.db import get_session
from app.models import Client


@router.get(
    "/clients/{client_id}/windows/{window_id}/git-runs",
    response_model=GitWorktreeRunListOut,
)
async def read_window_git_runs(
    request: Request,
    client_id: UUID,
    window_id: UUID,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
    session: AsyncSession = Depends(get_session),
) -> GitWorktreeRunListOut:
    await _require_window_for_agent_record(session, client_id, window_id)
    registry = client_connection_registry_from_state(request.app.state)
    client_runtime = await session.scalar(select(Client.runtime).where(Client.id == client_id))
    binding = await get_window_git_binding(session, window_id)
    if binding is None:
        materialized = await materialize_agent_worktree_markers(
            session,
            client_id=client_id,
            window_ids=(window_id,),
            registry=registry,
        )
        if materialized:
            await process_git_worktree_snapshot_refresh(
                session,
                client_id=client_id,
                window_id=window_id,
                registry=registry,
                client_runtime=client_runtime,
            )
            await session.commit()
            binding = await get_window_git_binding(session, window_id)
    if binding is None:
        return GitWorktreeRunListOut(supported=False, runs=[], total=0, limit=limit, offset=offset)
    runs, total = await list_git_worktree_runs(session, window_id, limit=limit, offset=offset)
    if _git_worktree_runs_need_refresh(runs):
        refreshed = await process_git_worktree_snapshot_refresh(
            session,
            client_id=client_id,
            window_id=window_id,
            registry=registry,
            client_runtime=client_runtime,
        )
        if refreshed:
            await session.commit()
            runs, total = await list_git_worktree_runs(session, window_id, limit=limit, offset=offset)
    return GitWorktreeRunListOut(
        supported=True,
        runs=[to_git_worktree_run_out(run) for run in runs],
        total=total,
        limit=limit,
        offset=offset,
    )


def _git_worktree_runs_need_refresh(runs: list[object]) -> bool:
    return any(
        getattr(run, "end_snapshot_json", None) is None
        or getattr(run, "session_diff_json", None) is None
        or _git_worktree_run_has_empty_merged_diff(run)
        for run in runs
    )


def _git_worktree_run_has_empty_merged_diff(run: object) -> bool:
    if not str(getattr(run, "command_sequence", "")).startswith("worktree:"):
        return False
    session_diff = getattr(run, "session_diff_json", None)
    if not isinstance(session_diff, dict):
        return False
    if session_diff.get("has_changes") or session_diff.get("commits") or session_diff.get("files"):
        return False
    return _snapshot_is_merged(getattr(run, "start_snapshot_json", None)) or _snapshot_is_merged(
        getattr(run, "end_snapshot_json", None)
    )


def _snapshot_is_merged(snapshot: object) -> bool:
    return isinstance(snapshot, dict) and (
        snapshot.get("merged_to_main") is True or snapshot.get("merge_status") == "merged"
    )
