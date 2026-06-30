from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "20260609_0061"
down_revision: str | None = "20260608_0060"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

INDEX_NAME = "ix_events_client_agent_message_recent"
INDEX_PREDICATE = (
    "((kind IN ('user_message', 'assistant_message')) "
    "OR (kind = 'system_message' AND source_type = 'agent_tool_record') "
    "OR (kind IN ('response_item', 'event_msg')))"
)


def upgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        with op.get_context().autocommit_block():
            op.execute(
                "CREATE INDEX CONCURRENTLY IF NOT EXISTS "
                f"{INDEX_NAME} "
                "ON events (client_id, created_at DESC, id DESC) "
                f"WHERE {INDEX_PREDICATE}"
            )
        return

    op.create_index(
        INDEX_NAME,
        "events",
        ["client_id", sa.text("created_at DESC"), sa.text("id DESC")],
        sqlite_where=sa.text(INDEX_PREDICATE),
    )


def downgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        with op.get_context().autocommit_block():
            op.execute(f"DROP INDEX CONCURRENTLY IF EXISTS {INDEX_NAME}")
        return

    op.drop_index(INDEX_NAME, table_name="events")
