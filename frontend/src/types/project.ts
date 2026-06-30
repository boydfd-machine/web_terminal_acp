import type { AgentModelSelection } from "./agent";
import type { ProjectTodoWorktree } from "./projectWorktree";
import type { GitWorktreeActivity, WorkStatus } from "./window";

export type ProjectAgentPreference = {
  agent_profile_id: string | null;
  agent_client: string | null;
  agent_command: string | null;
  agent_model_selection: AgentModelSelection | null;
};

export type Project = {
  client_id: string;
  path: string;
  display_name: string | null;
  summary_status: string | null;
  summary_updated_at: string | null;
  window_count: number;
  agent_preference?: ProjectAgentPreference | null;
};

export type ProjectBrowseRoot = {
  kind: "main" | "worktree";
  project_path: string;
  browse_root: string | null;
  branch?: string | null;
  pending_commit: boolean;
};

export type ProjectBrowseRootList = {
  roots: ProjectBrowseRoot[];
};

export type ProjectFileEntry = {
  name: string;
  path: string;
  kind: "file" | "directory";
  size: number | null;
  mtime: number | null;
};

export type ProjectFileList = {
  project_path: string;
  path: string;
  entries: ProjectFileEntry[];
};

export type ProjectFileContent = {
  project_path: string;
  path: string;
  content: string;
  encoding: "utf-8";
  truncated: boolean;
  size: number | null;
};

export type ProjectFileUploadResult = {
  project_path: string;
  path: string;
  size: number;
};

export type ProjectFileSearchMatch = {
  field: "path" | "snippet";
  start: number;
  end: number;
};

export type ProjectFileSearchResult = {
  project_path: string;
  path: string;
  line: number | null;
  snippet: string;
  matches: ProjectFileSearchMatch[];
};

export type ProjectFileSearchResponse = {
  query: string;
  results: ProjectFileSearchResult[];
  total: number;
  limit: number;
  offset: number;
  has_more: boolean;
  scanned_files: number;
  truncated: boolean;
};

export type ProjectFileSearchMode = "all" | "content" | "filename";

export type ProjectSummary = {
  project_path: string;
  display_name: string | null;
  status: string;
  last_error: string | null;
  updated_at: string;
};

export type ProjectTodoStatus = "TODO" | "BLOCKED" | "DISPATCHED" | "AWAITING_REVIEW" | "DONE";
export type ProjectTodoDispatchMode = "submit" | "compose";
export type ProjectTodoDispatchStage = "STARTING" | "WINDOW_CREATED" | "TERMINAL_READY" | "verifying" | "FAILED";
export type ProjectTodoExecutionKind = "ONCE" | "PERIODIC";
export type ProjectTodoTerminalPolicy = "NEW_TERMINAL" | "REUSE_LATEST";
export type ProjectTodoTriggerStrategy = "MANUAL" | "CRON";
export type ProjectTodoReviewStrategy = "LOCAL_CARD" | "GITEA" | "GITHUB";
export type ProjectReviewProvider = "LOCAL_CARD" | "GITEA" | "GITHUB";
export type ProjectReviewMergePolicy = "MANUAL" | "AUTO_AFTER_PASSED";
export type ProjectTodoReviewStatus =
  | "NOT_REQUESTED"
  | "PENDING"
  | "RUNNING"
  | "REVIEWED"
  | "APPROVED"
  | "CHANGES_REQUESTED"
  | "NEEDS_HUMAN_REVIEW";
export type ProjectTodoHistoryActorType = "user" | "agent" | "system";
export type ProjectTodoAuditAction = "created" | "updated" | "restored";

export type ProjectReviewConfig = {
  id: string;
  client_id: string;
  project_path: string;
  pr_provider: ProjectReviewProvider;
  pr_provider_config: Record<string, unknown> | null;
  review_agent: string | null;
  review_agent_command: string | null;
  review_agent_profile_id: string | null;
  auto_create_review_target: boolean;
  auto_dispatch_review: boolean;
  merge_policy: ProjectReviewMergePolicy;
  required_artifact_kinds: string[];
  created_at: string;
  updated_at: string;
};

export type ProjectTodoTypeScope = "system" | "project";

export type ProjectTodoType = {
  id: string;
  scope: ProjectTodoTypeScope;
  client_id: string | null;
  project_path: string | null;
  name: string;
  description: string | null;
  agent: string | null;
  agent_profile_id: string | null;
  artifact_kinds: string[];
  input_artifact_ids: string[];
  dispatch_template: string | null;
  created_at: string;
  updated_at: string;
};

export type ProjectTodoTypeList = {
  todo_types: ProjectTodoType[];
};

