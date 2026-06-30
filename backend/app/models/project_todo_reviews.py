from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Index, JSON, String, Text, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.model_base import Base


class ProjectTodoWorkSnapshot(Base):
    __tablename__ = "project_todo_work_snapshots"
    __table_args__ = (
        Index("ix_project_todo_work_snapshots_todo_captured", "project_todo_id", "captured_at", "id"),
        Index("ix_project_todo_work_snapshots_client_project", "client_id", "project_path", "captured_at"),
        Index("ix_project_todo_work_snapshots_window", "window_id"),
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
    role: Mapped[str] = mapped_column(String(32), nullable=False, default="implementation", server_default="implementation")
    branch_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    base_ref: Mapped[str | None] = mapped_column(Text, nullable=True)
    base_sha: Mapped[str | None] = mapped_column(String(128), nullable=True)
    head_sha: Mapped[str | None] = mapped_column(String(128), nullable=True)
    commit_shas_json: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    diff_stat_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    changed_files_json: Mapped[list[dict[str, Any]] | None] = mapped_column(JSON, nullable=True)
    dirty_state: Mapped[str] = mapped_column(String(32), nullable=False, default="unknown", server_default="unknown")
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class ProjectTodoReviewTarget(Base):
    __tablename__ = "project_todo_review_targets"
    __table_args__ = (
        Index("ix_project_todo_review_targets_todo_updated", "project_todo_id", "updated_at", "id"),
        Index("ix_project_todo_review_targets_snapshot", "work_snapshot_id"),
        Index("ix_project_todo_review_targets_provider_external", "provider", "external_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_todo_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("project_todos.id", ondelete="CASCADE"), nullable=False
    )
    work_snapshot_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("project_todo_work_snapshots.id", ondelete="CASCADE"), nullable=False
    )
    provider: Mapped[str] = mapped_column(String(32), nullable=False, default="LOCAL_CARD", server_default="LOCAL_CARD")
    external_id: Mapped[str] = mapped_column(String(128), nullable=False, default=lambda: uuid.uuid4().hex)
    url: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="OPEN", server_default="OPEN")
    base_sha: Mapped[str | None] = mapped_column(String(128), nullable=True)
    head_sha: Mapped[str | None] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class ProjectTodoReviewRun(Base):
    __tablename__ = "project_todo_review_runs"
    __table_args__ = (
        Index("ix_project_todo_review_runs_todo_created", "project_todo_id", "created_at", "id"),
        Index("ix_project_todo_review_runs_target", "review_target_id"),
        Index("ix_project_todo_review_runs_window", "review_window_id"),
        Index("ix_project_todo_review_runs_status", "status", "updated_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_todo_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("project_todos.id", ondelete="CASCADE"), nullable=False
    )
    review_target_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("project_todo_review_targets.id", ondelete="CASCADE"), nullable=False
    )
    review_window_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("virtual_windows.id", ondelete="SET NULL"), nullable=True
    )
    agent_client: Mapped[str | None] = mapped_column(String(64), nullable=True)
    agent_profile_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="QUEUED", server_default="QUEUED")
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    findings_json: Mapped[list[dict[str, Any]] | None] = mapped_column(JSON, nullable=True)
    test_commands_json: Mapped[list[dict[str, Any]] | None] = mapped_column(JSON, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
