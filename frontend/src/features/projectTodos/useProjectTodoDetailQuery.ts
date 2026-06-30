import { useQuery } from "@tanstack/react-query";

import { fetchProjectTodo } from "../../api";
import { ApiError, apiErrorDetailText } from "../../apiCore";
import { projectTodoDetailQueryKey, projectTodoFocusRequestKey } from "./projectTodoPanelUtils";

export { projectTodoFocusRequestKey };

export function useProjectTodoDetailQuery(clientId: string, projectPath: string, todoId: string | null) {
  return useQuery({
    queryKey: todoId === null
      ? ["project-todo", clientId, projectPath, "none"]
      : projectTodoDetailQueryKey(clientId, projectPath, todoId),
    queryFn: () => fetchProjectTodo(clientId, projectPath, todoId as string),
    enabled: todoId !== null,
    meta: { suppressProjectTodoNotFoundToast: true },
    staleTime: 5000
  });
}

export function isProjectTodoNotFoundError(error: unknown): boolean {
  return error instanceof ApiError
    && error.status === 404
    && apiErrorDetailText(error.detail) === "todo not found";
}
