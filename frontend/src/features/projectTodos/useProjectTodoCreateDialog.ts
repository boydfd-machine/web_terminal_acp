import { useCallback, useState } from "react";

import type { ProjectTodo, ProjectTodoListItem } from "../../types";

export function useProjectTodoCreateDialog() {
  const [isOpen, setIsOpen] = useState(false);
  const [parentTodoId, setParentTodoId] = useState<string | null>(null);

  const openCreateTodo = useCallback(() => {
    setParentTodoId(null);
    setIsOpen(true);
  }, []);
  const openCreateChildTodo = useCallback((todo: ProjectTodoListItem | ProjectTodo) => {
    setParentTodoId(todo.id);
    setIsOpen(true);
  }, []);
  const close = useCallback(() => {
    setIsOpen(false);
    setParentTodoId(null);
  }, []);

  return {
    close,
    isOpen,
    openCreateChildTodo,
    openCreateTodo,
    parentTodoId
  };
}
