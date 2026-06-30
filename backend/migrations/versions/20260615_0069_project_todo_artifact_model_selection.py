"""project todo artifact model selection

Revision ID: 20260615_0069
Revises: 20260613_0068
Create Date: 2026-06-15 00:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260615_0069"
down_revision = "20260613_0068"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "project_todos",
        sa.Column("artifact_model_selection_json", sa.JSON(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("project_todos", "artifact_model_selection_json")