export type ProjectTodoArtifact = {
  id: string;
  artifact_id: string;
  client_id: string;
  window_id: string;
  source_window_id: string | null;
  ephemeral_window_id: string | null;
  artifact_scope: "terminal" | "project";
  project_path: string | null;
  review_run_id: string | null;
  created_by_window_id: string | null;
  title: string;
  artifact_kind: string;
  status: string;
  purpose: string;
  agent_name: string | null;
  agent_status: WorkStatus | null;
  metadata_json: Record<string, unknown> | null;
  last_error: string | null;
  started_at: string | null;
  completed_at: string | null;
  created_at: string;
  updated_at: string;
};

export type ProjectTodoAttachmentStatus = "pending" | "uploaded";

export type ProjectTodoAttachment = {
  id: string;
  todo_id: string;
  filename: string;
  content_type: string;
  size_bytes: number | null;
  status: ProjectTodoAttachmentStatus;
  uploaded_at: string | null;
  created_at: string;
  updated_at: string;
};

export type ProjectTodoAttachmentUpload = {
  attachment: ProjectTodoAttachment;
  upload_url: string;
  upload_headers: Record<string, string>;
  expires_at: string;
};

export type ProjectTodoAttachmentDownload = {
  attachment: ProjectTodoAttachment;
  download_url: string;
  expires_at: string;
};

export type ProjectTodoRelation = {
  id: string;
  title: string;
  status: ProjectTodoStatus;
  completed_at: string | null;
};

export type ProjectTodoReference = {
  id: string;
  title: string;
  description: string | null;
  status: ProjectTodoStatus;
};

export type ProjectTodoAssignedTerminal = {
  id: string;
  title: string;
  summary: string | null;
  title_tags: string[];
  runtime_tags: string[];
  work_status: WorkStatus;
  topic_path: string | null;
  git_worktree?: GitWorktreeActivity | null;
  parent_window_id?: string | null;
  root_window_id?: string | null;
  derived_mode?: string | null;
  created_at: string;
};

export type ProjectTodoRun = {
  id: string;
  todo_id: string;
  window_id: string | null;
  run_number: number;
  trigger_strategy: ProjectTodoTriggerStrategy;
  trigger_reason: string;
  terminal_policy: ProjectTodoTerminalPolicy;
  dispatch_mode: ProjectTodoDispatchMode;
  prompt: string | null;
  status: string;
  started_at: string | null;
  dispatched_at: string | null;
  completed_at: string | null;
  last_error: string | null;
  assigned_terminal: ProjectTodoAssignedTerminal | null;
  created_at: string;
  updated_at: string;
};

export type ProjectTodo = {
  id: string;
  client_id: string;
  project_path: string;
  todo_type_id: string;
  todo_type: ProjectTodoType;
  parent_todo_id: string | null;
  parent_todo: ProjectTodoRelation | null;
  title: string;
  description: string | null;
  status: ProjectTodoStatus;
  sort_order: number;
  assigned_window_id: string | null;
  assigned_agent: string | null;
  agent_profile_id: string | null;
  dispatch_prompt: string | null;
  dispatch_stage: ProjectTodoDispatchStage | null;
  dispatch_error: string | null;
  blocked_reason: string | null;
  dispatched_at: string | null;
  awaiting_review_at: string | null;
  completed_at: string | null;
  review_strategy: ProjectTodoReviewStrategy;
  review_status: ProjectTodoReviewStatus;
  review_agent: string | null;
  review_agent_profile_id: string | null;
  review_window_id: string | null;
  review_prompt: string | null;
  review_dispatched_at: string | null;
  reviewed_at: string | null;
  review_unseen: boolean;
  needs_human_review: boolean;
  review_notes: string | null;
  implementation_worktree: ProjectTodoWorktree | null;
  execution_kind: ProjectTodoExecutionKind;
  terminal_policy: ProjectTodoTerminalPolicy;
  trigger_strategy: ProjectTodoTriggerStrategy;
  cron_expression: string | null;
  schedule_enabled: boolean;
  next_trigger_at: string | null;
  last_triggered_at: string | null;
  execution_run_count: number;
  artifact_kinds: string[];
  input_artifact_ids: string[];
  artifact_model_selection: AgentModelSelection | null;
  assigned_terminal: ProjectTodoAssignedTerminal | null;
  execution_runs: ProjectTodoRun[];
  attachments: ProjectTodoAttachment[];
  artifacts: ProjectTodoArtifact[];
  dependencies: ProjectTodoRelation[];
  dependents: ProjectTodoRelation[];
  child_todos: ProjectTodoRelation[];
  referenced_todos: ProjectTodoReference[];
  queued_dispatch: boolean;
  created_at: string;
  updated_at: string;
};

