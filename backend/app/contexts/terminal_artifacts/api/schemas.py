from datetime import datetime
from typing import Annotated, Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field, StringConstraints

from app.platform.common_schemas import AgentModelSelectionIn

ArtifactKind = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=64)]
ArtifactTitle = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255)]


class TerminalArtifactCreateIn(BaseModel):
    artifact_kind: ArtifactKind = "agent_trace_graph"
    artifact_scope: Literal["terminal", "project"] = "terminal"
    project_path: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=4096)] | None = None
    title: ArtifactTitle | None = None
    prompt: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=65536)] | None = None
    output_language: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=64)] | None = None
    metadata_json: dict[str, Any] | None = None
    artifact_model_selection: AgentModelSelectionIn | None = None
    terminal_retention_seconds: float | None = Field(default=None, ge=0, le=3600)


class TerminalArtifactOut(BaseModel):
    id: UUID
    client_id: UUID
    virtual_window_id: UUID
    source_window_id: UUID | None
    ephemeral_window_id: UUID | None
    artifact_scope: str = "terminal"
    project_path: str | None = None
    artifact_kind: str
    title: str
    status: str
    content_json: dict[str, Any] | None
    display_html: str | None
    metadata_json: dict[str, Any] | None
    last_error: str | None
    started_at: datetime | None
    completed_at: datetime | None
    created_at: datetime
    updated_at: datetime


class ProjectArtifactVersionOut(BaseModel):
    artifact: TerminalArtifactOut
    version_number: int
    created_at: datetime
    completed_at: datetime | None
    source_window_id: UUID | None
    source_window_title: str | None
    virtual_window_title: str | None


class ProjectArtifactGroupOut(BaseModel):
    artifact_kind: str
    latest_artifact: TerminalArtifactOut
    version_count: int
    versions: list[ProjectArtifactVersionOut] = Field(default_factory=list)


class TerminalArtifactListOut(BaseModel):
    window_id: UUID
    artifact_scope: str = "terminal"
    project_path: str | None = None
    artifacts: list[TerminalArtifactOut] = Field(default_factory=list)
    total: int
    limit: int
    offset: int
    has_more: bool


class ProjectArtifactListOut(BaseModel):
    project_path: str
    artifacts: list[TerminalArtifactOut] = Field(default_factory=list)
    artifact_groups: list[ProjectArtifactGroupOut] = Field(default_factory=list)
    total: int
    limit: int
    offset: int
    has_more: bool
