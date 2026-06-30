import type { TranslateFn, TranslationKey } from "../../i18n";
import type { ProjectTodoListItem, ProjectTodoReviewStatus, ProjectTodoStatus, ProjectTodoType } from "../../types";

export type ProjectTodoBoardColumn = ProjectTodoStatus | "PENDING";

const PROJECT_TODO_STATUS_KEYS: Record<ProjectTodoStatus, TranslationKey> = {
  TODO: "projectTodo.status.todo",
  BLOCKED: "projectTodo.status.blocked",
  DISPATCHED: "projectTodo.status.dispatched",
  AWAITING_REVIEW: "projectTodo.status.awaitingReview",
  DONE: "projectTodo.status.done"
};

const PROJECT_TODO_REVIEW_STATUS_KEYS: Record<ProjectTodoReviewStatus, TranslationKey> = {
  NOT_REQUESTED: "projectTodo.review.notRequested",
  PENDING: "projectTodo.review.pending",
  RUNNING: "projectTodo.review.running",
  REVIEWED: "projectTodo.review.reviewed",
  APPROVED: "projectTodo.review.approved",
  CHANGES_REQUESTED: "projectTodo.review.changesRequested",
  NEEDS_HUMAN_REVIEW: "projectTodo.review.needsHuman"
};

export const PROJECT_TODO_STATUS_LABELS: Record<ProjectTodoStatus, string> = {
  TODO: "Todo",
  BLOCKED: "Blocked",
  DISPATCHED: "Running",
  AWAITING_REVIEW: "Review",
  DONE: "Done"
};

export const PROJECT_TODO_BOARD_COLUMN_LABELS: Record<ProjectTodoBoardColumn, string> = {
  ...PROJECT_TODO_STATUS_LABELS,
  PENDING: "Pending"
};

export const PROJECT_TODO_BOARD_COLUMN_ORDER: ProjectTodoBoardColumn[] = [
  "TODO",
  "PENDING",
  "DISPATCHED",
  "AWAITING_REVIEW",
  "DONE",
  "BLOCKED"
];

export const PROJECT_TODO_REVIEW_STATUS_LABELS: Record<ProjectTodoReviewStatus, string> = {
  NOT_REQUESTED: "Not requested",
  PENDING: "Review requested",
  RUNNING: "Review running",
  REVIEWED: "Reviewed",
  APPROVED: "Approved",
  CHANGES_REQUESTED: "Changes requested",
  NEEDS_HUMAN_REVIEW: "Human review"
};

export function projectTodoStatusLabel(status: ProjectTodoStatus, t?: TranslateFn): string {
  return t?.(PROJECT_TODO_STATUS_KEYS[status]) ?? PROJECT_TODO_STATUS_LABELS[status];
}

export function projectTodoBoardColumnLabel(column: ProjectTodoBoardColumn, t?: TranslateFn): string {
  return column === "PENDING"
    ? t?.("projectTodo.status.pending") ?? PROJECT_TODO_BOARD_COLUMN_LABELS.PENDING
    : projectTodoStatusLabel(column, t);
}

export function projectTodoReviewStatusLabel(status: ProjectTodoReviewStatus, t?: TranslateFn): string {
  return t?.(PROJECT_TODO_REVIEW_STATUS_KEYS[status]) ?? PROJECT_TODO_REVIEW_STATUS_LABELS[status];
}

export function projectTodoTypeLabel(todoType: ProjectTodoType, t?: TranslateFn): string {
  const label = todoType.name.trim() || todoType.id;
  return todoType.scope === "project" ? t?.("projectTodo.create.projectType", { label }) ?? `${label} (Project)` : label;
}

export function formatProjectTodoDate(value: string | null | undefined): string {
  if (!value) {
    return "";
  }
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString();
}

export function formatProjectTodoShortDate(value: string | null | undefined): string {
  if (!value) {
    return "";
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return date.toLocaleString(undefined, {
    month: "numeric",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit"
  });
}

export function projectTodoStatusClass(status: ProjectTodoStatus): string {
  return `project-todo-status-${status.toLowerCase().replace(/_/g, "-")}`;
}

export function projectTodoBoardColumn(
  todo: Pick<ProjectTodoListItem, "status" | "queued_dispatch" | "dispatch_stage">
): ProjectTodoBoardColumn {
  // While the dispatch runtime is still starting the terminal, the card sits
  // in the PENDING column. Once the agent is running, we keep the card in its
  // real status column even during the post-completion "verifying" stage so
  // the user does not see the card flicker from running → waiting → running
  // before reaching review. The verifying state is part of the agent's work,
  // not a queued dispatch.
  if (
    todo.dispatch_stage !== null
    && todo.dispatch_stage !== "FAILED"
    && todo.dispatch_stage !== "verifying"
  ) {
    return "PENDING";
  }
  if (todo.queued_dispatch) {
    return "PENDING";
  }
  if (todo.status === "BLOCKED") {
    return "BLOCKED";
  }
  return todo.status;
}
