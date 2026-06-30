from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    cast,
    false,
    func,
    literal_column,
)
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column

from app.model_base import Base
from app.models.common import ProjectTodoStatus, enum_values


class ProjectTodoType(Base):
    __tablename__ = "project_todo_types"
    __table_args__ = (
        Index("ix_project_todo_types_scope", "scope", "id"),
        Index("ix_project_todo_types_project", "client_id", "project_path", "id"),
    )

    record_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    id: Mapped[str] = mapped_column(String(64), nullable=False)
    scope: Mapped[str] = mapped_column(String(16), nullable=False, default="system", server_default="system")
    owner_user_id: Mapped[str | None] = mapped_column(
        String(255),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=True,
    )
    client_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("clients.id", ondelete="CASCADE"),
        nullable=True,
    )
    project_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    agent: Mapped[str | None] = mapped_column(String(64), nullable=True)
    agent_profile_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    artifact_kinds_json: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    input_artifact_ids_json: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    dispatch_template: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


Index(
    "uq_project_todo_types_global_system_id",
    ProjectTodoType.id,
    unique=True,
    sqlite_where=(ProjectTodoType.scope == "system") & ProjectTodoType.owner_user_id.is_(None),
    postgresql_where=(ProjectTodoType.scope == "system") & ProjectTodoType.owner_user_id.is_(None),
)
Index(
    "uq_project_todo_types_user_system_id",
    ProjectTodoType.owner_user_id,
    ProjectTodoType.id,
    unique=True,
    sqlite_where=(ProjectTodoType.scope == "system") & ProjectTodoType.owner_user_id.is_not(None),
    postgresql_where=(ProjectTodoType.scope == "system") & ProjectTodoType.owner_user_id.is_not(None),
)
Index(
    "uq_project_todo_types_project_id",
    ProjectTodoType.client_id,
    ProjectTodoType.project_path,
    ProjectTodoType.id,
    unique=True,
    sqlite_where=ProjectTodoType.scope == "project",
    postgresql_where=ProjectTodoType.scope == "project",
)


class ProjectTodo(Base):
    __tablename__ = "project_todos"
    __table_args__ = (
        Index("ix_project_todos_client_project_status", "client_id", "project_path", "status", "updated_at"),
        Index("ix_project_todos_client_project_updated", "client_id", "project_path", "updated_at", "id"),
        Index("ix_project_todos_parent_todo", "parent_todo_id"),
        Index("ix_project_todos_assigned_window", "assigned_window_id"),
        Index("ix_project_todos_review_window", "review_window_id"),
        Index("ix_project_todos_review_status", "client_id", "project_path", "review_status", "updated_at"),
        Index(
            "ix_project_todos_periodic_due",
            "client_id",
            "trigger_strategy",
            "schedule_enabled",
            "next_trigger_at",
            "status",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    client_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("clients.id", ondelete="CASCADE"),
        nullable=False,
    )
    project_path: Mapped[str] = mapped_column(Text, nullable=False)
    parent_todo_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("project_todos.id", ondelete="SET NULL"), nullable=True
    )
    todo_type_id: Mapped[str] = mapped_column(String(64), nullable=False, default="default", server_default="default")
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[ProjectTodoStatus] = mapped_column(
        SAEnum(
            ProjectTodoStatus,
            name="projecttodostatus",
            values_callable=enum_values,
            create_constraint=True,
            validate_strings=True,
        ),
        nullable=False,
        default=ProjectTodoStatus.todo,
        server_default=ProjectTodoStatus.todo.value,
    )
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    assigned_window_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("virtual_windows.id", ondelete="SET NULL"), nullable=True
    )
    assigned_agent: Mapped[str | None] = mapped_column(String(64), nullable=True)
    agent_profile_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    dispatch_prompt: Mapped[str | None] = mapped_column(Text, nullable=True)
    dispatch_output_language: Mapped[str | None] = mapped_column(String(64), nullable=True)
    dispatch_stage: Mapped[str | None] = mapped_column(String(32), nullable=True)
    dispatch_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    blocked_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    dispatched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    awaiting_review_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    review_strategy: Mapped[str] = mapped_column(
        String(32), nullable=False, default="LOCAL_CARD", server_default="LOCAL_CARD"
    )
    review_status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="NOT_REQUESTED", server_default="NOT_REQUESTED"
    )
    review_agent: Mapped[str | None] = mapped_column(String(64), nullable=True)
    review_agent_profile_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    review_window_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("virtual_windows.id", ondelete="SET NULL"), nullable=True
    )
    review_prompt: Mapped[str | None] = mapped_column(Text, nullable=True)
    review_dispatched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    review_unseen: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default=false())
    needs_human_review: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default=false())
    review_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    implementation_worktree_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    execution_kind: Mapped[str] = mapped_column(String(16), nullable=False, default="ONCE", server_default="ONCE")
    terminal_policy: Mapped[str] = mapped_column(
        String(32), nullable=False, default="NEW_TERMINAL", server_default="NEW_TERMINAL"
    )
    trigger_strategy: Mapped[str] = mapped_column(String(16), nullable=False, default="MANUAL", server_default="MANUAL")
    cron_expression: Mapped[str | None] = mapped_column(String(128), nullable=True)
    schedule_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default=false())
    next_trigger_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_triggered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    execution_run_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    last_agent_launch_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    last_dispatch_mode: Mapped[str] = mapped_column(String(16), nullable=False, default="submit", server_default="submit")
    artifact_kinds_json: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    input_artifact_ids_json: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    artifact_model_selection_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


