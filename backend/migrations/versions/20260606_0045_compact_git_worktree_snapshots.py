from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import sqlalchemy as sa
from alembic import op

revision: str = "20260606_0045"
down_revision: str | None = "20260605_0044"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_COMPACT_SNAPSHOT_KEYS = {
    "is_linked_worktree",
    "worktree_root",
    "main_repo_root",
    "branch",
    "head_sha",
    "status_porcelain",
    "diff_stat",
    "staged_diff_stat",
    "merge_status",
    "merge_status_reason",
    "merged_to_main",
    "main_branch",
    "main_head_sha",
    "main_merge_head_sha",
    "main_merge_in_progress",
    "main_merge_matches_worktree",
    "unmerged_files",
}


def upgrade() -> None:
    connection = op.get_bind()
    table = sa.table(
        "git_worktree_runs",
        sa.column("id", sa.Uuid()),
        sa.column("start_snapshot_json", sa.JSON()),
        sa.column("end_snapshot_json", sa.JSON()),
    )
    rows = connection.execute(
        sa.select(table.c.id, table.c.start_snapshot_json, table.c.end_snapshot_json).where(
            sa.or_(
                table.c.start_snapshot_json.is_not(None),
                table.c.end_snapshot_json.is_not(None),
            )
        )
    )
    for row in rows:
        start_snapshot = _compact_snapshot(row.start_snapshot_json)
        end_snapshot = _compact_snapshot(row.end_snapshot_json)
        if start_snapshot == row.start_snapshot_json and end_snapshot == row.end_snapshot_json:
            continue
        connection.execute(
            table.update()
            .where(table.c.id == row.id)
            .values(
                start_snapshot_json=start_snapshot,
                end_snapshot_json=end_snapshot,
            )
        )


def downgrade() -> None:
    pass


def _compact_snapshot(snapshot: Any) -> dict[str, Any] | None:
    if not isinstance(snapshot, dict):
        return None
    return {
        key: value
        for key, value in snapshot.items()
        if key in _COMPACT_SNAPSHOT_KEYS and value is not None
    }
