from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "20260612_0064"
down_revision: str | None = "20260609_0063"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if "users" not in inspector.get_table_names():
        op.create_table(
            "users",
            sa.Column("id", sa.String(length=255), nullable=False),
            sa.Column("auth_provider", sa.String(length=64), nullable=False),
            sa.Column("subject", sa.String(length=255), nullable=False),
            sa.Column("username", sa.String(length=255), nullable=True),
            sa.Column("email", sa.String(length=320), nullable=True),
            sa.Column("display_name", sa.String(length=255), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("now()") if _is_postgresql() else sa.text("CURRENT_TIMESTAMP"),
                nullable=False,
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("now()") if _is_postgresql() else sa.text("CURRENT_TIMESTAMP"),
                nullable=False,
            ),
            sa.PrimaryKeyConstraint("id"),
        )
    _create_index_if_missing(
        "ix_users_auth_provider_subject",
        "users",
        ["auth_provider", "subject"],
        unique=True,
    )
    _add_owner_column_if_missing("clients")
    _add_owner_column_if_missing("client_registration_keys")
    _create_index_if_missing("ix_clients_owner_user_id", "clients", ["owner_user_id"])


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if "ix_clients_owner_user_id" in {index["name"] for index in inspector.get_indexes("clients")}:
        op.drop_index("ix_clients_owner_user_id", table_name="clients")
    for table_name in ("client_registration_keys", "clients"):
        columns = {column["name"] for column in inspector.get_columns(table_name)}
        if "owner_user_id" in columns:
            op.drop_column(table_name, "owner_user_id")
    if "users" in inspector.get_table_names():
        op.drop_index("ix_users_auth_provider_subject", table_name="users")
        op.drop_table("users")


def _add_owner_column_if_missing(table_name: str) -> None:
    inspector = sa.inspect(op.get_bind())
    columns = {column["name"] for column in inspector.get_columns(table_name)}
    if "owner_user_id" in columns:
        return
    op.add_column(table_name, sa.Column("owner_user_id", sa.String(length=255), nullable=True))
    if _is_postgresql():
        op.create_foreign_key(
            f"fk_{table_name}_owner_user_id_users",
            table_name,
            "users",
            ["owner_user_id"],
            ["id"],
            ondelete="SET NULL",
        )


def _create_index_if_missing(
    name: str,
    table_name: str,
    columns: list[str],
    *,
    unique: bool = False,
) -> None:
    indexes = {index["name"] for index in sa.inspect(op.get_bind()).get_indexes(table_name)}
    if name not in indexes:
        op.create_index(name, table_name, columns, unique=unique)


def _is_postgresql() -> bool:
    return op.get_bind().dialect.name == "postgresql"
