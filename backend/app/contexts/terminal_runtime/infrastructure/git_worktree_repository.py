from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import desc, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import load_only

from app.models import GitWorktreeRun, WindowGitBinding


async def get_window_git_binding(
    session: AsyncSession,
    window_id: UUID,
) -> WindowGitBinding | None:
    return await session.scalar(
        select(WindowGitBinding).where(WindowGitBinding.virtual_window_id == window_id)
    )


async def upsert_window_git_binding(
    session: AsyncSession,
    *,
    client_id: UUID,
    window_id: UUID,
    main_repo_root: str,
    worktree_root: str,
    branch: str | None,
    discovery_method: str,
) -> WindowGitBinding:
    binding = await get_window_git_binding(session, window_id)
    now = datetime.now(UTC)
    if binding is None:
        binding = WindowGitBinding(
            client_id=client_id,
            virtual_window_id=window_id,
            main_repo_root=main_repo_root,
            worktree_root=worktree_root,
            branch=branch,
            discovery_method=discovery_method,
            bound_at=now,
            updated_at=now,
        )
        session.add(binding)
    else:
        binding.main_repo_root = main_repo_root
        binding.worktree_root = worktree_root
        binding.branch = branch
        binding.discovery_method = discovery_method
        binding.updated_at = now
    await session.flush()
    return binding


async def get_git_worktree_run(
    session: AsyncSession,
    window_id: UUID,
    command_sequence: str,
    *,
    include_payloads: bool = True,
) -> GitWorktreeRun | None:
    query = select(GitWorktreeRun).where(
        GitWorktreeRun.virtual_window_id == window_id,
        GitWorktreeRun.command_sequence == command_sequence,
    )
    if not include_payloads:
        query = query.options(_git_worktree_run_scalar_columns())
    return await session.scalar(
        query
    )


async def create_git_worktree_run(
    session: AsyncSession,
    *,
    client_id: UUID,
    window_id: UUID,
    command_sequence: str,
    agent_provider: str | None,
    status: str = "awaiting_worktree",
) -> GitWorktreeRun:
    run = GitWorktreeRun(
        client_id=client_id,
        virtual_window_id=window_id,
        command_sequence=command_sequence,
        agent_provider=agent_provider,
        status=status,
    )
    session.add(run)
    await session.flush()
    return run


async def list_git_worktree_runs(
    session: AsyncSession,
    window_id: UUID,
    *,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[GitWorktreeRun], int]:
    count = await session.scalar(
        select(func.count())
        .select_from(GitWorktreeRun)
        .where(GitWorktreeRun.virtual_window_id == window_id)
    )
    rows = list(
        await session.scalars(
            select(GitWorktreeRun)
            .where(GitWorktreeRun.virtual_window_id == window_id)
            .order_by(desc(GitWorktreeRun.started_at), desc(GitWorktreeRun.id))
            .offset(offset)
            .limit(limit)
        )
    )
    return rows, int(count or 0)


async def list_window_git_bindings(
    session: AsyncSession,
    window_ids: Sequence[UUID],
) -> list[WindowGitBinding]:
    if not window_ids:
        return []
    return list(
        await session.scalars(
            select(WindowGitBinding).where(WindowGitBinding.virtual_window_id.in_(window_ids))
        )
    )


async def list_unresolved_git_worktree_window_targets(
    session: AsyncSession,
    *,
    limit: int = 100,
) -> list[tuple[UUID, UUID]]:
    rows = await session.execute(
        select(WindowGitBinding.client_id, WindowGitBinding.virtual_window_id)
        .join(
            GitWorktreeRun,
            GitWorktreeRun.virtual_window_id == WindowGitBinding.virtual_window_id,
        )
        .where(
            GitWorktreeRun.worktree_root.is_not(None),
            GitWorktreeRun.resolved_at.is_(None),
        )
        .distinct()
        .limit(limit)
    )
    return [(client_id, window_id) for client_id, window_id in rows]


