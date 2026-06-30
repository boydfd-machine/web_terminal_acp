from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "20260607_0055"
down_revision: str | None = "20260607_0054"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "virtual_windows",
        sa.Column("tmux_window_index", sa.String(length=64), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("virtual_windows", "tmux_window_index")