export type ProjectTodoListItem = {
  id: string;
  client_id: string;
  project_path: string;
  todo_type_id: string;
  todo_type: ProjectTodoType;
  parent_todo_id: string | null;
  parent_todo: ProjectTodoRelation | null;
  title: string;
  description: string | null;
  status: ProjectTodoStatus;
  sort_order: number;
  assigned_window_id: string | null;
  assigned_agent: string | null;
  agent_profile_id: string | null;
  dispatch_stage: ProjectTodoDispatchStage | null;
  dispatch_error: string | null;
  blocked_reason: string | null;
  review_status: ProjectTodoReviewStatus;
  review_unseen: boolean;
  needs_human_review: boolean;
  implementation_worktree: ProjectTodoWorktree | null;
  execution_kind: ProjectTodoExecutionKind;
  terminal_policy: ProjectTodoTerminalPolicy;
  trigger_strategy: ProjectTodoTriggerStrategy;
  cron_expression: string | null;
  schedule_enabled: boolean;
  execution_run_count: number;
  artifact_kinds: string[];
  input_artifact_ids: string[];
  artifact_model_selection: AgentModelSelection | null;
  assigned_terminal: ProjectTodoAssignedTerminal | null;
  attachments: ProjectTodoAttachment[];
  artifacts: ProjectTodoArtifact[];
  child_todos: ProjectTodoRelation[];
  queued_dispatch: boolean;
  created_at: string;
  updated_at: string;
};

export type ProjectTodoList = {
  todos: ProjectTodoListItem[];
};

export type ProjectTodoVersion = {
  id: string;
  todo_id: string;
  version_number: number;
  title: string;
  description: string | null;
  actor_type: ProjectTodoHistoryActorType;
  actor_id: string | null;
  actor_display: string | null;
  source_window_id: string | null;
  created_at: string;
};

export type ProjectTodoAuditLog = {
  id: string;
  todo_id: string;
  action: ProjectTodoAuditAction;
  fields: string[];
  actor_type: ProjectTodoHistoryActorType;
  actor_id: string | null;
  actor_display: string | null;
  source_window_id: string | null;
  from_version_number: number | null;
  to_version_number: number | null;
  restored_version_number: number | null;
  created_at: string;
};

export type ProjectTodoHistory = {
  todo_id: string;
  versions: ProjectTodoVersion[];
  audit_logs: ProjectTodoAuditLog[];
};

export type ProjectTodoSearchMatch = {
  field: "title" | "description" | "project_path" | "status" | "assigned_agent";
  start: number;
  end: number;
};

export type ProjectTodoSearchResult = {
  id: string;
  client_id: string;
  project_path: string;
  title: string;
  description: string | null;
  status: ProjectTodoStatus;
  assigned_window_id: string | null;
  assigned_agent: string | null;
  updated_at: string;
  matches: ProjectTodoSearchMatch[];
};

export type ProjectTodoSearchResponse = {
  query: string;
  results: ProjectTodoSearchResult[];
  total: number;
  limit: number;
  offset: number;
  has_more: boolean;
};

export type ProjectTodoWorkSnapshot = {
  id: string;
  todo_id: string;
  client_id: string;
  project_path: string;
  window_id: string | null;
  role: string;
  branch_name: string | null;
  base_ref: string | null;
  base_sha: string | null;
  head_sha: string | null;
  commit_shas: string[];
  diff_stat: Record<string, unknown> | null;
  changed_files: Record<string, unknown>[];
  dirty_state: string;
  captured_at: string;
};

export type ProjectTodoWorkSnapshotList = {
  work_snapshots: ProjectTodoWorkSnapshot[];
};

export type ProjectTodoReviewTarget = {
  id: string;
  todo_id: string;
  work_snapshot_id: string;
  provider: string;
  external_id: string;
  url: string | null;
  status: string;
  base_sha: string | null;
  head_sha: string | null;
  created_at: string;
  updated_at: string;
};

export type ProjectTodoReviewTargetList = {
  review_targets: ProjectTodoReviewTarget[];
};

export type ProjectTodoReviewRun = {
  id: string;
  todo_id: string;
  review_target_id: string;
  review_window_id: string | null;
  agent_client: string | null;
  agent_profile_id: string | null;
  status: string;
  summary: string | null;
  findings: Record<string, unknown>[];
  test_commands: Record<string, unknown>[];
  started_at: string | null;
  completed_at: string | null;
  last_error: string | null;
  created_at: string;
  updated_at: string;
};

export type ProjectTodoReviewRunList = {
  review_runs: ProjectTodoReviewRun[];
};
