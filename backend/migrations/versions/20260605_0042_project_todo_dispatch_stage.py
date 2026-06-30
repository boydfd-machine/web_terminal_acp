from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "20260605_0042"
down_revision: str | None = "20260605_0041"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("project_todos", sa.Column("dispatch_stage", sa.String(length=32), nullable=True))
    op.add_column("project_todos", sa.Column("dispatch_error", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("project_todos", "dispatch_error")
    op.drop_column("project_todos", "dispatch_stage")
