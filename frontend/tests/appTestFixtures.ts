import type { ProjectTodo, ProjectTodoListItem, ProjectTodoType } from "../src/types";

const createdWindow = {
  id: "window-2",
  client_id: "client-1",
  title: "window-2",
  folder_id: null,
  parent_window_id: null,
  root_window_id: null,
  derived_mode: null,
  derived_context: null,
  status: "ACTIVE",
  tmux_session: "session",
  tmux_window_id: "2",
  tmux_window_index: "2",
  remote_session_id: null,
  remote_window_id: null,
  cwd: null,
  shell_command: null,
  summary: null,
  title_tags: [],
  runtime_tags: [],
  work_status: {
    state: "RECENT_ACTIVE",
    label: "recent active",
    color: "green"
  },
  title_manually_overridden: false,
  folder_manually_overridden: false,
  command_capture_supported: true,
  summary_job: null,
  created_at: "2026-05-31T00:00:00Z",
  last_terminal_command_at: null,
  last_agent_event_at: null,
  last_active_at: "2026-05-31T00:00:00Z"
};

const treeWindow = {
  id: "window-1",
  title: "Codex window",
  status: "ACTIVE",
  title_tags: [],
  created_at: "2026-05-31T00:00:00Z",
  parent_window_id: null,
  root_window_id: null,
  derived_mode: null
};

const clonedTreeWindow = {
  id: "window-2",
  title: "Codex clone",
  status: "ACTIVE",
  title_tags: ["linked"],
  created_at: "2026-05-31T00:01:00Z",
  parent_window_id: "window-1",
  root_window_id: "window-1",
  derived_mode: "linked"
};

const codexWindowActivity = {
  window_id: "window-1",
  work_status: {
    state: "RECENT_ACTIVE",
    label: "recent active",
    color: "green"
  },
  runtime_tags: ["codex", "/workspace"],
  last_agent_task_completed_at: null,
  last_agent_task_status: null,
  last_agent_task_status_at: null,
  git_worktree: null,
  parent_window_id: null,
  root_window_id: null,
  derived_mode: null
};

const clonedWindowActivity = {
  window_id: "window-2",
  work_status: {
    state: "RECENT_ACTIVE",
    label: "recent active",
    color: "green",
    last_activity_at: "2026-05-31T00:01:00Z"
  },
  runtime_tags: ["codex", "/workspace"],
  last_agent_task_completed_at: null,
  last_agent_task_status: null,
  last_agent_task_status_at: null,
  git_worktree: null,
  parent_window_id: "window-1",
  root_window_id: "window-1",
  derived_mode: "linked"
};

const codexWindowDetail = {
  id: "window-1",
  client_id: "client-1",
  title: "Codex window",
  folder_id: "folder-1",
  parent_window_id: null,
  root_window_id: null,
  derived_mode: null,
  derived_context: null,
  status: "ACTIVE",
  tmux_session: "session",
  tmux_window_id: "1",
  tmux_window_index: "1",
  remote_session_id: null,
  remote_window_id: null,
  cwd: "/workspace",
  shell_command: "codex",
  summary: null,
  title_tags: [],
  runtime_tags: ["codex", "/workspace"],
  work_status: codexWindowActivity.work_status,
  title_manually_overridden: false,
  folder_manually_overridden: false,
  command_capture_supported: true,
  summary_job: null,
  created_at: "2026-05-31T00:00:00Z",
  last_terminal_command_at: null,
  last_agent_event_at: null,
  last_active_at: "2026-05-31T00:00:00Z"
};

const clonedWindowDetail = {
  ...codexWindowDetail,
  id: "window-2",
  title: "Codex clone",
  parent_window_id: "window-1",
  root_window_id: "window-1",
  derived_mode: "linked",
  derived_context: { source_window_id: "window-1", mode: "linked" },
  work_status: clonedWindowActivity.work_status,
  created_at: "2026-05-31T00:01:00Z",
  last_active_at: "2026-05-31T00:01:00Z"
};

const otherTreeWindow = {
  id: "window-3",
  title: "Other window",
  status: "ACTIVE",
  title_tags: [],
  created_at: "2026-05-31T00:00:00Z",
  parent_window_id: null,
  root_window_id: null,
  derived_mode: null
};

