from datetime import datetime
from typing import Annotated, Any, Literal
from uuid import UUID
from pydantic import BaseModel, Field, StringConstraints

from app.contexts.activity.api.schemas import GitWorktreeActivityOut, WorkStatusOut
from app.contexts.workspace.api.project_agent_preference_schemas import ProjectAgentPreferenceOut
from app.contexts.workspace.api.project_todo_attachment_schemas import ProjectTodoAttachmentOut
from app.platform.common_schemas import AgentLaunchIn, AgentModelSelectionIn


class TerminalProjectOut(BaseModel):
    project_path: str
    window_count: int


class ProjectBrowseRootOut(BaseModel):
    kind: Literal["main", "worktree"]
    project_path: str
    browse_root: str | None = None
    branch: str | None = None
    pending_commit: bool = False


class ProjectBrowseRootListOut(BaseModel):
    roots: list[ProjectBrowseRootOut] = Field(default_factory=list)


class ProjectOut(BaseModel):
    client_id: UUID
    path: str
    display_name: str | None = None
    summary_status: str | None = None
    summary_updated_at: datetime | None = None
    window_count: int = 0
    agent_preference: ProjectAgentPreferenceOut = Field(default_factory=ProjectAgentPreferenceOut)


class ProjectFileEntryOut(BaseModel):
    name: str
    path: str
    kind: Literal["file", "directory"]
    size: int | None = None
    mtime: float | None = None


class ProjectFileListOut(BaseModel):
    project_path: str
    path: str
    entries: list[ProjectFileEntryOut] = Field(default_factory=list)


class ProjectFileContentOut(BaseModel):
    project_path: str
    path: str
    content: str
    encoding: Literal["utf-8"]
    truncated: bool = False
    size: int | None = None


class ProjectFileSaveIn(BaseModel):
    path: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=4096)]
    content: str
    overwrite: bool = True


class ProjectFileUploadIn(BaseModel):
    path: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=4096)]
    content_base64: str
    overwrite: bool = True


class ProjectFileUploadOut(BaseModel):
    project_path: str
    path: str
    size: int


class FolderCreateIn(BaseModel):
    path: str


class FolderOut(BaseModel):
    id: UUID
    name: str
    path: str


class ProjectSummaryOut(BaseModel):
    project_path: str
    display_name: str | None
    status: str
    last_error: str | None
    updated_at: datetime


class ProjectSummarySummarizeIn(BaseModel):
    project_path: str
    output_language: str | None = None


ProjectTodoTitle = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255)]
ProjectTodoDescription = Annotated[str, StringConstraints(strip_whitespace=True, max_length=262144)]
ProjectTodoStatusIn = Literal["TODO", "BLOCKED", "DISPATCHED", "AWAITING_REVIEW", "DONE"]
ProjectTodoDispatchModeIn = Literal["submit", "compose"]
ProjectTodoDispatchStageIn = Literal["STARTING", "WINDOW_CREATED", "TERMINAL_READY", "verifying", "FAILED"]
ProjectTodoExecutionKindIn = Literal["ONCE", "PERIODIC"]
ProjectTodoTerminalPolicyIn = Literal["NEW_TERMINAL", "REUSE_LATEST"]
ProjectTodoTriggerStrategyIn = Literal["MANUAL", "CRON"]
ProjectTodoReviewStrategyIn = Literal["LOCAL_CARD", "GITEA", "GITHUB"]
ProjectTodoReviewStatusIn = Literal[
    "NOT_REQUESTED",
    "PENDING",
    "RUNNING",
    "REVIEWED",
    "APPROVED",
    "CHANGES_REQUESTED",
    "NEEDS_HUMAN_REVIEW",
]
ProjectTodoReviewNotes = Annotated[str, StringConstraints(strip_whitespace=True, max_length=65536)]
ProjectTodoReviewAgentProfile = Annotated[str, StringConstraints(strip_whitespace=True, max_length=128)]
ProjectTodoArtifactPurpose = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=32)]
ProjectTodoTypeId = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_.-]+$"),
]
ProjectTodoTypeName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255)]
ProjectTodoTypeDescription = Annotated[str, StringConstraints(strip_whitespace=True, max_length=4096)]
ProjectTodoTypeScope = Literal["system", "project"]
ProjectReviewProviderIn = Literal["LOCAL_CARD", "GITEA", "GITHUB"]
ProjectReviewMergePolicyIn = Literal["MANUAL", "AUTO_AFTER_PASSED"]
ProjectReviewAgent = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=64)]
ProjectReviewCommand = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=4096)]
ProjectReviewArtifactKind = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=64)]
ProjectTodoInputArtifactId = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=128)]
ProjectTodoDispatchTemplate = Annotated[str, StringConstraints(strip_whitespace=True, max_length=65536)]
ProjectTodoOutputLanguage = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=64)]


