from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "20260609_0063"
down_revision: str | None = "20260609_0062"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

INDEX_NAME = "ix_project_todos_worktree_attention"
POSTGRESQL_PREDICATE = (
    "assigned_window_id IS NOT NULL "
    "AND implementation_worktree_json IS NOT NULL "
    "AND status IN ('AWAITING_REVIEW', 'DONE') "
    "AND (CAST((implementation_worktree_json ->> 'merge_attention_required') AS BOOLEAN) IS true "
    "OR (implementation_worktree_json ->> 'merge_status') IN ('unmerged', 'conflict') "
    "OR CAST((implementation_worktree_json ->> 'merged_to_main') AS BOOLEAN) IS false)"
)
SQLITE_PREDICATE = (
    "assigned_window_id IS NOT NULL "
    "AND implementation_worktree_json IS NOT NULL "
    "AND status IN ('AWAITING_REVIEW', 'DONE') "
    "AND (json_extract(implementation_worktree_json, '$.merge_attention_required') = 1 "
    "OR json_extract(implementation_worktree_json, '$.merge_status') IN ('unmerged', 'conflict') "
    "OR json_extract(implementation_worktree_json, '$.merged_to_main') = 0)"
)


def upgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        with op.get_context().autocommit_block():
            op.execute(
                "CREATE INDEX CONCURRENTLY IF NOT EXISTS "
                f"{INDEX_NAME} "
                "ON project_todos (updated_at DESC, id DESC, client_id, assigned_window_id) "
                f"WHERE {POSTGRESQL_PREDICATE}"
            )
        return

    op.create_index(
        INDEX_NAME,
        "project_todos",
        [sa.text("updated_at DESC"), sa.text("id DESC"), "client_id", "assigned_window_id"],
        sqlite_where=sa.text(SQLITE_PREDICATE),
    )


def downgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        with op.get_context().autocommit_block():
            op.execute(f"DROP INDEX CONCURRENTLY IF EXISTS {INDEX_NAME}")
        return

    op.drop_index(INDEX_NAME, table_name="project_todos")
