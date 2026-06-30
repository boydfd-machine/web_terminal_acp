from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260604_0035"
down_revision: str | None = "20260603_0034"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_INDEX_NAME = "uq_summary_jobs_active_virtual_window_id"
_PENDING_ONLY_FILTER = sa.text("status = 'PENDING'")
_ACTIVE_FILTER = sa.text("status IN ('PENDING', 'RUNNING')")


def upgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        with op.get_context().autocommit_block():
            op.execute(
                "DROP INDEX CONCURRENTLY IF EXISTS "
                "uq_summary_jobs_active_virtual_window_id"
            )
            op.execute(
                "CREATE UNIQUE INDEX CONCURRENTLY IF NOT EXISTS "
                "uq_summary_jobs_active_virtual_window_id "
                "ON summary_jobs (virtual_window_id) WHERE status = 'PENDING'"
            )
        return

    op.drop_index(_INDEX_NAME, table_name="summary_jobs")
    op.create_index(
        _INDEX_NAME,
        "summary_jobs",
        ["virtual_window_id"],
        unique=True,
        postgresql_where=_PENDING_ONLY_FILTER,
        sqlite_where=_PENDING_ONLY_FILTER,
    )


def downgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        with op.get_context().autocommit_block():
            op.execute(
                "DROP INDEX CONCURRENTLY IF EXISTS "
                "uq_summary_jobs_active_virtual_window_id"
            )
            op.execute(
                "CREATE UNIQUE INDEX CONCURRENTLY IF NOT EXISTS "
                "uq_summary_jobs_active_virtual_window_id "
                "ON summary_jobs (virtual_window_id) WHERE status IN ('PENDING', 'RUNNING')"
            )
        return

    op.drop_index(_INDEX_NAME, table_name="summary_jobs")
    op.create_index(
        _INDEX_NAME,
        "summary_jobs",
        ["virtual_window_id"],
        unique=True,
        postgresql_where=_ACTIVE_FILTER,
        sqlite_where=_ACTIVE_FILTER,
    )
