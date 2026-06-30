import type { DragEvent } from "react";

const PROJECT_TODO_DRAG_TYPE = "application/x-web-terminal-project-todo";

export const PROJECT_TODO_MERGE_HOVER_MS = 3000;

export function setProjectTodoDragData(event: DragEvent<HTMLElement>, todoId: string): void {
  event.dataTransfer.effectAllowed = "move";
  event.dataTransfer.setData(PROJECT_TODO_DRAG_TYPE, todoId);
  event.dataTransfer.setData("text/plain", todoId);
}

export function hasProjectTodoDragData(event: DragEvent<HTMLElement>, draggingTodoId: string | null): boolean {
  if (draggingTodoId !== null) {
    return true;
  }
  const types = Array.from(event.dataTransfer.types ?? []);
  if (types.includes(PROJECT_TODO_DRAG_TYPE)) {
    return true;
  }
  return Boolean(event.dataTransfer.getData(PROJECT_TODO_DRAG_TYPE));
}

export function projectTodoColumnDropTodoId(event: DragEvent<HTMLElement>, draggingTodoId: string | null): string {
  return (
    event.dataTransfer.getData(PROJECT_TODO_DRAG_TYPE)
    || event.dataTransfer.getData("text/plain")
    || draggingTodoId
    || ""
  );
}

export function projectTodoCardDropTodoId(event: DragEvent<HTMLElement>, draggingTodoId: string | null): string {
  return event.dataTransfer.getData(PROJECT_TODO_DRAG_TYPE) || draggingTodoId || "";
}
