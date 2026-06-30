from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "20260609_0062"
down_revision: str | None = "20260609_0061"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    _add_column_if_missing("project_todo_types", "input_artifact_ids_json")
    _add_column_if_missing("project_todos", "input_artifact_ids_json")


def downgrade() -> None:
    op.drop_column("project_todos", "input_artifact_ids_json")
    op.drop_column("project_todo_types", "input_artifact_ids_json")


def _add_column_if_missing(table_name: str, column_name: str) -> None:
    columns = {
        column["name"]
        for column in sa.inspect(op.get_bind()).get_columns(table_name)
    }
    if column_name not in columns:
        op.add_column(table_name, sa.Column(column_name, sa.JSON(), nullable=True))
