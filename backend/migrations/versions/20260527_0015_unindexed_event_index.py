from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "20260527_0015"
down_revision: str | None = "20260526_0014"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _index_exists(name: str, table: str) -> bool:
    return name in {
        index["name"] for index in sa.inspect(op.get_bind()).get_indexes(table)
    }


def upgrade() -> None:
    index_name = "ix_events_source_unindexed_created"
    if _index_exists(index_name, "events"):
        return

    if op.get_bind().dialect.name == "postgresql":
        op.execute(
            sa.text(
                "CREATE INDEX IF NOT EXISTS ix_events_source_unindexed_created "
                "ON events (source_type, created_at, id) "
                "WHERE indexed_at IS NULL"
            )
        )
        return

    op.create_index(
        index_name,
        "events",
        ["source_type", "created_at", "id"],
        postgresql_where=sa.text("indexed_at IS NULL"),
        sqlite_where=sa.text("indexed_at IS NULL"),
    )


def downgrade() -> None:
    index_name = "ix_events_source_unindexed_created"
    if _index_exists(index_name, "events"):
        op.drop_index(index_name, table_name="events")
