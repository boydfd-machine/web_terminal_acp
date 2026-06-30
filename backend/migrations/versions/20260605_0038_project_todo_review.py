from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "20260605_0038"
down_revision: str | None = "20260605_0037"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "project_review_configs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("client_id", sa.Uuid(), nullable=False),
        sa.Column("project_path", sa.Text(), nullable=False),
        sa.Column("pr_provider", sa.String(length=32), server_default="LOCAL_CARD", nullable=False),
        sa.Column("pr_provider_config_json", sa.JSON(), nullable=True),
        sa.Column("review_agent", sa.String(length=64), nullable=True),
        sa.Column("review_agent_command", sa.String(length=4096), nullable=True),
        sa.Column("review_agent_profile_id", sa.String(length=128), nullable=True),
        sa.Column("auto_create_review_target", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("auto_dispatch_review", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("merge_policy", sa.String(length=32), server_default="MANUAL", nullable=False),
        sa.Column("required_artifact_kinds_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["client_id"], ["clients.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("client_id", "project_path", name="uq_project_review_configs_client_path"),
    )
    op.create_index(
        "ix_project_review_configs_client_project",
        "project_review_configs",
        ["client_id", "project_path"],
    )
    op.add_column(
        "project_todos",
        sa.Column("review_strategy", sa.String(length=32), server_default="LOCAL_CARD", nullable=False),
    )
    op.add_column(
        "project_todos",
        sa.Column("review_status", sa.String(length=32), server_default="NOT_REQUESTED", nullable=False),
    )
    op.add_column("project_todos", sa.Column("review_agent", sa.String(length=64), nullable=True))
    op.add_column("project_todos", sa.Column("review_agent_profile_id", sa.String(length=128), nullable=True))
    op.add_column("project_todos", sa.Column("review_window_id", sa.Uuid(), nullable=True))
    op.add_column("project_todos", sa.Column("review_prompt", sa.Text(), nullable=True))
    op.add_column("project_todos", sa.Column("review_dispatched_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("project_todos", sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column(
        "project_todos",
        sa.Column("needs_human_review", sa.Boolean(), server_default=sa.false(), nullable=False),
    )
    op.add_column("project_todos", sa.Column("review_notes", sa.Text(), nullable=True))
    op.add_column("project_todos", sa.Column("implementation_worktree_json", sa.JSON(), nullable=True))
    if op.get_bind().dialect.name == "sqlite":
        with op.batch_alter_table("project_todos") as batch_op:
            batch_op.create_foreign_key(
                "fk_project_todos_review_window_id_virtual_windows",
                "virtual_windows",
                ["review_window_id"],
                ["id"],
                ondelete="SET NULL",
            )
    else:
        op.create_foreign_key(
            "fk_project_todos_review_window_id_virtual_windows",
            "project_todos",
            "virtual_windows",
            ["review_window_id"],
            ["id"],
            ondelete="SET NULL",
        )
    op.create_index("ix_project_todos_review_window", "project_todos", ["review_window_id"])
    op.create_index(
        "ix_project_todos_review_status",
        "project_todos",
        ["client_id", "project_path", "review_status", "updated_at"],
    )
    op.create_table(
        "project_todo_artifacts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("project_todo_id", sa.Uuid(), nullable=False),
        sa.Column("terminal_artifact_id", sa.Uuid(), nullable=False),
        sa.Column("purpose", sa.String(length=32), server_default="review", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["project_todo_id"], ["project_todos.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["terminal_artifact_id"], ["terminal_artifacts.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("project_todo_id", "terminal_artifact_id", name="uq_project_todo_artifacts_pair"),
    )
    op.create_index("ix_project_todo_artifacts_todo", "project_todo_artifacts", ["project_todo_id"])
    op.create_index("ix_project_todo_artifacts_artifact", "project_todo_artifacts", ["terminal_artifact_id"])


def downgrade() -> None:
    op.drop_index("ix_project_todo_artifacts_artifact", table_name="project_todo_artifacts")
    op.drop_index("ix_project_todo_artifacts_todo", table_name="project_todo_artifacts")
    op.drop_table("project_todo_artifacts")
    op.drop_index("ix_project_todos_review_status", table_name="project_todos")
    op.drop_index("ix_project_todos_review_window", table_name="project_todos")
    if op.get_bind().dialect.name == "sqlite":
        with op.batch_alter_table("project_todos") as batch_op:
            batch_op.drop_constraint(
                "fk_project_todos_review_window_id_virtual_windows",
                type_="foreignkey",
            )
    else:
        op.drop_constraint(
            "fk_project_todos_review_window_id_virtual_windows",
            "project_todos",
            type_="foreignkey",
        )
    op.drop_column("project_todos", "implementation_worktree_json")
    op.drop_column("project_todos", "review_notes")
    op.drop_column("project_todos", "needs_human_review")
    op.drop_column("project_todos", "reviewed_at")
    op.drop_column("project_todos", "review_dispatched_at")
    op.drop_column("project_todos", "review_prompt")
    op.drop_column("project_todos", "review_window_id")
    op.drop_column("project_todos", "review_agent_profile_id")
    op.drop_column("project_todos", "review_agent")
    op.drop_column("project_todos", "review_status")
    op.drop_column("project_todos", "review_strategy")
    op.drop_index("ix_project_review_configs_client_project", table_name="project_review_configs")
    op.drop_table("project_review_configs")
