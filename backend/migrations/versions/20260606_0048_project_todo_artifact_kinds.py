from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "20260606_0048"
down_revision: str | None = "20260606_0047"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("project_todos", sa.Column("artifact_kinds_json", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("project_todos", "artifact_kinds_json")