async def list_client_git_bindings_for_roots(
    session: AsyncSession,
    client_id: UUID,
    roots: Sequence[str],
) -> list[WindowGitBinding]:
    normalized_roots = [root for root in dict.fromkeys(roots) if root]
    if not normalized_roots:
        return []
    return list(
        await session.scalars(
            select(WindowGitBinding).where(
                WindowGitBinding.client_id == client_id,
                or_(
                    WindowGitBinding.main_repo_root.in_(normalized_roots),
                    WindowGitBinding.worktree_root.in_(normalized_roots),
                ),
            )
        )
    )


async def list_client_git_bindings_for_project_root(
    session: AsyncSession,
    client_id: UUID,
    project_root: str,
) -> list[WindowGitBinding]:
    seed_bindings = await list_client_git_bindings_for_roots(session, client_id, [project_root])
    main_roots = {
        binding.main_repo_root
        for binding in seed_bindings
        if project_root in {binding.main_repo_root, binding.worktree_root}
    } or {project_root}
    return list(
        await session.scalars(
            select(WindowGitBinding)
            .where(
                WindowGitBinding.client_id == client_id,
                WindowGitBinding.main_repo_root.in_(main_roots),
            )
            .order_by(WindowGitBinding.branch, WindowGitBinding.worktree_root)
        )
    )


async def window_has_pending_commit(session: AsyncSession, window_id: UUID) -> bool:
    pending_run = await session.scalar(
        select(GitWorktreeRun.id)
        .where(
            GitWorktreeRun.virtual_window_id == window_id,
            GitWorktreeRun.pending_commit.is_(True),
        )
        .limit(1)
    )
    return pending_run is not None


async def pending_commit_window_ids(
    session: AsyncSession,
    window_ids: Sequence[UUID],
) -> set[UUID]:
    if not window_ids:
        return set()
    rows = await session.scalars(
        select(GitWorktreeRun.virtual_window_id)
        .where(
            GitWorktreeRun.virtual_window_id.in_(window_ids),
            GitWorktreeRun.pending_commit.is_(True),
        )
        .group_by(GitWorktreeRun.virtual_window_id)
    )
    return set(rows)


async def latest_git_worktree_snapshots_by_window_ids(
    session: AsyncSession,
    window_ids: Sequence[UUID],
) -> dict[UUID, dict]:
    if not window_ids:
        return {}
    ranked = (
        select(
            GitWorktreeRun.virtual_window_id.label("window_id"),
            GitWorktreeRun.end_snapshot_json.label("snapshot"),
            func.row_number()
            .over(
                partition_by=GitWorktreeRun.virtual_window_id,
                order_by=(
                    desc(
                        func.coalesce(
                            GitWorktreeRun.resolved_at,
                            GitWorktreeRun.ended_at,
                            GitWorktreeRun.started_at,
                        )
                    ),
                    desc(GitWorktreeRun.id),
                ),
            )
            .label("rank"),
        )
        .where(
            GitWorktreeRun.virtual_window_id.in_(window_ids),
            GitWorktreeRun.end_snapshot_json.is_not(None),
        )
        .subquery()
    )
    rows = await session.execute(
        select(ranked.c.window_id, ranked.c.snapshot).where(ranked.c.rank == 1)
    )
    snapshots: dict[UUID, dict] = {}
    for window_id, snapshot in rows:
        if isinstance(snapshot, dict):
            snapshots[window_id] = snapshot
    return snapshots


def _git_worktree_run_scalar_columns():
    return load_only(
        GitWorktreeRun.id,
        GitWorktreeRun.client_id,
        GitWorktreeRun.virtual_window_id,
        GitWorktreeRun.command_sequence,
        GitWorktreeRun.agent_provider,
        GitWorktreeRun.status,
        GitWorktreeRun.main_repo_root,
        GitWorktreeRun.worktree_root,
        GitWorktreeRun.discovery_method,
        GitWorktreeRun.pending_commit,
        GitWorktreeRun.resolved_at,
        GitWorktreeRun.started_at,
        GitWorktreeRun.ended_at,
    )
