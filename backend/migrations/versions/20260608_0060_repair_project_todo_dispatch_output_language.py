from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "20260608_0060"
down_revision: str | None = "20260608_0059"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    columns = {
        column["name"]
        for column in sa.inspect(op.get_bind()).get_columns("project_todos")
    }
    if "dispatch_output_language" not in columns:
        op.add_column(
            "project_todos",
            sa.Column("dispatch_output_language", sa.String(length=64), nullable=True),
        )


def downgrade() -> None:
    pass
