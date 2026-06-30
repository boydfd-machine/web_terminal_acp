from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "20260608_0059"
down_revision: str | None = "20260608_0058"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    _ensure_dispatch_output_language_column()
    op.create_index(
        "ix_project_todos_client_project_updated",
        "project_todos",
        ["client_id", "project_path", "updated_at", "id"],
        if_not_exists=True,
    )
    op.create_index(
        "ix_project_todos_artifact_candidates",
        "project_todos",
        ["client_id", "project_path", "sort_order", "updated_at", "id"],
        if_not_exists=True,
        postgresql_where=sa.text(
            "artifact_kinds_json IS NOT NULL "
            "AND assigned_window_id IS NOT NULL "
            "AND status IN ('AWAITING_REVIEW', 'DONE')"
        ),
        sqlite_where=sa.text(
            "artifact_kinds_json IS NOT NULL "
            "AND assigned_window_id IS NOT NULL "
            "AND status IN ('AWAITING_REVIEW', 'DONE')"
        ),
    )


def downgrade() -> None:
    op.drop_index("ix_project_todos_artifact_candidates", table_name="project_todos")
    op.drop_index("ix_project_todos_client_project_updated", table_name="project_todos")


def _ensure_dispatch_output_language_column() -> None:
    columns = {
        column["name"]
        for column in sa.inspect(op.get_bind()).get_columns("project_todos")
    }
    if "dispatch_output_language" not in columns:
        op.add_column(
            "project_todos",
            sa.Column("dispatch_output_language", sa.String(length=64), nullable=True),
        )
