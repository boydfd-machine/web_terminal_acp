from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "20260605_0044"
down_revision: str | None = "20260605_0043"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        UPDATE project_todos
        SET status = 'TODO'
        WHERE status = 'BLOCKED'
          AND id IN (
              SELECT project_todo_id
              FROM project_todo_queued_dispatches
          )
        """
    )


def downgrade() -> None:
    op.execute(
        """
        UPDATE project_todos
        SET status = 'BLOCKED'
        WHERE status = 'TODO'
          AND id IN (
              SELECT project_todo_id
              FROM project_todo_queued_dispatches
          )
        """
    )
