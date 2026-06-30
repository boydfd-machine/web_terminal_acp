from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "20260606_0046"
down_revision: str | None = "20260606_0045"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("project_todos", sa.Column("execution_kind", sa.String(length=16), server_default="ONCE", nullable=False))
    op.add_column(
        "project_todos",
        sa.Column("terminal_policy", sa.String(length=32), server_default="NEW_TERMINAL", nullable=False),
    )
    op.add_column(
        "project_todos",
        sa.Column("trigger_strategy", sa.String(length=16), server_default="MANUAL", nullable=False),
    )
    op.add_column("project_todos", sa.Column("cron_expression", sa.String(length=128), nullable=True))
    op.add_column("project_todos", sa.Column("next_trigger_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("project_todos", sa.Column("last_triggered_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column(
        "project_todos",
        sa.Column("execution_run_count", sa.Integer(), server_default="0", nullable=False),
    )
    op.add_column("project_todos", sa.Column("last_agent_launch_json", sa.JSON(), nullable=True))
    op.add_column(
        "project_todos",
        sa.Column("last_dispatch_mode", sa.String(length=16), server_default="submit", nullable=False),
    )
    op.create_index(
        "ix_project_todos_periodic_due",
        "project_todos",
        ["client_id", "trigger_strategy", "next_trigger_at", "status"],
    )
    op.create_table(
        "project_todo_runs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("project_todo_id", sa.Uuid(), nullable=False),
        sa.Column("client_id", sa.Uuid(), nullable=False),
        sa.Column("project_path", sa.Text(), nullable=False),
        sa.Column("window_id", sa.Uuid(), nullable=True),
        sa.Column("run_number", sa.Integer(), nullable=False),
        sa.Column("trigger_strategy", sa.String(length=16), nullable=False),
        sa.Column("trigger_reason", sa.String(length=64), server_default="manual", nullable=False),
        sa.Column("terminal_policy", sa.String(length=32), nullable=False),
        sa.Column("agent_launch_json", sa.JSON(), nullable=True),
        sa.Column("dispatch_mode", sa.String(length=16), server_default="submit", nullable=False),
        sa.Column("prompt", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=32), server_default="STARTING", nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("dispatched_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["client_id"], ["clients.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["project_todo_id"], ["project_todos.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["window_id"], ["virtual_windows.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("project_todo_id", "run_number", name="uq_project_todo_runs_todo_number"),
    )
    op.create_index("ix_project_todo_runs_todo_created", "project_todo_runs", ["project_todo_id", "created_at", "id"])
    op.create_index("ix_project_todo_runs_client_project", "project_todo_runs", ["client_id", "project_path", "created_at"])
    op.create_index("ix_project_todo_runs_window", "project_todo_runs", ["window_id"])
    op.create_index("ix_project_todo_runs_status", "project_todo_runs", ["status", "updated_at"])


def downgrade() -> None:
    op.drop_index("ix_project_todo_runs_status", table_name="project_todo_runs")
    op.drop_index("ix_project_todo_runs_window", table_name="project_todo_runs")
    op.drop_index("ix_project_todo_runs_client_project", table_name="project_todo_runs")
    op.drop_index("ix_project_todo_runs_todo_created", table_name="project_todo_runs")
    op.drop_table("project_todo_runs")
    op.drop_index("ix_project_todos_periodic_due", table_name="project_todos")
    op.drop_column("project_todos", "last_dispatch_mode")
    op.drop_column("project_todos", "last_agent_launch_json")
    op.drop_column("project_todos", "execution_run_count")
    op.drop_column("project_todos", "last_triggered_at")
    op.drop_column("project_todos", "next_trigger_at")
    op.drop_column("project_todos", "cron_expression")
    op.drop_column("project_todos", "trigger_strategy")
    op.drop_column("project_todos", "terminal_policy")
    op.drop_column("project_todos", "execution_kind")
