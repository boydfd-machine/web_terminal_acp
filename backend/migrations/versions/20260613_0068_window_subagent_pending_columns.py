from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "20260613_0068"
down_revision: str | None = "20260612_0067"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "virtual_windows",
        sa.Column(
            "agent_activity_deferred_completed_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )
    op.add_column(
        "virtual_windows",
        sa.Column(
            "agent_activity_pending_subagent_count",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
    )
    op.add_column(
        "virtual_windows",
        sa.Column(
            "agent_activity_latest_subagent_call_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )
    op.add_column(
        "project_todos",
        sa.Column("blocked_reason", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("project_todos", "blocked_reason")
    op.drop_column("virtual_windows", "agent_activity_latest_subagent_call_at")
    op.drop_column("virtual_windows", "agent_activity_pending_subagent_count")
    op.drop_column("virtual_windows", "agent_activity_deferred_completed_at")
