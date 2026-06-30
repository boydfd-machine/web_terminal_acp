from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "20260629_0071"
down_revision: str | None = "20260623_0070"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


REMOVED_SYSTEM_TYPE_IDS = (
    "quick-fix",
    "ui-change",
    "debug",
    "small-feature",
    "large-feature",
    "solution-research",
    "performance-optimization",
    "review",
    "product-design",
    "user-review",
    "requirement-review",
)


def upgrade() -> None:
    table = _project_todo_types_table()
    op.execute(
        table.delete().where(
            table.c.scope == "system",
            table.c.owner_user_id.is_(None),
            table.c.id.in_(REMOVED_SYSTEM_TYPE_IDS),
        )
    )


def downgrade() -> None:
    pass


def _project_todo_types_table() -> sa.Table:
    return sa.table(
        "project_todo_types",
        sa.column("id", sa.String(length=64)),
        sa.column("scope", sa.String(length=16)),
        sa.column("owner_user_id", sa.String(length=255)),
    )
