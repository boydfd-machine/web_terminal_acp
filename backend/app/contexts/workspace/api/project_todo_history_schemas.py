from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


class ProjectTodoVersionOut(BaseModel):
    id: UUID
    todo_id: UUID
    version_number: int
    title: str
    description: str | None
    actor_type: Literal["user", "agent", "system"]
    actor_id: str | None
    actor_display: str | None
    source_window_id: UUID | None
    created_at: datetime


class ProjectTodoAuditLogOut(BaseModel):
    id: UUID
    todo_id: UUID
    action: Literal["created", "updated", "restored"]
    fields: list[str] = Field(default_factory=list)
    actor_type: Literal["user", "agent", "system"]
    actor_id: str | None
    actor_display: str | None
    source_window_id: UUID | None
    from_version_number: int | None
    to_version_number: int | None
    restored_version_number: int | None
    created_at: datetime


class ProjectTodoHistoryOut(BaseModel):
    todo_id: UUID
    versions: list[ProjectTodoVersionOut] = Field(default_factory=list)
    audit_logs: list[ProjectTodoAuditLogOut] = Field(default_factory=list)
