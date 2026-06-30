import type { ProjectTodoFocusRequest } from "../../appState";
import type {
  AgentModelSelection,
  ArtifactScope,
  ProjectTodo,
  ProjectTodoArtifact,
  ProjectTodoDispatchMode,
  ProjectTodoListItem,
  ProjectTodoList as ProjectTodoListPayload,
  ProjectTodoReviewStatus,
  ProjectTodoStatus,
  ProjectTodoTriggerStrategy
} from "../../types";
import type { TerminalCreateSubmit } from "../../components/TerminalCreateModal";
import type { TranslateFn } from "../../i18n";
import { PROJECT_TODO_BOARD_COLUMN_ORDER, projectTodoBoardColumn } from "./projectTodoDisplay";
import type { ProjectTodoDateFilter } from "./projectTodoDateFilter";
import { projectTodoDateFilterQueryKey } from "./projectTodoDateFilter";

export function upsertProjectTodoInList(
  current: ProjectTodoListPayload | undefined,
  todo: ProjectTodo,
  options: { allowInsert?: boolean } = {}
): ProjectTodoListPayload | undefined {
  if (current === undefined) {
    return current;
  }
  const exists = current.todos.some((candidate) => candidate.id === todo.id);
  if (!exists && options.allowInsert === false) {
    return current;
  }
  return {
    todos: exists
      ? current.todos.map((candidate) => candidate.id === todo.id ? todo : candidate)
      : [todo, ...current.todos]
  };
}

export function projectTodoQueryKey(
  clientId: string,
  projectPath: string,
  dateFilter?: ProjectTodoDateFilter
) {
  const dateFilterKey = projectTodoDateFilterQueryKey(dateFilter);
  return dateFilterKey === null
    ? ["project-todos", clientId, projectPath] as const
    : ["project-todos", clientId, projectPath, dateFilterKey] as const;
}

export function projectTodoDetailQueryKey(clientId: string, projectPath: string, todoId: string) {
  return ["project-todo", clientId, projectPath, todoId] as const;
}

export function projectTodoDetailFromListItem(todo: ProjectTodoListItem): ProjectTodo {
  return {
    ...todo,
    parent_todo: todo.parent_todo ?? null,
    description: todo.description ?? null,
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
    implementation_worktree: todo.implementation_worktree ?? null,
    artifact_kinds: todo.artifact_kinds ?? [],
    input_artifact_ids: todo.input_artifact_ids ?? [],
    assigned_terminal: todo.assigned_terminal ?? null,
    next_trigger_at: null,
    last_triggered_at: null,
    execution_runs: [],
    attachments: todo.attachments ?? [],
    artifacts: todo.artifacts ?? [],
    dependencies: [],
    dependents: [],
    child_todos: todo.child_todos ?? [],
    referenced_todos: [],
    queued_dispatch: todo.queued_dispatch ?? false
  };
}

export function projectTodoFocusRequestKey(focusRequest: ProjectTodoFocusRequest): string {
  return `${focusRequest.clientId}\n${focusRequest.projectPath}\n${focusRequest.todoId}\n${focusRequest.nonce}`;
}

export function projectTodoLatestFirst(first: ProjectTodoListItem, second: ProjectTodoListItem): number {
  const sortOrderDiff = second.sort_order - first.sort_order;
  if (sortOrderDiff !== 0) {
    return sortOrderDiff;
  }

  const updatedAtDiff = timestampValue(second.updated_at) - timestampValue(first.updated_at);
  if (updatedAtDiff !== 0) {
    return updatedAtDiff;
  }

  return second.id.localeCompare(first.id);
}

export function projectTodoBoardOrder(first: ProjectTodoListItem, second: ProjectTodoListItem): number {
  const firstColumnIndex = PROJECT_TODO_BOARD_COLUMN_ORDER.indexOf(projectTodoBoardColumn(first));
  const secondColumnIndex = PROJECT_TODO_BOARD_COLUMN_ORDER.indexOf(projectTodoBoardColumn(second));
  const columnDiff = firstColumnIndex - secondColumnIndex;
  if (columnDiff !== 0) {
    return columnDiff;
  }

  return projectTodoLatestFirst(first, second);
}

export const projectTodoDispatchErrorMessage = (error: unknown, t?: TranslateFn): string =>
  error instanceof Error && error.message.trim().length > 0 ? error.message : t?.("projectTodo.dispatch.failed") ?? "Dispatch failed.";

export const projectTodoCommentErrorMessage = (error: unknown, t?: TranslateFn): string =>
  error instanceof Error && error.message.trim().length > 0 ? error.message : t?.("projectTodo.comment.failed") ?? "Comment failed.";

export type TodoUpdateVariables = {
  todo: Pick<ProjectTodo, "id">;
  input: {
    title?: string;
    description?: string | null;
    parent_todo_id?: string | null;
    todo_type_id?: string;
    artifact_kinds?: string[];
    input_artifact_ids?: string[];
    status?: ProjectTodoStatus;
    sort_order?: number;
    review_status?: ProjectTodoReviewStatus;
    review_unseen?: boolean;
    needs_human_review?: boolean;
    review_notes?: string | null;
    trigger_strategy?: ProjectTodoTriggerStrategy;
    cron_expression?: string | null;
    schedule_enabled?: boolean;
  };
  optimisticPrevious?: ProjectTodoListPayload;
};

export type TodoDispatchVariables = {
  todo: ProjectTodo;
  payload: TerminalCreateSubmit;
  dispatchMode: ProjectTodoDispatchMode;
  dependencyIds: string[];
  prompt: string | null;
  artifactModelSelection: AgentModelSelection | null;
};

export type TodoCommentVariables = {
  todo: ProjectTodo;
  comment: string;
  artifactKinds?: string[];
};

export type TodoArtifactGenerateVariables = {
  todo: ProjectTodo;
  artifactKind: string;
  artifactScope: ArtifactScope;
  title: string;
};

export type TodoArtifactRetryVariables = {
  todo: ProjectTodoListItem;
  artifact: ProjectTodoArtifact;
};

export type TodoMergeVariables = {
  sourceTodoId: string;
  targetTodoId: string;
};

export type TodoProjectMoveVariables = {
  todo: ProjectTodo;
  targetProjectPath: string;
};

export type EditingTodoField = { todoId: string; field: "title" | "description" };

export function isReviewSeenOnlyUpdate(input: TodoUpdateVariables["input"]): boolean {
  return Object.keys(input).length === 1 && input.review_unseen === false;
}

function timestampValue(value: string): number {
  const parsed = Date.parse(value);
  return Number.isFinite(parsed) ? parsed : 0;
}
