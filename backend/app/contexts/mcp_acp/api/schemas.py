from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any
from uuid import UUID

from pydantic import BaseModel, Field, StringConstraints


WindowInput = Annotated[str, StringConstraints(min_length=1, max_length=65536)]
OptionalPath = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=4096)]


class McpClientOut(BaseModel):
    id: UUID
    name: str
    status: str
    runtime: str
    hostname: str | None = None
    version: str | None = None
    online: bool


class McpClientListOut(BaseModel):
    clients: list[McpClientOut]


class McpWindowOut(BaseModel):
    id: UUID
    client_id: UUID
    title: str
    status: str
    cwd: str | None = None
    shell_command: str | None = None
    runtime_ready: bool
    derived_mode: str | None = None
    derived_context: dict[str, Any] | None = None


class McpWindowListOut(BaseModel):
    windows: list[McpWindowOut]


class McpCreateWindowIn(BaseModel):
    target_client_id: UUID
    cwd: OptionalPath | None = None
    shell_command: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=4096)] | None = None
    agent_client: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=64)] | None = None
    prompt: Annotated[str, StringConstraints(min_length=1, max_length=65536)] | None = None
    folder_path: OptionalPath | None = None


class McpSendInputIn(BaseModel):
    target_client_id: UUID
    window_id: UUID
    input: WindowInput
    append_enter: bool = False


class McpCaptureOutputIn(BaseModel):
    target_client_id: UUID
    window_id: UUID
    history_lines: int | None = Field(default=None, ge=1, le=10000)
    max_bytes: int | None = Field(default=65536, ge=1, le=1048576)


class McpWaitForOutputIn(BaseModel):
    target_client_id: UUID
    window_id: UUID
    contains: Annotated[str, StringConstraints(min_length=1, max_length=4096)]
    timeout_seconds: float = Field(default=60.0, ge=0.1, le=600.0)
    poll_interval_seconds: float = Field(default=1.0, ge=0.1, le=30.0)
    history_lines: int | None = Field(default=None, ge=1, le=10000)


class McpReadProjectTodoIn(BaseModel):
    todo_id: UUID
    include_agent_record: bool = True
    include_worktree: bool = True
    include_related: bool = True
    agent_record_message_limit: int = Field(default=200, ge=1, le=500)


class McpSendInputOut(BaseModel):
    ok: bool


class McpCaptureOutputOut(BaseModel):
    text: str
    truncated: bool = False


class McpWaitForOutputOut(McpCaptureOutputOut):
    matched: bool


class McpProjectTodoContextOut(BaseModel):
    todo: dict[str, Any]
    relationships: dict[str, Any] | None = None
    artifacts: list[dict[str, Any]] | None = None
    worktree: dict[str, Any] | None = None
    work_snapshots: list[dict[str, Any]] | None = None
    review_targets: list[dict[str, Any]] | None = None
    review_runs: list[dict[str, Any]] | None = None
    agent_records: list[dict[str, Any]] | None = None


class McpArtifactPluginPreviewUpsertIn(BaseModel):
    preview_id: UUID | None = None
    title: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255)]
    python_source: Annotated[str, StringConstraints(min_length=1, max_length=262144)]
    prompt_template: Annotated[str, StringConstraints(min_length=1, max_length=262144)]
    html_template: Annotated[str, StringConstraints(min_length=1, max_length=262144)]
    json_schema: dict[str, Any]
    demo_content_json: dict[str, Any] | None = None


class McpArtifactPluginPreviewOut(BaseModel):
    id: UUID
    client_id: UUID
    window_id: UUID
    created_by_window_id: UUID
    status: str
    draft_artifact_kind: str | None = None
    title: str
    demo_content_json: dict[str, Any] | None = None
    rendered_content_json: dict[str, Any] | None = None
    last_error: str | None = None
    created_at: datetime
    updated_at: datetime
    expires_at: datetime
