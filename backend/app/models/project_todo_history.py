from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Index, Integer, JSON, String, Text, UniqueConstraint, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.model_base import Base


class ProjectTodoVersion(Base):
    __tablename__ = "project_todo_versions"
    __table_args__ = (
        UniqueConstraint("project_todo_id", "version_number", name="uq_project_todo_versions_todo_number"),
        Index("ix_project_todo_versions_todo_created", "project_todo_id", "created_at", "id"),
        Index("ix_project_todo_versions_client_project", "client_id", "project_path", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_todo_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("project_todos.id", ondelete="CASCADE"), nullable=False
    )
    client_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("clients.id", ondelete="CASCADE"), nullable=False
    )
    project_path: Mapped[str] = mapped_column(Text, nullable=False)
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    actor_type: Mapped[str] = mapped_column(String(16), nullable=False)
    actor_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    actor_display: Mapped[str | None] = mapped_column(String(255), nullable=True)
    source_window_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("virtual_windows.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class ProjectTodoAuditLog(Base):
    __tablename__ = "project_todo_audit_logs"
    __table_args__ = (
        Index("ix_project_todo_audit_logs_todo_created", "project_todo_id", "created_at", "id"),
        Index("ix_project_todo_audit_logs_client_project", "client_id", "project_path", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_todo_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("project_todos.id", ondelete="CASCADE"), nullable=False
    )
    client_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("clients.id", ondelete="CASCADE"), nullable=False
    )
    project_path: Mapped[str] = mapped_column(Text, nullable=False)
    action: Mapped[str] = mapped_column(String(32), nullable=False)
    fields_json: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    actor_type: Mapped[str] = mapped_column(String(16), nullable=False)
    actor_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    actor_display: Mapped[str | None] = mapped_column(String(255), nullable=True)
    source_window_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("virtual_windows.id", ondelete="SET NULL"), nullable=True
    )
    from_version_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    to_version_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    restored_version_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    changes_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
