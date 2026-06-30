from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "20260607_0056"
down_revision: str | None = "20260607_0055"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("project_todos", sa.Column("parent_todo_id", sa.Uuid(), nullable=True))
    with op.batch_alter_table("project_todos") as batch_op:
        batch_op.create_foreign_key(
            "fk_project_todos_parent_todo_id_project_todos",
            "project_todos",
            ["parent_todo_id"],
            ["id"],
            ondelete="SET NULL",
        )
    op.create_index("ix_project_todos_parent_todo", "project_todos", ["parent_todo_id"])


def downgrade() -> None:
    op.drop_index("ix_project_todos_parent_todo", table_name="project_todos")
    with op.batch_alter_table("project_todos") as batch_op:
        batch_op.drop_constraint("fk_project_todos_parent_todo_id_project_todos", type_="foreignkey")
    op.drop_column("project_todos", "parent_todo_id")
