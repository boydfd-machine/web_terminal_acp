import { useCallback, type Dispatch, type SetStateAction } from "react";
import type { QueryClient } from "@tanstack/react-query";

import type { ProjectTodoList as ProjectTodoListPayload, ProjectTodoListItem } from "../../types";
import { projectTodoQueryKey, type EditingTodoField, type TodoUpdateVariables } from "./projectTodoPanelUtils";

type UseProjectTodoOpenHandlersArgs = {
  queryClient: QueryClient;
  queryKey: ReturnType<typeof projectTodoQueryKey>;
  todos: ProjectTodoListItem[];
  updateMutation: {
    isPending: boolean;
    mutate: (variables: TodoUpdateVariables) => void;
  };
  setEditingTodoField: Dispatch<SetStateAction<EditingTodoField | null>>;
  setFocusedSelectionRequestKey: Dispatch<SetStateAction<string | null>>;
  setSelectedTodoId: Dispatch<SetStateAction<string | null>>;
};

export function useProjectTodoOpenHandlers({
  queryClient,
  queryKey,
  todos,
  updateMutation,
  setEditingTodoField,
  setFocusedSelectionRequestKey,
  setSelectedTodoId
}: UseProjectTodoOpenHandlersArgs) {
  const openTodo = useCallback((todoId: string, source: "manual" | "focus" = "manual") => {
    setSelectedTodoId(todoId);
    if (source === "manual") {
      setFocusedSelectionRequestKey(null);
    }
    const todo = todos.find((candidate) => candidate.id === todoId);
    if (todo === undefined || !todo.review_unseen || updateMutation.isPending) {
      return;
    }
    const previousTodos = queryClient.getQueryData<ProjectTodoListPayload>(queryKey);
    queryClient.setQueryData<ProjectTodoListPayload>(queryKey, (current) => current === undefined
      ? current
      : {
          todos: current.todos.map((currentTodo) => currentTodo.id === todo.id
            ? { ...currentTodo, review_unseen: false }
            : currentTodo)
        });
    updateMutation.mutate({
      todo,
      input: { review_unseen: false },
      optimisticPrevious: previousTodos
    });
  }, [queryClient, queryKey, setFocusedSelectionRequestKey, setSelectedTodoId, todos, updateMutation]);

  const closeDetail = () => {
    setSelectedTodoId(null);
    setEditingTodoField(null);
  };

  return { closeDetail, openTodo };
}
