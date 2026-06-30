from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "20260612_0067"
down_revision: str | None = "20260612_0066"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    _add_owner_user_id_column_if_missing()
    if _is_postgresql():
        _create_owner_user_id_fk_if_missing()

    _drop_index_if_exists("project_todo_types", "uq_project_todo_types_system_id")
    _create_partial_index_if_missing(
        "uq_project_todo_types_global_system_id",
        "project_todo_types",
        ["id"],
        "scope = 'system' AND owner_user_id IS NULL",
    )
    _create_partial_index_if_missing(
        "uq_project_todo_types_user_system_id",
        "project_todo_types",
        ["owner_user_id", "id"],
        "scope = 'system' AND owner_user_id IS NOT NULL",
    )


def downgrade() -> None:
    _drop_index_if_exists("project_todo_types", "uq_project_todo_types_user_system_id")
    _drop_index_if_exists("project_todo_types", "uq_project_todo_types_global_system_id")
    op.create_index(
        "uq_project_todo_types_system_id",
        "project_todo_types",
        ["id"],
        unique=True,
        sqlite_where=sa.text("scope = 'system'"),
        postgresql_where=sa.text("scope = 'system'"),
    )
    if _is_postgresql():
        op.drop_constraint(
            "fk_project_todo_types_owner_user_id_users",
            "project_todo_types",
            type_="foreignkey",
        )
    op.drop_column("project_todo_types", "owner_user_id")


def _is_postgresql() -> bool:
    return op.get_bind().dialect.name == "postgresql"


def _columns(table: str) -> set[str]:
    return {column["name"] for column in sa.inspect(op.get_bind()).get_columns(table)}


def _indexes(table: str) -> set[str]:
    return {index["name"] for index in sa.inspect(op.get_bind()).get_indexes(table)}


def _foreign_keys(table: str) -> set[str]:
    return {constraint["name"] for constraint in sa.inspect(op.get_bind()).get_foreign_keys(table)}


def _add_owner_user_id_column_if_missing() -> None:
    if "owner_user_id" in _columns("project_todo_types"):
        return
    op.add_column(
        "project_todo_types",
        sa.Column("owner_user_id", sa.String(length=255), nullable=True),
    )


def _create_owner_user_id_fk_if_missing() -> None:
    if "fk_project_todo_types_owner_user_id_users" in _foreign_keys("project_todo_types"):
        return
    op.create_foreign_key(
        "fk_project_todo_types_owner_user_id_users",
        "project_todo_types",
        "users",
        ["owner_user_id"],
        ["id"],
        ondelete="CASCADE",
    )


def _drop_index_if_exists(table: str, name: str) -> None:
    if name in _indexes(table):
        op.drop_index(name, table_name=table)


def _create_partial_index_if_missing(
    name: str, table: str, columns: list[str], condition: str
) -> None:
    if name in _indexes(table):
        return
    op.create_index(
        name,
        table,
        columns,
        unique=True,
        sqlite_where=sa.text(condition),
        postgresql_where=sa.text(condition),
    )
