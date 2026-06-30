from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "20260604_0036"
down_revision: str | None = "20260604_0035"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "project_todos",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("client_id", sa.Uuid(), nullable=False),
        sa.Column("project_path", sa.Text(), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "status",
            sa.Enum(
                "TODO",
                "BLOCKED",
                "DISPATCHED",
                "AWAITING_REVIEW",
                "DONE",
                name="projecttodostatus",
                create_constraint=True,
            ),
            server_default="TODO",
            nullable=False,
        ),
        sa.Column("sort_order", sa.Integer(), server_default="0", nullable=False),
        sa.Column("assigned_window_id", sa.Uuid(), nullable=True),
        sa.Column("assigned_agent", sa.String(length=64), nullable=True),
        sa.Column("agent_profile_id", sa.String(length=128), nullable=True),
        sa.Column("dispatch_prompt", sa.Text(), nullable=True),
        sa.Column("dispatched_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("awaiting_review_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["assigned_window_id"], ["virtual_windows.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["client_id"], ["clients.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_project_todos_client_project_status",
        "project_todos",
        ["client_id", "project_path", "status", "updated_at"],
    )
    op.create_index("ix_project_todos_assigned_window", "project_todos", ["assigned_window_id"])


def downgrade() -> None:
    op.drop_index("ix_project_todos_assigned_window", table_name="project_todos")
    op.drop_index("ix_project_todos_client_project_status", table_name="project_todos")
    op.drop_table("project_todos")
    if op.get_bind().dialect.name == "postgresql":
        op.execute("DROP TYPE IF EXISTS projecttodostatus")
