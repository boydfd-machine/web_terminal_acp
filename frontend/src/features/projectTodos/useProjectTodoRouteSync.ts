import { useCallback, useEffect } from "react";

import {
  readProjectTodoRouteRequest,
  writeProjectTodoRoute,
} from "../../projectTodoLinks";

type UseProjectTodoRouteSyncArgs = {
  clientId: string;
  projectPath: string;
  selectedTodoId: string | null;
  viewMode: "list" | "board";
  windowId: string | null;
  onRouteClear: () => void;
  onRouteTodo: (todoId: string) => void;
};

export function useProjectTodoRouteSync({
  clientId,
  projectPath,
  selectedTodoId,
  viewMode,
  windowId,
  onRouteClear,
  onRouteTodo,
}: UseProjectTodoRouteSyncArgs) {
  const routeEnabled = viewMode === "board";
  const writeTodoRoute = useCallback((todoId: string | null, mode: "push" | "replace") => {
    if (!routeEnabled) {
      return;
    }
    writeProjectTodoRoute({ clientId, windowId, projectPath, todoId }, mode);
  }, [clientId, projectPath, routeEnabled, windowId]);

  useEffect(() => {
    if (!routeEnabled) {
      return;
    }

    const applyRoute = () => {
      const request = readProjectTodoRouteRequest();
      if (request === null || request.clientId !== clientId || request.projectPath !== projectPath) {
        if (selectedTodoId !== null) {
          onRouteClear();
        }
        return;
      }
      if (request.todoId === null) {
        if (selectedTodoId !== null) {
          onRouteClear();
        }
        return;
      }
      if (request.todoId !== selectedTodoId) {
        onRouteTodo(request.todoId);
      }
    };

    applyRoute();
    window.addEventListener("popstate", applyRoute);
    return () => window.removeEventListener("popstate", applyRoute);
  }, [clientId, onRouteClear, onRouteTodo, projectPath, routeEnabled, selectedTodoId]);

  return { writeTodoRoute };
}
