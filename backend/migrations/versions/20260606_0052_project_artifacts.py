from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "20260606_0052"
down_revision: str | None = "20260606_0051"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "terminal_artifacts",
        sa.Column("artifact_scope", sa.String(length=16), server_default="terminal", nullable=False),
    )
    op.add_column("terminal_artifacts", sa.Column("project_path", sa.Text(), nullable=True))
    if not _is_sqlite():
        op.create_check_constraint(
            "ck_terminal_artifacts_scope",
            "terminal_artifacts",
            "artifact_scope IN ('terminal', 'project')",
        )
    op.create_index(
        "ix_terminal_artifacts_client_scope_project_created",
        "terminal_artifacts",
        ["client_id", "artifact_scope", "project_path", "created_at", "id"],
    )


def downgrade() -> None:
    op.drop_index("ix_terminal_artifacts_client_scope_project_created", table_name="terminal_artifacts")
    if not _is_sqlite():
        op.drop_constraint("ck_terminal_artifacts_scope", "terminal_artifacts", type_="check")
    op.drop_column("terminal_artifacts", "project_path")
    op.drop_column("terminal_artifacts", "artifact_scope")


def _is_sqlite() -> bool:
    return op.get_bind().dialect.name == "sqlite"
