import { useI18n } from "../i18n";
import type { ProjectTodo, ProjectTodoArtifact } from "../types";
import { ProjectTodoArtifactsPanel } from "./ProjectTodoArtifactsPanel";
import { ProjectTodoWorktreeSummary } from "./ProjectTodoWorktreeSummary";

type ProjectTodoReviewContextProps = {
  clientId: string;
  isMobileLayout?: boolean;
  todo: ProjectTodo;
  onOpenArtifact?: (artifact: ProjectTodoArtifact) => void;
};

export function ProjectTodoReviewContext({
  clientId,
  isMobileLayout = false,
  todo,
  onOpenArtifact
}: ProjectTodoReviewContextProps) {
  const { t } = useI18n();
  return (
    <section className="project-todo-review-panel" aria-label={t("projectTodo.review.todoReview")}>
      <header>
        <strong>{t("projectTodo.review.context")}</strong>
      </header>
      <ProjectTodoWorktreeSummary
        clientId={clientId}
        isMobileLayout={isMobileLayout}
        worktree={todo.implementation_worktree}
      />
      {todo.review_notes && <p className="project-todo-review-notes">{todo.review_notes}</p>}
      <ProjectTodoArtifactsPanel artifacts={todo.artifacts} onOpenArtifact={onOpenArtifact} />
    </section>
  );
}
