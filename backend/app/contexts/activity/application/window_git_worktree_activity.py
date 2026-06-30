from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.contexts.activity.api.schemas import GitWorktreeActivityOut
from app.contexts.terminal_runtime.application.git_worktree_queries import (
    get_window_git_binding,
    latest_git_worktree_snapshots_by_window_ids,
    window_has_pending_commit,
)
from app.contexts.terminal_runtime.domain.git_worktree_ops import (
    git_worktree_merge_state,
    git_worktree_needs_merge_attention,
)


async def load_window_git_worktree_activity(
    session: AsyncSession,
    window_id: UUID,
) -> GitWorktreeActivityOut | None:
    binding = await get_window_git_binding(session, window_id)
    if binding is None:
        return None
    snapshots = await latest_git_worktree_snapshots_by_window_ids(session, [window_id])
    return git_worktree_activity_out(
        binding,
        pending_commit=await window_has_pending_commit(session, window_id),
        snapshot=snapshots.get(window_id),
    )


def git_worktree_activity_out(
    binding,
    *,
    pending_commit: bool,
    snapshot: dict | None,
) -> GitWorktreeActivityOut:
    merge_state = git_worktree_merge_state(snapshot)
    return GitWorktreeActivityOut(
        worktree_root=binding.worktree_root,
        main_repo_root=binding.main_repo_root,
        branch=binding.branch,
        pending_commit=pending_commit,
        merge_attention_required=git_worktree_needs_merge_attention(snapshot),
        **merge_state,
    )
