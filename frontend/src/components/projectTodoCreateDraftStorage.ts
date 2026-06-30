import type {
  AgentModelSelection,
  ProjectTodoExecutionKind,
  ProjectTodoTerminalPolicy,
  ProjectTodoTriggerStrategy
} from "../types";

export type ProjectTodoCreateDraft = {
  title: string;
  description: string;
  parent_todo_id: string;
  todo_type_id: string;
  execution_kind: ProjectTodoExecutionKind;
  terminal_policy: ProjectTodoTerminalPolicy;
  trigger_strategy: ProjectTodoTriggerStrategy;
  cron_expression: string;
  artifact_kinds: string[];
  input_artifact_ids: string[];
  artifact_model_selection: AgentModelSelection | null;
};

const PROJECT_TODO_CREATE_DRAFT_STORAGE_PREFIX = "web-terminal-acp:project-todo-create-draft:";

const EMPTY_PROJECT_TODO_CREATE_DRAFT: ProjectTodoCreateDraft = {
  title: "",
  description: "",
  parent_todo_id: "",
  todo_type_id: "default",
  execution_kind: "ONCE",
  terminal_policy: "NEW_TERMINAL",
  trigger_strategy: "MANUAL",
  cron_expression: "",
  artifact_kinds: [],
  input_artifact_ids: [],
  artifact_model_selection: null
};

export function projectTodoCreateDraftStorageKey(clientId: string, projectPath: string): string {
  return `${PROJECT_TODO_CREATE_DRAFT_STORAGE_PREFIX}${encodeURIComponent(clientId)}:${encodeURIComponent(projectPath)}`;
}

export function readProjectTodoCreateDraft(storageKey: string): ProjectTodoCreateDraft {
  try {
    const rawValue = window.localStorage.getItem(storageKey);
    if (rawValue === null) {
      return EMPTY_PROJECT_TODO_CREATE_DRAFT;
    }
    const parsed = JSON.parse(rawValue) as Partial<ProjectTodoCreateDraft>;
    return {
      title: typeof parsed.title === "string" ? parsed.title : "",
      description: typeof parsed.description === "string" ? parsed.description : "",
      parent_todo_id: typeof parsed.parent_todo_id === "string" ? parsed.parent_todo_id : "",
      todo_type_id: typeof parsed.todo_type_id === "string" && parsed.todo_type_id.trim().length > 0
        ? parsed.todo_type_id
        : "default",
      execution_kind: parsed.execution_kind === "PERIODIC" ? "PERIODIC" : "ONCE",
      terminal_policy: parsed.terminal_policy === "REUSE_LATEST" ? "REUSE_LATEST" : "NEW_TERMINAL",
      trigger_strategy: parsed.trigger_strategy === "CRON" ? "CRON" : "MANUAL",
      cron_expression: typeof parsed.cron_expression === "string" ? parsed.cron_expression : "",
      artifact_kinds: Array.isArray(parsed.artifact_kinds)
        ? parsed.artifact_kinds.filter((value): value is string => typeof value === "string")
        : [],
      input_artifact_ids: Array.isArray(parsed.input_artifact_ids)
        ? parsed.input_artifact_ids.filter((value): value is string => typeof value === "string")
        : [],
      artifact_model_selection: isAgentModelSelection(parsed.artifact_model_selection)
        ? parsed.artifact_model_selection
        : null
    };
  } catch {
    return EMPTY_PROJECT_TODO_CREATE_DRAFT;
  }
}

export function writeProjectTodoCreateDraft(storageKey: string, draft: ProjectTodoCreateDraft): void {
  try {
    const storageValue = projectTodoCreateDraftStorageValue(draft);
    if (Object.keys(storageValue).length === 0) {
      window.localStorage.removeItem(storageKey);
      return;
    }
    window.localStorage.setItem(storageKey, JSON.stringify(storageValue));
  } catch {
    return;
  }
}

export function clearProjectTodoCreateDraft(storageKey: string): void {
  try {
    window.localStorage.removeItem(storageKey);
  } catch {
    return;
  }
}

function projectTodoCreateDraftStorageValue(
  draft: ProjectTodoCreateDraft
): Partial<ProjectTodoCreateDraft> {
  const value: Partial<ProjectTodoCreateDraft> = {};
  if (draft.title.length > 0) {
    value.title = draft.title;
  }
  if (draft.description.length > 0) {
    value.description = draft.description;
  }
  if (draft.parent_todo_id.length > 0) {
    value.parent_todo_id = draft.parent_todo_id;
  }
  if (draft.todo_type_id !== "default") {
    value.todo_type_id = draft.todo_type_id;
  }
  if (draft.execution_kind !== "ONCE") {
    value.execution_kind = draft.execution_kind;
  }
  if (draft.terminal_policy !== "NEW_TERMINAL") {
    value.terminal_policy = draft.terminal_policy;
  }
  if (draft.trigger_strategy !== "MANUAL") {
    value.trigger_strategy = draft.trigger_strategy;
  }
  if (draft.cron_expression.length > 0) {
    value.cron_expression = draft.cron_expression;
  }
  if (draft.artifact_kinds.length > 0) {
    value.artifact_kinds = draft.artifact_kinds;
  }
  if (draft.input_artifact_ids.length > 0) {
    value.input_artifact_ids = draft.input_artifact_ids;
  }
  if (draft.artifact_model_selection !== null) {
    value.artifact_model_selection = draft.artifact_model_selection;
  }
  return value;
}

function isAgentModelSelection(value: unknown): value is AgentModelSelection {
  if (value === null || typeof value !== "object") {
    return false;
  }
  const candidate = value as Partial<AgentModelSelection>;
  return typeof candidate.preset_id === "string" && candidate.preset_id.trim().length > 0;
}
