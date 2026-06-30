import type { TranslateFn } from "../i18n";
import type { ProjectTodo, ProjectTodoDispatchStage } from "../types";

export type ProjectTodoDispatchTone = "gray" | "orange" | "red";

export function projectTodoDispatchStageActive(todo: Pick<ProjectTodo, "dispatch_stage">): boolean {
  return todo.dispatch_stage !== null && todo.dispatch_stage !== "FAILED";
}

export function projectTodoDispatchTone(stage: ProjectTodoDispatchStage | null): ProjectTodoDispatchTone | null {
  if (stage === null) {
    return null;
  }
  if (stage === "FAILED") {
    return "red";
  }
  if (stage === "TERMINAL_READY") {
    return "orange";
  }
  return "gray";
}

export function projectTodoDispatchTitle(
  stage: ProjectTodoDispatchStage | null,
  error: string | null,
  t?: TranslateFn
): string | null {
  switch (stage) {
    case "STARTING":
      return t?.("projectTodo.dispatch.stage.starting") ?? "Dispatch: creating terminal";
    case "WINDOW_CREATED":
      return t?.("projectTodo.dispatch.stage.windowCreated") ?? "Dispatch: terminal created";
    case "TERMINAL_READY":
      return t?.("projectTodo.dispatch.stage.terminalReady") ?? "Dispatch: terminal ready";
    case "verifying":
      return t?.("projectTodo.dispatch.stage.verifying") ?? "Dispatch: verifying completion";
    case "FAILED":
      return error?.trim()
        ? t?.("projectTodo.dispatch.stage.failedWithReason", { reason: error.trim() }) ?? `Dispatch failed: ${error.trim()}`
        : t?.("projectTodo.dispatch.stage.failed") ?? "Dispatch failed";
    default:
      return null;
  }
}
