from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "20260602_0033"
down_revision: str | None = "20260602_0032"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "terminal_artifacts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("client_id", sa.Uuid(), nullable=False),
        sa.Column("virtual_window_id", sa.Uuid(), nullable=False),
        sa.Column("source_window_id", sa.Uuid(), nullable=True),
        sa.Column("ephemeral_window_id", sa.Uuid(), nullable=True),
        sa.Column("artifact_kind", sa.String(length=64), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "PENDING",
                "RUNNING",
                "SUCCEEDED",
                "FAILED",
                name="terminalartifactstatus",
                create_constraint=True,
            ),
            server_default="PENDING",
            nullable=False,
        ),
        sa.Column("content_json", sa.JSON(), nullable=True),
        sa.Column("display_html", sa.Text(), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["client_id"], ["clients.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["virtual_window_id"], ["virtual_windows.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_window_id"], ["virtual_windows.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["ephemeral_window_id"], ["virtual_windows.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_terminal_artifacts_client_window_created",
        "terminal_artifacts",
        ["client_id", "virtual_window_id", "created_at", "id"],
    )
    op.create_index(
        "ix_terminal_artifacts_client_window_kind_created",
        "terminal_artifacts",
        ["client_id", "virtual_window_id", "artifact_kind", "created_at", "id"],
    )
    op.create_index(
        "ix_terminal_artifacts_status_created",
        "terminal_artifacts",
        ["status", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_terminal_artifacts_status_created", table_name="terminal_artifacts")
    op.drop_index("ix_terminal_artifacts_client_window_kind_created", table_name="terminal_artifacts")
    op.drop_index("ix_terminal_artifacts_client_window_created", table_name="terminal_artifacts")
    op.drop_table("terminal_artifacts")
