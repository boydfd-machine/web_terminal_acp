from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Index, JSON, String, Text, UniqueConstraint, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.model_base import Base


class ProjectTodoDependency(Base):
    __tablename__ = "project_todo_dependencies"
    __table_args__ = (
        UniqueConstraint("project_todo_id", "depends_on_todo_id", name="uq_project_todo_dependency_pair"),
        Index("ix_project_todo_dependencies_todo", "project_todo_id"),
        Index("ix_project_todo_dependencies_upstream", "depends_on_todo_id"),
        Index("ix_project_todo_dependencies_client_project", "client_id", "project_path"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    client_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("clients.id", ondelete="CASCADE"), nullable=False
    )
    project_path: Mapped[str] = mapped_column(Text, nullable=False)
    project_todo_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("project_todos.id", ondelete="CASCADE"), nullable=False
    )
    depends_on_todo_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("project_todos.id", ondelete="CASCADE"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class ProjectTodoQueuedDispatch(Base):
    __tablename__ = "project_todo_queued_dispatches"
    __table_args__ = (
        UniqueConstraint("project_todo_id", name="uq_project_todo_queued_dispatch_todo"),
        Index("ix_project_todo_queued_dispatches_client_project", "client_id", "project_path", "queued_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_todo_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("project_todos.id", ondelete="CASCADE"), nullable=False
    )
    client_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("clients.id", ondelete="CASCADE"), nullable=False
    )
    project_path: Mapped[str] = mapped_column(Text, nullable=False)
    agent_launch_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    dispatch_mode: Mapped[str] = mapped_column(String(16), nullable=False, default="submit", server_default="submit")
    prompt: Mapped[str] = mapped_column(Text, nullable=False)
    queued_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
