from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

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
) -> GitWorktreeRun | None:
    return await session.scalar(
        select(GitWorktreeRun).where(
            GitWorktreeRun.virtual_window_id == window_id,
            GitWorktreeRun.command_sequence == command_sequence,
        )
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
