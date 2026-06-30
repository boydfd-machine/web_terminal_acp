from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "20260605_0043"
down_revision: str | None = "20260605_0042"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "virtual_windows",
        sa.Column("manual_work_status_state", sa.String(length=32), nullable=True),
    )
    op.add_column(
        "virtual_windows",
        sa.Column("manual_work_status_updated_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("virtual_windows", "manual_work_status_updated_at")
    op.drop_column("virtual_windows", "manual_work_status_state")
