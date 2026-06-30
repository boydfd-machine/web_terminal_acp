import { useI18n } from "../i18n";
import type { ProjectTodo, ProjectTodoStatus } from "../types";
import {
  projectTodoDispatchStageActive,
  projectTodoDispatchTitle,
  projectTodoDispatchTone,
} from "./projectTodoDispatchStage";

type ProjectTodoActionsProps = {
  todo: ProjectTodo;
  busy: boolean;
  dispatching: boolean;
  onDispatch: () => void;
  onSelectWindow: (windowId: string) => void;
  onStatus: (status: ProjectTodoStatus) => void;
};

export function ProjectTodoActions({
  todo,
  busy,
  dispatching,
  onDispatch,
  onSelectWindow,
  onStatus
}: ProjectTodoActionsProps) {
  const { t } = useI18n();
  const stageDispatching = projectTodoDispatchStageActive(todo);
  const dispatchTone = projectTodoDispatchTone(todo.dispatch_stage);
  const dispatchWaiting = todo.queued_dispatch && !stageDispatching;
  const dispatchTitle = projectTodoDispatchTitle(todo.dispatch_stage, todo.dispatch_error, t)
    ?? (dispatchWaiting ? t("projectTodo.dispatch.waiting") : null);
  const dispatchBusy = dispatching || stageDispatching;
  if (todo.status === "DONE") {
    return (
      <div className="project-todo-actions">
        <button type="button" disabled={busy} onClick={() => onStatus("TODO")}>{t("projectTodo.action.reopen")}</button>
      </div>
    );
  }

  if (todo.status === "AWAITING_REVIEW") {
    return (
      <div className="project-todo-actions">
        <button type="button" disabled={busy} onClick={() => onStatus("DONE")}>{t("projectTodo.action.done")}</button>
        <button type="button" disabled={busy} onClick={() => onStatus("TODO")}>{t("projectTodo.action.reopen")}</button>
      </div>
    );
  }

  if (todo.status === "DISPATCHED") {
    return (
      <div className="project-todo-actions">
        {todo.assigned_window_id && (
          <button type="button" onClick={() => onSelectWindow(todo.assigned_window_id as string)}>{t("projectTodo.action.open")}</button>
        )}
        <button type="button" disabled={busy} onClick={() => onStatus("AWAITING_REVIEW")}>{t("projectTodo.action.review")}</button>
      </div>
    );
  }

  if (todo.status === "BLOCKED") {
    return (
      <div className="project-todo-actions">
        <button type="button" disabled={busy} onClick={() => onStatus("TODO")}>{t("projectTodo.action.unblock")}</button>
      </div>
    );
  }

  return (
    <div className="project-todo-actions">
      <button
        type="button"
        disabled={busy || dispatchBusy || dispatchWaiting}
        title={dispatchTitle ?? undefined}
        onClick={onDispatch}
      >
        {dispatchBusy && (
          <span
            className={`terminal-create-progress-spinner project-todo-button-spinner ${dispatchTone ?? "blue"}`}
            aria-hidden="true"
          />
        )}
        <span>{dispatchBusy ? t("projectTodo.action.starting") : dispatchWaiting ? t("projectTodo.action.pending") : t("projectTodo.action.dispatch")}</span>
      </button>
      <button type="button" disabled={busy || dispatchBusy} onClick={() => onStatus("BLOCKED")}>
        {t("projectTodo.action.block")}
      </button>
    </div>
  );
}
