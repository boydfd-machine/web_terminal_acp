from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.contexts.terminal_runtime.application.client_connections import ClientConnectionRegistry
from app.contexts.terminal_runtime.application.git_worktree_coordinator.tracking_service import (
    _git_worktree_action,
)
from app.contexts.terminal_runtime.domain.git_worktree_ops import pending_commit_from_live_snapshot
from app.contexts.terminal_runtime.infrastructure.git_worktree_repository import (
    get_window_git_binding,
    window_has_pending_commit,
)
from app.models import ClientRuntime, GitWorktreeRun


async def load_git_worktree_activity_for_window(
    session: AsyncSession,
    *,
    client_id: UUID,
    window_id: UUID,
    registry: ClientConnectionRegistry | None,
    client_runtime: ClientRuntime | None = None,
) -> dict[str, Any] | None:
    binding = await get_window_git_binding(session, window_id)
    if binding is None:
        return None

    if registry is not None:
        result = await _git_worktree_action(
            registry,
            client_id,
            client_runtime,
            action="detect",
            path=binding.worktree_root,
        )
        if result and result.get("ok"):
            context = result.get("context") or {}
            if not context.get("is_linked_worktree"):
                return None
            binding.branch = context.get("branch") or binding.branch

        live = await _git_worktree_action(
            registry,
            client_id,
            client_runtime,
            action="snapshot",
            worktree_root=binding.worktree_root,
        )
        if live and live.get("ok"):
            snapshot = live.get("snapshot") or {}
            pending = await window_has_pending_commit(session, window_id)
            if pending:
                still_pending = pending_commit_from_live_snapshot(snapshot)
                if not still_pending:
                    await session.execute(
                        update(GitWorktreeRun)
                        .where(
                            GitWorktreeRun.virtual_window_id == window_id,
                            GitWorktreeRun.pending_commit.is_(True),
                        )
                        .values(pending_commit=False, resolved_at=datetime.now(UTC))
                    )

    pending_commit = await window_has_pending_commit(session, window_id)
    return {
        "worktree_root": binding.worktree_root,
        "main_repo_root": binding.main_repo_root,
        "branch": binding.branch,
        "pending_commit": pending_commit,
    }
