from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "20260623_0070"
down_revision: str | None = "20260615_0069"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "project_todo_versions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("project_todo_id", sa.Uuid(), nullable=False),
        sa.Column("client_id", sa.Uuid(), nullable=False),
        sa.Column("project_path", sa.Text(), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("actor_type", sa.String(length=16), nullable=False),
        sa.Column("actor_id", sa.String(length=255), nullable=True),
        sa.Column("actor_display", sa.String(length=255), nullable=True),
        sa.Column("source_window_id", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["client_id"], ["clients.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["project_todo_id"], ["project_todos.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_window_id"], ["virtual_windows.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("project_todo_id", "version_number", name="uq_project_todo_versions_todo_number"),
    )
    op.create_index(
        "ix_project_todo_versions_todo_created",
        "project_todo_versions",
        ["project_todo_id", "created_at", "id"],
    )
    op.create_index(
        "ix_project_todo_versions_client_project",
        "project_todo_versions",
        ["client_id", "project_path", "created_at"],
    )
    op.create_table(
        "project_todo_audit_logs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("project_todo_id", sa.Uuid(), nullable=False),
        sa.Column("client_id", sa.Uuid(), nullable=False),
        sa.Column("project_path", sa.Text(), nullable=False),
        sa.Column("action", sa.String(length=32), nullable=False),
        sa.Column("fields_json", sa.JSON(), nullable=False),
        sa.Column("actor_type", sa.String(length=16), nullable=False),
        sa.Column("actor_id", sa.String(length=255), nullable=True),
        sa.Column("actor_display", sa.String(length=255), nullable=True),
        sa.Column("source_window_id", sa.Uuid(), nullable=True),
        sa.Column("from_version_number", sa.Integer(), nullable=True),
        sa.Column("to_version_number", sa.Integer(), nullable=True),
        sa.Column("restored_version_number", sa.Integer(), nullable=True),
        sa.Column("changes_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["client_id"], ["clients.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["project_todo_id"], ["project_todos.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_window_id"], ["virtual_windows.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_project_todo_audit_logs_todo_created",
        "project_todo_audit_logs",
        ["project_todo_id", "created_at", "id"],
    )
    op.create_index(
        "ix_project_todo_audit_logs_client_project",
        "project_todo_audit_logs",
        ["client_id", "project_path", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_project_todo_audit_logs_client_project", table_name="project_todo_audit_logs")
    op.drop_index("ix_project_todo_audit_logs_todo_created", table_name="project_todo_audit_logs")
    op.drop_table("project_todo_audit_logs")
    op.drop_index("ix_project_todo_versions_client_project", table_name="project_todo_versions")
    op.drop_index("ix_project_todo_versions_todo_created", table_name="project_todo_versions")
    op.drop_table("project_todo_versions")
