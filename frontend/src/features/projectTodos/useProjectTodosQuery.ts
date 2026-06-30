import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";

import { fetchProjectTodos, fetchWindowActivity } from "../../api";
import { activityHasWorkingTerminal } from "../../terminalTree";
import type { ProjectTodoListItem, WorkStatus } from "../../types";
import {
  PROJECT_TODO_BOARD_COLUMN_ORDER,
  projectTodoBoardColumn,
  type ProjectTodoBoardColumn
} from "./projectTodoDisplay";
import { projectTodoLatestFirst, projectTodoQueryKey } from "./projectTodoPanelUtils";
import { projectTodoDateFilterRequest, type ProjectTodoDateFilter } from "./projectTodoDateFilter";

type UseProjectTodosQueryArgs = {
  clientId: string;
  dateFilter?: ProjectTodoDateFilter;
  projectPath: string;
};

export function useProjectTodosQuery({ clientId, dateFilter, projectPath }: UseProjectTodosQueryArgs) {
  const queryKey = projectTodoQueryKey(clientId, projectPath, dateFilter);
  const dateFilterRequest = projectTodoDateFilterRequest(dateFilter);
  const todosQuery = useQuery({
    queryKey,
    queryFn: () => fetchProjectTodos(clientId, projectPath, dateFilterRequest),
    refetchInterval: 10000
  });
  const windowActivityQuery = useQuery({
    queryKey: ["window-activity", clientId, "project-todos", projectPath],
    queryFn: () => fetchWindowActivity(clientId, { projectPath }),
    refetchInterval: (query) => (activityHasWorkingTerminal(query.state.data) ? 3000 : 10000)
  });
  const todos = todosQuery.data?.todos ?? [];
  const agentWorkStatusByWindowId = useMemo(() => {
    const map = new Map<string, WorkStatus>();
    for (const todo of todos) {
      if (todo.assigned_window_id !== null && todo.assigned_terminal?.work_status !== undefined) {
        map.set(todo.assigned_window_id, todo.assigned_terminal.work_status);
      }
    }
    for (const windowActivity of windowActivityQuery.data?.windows ?? []) {
      map.set(windowActivity.window_id, windowActivity.work_status);
    }
    return map;
  }, [todos, windowActivityQuery.data]);
  const grouped = useMemo(() => {
    const map = new Map<ProjectTodoBoardColumn, ProjectTodoListItem[]>();
    for (const column of PROJECT_TODO_BOARD_COLUMN_ORDER) {
      map.set(column, []);
    }
    for (const todo of todos) {
      map.get(projectTodoBoardColumn(todo))?.push(todo);
    }
    for (const cards of map.values()) {
      cards.sort(projectTodoLatestFirst);
    }
    return map;
  }, [todos]);

  return {
    agentWorkStatusByWindowId,
    grouped,
    queryKey,
    todos,
    todosQuery,
    windowActivityQuery
  };
}
