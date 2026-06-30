import { useI18n } from "../i18n";
import type { ProjectTodo } from "../types";
import { projectTodoDispatchStageActive } from "./projectTodoDispatchStage";

type ProjectTodoTerminalActionsProps = {
  todo: ProjectTodo;
  projectPath: string;
  busy: boolean;
  commenting: boolean;
  commentDispatching?: boolean;
  onComment: () => void;
  onSelectWindow: (windowId: string, projectPath: string) => void;
};

export function ProjectTodoTerminalActions({
  todo,
  projectPath,
  busy,
  commenting,
  commentDispatching,
  onComment,
  onSelectWindow
}: ProjectTodoTerminalActionsProps) {
  const { t } = useI18n();
  const assignedWindowId = todo.assigned_window_id;
  const reviewWindowId = todo.review_window_id;
  const dispatching = commentDispatching ?? projectTodoDispatchStageActive(todo);

  if (!assignedWindowId && !reviewWindowId) {
    return null;
  }

  return (
    <section className="project-todo-action-group" aria-label={t("projectTodo.action.terminalActions")}>
      <header><strong>{t("projectTodo.create.terminal")}</strong></header>
      <div className="project-todo-terminal-actions">
        {assignedWindowId && (
          <>
            <button
              type="button"
              className="project-todo-action-button project-todo-terminal-action"
              disabled={busy || commenting || dispatching}
              onClick={onComment}
            >
              {commenting || dispatching ? t("projectTodo.action.sending") : t("projectTodo.action.comment")}
            </button>
            <button
              type="button"
              className="project-todo-action-button project-todo-terminal-action"
              onClick={() => onSelectWindow(assignedWindowId, projectPath)}
            >
              {t("projectTodo.action.openTerminal")}
            </button>
          </>
        )}
        {reviewWindowId && (
          <button
            type="button"
            className="project-todo-action-button project-todo-terminal-action"
            onClick={() => onSelectWindow(reviewWindowId, projectPath)}
          >
            {t("projectTodo.action.openReviewTerminal")}
          </button>
        )}
      </div>
    </section>
  );
}
