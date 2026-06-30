from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "20260608_0058"
down_revision: str | None = "20260607_0057"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("project_todos", sa.Column("dispatch_output_language", sa.String(length=64), nullable=True))


def downgrade() -> None:
    op.drop_column("project_todos", "dispatch_output_language")
