from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from alembic import op
import sqlalchemy as sa

revision: str = "20260607_0057"
down_revision: str | None = "20260607_0056"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SEEDED_TYPE_IDS = ("requirement-review",)


def upgrade() -> None:
    table = _project_todo_types_table()
    existing_ids = set(
        op.get_bind()
        .execute(
            sa.select(table.c.id).where(
                table.c.scope == "system",
                table.c.id.in_(SEEDED_TYPE_IDS),
            )
        )
        .scalars()
    )
    rows = [row for row in _seed_rows() if row["id"] not in existing_ids]
    if rows:
        op.bulk_insert(table, rows)


def downgrade() -> None:
    table = _project_todo_types_table()
    op.execute(
        table.delete().where(
            table.c.scope == "system",
            table.c.id.in_(SEEDED_TYPE_IDS),
        )
    )


def _project_todo_types_table() -> sa.Table:
    return sa.table(
        "project_todo_types",
        sa.column("record_id", sa.Uuid()),
        sa.column("id", sa.String(length=64)),
        sa.column("scope", sa.String(length=16)),
        sa.column("name", sa.String(length=255)),
        sa.column("description", sa.Text()),
        sa.column("agent", sa.String(length=64)),
        sa.column("agent_profile_id", sa.String(length=128)),
        sa.column("artifact_kinds_json", sa.JSON()),
        sa.column("dispatch_template", sa.Text()),
    )


def _seed_rows() -> list[dict[str, object]]:
    return [
        {
            "record_id": UUID("00000000-0000-0000-0000-000000000111"),
            "id": "requirement-review",
            "scope": "system",
            "name": "需求优化",
            "description": "Requirement-quality review that checks clarity, reasonableness, type fit, split candidates, and acceptance criteria before implementation.",
            "agent": "codex",
            "agent_profile_id": None,
            "artifact_kinds_json": ["requirement_review_report"],
            "dispatch_template": """You are assigned a requirement-review project todo.
Project path: {{ project_path }}
Todo: {{ title }}

Context:
{{ description }}

Review the requirement before implementation. Classify the requirement type, judge whether it is reasonable and ready, identify missing context, separate evidence from assumptions and recommendations, propose an optimized requirement, and prepare project-todo-ready split cards with suitable todo types. Do not modify the original todo, do not automatically block dispatch, and do not implement code. Produce a structured requirement_review_report artifact as the review output.""",
        }
    ]
