from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "20260606_0051"
down_revision: str | None = "20260606_0050"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "project_todos",
        sa.Column("schedule_enabled", sa.Boolean(), server_default=sa.false(), nullable=False),
    )
    op.execute(
        "UPDATE project_todos "
        "SET schedule_enabled = TRUE "
        "WHERE execution_kind = 'PERIODIC' "
        "AND trigger_strategy = 'CRON' "
        "AND cron_expression IS NOT NULL"
    )
    op.drop_index("ix_project_todos_periodic_due", table_name="project_todos")
    op.create_index(
        "ix_project_todos_periodic_due",
        "project_todos",
        ["client_id", "trigger_strategy", "schedule_enabled", "next_trigger_at", "status"],
    )


def downgrade() -> None:
    op.drop_index("ix_project_todos_periodic_due", table_name="project_todos")
    op.create_index(
        "ix_project_todos_periodic_due",
        "project_todos",
        ["client_id", "trigger_strategy", "next_trigger_at", "status"],
    )
    op.drop_column("project_todos", "schedule_enabled")
