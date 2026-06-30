from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "20260606_0050"
down_revision: str | None = "20260606_0049"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("project_todo_types", sa.Column("artifact_kinds_json", sa.JSON(), nullable=True))
    op.add_column("project_todo_types", sa.Column("dispatch_template", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("project_todo_types", "dispatch_template")
    op.drop_column("project_todo_types", "artifact_kinds_json")
