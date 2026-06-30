from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "20260605_0039"
down_revision: str | None = "20260605_0038"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "project_todo_work_snapshots",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("project_todo_id", sa.Uuid(), nullable=False),
        sa.Column("client_id", sa.Uuid(), nullable=False),
        sa.Column("project_path", sa.Text(), nullable=False),
        sa.Column("window_id", sa.Uuid(), nullable=True),
        sa.Column("role", sa.String(length=32), server_default="implementation", nullable=False),
        sa.Column("branch_name", sa.Text(), nullable=True),
        sa.Column("base_ref", sa.Text(), nullable=True),
        sa.Column("base_sha", sa.String(length=128), nullable=True),
        sa.Column("head_sha", sa.String(length=128), nullable=True),
        sa.Column("commit_shas_json", sa.JSON(), nullable=True),
        sa.Column("diff_stat_json", sa.JSON(), nullable=True),
        sa.Column("changed_files_json", sa.JSON(), nullable=True),
        sa.Column("dirty_state", sa.String(length=32), server_default="unknown", nullable=False),
        sa.Column("captured_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["client_id"], ["clients.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["project_todo_id"], ["project_todos.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["window_id"], ["virtual_windows.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_project_todo_work_snapshots_client_project", "project_todo_work_snapshots", ["client_id", "project_path", "captured_at"])
    op.create_index("ix_project_todo_work_snapshots_todo_captured", "project_todo_work_snapshots", ["project_todo_id", "captured_at", "id"])
    op.create_index("ix_project_todo_work_snapshots_window", "project_todo_work_snapshots", ["window_id"])

    op.create_table(
        "project_todo_review_targets",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("project_todo_id", sa.Uuid(), nullable=False),
        sa.Column("work_snapshot_id", sa.Uuid(), nullable=False),
        sa.Column("provider", sa.String(length=32), server_default="LOCAL_CARD", nullable=False),
        sa.Column("external_id", sa.String(length=128), nullable=False),
        sa.Column("url", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=32), server_default="OPEN", nullable=False),
        sa.Column("base_sha", sa.String(length=128), nullable=True),
        sa.Column("head_sha", sa.String(length=128), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["project_todo_id"], ["project_todos.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["work_snapshot_id"], ["project_todo_work_snapshots.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_project_todo_review_targets_provider_external", "project_todo_review_targets", ["provider", "external_id"])
    op.create_index("ix_project_todo_review_targets_snapshot", "project_todo_review_targets", ["work_snapshot_id"])
    op.create_index("ix_project_todo_review_targets_todo_updated", "project_todo_review_targets", ["project_todo_id", "updated_at", "id"])

    op.create_table(
        "project_todo_review_runs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("project_todo_id", sa.Uuid(), nullable=False),
        sa.Column("review_target_id", sa.Uuid(), nullable=False),
        sa.Column("review_window_id", sa.Uuid(), nullable=True),
        sa.Column("agent_client", sa.String(length=64), nullable=True),
        sa.Column("agent_profile_id", sa.String(length=128), nullable=True),
        sa.Column("status", sa.String(length=32), server_default="QUEUED", nullable=False),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("findings_json", sa.JSON(), nullable=True),
        sa.Column("test_commands_json", sa.JSON(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["project_todo_id"], ["project_todos.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["review_target_id"], ["project_todo_review_targets.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["review_window_id"], ["virtual_windows.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_project_todo_review_runs_status", "project_todo_review_runs", ["status", "updated_at"])
    op.create_index("ix_project_todo_review_runs_target", "project_todo_review_runs", ["review_target_id"])
    op.create_index("ix_project_todo_review_runs_todo_created", "project_todo_review_runs", ["project_todo_id", "created_at", "id"])
    op.create_index("ix_project_todo_review_runs_window", "project_todo_review_runs", ["review_window_id"])

    op.add_column("project_todo_artifacts", sa.Column("review_run_id", sa.Uuid(), nullable=True))
    op.add_column("project_todo_artifacts", sa.Column("created_by_window_id", sa.Uuid(), nullable=True))
    op.create_index("ix_project_todo_artifacts_review_run", "project_todo_artifacts", ["review_run_id"])
    op.create_index("ix_project_todo_artifacts_created_by_window", "project_todo_artifacts", ["created_by_window_id"])
    if op.get_bind().dialect.name == "sqlite":
        with op.batch_alter_table("project_todo_artifacts") as batch_op:
            batch_op.create_foreign_key(
                "fk_project_todo_artifacts_review_run_id",
                "project_todo_review_runs",
                ["review_run_id"],
                ["id"],
                ondelete="SET NULL",
            )
            batch_op.create_foreign_key(
                "fk_project_todo_artifacts_created_by_window_id",
                "virtual_windows",
                ["created_by_window_id"],
                ["id"],
                ondelete="SET NULL",
            )
    else:
        op.create_foreign_key("fk_project_todo_artifacts_review_run_id", "project_todo_artifacts", "project_todo_review_runs", ["review_run_id"], ["id"], ondelete="SET NULL")
        op.create_foreign_key("fk_project_todo_artifacts_created_by_window_id", "project_todo_artifacts", "virtual_windows", ["created_by_window_id"], ["id"], ondelete="SET NULL")


def downgrade() -> None:
    if op.get_bind().dialect.name == "sqlite":
        with op.batch_alter_table("project_todo_artifacts") as batch_op:
            batch_op.drop_constraint("fk_project_todo_artifacts_created_by_window_id", type_="foreignkey")
            batch_op.drop_constraint("fk_project_todo_artifacts_review_run_id", type_="foreignkey")
    else:
        op.drop_constraint("fk_project_todo_artifacts_created_by_window_id", "project_todo_artifacts", type_="foreignkey")
        op.drop_constraint("fk_project_todo_artifacts_review_run_id", "project_todo_artifacts", type_="foreignkey")
    op.drop_index("ix_project_todo_artifacts_created_by_window", table_name="project_todo_artifacts")
    op.drop_index("ix_project_todo_artifacts_review_run", table_name="project_todo_artifacts")
    op.drop_column("project_todo_artifacts", "created_by_window_id")
    op.drop_column("project_todo_artifacts", "review_run_id")

    op.drop_index("ix_project_todo_review_runs_window", table_name="project_todo_review_runs")
    op.drop_index("ix_project_todo_review_runs_todo_created", table_name="project_todo_review_runs")
    op.drop_index("ix_project_todo_review_runs_target", table_name="project_todo_review_runs")
    op.drop_index("ix_project_todo_review_runs_status", table_name="project_todo_review_runs")
    op.drop_table("project_todo_review_runs")

    op.drop_index("ix_project_todo_review_targets_todo_updated", table_name="project_todo_review_targets")
    op.drop_index("ix_project_todo_review_targets_snapshot", table_name="project_todo_review_targets")
    op.drop_index("ix_project_todo_review_targets_provider_external", table_name="project_todo_review_targets")
    op.drop_table("project_todo_review_targets")

    op.drop_index("ix_project_todo_work_snapshots_window", table_name="project_todo_work_snapshots")
    op.drop_index("ix_project_todo_work_snapshots_todo_captured", table_name="project_todo_work_snapshots")
    op.drop_index("ix_project_todo_work_snapshots_client_project", table_name="project_todo_work_snapshots")
    op.drop_table("project_todo_work_snapshots")
