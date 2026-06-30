export type WorkStatusState = "LONG_IDLE" | "RECENT_ACTIVE" | "WORKING" | "FINISHED" | "ABORTED" | "FAILED";

export type WorkStatus = {
  state: WorkStatusState;
  label: string;
  color: "gray" | "green" | "orange" | "red";
  last_activity_at?: string | null;
  last_working_activity_at?: string | null;
  source?: "activity" | "manual";
  manual_updated_at?: string | null;
};

export type TreeWindowCore = {
  id: string;
  title: string;
  status: string;
  title_tags?: string[] | null;
  created_at: string;
  parent_window_id?: string | null;
  root_window_id?: string | null;
  derived_mode?: string | null;
};

export type GitWorktreeActivity = {
  worktree_root: string;
  main_repo_root: string;
  branch?: string | null;
  pending_commit: boolean;
  merge_status?: "merged" | "unmerged" | "conflict" | "unknown";
  merge_status_reason?: string | null;
  merged_to_main?: boolean | null;
  merge_attention_required?: boolean;
  main_branch?: string | null;
  main_head_sha?: string | null;
  main_merge_head_sha?: string | null;
  main_merge_in_progress?: boolean;
  main_merge_matches_worktree?: boolean | null;
  unmerged_files?: string[];
};

export type AgentTokenUsageCounts = {
  input_tokens: number;
  output_tokens: number;
  total_tokens: number;
  cached_input_tokens: number;
  cache_creation_input_tokens: number;
  reasoning_output_tokens: number;
};

export type AgentTokenUsage = {
  context: AgentTokenUsageCounts | null;
  total: AgentTokenUsageCounts;
  context_window: number | null;
  auto_compact_token_limit?: number | null;
  latest_event_at: string | null;
  providers: string[];
  event_count: number;
};

export type WindowActivity = {
  work_status: WorkStatus;
  runtime_tags: string[];
  todo_title?: string | null;
  last_agent_task_completed_at?: string | null;
  last_agent_task_status?: "FINISHED" | "ABORTED" | "FAILED" | null;
  last_agent_task_status_at?: string | null;
  git_worktree?: GitWorktreeActivity | null;
  parent_window_id?: string | null;
  root_window_id?: string | null;
  derived_mode?: string | null;
};

export type TreeWindow = TreeWindowCore & WindowActivity;

export type ClientWindowsActivity = {
  windows: Array<WindowActivity & { window_id: string }>;
};

export type TerminalProject = {
  project_path: string;
  window_count: number;
};

export type TerminalNotification = {
  id: string;
  client_id: string;
  window_id: string;
  window_title: string;
  completed_at: string;
  status: "FINISHED" | "ABORTED" | "FAILED";
  read: boolean;
};

export type TerminalNotificationList = {
  notifications: TerminalNotification[];
};

export type TreeFolderCore = {
  id: string;
  name: string;
  path: string;
  folders: TreeFolderCore[];
  windows: TreeWindowCore[];
};

export type TreeFolder = {
  id: string;
  name: string;
  path: string;
  folders: TreeFolder[];
  windows: TreeWindow[];
};

export type SummaryJobStatus = "PENDING" | "RUNNING" | "SUCCEEDED" | "FAILED";

export type SummaryJob = {
  id: string;
  status: SummaryJobStatus | string;
  attempts: number;
  last_error: string | null;
  trigger_reason: string | null;
  run_after: string | null;
  created_at?: string;
  updated_at?: string;
};

export type VirtualWindow = {
  id: string;
  client_id: string;
  title: string;
  folder_id: string | null;
  parent_window_id: string | null;
  root_window_id: string | null;
  derived_mode: string | null;
  derived_context: Record<string, unknown> | null;
  status: string;
  tmux_session: string | null;
  tmux_window_id: string | null;
  tmux_window_index: string | null;
  remote_session_id: string | null;
  remote_window_id: string | null;
  cwd: string | null;
  shell_command: string | null;
  summary: string | null;
  title_tags: string[] | null;
  runtime_tags: string[];
  git_worktree?: GitWorktreeActivity | null;
  agent_token_usage?: AgentTokenUsage | null;
  work_status: WorkStatus;
  title_manually_overridden: boolean;
  folder_manually_overridden: boolean;
  command_capture_supported: boolean;
  summary_job: SummaryJob | null;
  created_at: string;
  last_terminal_command_at: string | null;
  last_agent_event_at: string | null;
  last_active_at: string;
};

export type CommandHistoryItem = {
  id: string;
  command: string;
  shell: string | null;
  cwd: string | null;
  sequence: number | string | null;
  exit_status: number | string | null;
  captured_at: string;
  finished_at: string | null;
  created_at: string;
};

export type CommandHistory = {
  window_id: string;
  commands: CommandHistoryItem[];
  commands_total: number;
  commands_limit: number;
  commands_offset: number;
  commands_has_more: boolean;
};

export type WindowTitleHistoryItem = {
  id: string;
  title: string;
  summary: string | null;
  source: string;
  created_at: string;
};

export type WindowTitleHistory = {
  window_id: string;
  items: WindowTitleHistoryItem[];
  total: number;
  limit: number;
  offset: number;
  has_more: boolean;
};
