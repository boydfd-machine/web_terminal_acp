from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class ProjectTodoWorkSnapshotOut(BaseModel):
    id: UUID
    todo_id: UUID
    client_id: UUID
    project_path: str
    window_id: UUID | None
    role: str
    branch_name: str | None
    base_ref: str | None
    base_sha: str | None
    head_sha: str | None
    commit_shas: list[str] = Field(default_factory=list)
    diff_stat: dict[str, Any] | None
    changed_files: list[dict[str, Any]] = Field(default_factory=list)
    dirty_state: str
    captured_at: datetime


class ProjectTodoWorkSnapshotListOut(BaseModel):
    work_snapshots: list[ProjectTodoWorkSnapshotOut] = Field(default_factory=list)


class ProjectTodoReviewTargetOut(BaseModel):
    id: UUID
    todo_id: UUID
    work_snapshot_id: UUID
    provider: str
    external_id: str
    url: str | None
    status: str
    base_sha: str | None
    head_sha: str | None
    created_at: datetime
    updated_at: datetime


class ProjectTodoReviewTargetListOut(BaseModel):
    review_targets: list[ProjectTodoReviewTargetOut] = Field(default_factory=list)


class ProjectTodoReviewRunOut(BaseModel):
    id: UUID
    todo_id: UUID
    review_target_id: UUID
    review_window_id: UUID | None
    agent_client: str | None
    agent_profile_id: str | None
    status: str
    summary: str | None
    findings: list[dict[str, Any]] = Field(default_factory=list)
    test_commands: list[dict[str, Any]] = Field(default_factory=list)
    started_at: datetime | None
    completed_at: datetime | None
    last_error: str | None
    created_at: datetime
    updated_at: datetime


class ProjectTodoReviewRunListOut(BaseModel):
    review_runs: list[ProjectTodoReviewRunOut] = Field(default_factory=list)
