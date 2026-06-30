from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field, StringConstraints

from app.contexts.activity.api.schemas import (
    AgentEventOut,
    AgentEventProjectionOut,
    AgentSessionOut,
    AgentTokenUsageOut,
    GitWorktreeActivityOut,
    WorkStatusOut,
)
from app.platform.common_schemas import (
    AgentConfigSelectionIn,
    AgentLaunchIn,
    WindowStatusIn,
    WindowText,
    WindowTitle,
    WindowTitleTag,
)


class TreeWindowOut(BaseModel):
    id: UUID
    title: str
    status: str
    created_at: datetime
    title_tags: list[str] | None = None
    parent_window_id: UUID | None = None
    root_window_id: UUID | None = None
    derived_mode: str | None = None


class GitWorktreeRunOut(BaseModel):
    id: UUID
    virtual_window_id: UUID
    command_sequence: str
    agent_provider: str | None
    status: str
    run_type: Literal["agent", "tracking"]
    worktree_root: str | None
    main_repo_root: str | None
    discovery_method: str | None
    start_snapshot_json: dict[str, Any] | None
    end_snapshot_json: dict[str, Any] | None
    session_diff_json: dict[str, Any] | None
    pending_commit: bool
    resolved_at: datetime | None
    started_at: datetime
    ended_at: datetime | None


class GitWorktreeRunListOut(BaseModel):
    supported: bool
    runs: list[GitWorktreeRunOut] = Field(default_factory=list)
    total: int = 0
    limit: int
    offset: int


class TreeFolderOut(BaseModel):
    id: UUID
    name: str
    path: str
    folders: list["TreeFolderOut"] = Field(default_factory=list)
    windows: list[TreeWindowOut] = Field(default_factory=list)


class WindowCreateIn(BaseModel):
    cwd: WindowText | None = None
    shell_command: WindowText | None = None
    folder_path: WindowText | None = None
    agent_launch: AgentLaunchIn | None = None


class WindowCloneIn(BaseModel):
    mode: Literal["linked", "ephemeral"] = "linked"
    prompt: Annotated[
        str,
        StringConstraints(strip_whitespace=True, min_length=1, max_length=65536),
    ] | None = None
    collect_paths: list[WindowText] | None = Field(default=None, max_length=20)


class SummaryJobRetryIn(BaseModel):
    allow_title_folder_override: bool = False


class WindowPatchIn(BaseModel):
    folder_id: UUID | None = None
    title: WindowTitle | None = None
    status: WindowStatusIn | None = None
    summary: str | None = None
    title_tags: list[WindowTitleTag] | None = Field(default=None, max_length=20)


class SummaryJobOut(BaseModel):
    id: UUID
    status: str
    trigger_reason: str | None
    attempts: int
    last_error: str | None
    run_after: datetime | None
    updated_at: datetime
    allow_title_folder_override: bool


class WindowOut(BaseModel):
    id: UUID
    client_id: UUID
    title: str
    folder_id: UUID | None
    parent_window_id: UUID | None = None
    root_window_id: UUID | None = None
    derived_mode: str | None = None
    derived_context: dict[str, Any] | None = None
    status: str
    tmux_session: str | None
    tmux_window_id: str | None
    tmux_window_index: str | None
    remote_session_id: str | None
    remote_window_id: str | None
    cwd: str | None
    shell_command: str | None
    title_manually_overridden: bool
    folder_manually_overridden: bool
    command_capture_supported: bool
    summary: str | None
    title_tags: list[str] | None
    runtime_tags: list[str] = Field(default_factory=list)
    git_worktree: GitWorktreeActivityOut | None = None
    agent_token_usage: AgentTokenUsageOut | None = None
    work_status: WorkStatusOut
    summary_job: SummaryJobOut | None
    created_at: datetime
    last_terminal_command_at: datetime | None
    last_agent_event_at: datetime | None
    last_active_at: datetime


class AgentRecordOut(BaseModel):
    window_id: UUID
    sessions: list[AgentSessionOut]
    events: list[AgentEventOut]
    events_total: int
    events_limit: int
    events_offset: int
    events_has_more: bool


class AgentChatMessageOut(BaseModel):
    id: UUID
    ai_session_id: UUID | None
    source_type: str
    source_id: str
    role: Literal["user", "agent"]
    body: str
    body_format: Literal["markdown", "json"] = "markdown"
    agent_message_type: Literal["agent", "subagent_call", "subagent_result"] | None = None
    subagent_id: str | None = None
    subagent_tool_use_id: str | None = None
    target_session_id: UUID | None = None
    target_session_source_id: str | None = None
    created_at: datetime


class AgentChatRecordOut(BaseModel):
    window_id: UUID
    messages: list[AgentChatMessageOut]
    messages_total: int
    messages_total_exact: bool = True
    messages_limit: int
    messages_offset: int
    messages_has_more: bool


class SearchMatchOut(BaseModel):
    field: str
    start: int
    end: int


class AgentRecordSearchResultOut(BaseModel):
    message: AgentChatMessageOut
    window_id: UUID
    session_id: UUID | None
    provider: str | None
    matches: list[SearchMatchOut] = Field(default_factory=list)


class AgentRecordSearchOut(BaseModel):
    query: str
    results: list[AgentRecordSearchResultOut] = Field(default_factory=list)
    total: int
    limit: int
    offset: int
    has_more: bool
    scope: Literal["window", "global"]


class CommandHistoryItemOut(BaseModel):
    id: UUID
    command: str
    shell: str | None = None
    cwd: str | None = None
    sequence: int | str | None = None
    exit_status: int | str | None = None
    captured_at: datetime
    finished_at: datetime | None = None
    created_at: datetime


class CommandHistoryOut(BaseModel):
    window_id: UUID
    commands: list[CommandHistoryItemOut]
    commands_total: int
    commands_limit: int
    commands_offset: int
    commands_has_more: bool


class WindowTitleHistoryItemOut(BaseModel):
    id: UUID
    title: str
    summary: str | None
    source: str
    created_at: datetime


class WindowTitleHistoryOut(BaseModel):
    window_id: UUID
    items: list[WindowTitleHistoryItemOut]
    total: int
    limit: int
    offset: int
    has_more: bool
