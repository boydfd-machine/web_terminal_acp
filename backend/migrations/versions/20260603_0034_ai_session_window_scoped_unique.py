from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "20260603_0034"
down_revision: str | None = "20260602_0033"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("ai_sessions") as batch_op:
        batch_op.drop_constraint(
            "uq_ai_sessions_client_id_provider_source_id",
            type_="unique",
        )
        batch_op.create_unique_constraint(
            "uq_ai_sessions_client_provider_source_window",
            ["client_id", "provider", "source_id", "virtual_window_id"],
        )


def downgrade() -> None:
    with op.batch_alter_table("ai_sessions") as batch_op:
        batch_op.drop_constraint(
            "uq_ai_sessions_client_provider_source_window",
            type_="unique",
        )
        batch_op.create_unique_constraint(
            "uq_ai_sessions_client_id_provider_source_id",
            ["client_id", "provider", "source_id"],
        )