Index(
    "ix_project_todos_artifact_candidates",
    ProjectTodo.client_id,
    ProjectTodo.project_path,
    ProjectTodo.sort_order,
    ProjectTodo.updated_at,
    ProjectTodo.id,
    sqlite_where=(
        ProjectTodo.artifact_kinds_json.is_not(None)
        & ProjectTodo.assigned_window_id.is_not(None)
        & ProjectTodo.status.in_((ProjectTodoStatus.awaiting_review, ProjectTodoStatus.done))
    ),
    postgresql_where=(
        ProjectTodo.artifact_kinds_json.is_not(None)
        & ProjectTodo.assigned_window_id.is_not(None)
        & ProjectTodo.status.in_((ProjectTodoStatus.awaiting_review, ProjectTodoStatus.done))
    ),
)

Index(
    "ix_project_todos_worktree_attention",
    ProjectTodo.updated_at.desc(),
    ProjectTodo.id.desc(),
    ProjectTodo.client_id,
    ProjectTodo.assigned_window_id,
    sqlite_where=(
        ProjectTodo.assigned_window_id.is_not(None)
        & ProjectTodo.implementation_worktree_json.is_not(None)
        & ProjectTodo.status.in_((ProjectTodoStatus.awaiting_review, ProjectTodoStatus.done))
        & (
            cast(
                ProjectTodo.implementation_worktree_json.op("->>")(
                    literal_column("'merge_attention_required'")
                ),
                Boolean,
            ).is_(True)
            | ProjectTodo.implementation_worktree_json.op("->>")(
                literal_column("'merge_status'")
            ).in_((literal_column("'unmerged'"), literal_column("'conflict'")))
            | cast(
                ProjectTodo.implementation_worktree_json.op("->>")(
                    literal_column("'merged_to_main'")
                ),
                Boolean,
            ).is_(False)
        )
    ),
    postgresql_where=(
        ProjectTodo.assigned_window_id.is_not(None)
        & ProjectTodo.implementation_worktree_json.is_not(None)
        & ProjectTodo.status.in_((ProjectTodoStatus.awaiting_review, ProjectTodoStatus.done))
        & (
            cast(
                ProjectTodo.implementation_worktree_json.op("->>")(
                    literal_column("'merge_attention_required'")
                ),
                Boolean,
            ).is_(True)
            | ProjectTodo.implementation_worktree_json.op("->>")(
                literal_column("'merge_status'")
            ).in_((literal_column("'unmerged'"), literal_column("'conflict'")))
            | cast(
                ProjectTodo.implementation_worktree_json.op("->>")(
                    literal_column("'merged_to_main'")
                ),
                Boolean,
            ).is_(False)
        )
    ),
)