class ProjectReviewConfigPutIn(BaseModel):
    pr_provider: ProjectReviewProviderIn = "LOCAL_CARD"
    pr_provider_config: dict[str, Any] | None = None
    review_agent: ProjectReviewAgent | None = None
    review_agent_command: ProjectReviewCommand | None = None
    review_agent_profile_id: ProjectTodoReviewAgentProfile | None = None
    auto_create_review_target: bool = True
    auto_dispatch_review: bool = False
    merge_policy: ProjectReviewMergePolicyIn = "MANUAL"
    required_artifact_kinds: list[ProjectReviewArtifactKind] = Field(default_factory=list, max_length=20)


class ProjectReviewConfigOut(BaseModel):
    id: UUID
    client_id: UUID
    project_path: str
    pr_provider: ProjectReviewProviderIn
    pr_provider_config: dict[str, Any] | None
    review_agent: str | None
    review_agent_command: str | None
    review_agent_profile_id: str | None
    auto_create_review_target: bool
    auto_dispatch_review: bool
    merge_policy: ProjectReviewMergePolicyIn
    required_artifact_kinds: list[str] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class ProjectTodoTypeUpsertIn(BaseModel):
    id: ProjectTodoTypeId
    name: ProjectTodoTypeName
    description: ProjectTodoTypeDescription | None = None
    agent: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=64)] | None = None
    agent_profile_id: ProjectTodoReviewAgentProfile | None = None
    artifact_kinds: list[ProjectReviewArtifactKind] = Field(default_factory=list, max_length=20)
    input_artifact_ids: list[ProjectTodoInputArtifactId] = Field(default_factory=list, max_length=50)
    dispatch_template: ProjectTodoDispatchTemplate | None = None


class ProjectTodoTypePatchIn(BaseModel):
    name: ProjectTodoTypeName | None = None
    description: ProjectTodoTypeDescription | None = None
    agent: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=64)] | None = None
    agent_profile_id: ProjectTodoReviewAgentProfile | None = None
    artifact_kinds: list[ProjectReviewArtifactKind] | None = Field(default=None, max_length=20)
    input_artifact_ids: list[ProjectTodoInputArtifactId] | None = Field(default=None, max_length=50)
    dispatch_template: ProjectTodoDispatchTemplate | None = None


class ProjectTodoTypeOut(BaseModel):
    id: str
    scope: ProjectTodoTypeScope
    client_id: UUID | None
    project_path: str | None
    name: str
    description: str | None
    agent: str | None
    agent_profile_id: str | None
    artifact_kinds: list[str] = Field(default_factory=list)
    input_artifact_ids: list[str] = Field(default_factory=list, exclude_if=lambda value: not value)
    dispatch_template: str | None
    created_at: datetime
    updated_at: datetime


class ProjectTodoTypeListOut(BaseModel):
    todo_types: list[ProjectTodoTypeOut] = Field(default_factory=list)


class ProjectTodoCreateIn(BaseModel):
    title: ProjectTodoTitle
    description: ProjectTodoDescription | None = None
    parent_todo_id: UUID | None = None
    todo_type_id: ProjectTodoTypeId = "default"
    status: Literal["TODO", "BLOCKED"] = "TODO"
    artifact_kinds: list[ProjectReviewArtifactKind] | None = Field(default=None, max_length=20)
    input_artifact_ids: list[ProjectTodoInputArtifactId] | None = Field(default=None, max_length=50)
    artifact_model_selection: AgentModelSelectionIn | None = None
    execution_kind: ProjectTodoExecutionKindIn = "ONCE"
    terminal_policy: ProjectTodoTerminalPolicyIn = "NEW_TERMINAL"
    trigger_strategy: ProjectTodoTriggerStrategyIn = "MANUAL"
    cron_expression: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=128)] | None = None
    schedule_enabled: bool | None = None
    review_strategy: ProjectTodoReviewStrategyIn = "LOCAL_CARD"
    review_agent: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=64)] | None = None
    review_agent_profile_id: ProjectTodoReviewAgentProfile | None = None


class ProjectTodoPatchIn(BaseModel):
    title: ProjectTodoTitle | None = None
    description: ProjectTodoDescription | None = None
    parent_todo_id: UUID | None = None
    todo_type_id: ProjectTodoTypeId | None = None
    status: ProjectTodoStatusIn | None = None
    sort_order: int | None = Field(default=None, ge=0)
    artifact_kinds: list[ProjectReviewArtifactKind] | None = Field(default=None, max_length=20)
    input_artifact_ids: list[ProjectTodoInputArtifactId] | None = Field(default=None, max_length=50)
    execution_kind: ProjectTodoExecutionKindIn | None = None
    terminal_policy: ProjectTodoTerminalPolicyIn | None = None
    trigger_strategy: ProjectTodoTriggerStrategyIn | None = None
    cron_expression: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=128)] | None = None
    schedule_enabled: bool | None = None
    review_strategy: ProjectTodoReviewStrategyIn | None = None
    review_status: ProjectTodoReviewStatusIn | None = None
    review_agent: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=64)] | None = None
    review_agent_profile_id: ProjectTodoReviewAgentProfile | None = None
    needs_human_review: bool | None = None
    review_unseen: bool | None = None
    review_notes: ProjectTodoReviewNotes | None = None