const otherWindowActivity = {
  window_id: "window-3",
  work_status: {
    state: "RECENT_ACTIVE",
    label: "recent active",
    color: "green"
  },
  runtime_tags: ["claude_code", "/other"],
  last_agent_task_completed_at: null,
  last_agent_task_status: null,
  last_agent_task_status_at: null,
  git_worktree: null,
  parent_window_id: null,
  root_window_id: null,
  derived_mode: null
};

const otherWindowDetail = {
  ...codexWindowDetail,
  id: "window-3",
  title: "Other window",
  folder_id: "folder-2",
  cwd: "/other",
  shell_command: "claude",
  runtime_tags: ["claude_code", "/other"],
  work_status: otherWindowActivity.work_status
};

const runningArtifact = {
  id: "artifact-1",
  client_id: "client-1",
  virtual_window_id: "window-1",
  source_window_id: "window-1",
  ephemeral_window_id: "artifact-window-1",
  artifact_scope: "terminal",
  project_path: null,
  artifact_kind: "agent_trace_graph",
  title: "Trace graph",
  status: "RUNNING",
  content_json: null,
  display_html: null,
  metadata_json: null,
  last_error: null,
  started_at: "2026-05-31T00:00:00Z",
  completed_at: null,
  created_at: "2026-05-31T00:00:00Z",
  updated_at: "2026-05-31T00:00:00Z"
};

const defaultTodoType: ProjectTodoType = {
  id: "default",
  scope: "system",
  client_id: null,
  project_path: null,
  name: "Default",
  description: "Default project todo card type.",
  agent: null,
  agent_profile_id: null,
  artifact_kinds: [],
  input_artifact_ids: [],
  dispatch_template: null,
  created_at: "2026-06-05T00:00:00Z",
  updated_at: "2026-06-05T00:00:00Z"
};

const projectTodoListItem: ProjectTodoListItem = {
  id: "todo-1",
  client_id: "client-1",
  project_path: "/workspace",
  todo_type_id: "default",
  todo_type: defaultTodoType,
  parent_todo_id: null,
  parent_todo: null,
  title: "Fix board drag",
  status: "TODO",
  sort_order: 1,
  assigned_window_id: "window-1",
  assigned_agent: "codex",
  agent_profile_id: null,
  dispatch_stage: null,
  dispatch_error: null,
  review_status: "NOT_REQUESTED",
  review_unseen: false,
  needs_human_review: false,
  implementation_worktree: null,
  execution_kind: "ONCE",
  terminal_policy: "NEW_TERMINAL",
  trigger_strategy: "MANUAL",
  cron_expression: null,
  schedule_enabled: false,
  execution_run_count: 0,
  artifact_kinds: [],
  input_artifact_ids: [],
  assigned_terminal: null,
  artifacts: [],
  child_todos: [],
  queued_dispatch: false,
  created_at: "2026-06-05T00:00:00Z",
  updated_at: "2026-06-05T00:00:00Z"
};

const projectTodoDetail: ProjectTodo = {
  ...projectTodoListItem,
  description: "Drag regression context",
  dispatch_prompt: null,
  dispatched_at: null,
  awaiting_review_at: null,
  completed_at: null,
  review_strategy: "LOCAL_CARD",
  review_agent: null,
  review_agent_profile_id: null,
  review_window_id: null,
  review_prompt: null,
  review_dispatched_at: null,
  reviewed_at: null,
  review_notes: null,
  next_trigger_at: null,
  last_triggered_at: null,
  execution_runs: [],
  attachments: [],
  artifacts: [],
  dependencies: [],
  dependents: [],
  child_todos: [],
  referenced_todos: []
};

class TestPointerEvent extends MouseEvent {
  pointerId: number;
  pointerType: string;
  isPrimary: boolean;

  constructor(type: string, init: PointerEventInit = {}) {
    super(type, init);
    this.pointerId = init.pointerId ?? 1;
    this.pointerType = init.pointerType ?? "mouse";
    this.isPrimary = init.isPrimary ?? true;
  }
}


export {
  createdWindow,
  defaultTodoType,
  treeWindow,
  clonedTreeWindow,
  codexWindowActivity,
  clonedWindowActivity,
  codexWindowDetail,
  clonedWindowDetail,
  otherTreeWindow,
  otherWindowActivity,
  otherWindowDetail,
  projectTodoDetail,
  projectTodoListItem,
  runningArtifact,
  TestPointerEvent
};