class ProjectTodoArtifact(Base):
    __tablename__ = "project_todo_artifacts"
    __table_args__ = (
        UniqueConstraint("project_todo_id", "terminal_artifact_id", name="uq_project_todo_artifacts_pair"),
        Index("ix_project_todo_artifacts_todo", "project_todo_id"),
        Index("ix_project_todo_artifacts_artifact", "terminal_artifact_id"),
        Index("ix_project_todo_artifacts_review_run", "review_run_id"),
        Index("ix_project_todo_artifacts_created_by_window", "created_by_window_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_todo_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("project_todos.id", ondelete="CASCADE"), nullable=False
    )
    terminal_artifact_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("terminal_artifacts.id", ondelete="CASCADE"), nullable=False
    )
    review_run_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("project_todo_review_runs.id", ondelete="SET NULL"), nullable=True
    )
    created_by_window_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("virtual_windows.id", ondelete="SET NULL"), nullable=True
    )
    purpose: Mapped[str] = mapped_column(String(32), nullable=False, default="review", server_default="review")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class ProjectTodoAttachment(Base):
    __tablename__ = "project_todo_attachments"
    __table_args__ = (
        UniqueConstraint("object_key", name="uq_project_todo_attachments_object_key"),
        Index("ix_project_todo_attachments_todo", "project_todo_id", "created_at", "id"),
        Index("ix_project_todo_attachments_client_project", "client_id", "project_path", "created_at"),
        Index("ix_project_todo_attachments_status", "status", "updated_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_todo_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("project_todos.id", ondelete="CASCADE"), nullable=False
    )
    client_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("clients.id", ondelete="CASCADE"), nullable=False
    )
    project_path: Mapped[str] = mapped_column(Text, nullable=False)
    object_key: Mapped[str] = mapped_column(Text, nullable=False)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    content_type: Mapped[str] = mapped_column(String(128), nullable=False)
    size_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="pending", server_default="pending")
    uploaded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class ProjectTodoRun(Base):
    __tablename__ = "project_todo_runs"
    __table_args__ = (
        UniqueConstraint("project_todo_id", "run_number", name="uq_project_todo_runs_todo_number"),
        Index("ix_project_todo_runs_todo_created", "project_todo_id", "created_at", "id"),
        Index("ix_project_todo_runs_client_project", "client_id", "project_path", "created_at"),
        Index("ix_project_todo_runs_window", "window_id"),
        Index("ix_project_todo_runs_status", "status", "updated_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_todo_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("project_todos.id", ondelete="CASCADE"), nullable=False
    )
    client_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("clients.id", ondelete="CASCADE"), nullable=False
    )
    project_path: Mapped[str] = mapped_column(Text, nullable=False)
    window_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("virtual_windows.id", ondelete="SET NULL"), nullable=True
    )
    run_number: Mapped[int] = mapped_column(Integer, nullable=False)
    trigger_strategy: Mapped[str] = mapped_column(String(16), nullable=False)
    trigger_reason: Mapped[str] = mapped_column(String(64), nullable=False, default="manual", server_default="manual")
    terminal_policy: Mapped[str] = mapped_column(String(32), nullable=False)
    agent_launch_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    dispatch_mode: Mapped[str] = mapped_column(String(16), nullable=False, default="submit", server_default="submit")
    prompt: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="STARTING", server_default="STARTING")
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    dispatched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
