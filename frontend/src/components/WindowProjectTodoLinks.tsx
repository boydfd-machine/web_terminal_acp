import { useQuery } from "@tanstack/react-query";

import { fetchProjectTodos } from "../api";
import { useI18n } from "../i18n";
import { projectTodoStatusLabel } from "../features/projectTodos/projectTodoDisplay";

type WindowProjectTodoLinksProps = {
  clientId: string;
  projectPath: string | null;
  windowId: string;
  onFocusProjectTodo: (projectPath: string, todoId: string) => void;
};

export function WindowProjectTodoLinks({
  clientId,
  projectPath,
  windowId,
  onFocusProjectTodo
}: WindowProjectTodoLinksProps) {
  const { t } = useI18n();
  const todosQuery = useQuery({
    queryKey: ["project-todos", clientId, projectPath],
    queryFn: () => fetchProjectTodos(clientId, projectPath as string),
    enabled: projectPath !== null,
    refetchInterval: 10000
  });
  const assignedTodos = (todosQuery.data?.todos ?? []).filter((todo) => todo.assigned_window_id === windowId);

  if (projectPath === null) {
    return <span className="detail-value-text muted">-</span>;
  }
  if (todosQuery.isLoading) {
    return <span className="detail-value-text muted">{t("common.loading")}</span>;
  }
  if (todosQuery.isError) {
    return <span className="detail-value-text error">{t("projectTodo.panel.loadFailed")}</span>;
  }
  if (assignedTodos.length === 0) {
    return <span className="detail-value-text muted">-</span>;
  }

  return (
    <span className="window-project-todo-links">
      {assignedTodos.map((todo) => (
        <button
          key={todo.id}
          type="button"
          onClick={() => onFocusProjectTodo(projectPath, todo.id)}
        >
          <span>{todo.title}</span>
          <strong>{projectTodoStatusLabel(todo.status, t)}</strong>
        </button>
      ))}
    </span>
  );
}
