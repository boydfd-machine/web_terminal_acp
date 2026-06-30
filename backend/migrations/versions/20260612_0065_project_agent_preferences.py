from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "20260612_0065"
down_revision: str | None = "20260612_0064"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "project_agent_preferences",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("client_id", sa.Uuid(), nullable=False),
        sa.Column("project_path", sa.Text(), nullable=False),
        sa.Column("agent_profile_id", sa.String(length=128), nullable=True),
        sa.Column("agent_client", sa.String(length=64), nullable=True),
        sa.Column("agent_command", sa.String(length=4096), nullable=True),
        sa.Column("agent_model_selection_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["client_id"], ["clients.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("client_id", "project_path", name="uq_project_agent_preferences_client_path"),
    )
    op.create_index(
        "ix_project_agent_preferences_client_project",
        "project_agent_preferences",
        ["client_id", "project_path"],
    )


def downgrade() -> None:
    op.drop_index("ix_project_agent_preferences_client_project", table_name="project_agent_preferences")
    op.drop_table("project_agent_preferences")
