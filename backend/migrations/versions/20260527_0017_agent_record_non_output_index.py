from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "20260527_0017"
down_revision: str | None = "20260527_0016"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        with op.get_context().autocommit_block():
            op.execute(
                "CREATE INDEX CONCURRENTLY IF NOT EXISTS "
                "ix_events_agent_record_non_output_window "
                "ON events (client_id, virtual_window_id, created_at, id) "
                "WHERE kind <> 'terminal_output'"
            )
        return

    op.create_index(
        "ix_events_agent_record_non_output_window",
        "events",
        ["client_id", "virtual_window_id", "created_at", "id"],
        sqlite_where=sa.text("kind <> 'terminal_output'"),
    )


def downgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        with op.get_context().autocommit_block():
            op.execute(
                "DROP INDEX CONCURRENTLY IF EXISTS "
                "ix_events_agent_record_non_output_window"
            )
        return

    op.drop_index("ix_events_agent_record_non_output_window", table_name="events")
