from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field

from app.platform.common_schemas import WindowTitle


class WorkStatusOut(BaseModel):
    state: Literal["LONG_IDLE", "RECENT_ACTIVE", "WORKING", "FINISHED", "ABORTED", "FAILED"]
    label: str
    color: Literal["gray", "green", "orange", "red"]
    last_activity_at: datetime | None
    last_working_activity_at: datetime | None
    source: Literal["activity", "manual"] = "activity"
    manual_updated_at: datetime | None = None


class GitWorktreeActivityOut(BaseModel):
    worktree_root: str
    main_repo_root: str
    branch: str | None = None
    pending_commit: bool = False
    merge_status: Literal["merged", "unmerged", "conflict", "unknown"] = "unknown"
    merge_status_reason: str | None = None
    merged_to_main: bool | None = None
    merge_attention_required: bool = False
    main_branch: str | None = None
    main_head_sha: str | None = None
    main_merge_head_sha: str | None = None
    main_merge_in_progress: bool = False
    main_merge_matches_worktree: bool | None = None
    unmerged_files: list[str] = Field(default_factory=list)


class WindowActivityOut(BaseModel):
    window_id: UUID
    work_status: WorkStatusOut
    runtime_tags: list[str] = Field(default_factory=list)
    todo_title: str | None = None
    last_agent_task_completed_at: datetime | None = None
    last_agent_task_status: Literal["FINISHED", "ABORTED", "FAILED"] | None = None
    last_agent_task_status_at: datetime | None = None
    git_worktree: GitWorktreeActivityOut | None = None
    parent_window_id: UUID | None = None
    root_window_id: UUID | None = None
    derived_mode: str | None = None


class ClientWindowsActivityOut(BaseModel):
    windows: list[WindowActivityOut] = Field(default_factory=list)


class TerminalNotificationOut(BaseModel):
    id: str
    client_id: UUID
    window_id: UUID
    window_title: str
    completed_at: datetime
    status: Literal["FINISHED", "ABORTED", "FAILED"]
    read: bool


class TerminalNotificationListOut(BaseModel):
    notifications: list[TerminalNotificationOut] = Field(default_factory=list)


class TerminalNotificationAckIn(BaseModel):
    window_id: UUID
    completed_at: datetime


class ManualWorkStatusIn(BaseModel):
    state: Literal["LONG_IDLE", "RECENT_ACTIVE", "WORKING", "FINISHED", "ABORTED", "FAILED"] | None


class IngestEventOut(BaseModel):
    id: UUID
    source_type: str
    source_id: str
    kind: str
    fingerprint: str


class TerminalRecentOut(BaseModel):
    window_id: UUID
    title: str
    todo_title: str | None = None
    last_used_at: datetime


class GlobalTerminalRecentOut(TerminalRecentOut):
    client_id: UUID
    client_name: str


class TerminalRecentPageOut(BaseModel):
    items: list[TerminalRecentOut]
    page: int
    page_size: int
    total: int
    total_pages: int


class GlobalTerminalRecentPageOut(BaseModel):
    items: list[GlobalTerminalRecentOut]
    page: int
    page_size: int
    total: int
    total_pages: int


class TerminalRecentTouchIn(BaseModel):
    window_id: UUID
    title: WindowTitle


class AgentSessionOut(BaseModel):
    id: UUID
    provider: str
    source_id: str
    source_path: str | None
    project_path: str | None
    virtual_window_id: UUID | None
    title: str | None
    tags: list[str] | None
    summary: str | None
    created_at: datetime
    updated_at: datetime


class AgentTokenUsageCountsOut(BaseModel):
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    cached_input_tokens: int = 0
    cache_creation_input_tokens: int = 0
    reasoning_output_tokens: int = 0


class AgentTokenUsageOut(BaseModel):
    context: AgentTokenUsageCountsOut | None = None
    total: AgentTokenUsageCountsOut
    context_window: int | None = None
    auto_compact_token_limit: int | None = None
    latest_event_at: datetime | None = None
    providers: list[str] = Field(default_factory=list)
    event_count: int = 0


class AgentEventProjectionOut(BaseModel):
    tone: str
    label: str
    body: str
    body_format: Literal["markdown", "json"] = "markdown"
    subtype: str | None = None
    agent_message_type: Literal["agent", "subagent_call", "subagent_result"] | None = None
    subagent_id: str | None = None
    subagent_tool_use_id: str | None = None
    target_session_id: UUID | None = None
    target_session_source_id: str | None = None


class AgentEventOut(BaseModel):
    id: UUID
    ai_session_id: UUID | None
    source_type: str
    source_id: str
    kind: str
    payload_json: dict[str, Any]
    projection: AgentEventProjectionOut | None = None
    created_at: datetime
