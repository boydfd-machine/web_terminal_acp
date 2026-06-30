import { useMemo, useState } from "react";

import type { ProjectTodoListItem } from "../../types";
import {
  PROJECT_TODO_BOARD_ALL,
  defaultProjectTodoBoardFilters,
  type ProjectTodoBoardFilters
} from "./projectTodoBoardModel";

export function useProjectTodoBoardFilters(todos: ProjectTodoListItem[]) {
  const [filters, setFilters] = useState<ProjectTodoBoardFilters>(() => defaultProjectTodoBoardFilters());
  const todoById = useMemo(() => new Map(todos.map((todo) => [todo.id, todo])), [todos]);
  const childFilterParentId = filters.parentTodoId === PROJECT_TODO_BOARD_ALL ? null : filters.parentTodoId;
  const childFilterParent = childFilterParentId === null ? null : todoById.get(childFilterParentId) ?? null;

  return {
    childFilterParent,
    childFilterParentId,
    filters,
    resetChildFilter: () => setFilters((current) => ({ ...current, parentTodoId: PROJECT_TODO_BOARD_ALL })),
    resetFilters: () => setFilters(defaultProjectTodoBoardFilters()),
    setFilters,
    showChildTodos: (todo: ProjectTodoListItem) => setFilters((current) => ({ ...current, parentTodoId: todo.id })),
    todoById,
  };
}
