from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "20260612_0066"
down_revision: str | None = "20260612_0065"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


PROFILE_BY_TYPE_ID = {
    "quick-fix": "builtin/developer",
    "ui-change": "builtin/developer",
    "debug": "builtin/debug-expert",
    "small-feature": "builtin/developer",
    "large-feature": "builtin/developer",
    "solution-research": "builtin/deep-researcher",
    "performance-optimization": "builtin/debug-expert",
    "review": "builtin/pr-review",
    "product-design": "builtin/page-review",
    "user-review": "builtin/page-review",
}


def upgrade() -> None:
    table = _project_todo_types_table()
    for type_id, profile_id in PROFILE_BY_TYPE_ID.items():
        op.execute(
            table.update()
            .where(table.c.scope == "system")
            .where(table.c.id == type_id)
            .where(table.c.agent_profile_id.is_(None))
            .values(agent_profile_id=profile_id)
        )


def downgrade() -> None:
    table = _project_todo_types_table()
    for type_id, profile_id in PROFILE_BY_TYPE_ID.items():
        op.execute(
            table.update()
            .where(table.c.scope == "system")
            .where(table.c.id == type_id)
            .where(table.c.agent_profile_id == profile_id)
            .values(agent_profile_id=None)
        )


def _project_todo_types_table() -> sa.Table:
    return sa.table(
        "project_todo_types",
        sa.column("id", sa.String(length=64)),
        sa.column("scope", sa.String(length=16)),
        sa.column("agent_profile_id", sa.String(length=128)),
    )
