import { useI18n, type TranslateFn } from "../i18n";
import type { ProjectTodo, ProjectTodoRelation } from "../types";
import {
  formatProjectTodoDate,
  projectTodoStatusLabel,
  projectTodoStatusClass,
} from "./projectTodoDisplay";

export function ProjectTodoRelations({
  todo,
  onOpenTodo
}: {
  todo: ProjectTodo;
  onOpenTodo?: (todoId: string) => void;
}) {
  const { t } = useI18n();
  const hasRelatedCards = todo.parent_todo !== null
    || todo.dependencies.length > 0
    || todo.dependents.length > 0;
  if (
    !hasRelatedCards
  ) {
    return null;
  }

  return (
    <section className="project-todo-relations" aria-label={t("projectTodo.relations.todoDependencies")}>
      <header>
        <strong>{t("projectTodo.relations.relatedCards")}</strong>
        {todo.queued_dispatch && <span>{t("projectTodo.relations.queued")}</span>}
      </header>
      {todo.parent_todo !== null && (
        <ProjectTodoRelationList
          title={t("projectTodo.relations.parent")}
          items={[todo.parent_todo]}
          t={t}
          onOpenTodo={onOpenTodo}
        />
      )}
      {todo.dependencies.length > 0 && (
        <ProjectTodoRelationList
          title={t("projectTodo.relations.waitsFor")}
          items={todo.dependencies}
          t={t}
          onOpenTodo={onOpenTodo}
        />
      )}
      {todo.dependents.length > 0 && (
        <ProjectTodoRelationList
          title={t("projectTodo.relations.blocks")}
          items={todo.dependents}
          t={t}
          onOpenTodo={onOpenTodo}
        />
      )}
    </section>
  );
}

function ProjectTodoRelationList({
  title,
  items,
  t,
  onOpenTodo,
}: {
  title: string;
  items: ProjectTodoRelation[];
  t: TranslateFn;
  onOpenTodo?: (todoId: string) => void;
}) {
  return (
    <div className="project-todo-relation-list">
      <span>{title}</span>
      <ul>
        {items.map((item) => (
          <li key={item.id}>
            <span className={`project-todo-status-pill ${projectTodoStatusClass(item.status)}`}>
              {projectTodoStatusLabel(item.status, t)}
            </span>
            {onOpenTodo === undefined ? (
              <strong>{item.title}</strong>
            ) : (
              <button type="button" onClick={() => onOpenTodo(item.id)}>
                <strong>{item.title}</strong>
              </button>
            )}
            <small>{formatProjectTodoDate(item.completed_at) || "-"}</small>
          </li>
        ))}
      </ul>
    </div>
  );
}