class ProjectTodoMoveProjectIn(BaseModel):
    project_path: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=4096)]


class ProjectTodoDispatchIn(BaseModel):
    agent_launch: AgentLaunchIn
    dispatch_mode: ProjectTodoDispatchModeIn = "submit"
    dispatch_after_todo_ids: list[UUID] | None = Field(default=None, max_length=100)
    output_language: ProjectTodoOutputLanguage | None = None
    artifact_model_selection: AgentModelSelectionIn | None = None
    prompt: Annotated[
        str,
        StringConstraints(strip_whitespace=True, min_length=1, max_length=262144),
    ] | None = None


class ProjectTodoReviewDispatchIn(BaseModel):
    agent_launch: AgentLaunchIn
    output_language: ProjectTodoOutputLanguage | None = None
    prompt: Annotated[
        str,
        StringConstraints(strip_whitespace=True, min_length=1, max_length=262144),
    ] | None = None


class ProjectTodoCommentIn(BaseModel):
    comment: Annotated[
        str,
        StringConstraints(strip_whitespace=True, min_length=1, max_length=65536),
    ]
    artifact_kinds: list[ProjectReviewArtifactKind] | None = Field(default=None, max_length=20)


class ProjectTodoArtifactLinkIn(BaseModel):
    artifact_id: UUID
    purpose: ProjectTodoArtifactPurpose = "review"


class ProjectTodoFromPageReviewCardIn(BaseModel):
    artifact_id: UUID
    card_id: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=64)]
    purpose: ProjectTodoArtifactPurpose = "page_review"


class ProjectTodoFromArtifactCardIn(BaseModel):
    artifact_id: UUID
    card: ProjectTodoCreateIn
    purpose: ProjectTodoArtifactPurpose = "artifact_card"


class ProjectTodoArtifactOut(BaseModel):
    id: UUID
    artifact_id: UUID
    client_id: UUID
    window_id: UUID
    source_window_id: UUID | None
    ephemeral_window_id: UUID | None
    review_run_id: UUID | None
    created_by_window_id: UUID | None
    artifact_scope: str = "terminal"
    project_path: str | None = None
    title: str
    artifact_kind: str
    status: str
    purpose: str
    agent_name: str | None = None
    agent_status: WorkStatusOut | None = None
    metadata_json: dict[str, Any] | None = None
    last_error: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class ProjectTodoRelationOut(BaseModel):
    id: UUID
    title: str
    status: ProjectTodoStatusIn
    completed_at: datetime | None


class ProjectTodoReferenceOut(BaseModel):
    id: UUID
    title: str
    description: str | None
    status: ProjectTodoStatusIn


class ProjectTodoAssignedTerminalOut(BaseModel):
    id: UUID
    title: str
    summary: str | None
    title_tags: list[str] = Field(default_factory=list)
    runtime_tags: list[str] = Field(default_factory=list)
    work_status: WorkStatusOut
    topic_path: str | None = None
    git_worktree: GitWorktreeActivityOut | None = None
    parent_window_id: UUID | None = None
    root_window_id: UUID | None = None
    derived_mode: str | None = None
    created_at: datetime


class ProjectTodoRunOut(BaseModel):
    id: UUID
    todo_id: UUID
    window_id: UUID | None
    run_number: int
    trigger_strategy: ProjectTodoTriggerStrategyIn
    trigger_reason: str
    terminal_policy: ProjectTodoTerminalPolicyIn
    dispatch_mode: ProjectTodoDispatchModeIn
    prompt: str | None
    status: str
    started_at: datetime | None
    dispatched_at: datetime | None
    completed_at: datetime | None
    last_error: str | None
    assigned_terminal: ProjectTodoAssignedTerminalOut | None = None
    created_at: datetime
    updated_at: datetime


