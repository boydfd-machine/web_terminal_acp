import { useCallback } from "react";
import type { QueryClient } from "@tanstack/react-query";

import type { ProjectTodo, ProjectTodoList as ProjectTodoListPayload } from "../../types";
import { projectTodoUpdatedAtMatchesDateFilter, type ProjectTodoDateFilter } from "./projectTodoDateFilter";
import {
  projectTodoDetailQueryKey,
  upsertProjectTodoInList,
  type projectTodoQueryKey
} from "./projectTodoPanelUtils";

type UseProjectTodoCacheUpdatesArgs = {
  clientId: string;
  dateFilter?: ProjectTodoDateFilter;
  projectPath: string;
  queryClient: QueryClient;
  queryKey: ReturnType<typeof projectTodoQueryKey>;
};

export function useProjectTodoCacheUpdates({
  clientId,
  dateFilter,
  projectPath,
  queryClient,
  queryKey
}: UseProjectTodoCacheUpdatesArgs) {
  return useCallback((todo: ProjectTodo) => {
    queryClient.setQueryData(projectTodoDetailQueryKey(clientId, projectPath, todo.id), todo);
    queryClient.setQueryData<ProjectTodoListPayload>(
      queryKey,
      (current) => upsertProjectTodoInList(current, todo, {
        allowInsert: projectTodoUpdatedAtMatchesDateFilter(todo, dateFilter)
      })
    );
    void queryClient.invalidateQueries({ queryKey, refetchType: "none" });
  }, [clientId, dateFilter, projectPath, queryClient, queryKey]);
}
