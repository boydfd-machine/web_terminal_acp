import { useCallback } from "react";
import type { QueryClient } from "@tanstack/react-query";

import type {
  ProjectTodoList as ProjectTodoListPayload,
  ProjectTodoListItem,
  ProjectTodoStatus
} from "../../types";
import type { ProjectTodoBoardColumn } from "./projectTodoDisplay";
import { projectTodoQueryKey, type TodoUpdateVariables } from "./projectTodoPanelUtils";

type TodoStatusMutation = {
  isPending: boolean;
  mutate: (variables: TodoUpdateVariables) => void;
};

type UseProjectTodoMoveHandlerArgs = {
  grouped: Map<ProjectTodoBoardColumn, ProjectTodoListItem[]>;
  queryClient: QueryClient;
  queryKey: ReturnType<typeof projectTodoQueryKey>;
  todos: ProjectTodoListItem[];
  updateMutation: TodoStatusMutation;
};

export function useProjectTodoMoveHandler({
  grouped,
  queryClient,
  queryKey,
  todos,
  updateMutation
}: UseProjectTodoMoveHandlerArgs) {
  return useCallback((todoId: string, nextStatus: ProjectTodoStatus) => {
    const todo = todos.find((candidate) => candidate.id === todoId);
    if (todo === undefined || (todo.status === nextStatus && !todo.queued_dispatch) || updateMutation.isPending) {
      return;
    }
    const previousTodos = queryClient.getQueryData<ProjectTodoListPayload>(queryKey);
    const nextSortOrder = Math.max(
      0,
      ...((grouped.get(nextStatus) ?? []).map((candidate) => candidate.sort_order))
    ) + 1;
    queryClient.setQueryData<ProjectTodoListPayload>(queryKey, (current) => current === undefined
      ? current
      : {
          todos: current.todos.map((currentTodo) => currentTodo.id === todo.id
            ? optimisticProjectTodoMove(currentTodo, nextStatus, nextSortOrder)
            : currentTodo)
        });
    updateMutation.mutate({
      todo,
      input: {
        status: nextStatus,
        sort_order: nextSortOrder
      },
      optimisticPrevious: previousTodos
    });
  }, [grouped, queryClient, queryKey, todos, updateMutation]);
}

export function optimisticProjectTodoMove(
  todo: ProjectTodoListItem,
  nextStatus: ProjectTodoStatus,
  nextSortOrder: number
): ProjectTodoListItem {
  const movedTodo = {
    ...todo,
    status: nextStatus,
    sort_order: nextSortOrder,
    queued_dispatch: false
  };
  if (nextStatus !== "TODO") {
    return movedTodo;
  }
  return {
    ...movedTodo,
    dispatch_stage: null,
    dispatch_error: null,
    review_status: "NOT_REQUESTED",
    review_unseen: false,
    needs_human_review: false,
    implementation_worktree: null
  };
}
