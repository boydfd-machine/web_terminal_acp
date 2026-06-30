from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "20260605_0041"
down_revision: str | None = "20260605_0040"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "project_todo_dependencies",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("client_id", sa.Uuid(), nullable=False),
        sa.Column("project_path", sa.Text(), nullable=False),
        sa.Column("project_todo_id", sa.Uuid(), nullable=False),
        sa.Column("depends_on_todo_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["client_id"], ["clients.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["depends_on_todo_id"], ["project_todos.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["project_todo_id"], ["project_todos.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("project_todo_id", "depends_on_todo_id", name="uq_project_todo_dependency_pair"),
    )
    op.create_index("ix_project_todo_dependencies_client_project", "project_todo_dependencies", ["client_id", "project_path"])
    op.create_index("ix_project_todo_dependencies_todo", "project_todo_dependencies", ["project_todo_id"])
    op.create_index("ix_project_todo_dependencies_upstream", "project_todo_dependencies", ["depends_on_todo_id"])

    op.create_table(
        "project_todo_queued_dispatches",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("project_todo_id", sa.Uuid(), nullable=False),
        sa.Column("client_id", sa.Uuid(), nullable=False),
        sa.Column("project_path", sa.Text(), nullable=False),
        sa.Column("agent_launch_json", sa.JSON(), nullable=False),
        sa.Column("dispatch_mode", sa.String(length=16), server_default="submit", nullable=False),
        sa.Column("prompt", sa.Text(), nullable=False),
        sa.Column("queued_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["client_id"], ["clients.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["project_todo_id"], ["project_todos.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("project_todo_id", name="uq_project_todo_queued_dispatch_todo"),
    )
    op.create_index(
        "ix_project_todo_queued_dispatches_client_project",
        "project_todo_queued_dispatches",
        ["client_id", "project_path", "queued_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_project_todo_queued_dispatches_client_project", table_name="project_todo_queued_dispatches")
    op.drop_table("project_todo_queued_dispatches")
    op.drop_index("ix_project_todo_dependencies_upstream", table_name="project_todo_dependencies")
    op.drop_index("ix_project_todo_dependencies_todo", table_name="project_todo_dependencies")
    op.drop_index("ix_project_todo_dependencies_client_project", table_name="project_todo_dependencies")
    op.drop_table("project_todo_dependencies")
