import type { ProjectTodoCreationPendingRequest } from "../appState";
import { useI18n } from "../i18n";

type ProjectTodoCreationPendingDialogProps = {
  request: ProjectTodoCreationPendingRequest | null;
};

export function ProjectTodoCreationPendingDialog({
  request
}: ProjectTodoCreationPendingDialogProps) {
  const { t } = useI18n();
  if (request === null) {
    return null;
  }

  return (
    <div className="project-todo-detail-backdrop project-todo-creation-pending-backdrop">
      <section
        className="project-todo-creation-pending-dialog"
        role="status"
        aria-live="polite"
        aria-label={t("projectTodo.creationPending.label", { title: request.title })}
      >
        <span className="terminal-create-progress-spinner blue project-todo-creation-pending-spinner" aria-hidden="true" />
        <strong>{t("projectTodo.creationPending.title")}</strong>
      </section>
    </div>
  );
}
