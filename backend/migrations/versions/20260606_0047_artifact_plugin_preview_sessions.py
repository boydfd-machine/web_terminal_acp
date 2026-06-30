from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "20260606_0047"
down_revision: str | None = "20260606_0046"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "artifact_plugin_preview_sessions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("client_id", sa.Uuid(), nullable=False),
        sa.Column("window_id", sa.Uuid(), nullable=False),
        sa.Column("created_by_window_id", sa.Uuid(), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "valid",
                "invalid",
                name="artifactpluginpreviewstatus",
                create_constraint=True,
            ),
            server_default="valid",
            nullable=False,
        ),
        sa.Column("draft_artifact_kind", sa.String(length=64), nullable=True),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("components_json", sa.JSON(), nullable=False),
        sa.Column("demo_content_json", sa.JSON(), nullable=True),
        sa.Column("rendered_content_json", sa.JSON(), nullable=True),
        sa.Column("display_html", sa.Text(), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["client_id"], ["clients.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["window_id"], ["virtual_windows.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by_window_id"], ["virtual_windows.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_artifact_plugin_previews_client_window_updated",
        "artifact_plugin_preview_sessions",
        ["client_id", "window_id", "updated_at", "id"],
    )
    op.create_index(
        "ix_artifact_plugin_previews_expires_at",
        "artifact_plugin_preview_sessions",
        ["expires_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_artifact_plugin_previews_expires_at", table_name="artifact_plugin_preview_sessions")
    op.drop_index(
        "ix_artifact_plugin_previews_client_window_updated",
        table_name="artifact_plugin_preview_sessions",
    )
    op.drop_table("artifact_plugin_preview_sessions")
