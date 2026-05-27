from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "20260526_0014"
down_revision: str | None = "20260524_0013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_index(
        "ix_folders_client_sort_name",
        "folders",
        ["client_id", "sort_order", "name", "id"],
    )
    op.create_index(
        "ix_virtual_windows_client_folder_created",
        "virtual_windows",
        ["client_id", "folder_id", "created_at", "title", "id"],
    )
    op.create_index(
        "ix_ai_sessions_client_window_updated",
        "ai_sessions",
        ["client_id", "virtual_window_id", "updated_at"],
    )
    op.create_index(
        "ix_events_client_window_source_created",
        "events",
        ["client_id", "virtual_window_id", "source_type", "created_at"],
    )
    op.create_index(
        "ix_window_git_bindings_window_client",
        "window_git_bindings",
        ["virtual_window_id", "client_id"],
    )
    op.create_index(
        "ix_git_worktree_runs_window_pending",
        "git_worktree_runs",
        ["virtual_window_id", "pending_commit"],
    )


def downgrade() -> None:
    op.drop_index("ix_git_worktree_runs_window_pending", table_name="git_worktree_runs")
    op.drop_index("ix_window_git_bindings_window_client", table_name="window_git_bindings")
    op.drop_index("ix_events_client_window_source_created", table_name="events")
    op.drop_index("ix_ai_sessions_client_window_updated", table_name="ai_sessions")
    op.drop_index("ix_virtual_windows_client_folder_created", table_name="virtual_windows")
    op.drop_index("ix_folders_client_sort_name", table_name="folders")