class ProjectTodoOut(BaseModel):
    id: UUID
    client_id: UUID
    project_path: str
    todo_type_id: str
    todo_type: ProjectTodoTypeOut
    parent_todo_id: UUID | None
    parent_todo: ProjectTodoRelationOut | None = None
    title: str
    description: str | None
    status: ProjectTodoStatusIn
    sort_order: int
    assigned_window_id: UUID | None
    assigned_agent: str | None
    agent_profile_id: str | None
    dispatch_prompt: str | None
    dispatch_stage: ProjectTodoDispatchStageIn | None
    dispatch_error: str | None
    blocked_reason: str | None
    dispatched_at: datetime | None
    awaiting_review_at: datetime | None
    completed_at: datetime | None
    review_strategy: ProjectTodoReviewStrategyIn
    review_status: ProjectTodoReviewStatusIn
    review_agent: str | None
    review_agent_profile_id: str | None
    review_window_id: UUID | None
    review_prompt: str | None
    review_dispatched_at: datetime | None
    reviewed_at: datetime | None
    review_unseen: bool
    needs_human_review: bool
    review_notes: str | None
    implementation_worktree: dict[str, Any] | None
    artifact_kinds: list[str] = Field(default_factory=list)
    input_artifact_ids: list[str] = Field(default_factory=list)
    artifact_model_selection: dict[str, Any] | None = None
    execution_kind: ProjectTodoExecutionKindIn
    terminal_policy: ProjectTodoTerminalPolicyIn
    trigger_strategy: ProjectTodoTriggerStrategyIn
    cron_expression: str | None
    schedule_enabled: bool
    next_trigger_at: datetime | None
    last_triggered_at: datetime | None
    execution_run_count: int
    assigned_terminal: ProjectTodoAssignedTerminalOut | None = None
    execution_runs: list[ProjectTodoRunOut] = Field(default_factory=list)
    attachments: list[ProjectTodoAttachmentOut] = Field(default_factory=list)
    artifacts: list[ProjectTodoArtifactOut] = Field(default_factory=list)
    dependencies: list[ProjectTodoRelationOut] = Field(default_factory=list)
    dependents: list[ProjectTodoRelationOut] = Field(default_factory=list)
    child_todos: list[ProjectTodoRelationOut] = Field(default_factory=list)
    referenced_todos: list[ProjectTodoReferenceOut] = Field(default_factory=list)
    queued_dispatch: bool = False
    created_at: datetime
    updated_at: datetime


class ProjectTodoListItemOut(BaseModel):
    id: UUID
    client_id: UUID
    project_path: str
    todo_type_id: str
    todo_type: ProjectTodoTypeOut
    parent_todo_id: UUID | None
    parent_todo: ProjectTodoRelationOut | None = None
    title: str
    status: ProjectTodoStatusIn
    sort_order: int
    assigned_window_id: UUID | None
    assigned_agent: str | None
    agent_profile_id: str | None
    dispatch_stage: ProjectTodoDispatchStageIn | None
    dispatch_error: str | None
    blocked_reason: str | None
    awaiting_review_at: datetime | None
    review_status: ProjectTodoReviewStatusIn
    review_unseen: bool
    needs_human_review: bool
    implementation_worktree: dict[str, Any] | None
    artifact_kinds: list[str] = Field(default_factory=list)
    input_artifact_ids: list[str] = Field(default_factory=list)
    artifact_model_selection: dict[str, Any] | None = None
    execution_kind: ProjectTodoExecutionKindIn
    terminal_policy: ProjectTodoTerminalPolicyIn
    trigger_strategy: ProjectTodoTriggerStrategyIn
    cron_expression: str | None
    schedule_enabled: bool
    execution_run_count: int
    assigned_terminal: ProjectTodoAssignedTerminalOut | None = None
    execution_runs: list[ProjectTodoRunOut] = Field(default_factory=list, exclude_if=lambda value: not value)
    attachments: list[ProjectTodoAttachmentOut] = Field(default_factory=list)
    artifacts: list[ProjectTodoArtifactOut] = Field(default_factory=list)
    child_todos: list[ProjectTodoRelationOut] = Field(default_factory=list)
    referenced_todos: list[ProjectTodoReferenceOut] = Field(default_factory=list, exclude_if=lambda value: not value)
    queued_dispatch: bool = False
    created_at: datetime
    updated_at: datetime


class ProjectTodoListOut(BaseModel):
    todos: list[ProjectTodoListItemOut] = Field(default_factory=list)


class ProjectTodoSearchMatchOut(BaseModel):
    field: Literal["title", "description", "project_path", "status", "assigned_agent"]
    start: int
    end: int


class ProjectTodoSearchResultOut(BaseModel):
    id: UUID
    client_id: UUID
    project_path: str
    title: str
    description: str | None
    status: ProjectTodoStatusIn
    assigned_window_id: UUID | None
    assigned_agent: str | None
    updated_at: datetime
    matches: list[ProjectTodoSearchMatchOut] = Field(default_factory=list)


class ProjectTodoSearchOut(BaseModel):
    query: str
    results: list[ProjectTodoSearchResultOut] = Field(default_factory=list)
    total: int
    limit: int
    offset: int
    has_more: bool
