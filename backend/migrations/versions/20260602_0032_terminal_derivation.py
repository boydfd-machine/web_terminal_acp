from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "20260602_0032"
down_revision: str | None = "20260602_0031"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("virtual_windows", sa.Column("parent_window_id", sa.Uuid(), nullable=True))
    op.add_column("virtual_windows", sa.Column("root_window_id", sa.Uuid(), nullable=True))
    op.add_column("virtual_windows", sa.Column("derived_mode", sa.String(length=32), nullable=True))
    op.add_column("virtual_windows", sa.Column("derived_context", sa.JSON(), nullable=True))
    if op.get_bind().dialect.name == "sqlite":
        with op.batch_alter_table("virtual_windows") as batch_op:
            batch_op.create_foreign_key(
                "fk_virtual_windows_parent_window_id_virtual_windows",
                "virtual_windows",
                ["parent_window_id"],
                ["id"],
                ondelete="SET NULL",
            )
            batch_op.create_foreign_key(
                "fk_virtual_windows_root_window_id_virtual_windows",
                "virtual_windows",
                ["root_window_id"],
                ["id"],
                ondelete="SET NULL",
            )
    else:
        op.create_foreign_key(
            "fk_virtual_windows_parent_window_id_virtual_windows",
            "virtual_windows",
            "virtual_windows",
            ["parent_window_id"],
            ["id"],
            ondelete="SET NULL",
        )
        op.create_foreign_key(
            "fk_virtual_windows_root_window_id_virtual_windows",
            "virtual_windows",
            "virtual_windows",
            ["root_window_id"],
            ["id"],
            ondelete="SET NULL",
        )
    op.create_index(
        "ix_virtual_windows_client_root_created",
        "virtual_windows",
        ["client_id", "root_window_id", "created_at", "id"],
    )
    op.create_index(
        "ix_virtual_windows_parent_window",
        "virtual_windows",
        ["parent_window_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_virtual_windows_parent_window", table_name="virtual_windows")
    op.drop_index("ix_virtual_windows_client_root_created", table_name="virtual_windows")
    if op.get_bind().dialect.name == "sqlite":
        with op.batch_alter_table("virtual_windows") as batch_op:
            batch_op.drop_constraint(
                "fk_virtual_windows_root_window_id_virtual_windows",
                type_="foreignkey",
            )
            batch_op.drop_constraint(
                "fk_virtual_windows_parent_window_id_virtual_windows",
                type_="foreignkey",
            )
    else:
        op.drop_constraint(
            "fk_virtual_windows_root_window_id_virtual_windows",
            "virtual_windows",
            type_="foreignkey",
        )
        op.drop_constraint(
            "fk_virtual_windows_parent_window_id_virtual_windows",
            "virtual_windows",
            type_="foreignkey",
        )
    op.drop_column("virtual_windows", "derived_context")
    op.drop_column("virtual_windows", "derived_mode")
    op.drop_column("virtual_windows", "root_window_id")
    op.drop_column("virtual_windows", "parent_window_id")
