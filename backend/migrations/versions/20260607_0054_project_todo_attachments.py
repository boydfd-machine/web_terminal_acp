from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "20260607_0054"
down_revision: str | None = "20260607_0053"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "project_todo_attachments",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("project_todo_id", sa.Uuid(), nullable=False),
        sa.Column("client_id", sa.Uuid(), nullable=False),
        sa.Column("project_path", sa.Text(), nullable=False),
        sa.Column("object_key", sa.Text(), nullable=False),
        sa.Column("filename", sa.String(length=255), nullable=False),
        sa.Column("content_type", sa.String(length=128), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(length=16), server_default="pending", nullable=False),
        sa.Column("uploaded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["client_id"], ["clients.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["project_todo_id"], ["project_todos.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("object_key", name="uq_project_todo_attachments_object_key"),
    )
    op.create_index(
        "ix_project_todo_attachments_todo",
        "project_todo_attachments",
        ["project_todo_id", "created_at", "id"],
    )
    op.create_index(
        "ix_project_todo_attachments_client_project",
        "project_todo_attachments",
        ["client_id", "project_path", "created_at"],
    )
    op.create_index(
        "ix_project_todo_attachments_status",
        "project_todo_attachments",
        ["status", "updated_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_project_todo_attachments_status", table_name="project_todo_attachments")
    op.drop_index("ix_project_todo_attachments_client_project", table_name="project_todo_attachments")
    op.drop_index("ix_project_todo_attachments_todo", table_name="project_todo_attachments")
    op.drop_table("project_todo_attachments")
