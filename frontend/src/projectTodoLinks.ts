import { terminalRouteSelectionFromPath } from "./appState";

export type ProjectTodoRouteRequest = {
  clientId: string;
  windowId: string | null;
  projectPath: string;
  todoId: string | null;
};

export function projectTodoRoutePath(request: ProjectTodoRouteRequest): string {
  const routePath = `/clients/${encodeURIComponent(request.clientId)}/kanban`;
  const params = new URLSearchParams({
    project_path: request.projectPath,
  });
  if (request.windowId !== null) {
    params.set("window_id", request.windowId);
  }
  if (request.todoId !== null) {
    params.set("todo_id", request.todoId);
  }
  return `${routePath}?${params.toString()}`;
}

export function projectTodoRouteRequestFromUrl(value: string, base?: string): ProjectTodoRouteRequest | null {
  const fallbackBase = typeof window === "undefined" ? "http://localhost/" : window.location.href;
  let url: URL;
  try {
    url = new URL(value, base ?? fallbackBase);
  } catch {
    return null;
  }
  if (typeof window !== "undefined" && url.origin !== window.location.origin) {
    return null;
  }
  const routeSelection = projectTodoRouteSelectionFromUrl(url);
  if (routeSelection === null) {
    return null;
  }
  const projectPath = url.searchParams.get("project_path");
  if (!projectPath) {
    return null;
  }
  return {
    clientId: routeSelection.clientId,
    windowId: routeSelection.windowId,
    projectPath,
    todoId: url.searchParams.get("todo_id"),
  };
}

export function readProjectTodoRouteRequest(): ProjectTodoRouteRequest | null {
  if (typeof window === "undefined") {
    return null;
  }
  return projectTodoRouteRequestFromUrl(`${window.location.pathname}${window.location.search}${window.location.hash}`);
}

function projectTodoRouteSelectionFromUrl(url: URL): { clientId: string; windowId: string | null } | null {
  const kanbanMatch = url.pathname.match(/^\/clients\/([^/]+)\/kanban\/?$/);
  if (kanbanMatch) {
    return {
      clientId: decodeURIComponent(kanbanMatch[1]),
      windowId: url.searchParams.get("window_id"),
    };
  }

  if (url.searchParams.get("view") !== "kanban") {
    return null;
  }
  const legacySelection = terminalRouteSelectionFromPath(url.pathname);
  return legacySelection.clientId === null
    ? null
    : { clientId: legacySelection.clientId, windowId: legacySelection.windowId };
}

export function writeProjectTodoRoute(request: ProjectTodoRouteRequest, mode: "push" | "replace"): void {
  if (typeof window === "undefined") {
    return;
  }
  const nextPath = projectTodoRoutePath(request);
  if (`${window.location.pathname}${window.location.search}${window.location.hash}` === nextPath) {
    return;
  }
  window.history[mode === "push" ? "pushState" : "replaceState"](
    { clientId: request.clientId, windowId: request.windowId, view: "kanban", todoId: request.todoId },
    "",
    nextPath
  );
}
