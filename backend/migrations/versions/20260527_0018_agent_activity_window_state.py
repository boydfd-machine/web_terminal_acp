from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "20260527_0018"
down_revision: str | None = "20260527_0017"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "virtual_windows",
        sa.Column("agent_activity_latest_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "virtual_windows",
        sa.Column("agent_activity_latest_event_id", sa.Uuid(), nullable=True),
    )
    op.add_column(
        "virtual_windows",
        sa.Column("agent_activity_burst_start_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "virtual_windows",
        sa.Column(
            "agent_activity_generation",
            sa.Integer(),
            server_default="0",
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column("virtual_windows", "agent_activity_generation")
    op.drop_column("virtual_windows", "agent_activity_burst_start_at")
    op.drop_column("virtual_windows", "agent_activity_latest_event_id")
    op.drop_column("virtual_windows", "agent_activity_latest_at")
