from __future__ import annotations

from collections.abc import Sequence
import uuid

from alembic import op
import sqlalchemy as sa

revision: str = "20260606_0049"
down_revision: str | None = "20260606_0048"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "project_todo_types",
        sa.Column("record_id", sa.Uuid(), nullable=False),
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("scope", sa.String(length=16), server_default="system", nullable=False),
        sa.Column("client_id", sa.Uuid(), nullable=True),
        sa.Column("project_path", sa.Text(), nullable=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("agent", sa.String(length=64), nullable=True),
        sa.Column("agent_profile_id", sa.String(length=128), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["client_id"], ["clients.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("record_id"),
    )
    op.create_index("ix_project_todo_types_scope", "project_todo_types", ["scope", "id"])
    op.create_index(
        "ix_project_todo_types_project",
        "project_todo_types",
        ["client_id", "project_path", "id"],
    )
    op.create_index(
        "uq_project_todo_types_system_id",
        "project_todo_types",
        ["id"],
        unique=True,
        sqlite_where=sa.text("scope = 'system'"),
        postgresql_where=sa.text("scope = 'system'"),
    )
    op.create_index(
        "uq_project_todo_types_project_id",
        "project_todo_types",
        ["client_id", "project_path", "id"],
        unique=True,
        sqlite_where=sa.text("scope = 'project'"),
        postgresql_where=sa.text("scope = 'project'"),
    )
    op.add_column(
        "project_todos",
        sa.Column("todo_type_id", sa.String(length=64), server_default="default", nullable=False),
    )


def downgrade() -> None:
    op.drop_column("project_todos", "todo_type_id")
    op.drop_index("uq_project_todo_types_project_id", table_name="project_todo_types")
    op.drop_index("uq_project_todo_types_system_id", table_name="project_todo_types")
    op.drop_index("ix_project_todo_types_project", table_name="project_todo_types")
    op.drop_index("ix_project_todo_types_scope", table_name="project_todo_types")
    op.drop_table("project_todo_types")
