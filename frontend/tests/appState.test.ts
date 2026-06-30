import { beforeEach, describe, expect, it } from "vitest";

import {
  CLIENT_RECENCY_STORAGE_KEY,
  CLIENT_WINDOW_SELECTION_STORAGE_KEY,
  TERMINAL_VIEWPORT_STORAGE_KEY,
  WORKSPACE_MODE_STORAGE_KEY,
  readClientRecency,
  readClientWindowSelections,
  readTerminalRouteSelection,
  readTerminalViewportMode,
  readWorkspaceMode,
  rememberClientRecency,
  terminalRoutePath,
  terminalRouteSelectionFromUrl,
  terminalStatusLabel,
  workspaceModeFromUrl
} from "../src/appState";
import {
  AUX_TERMINAL_WINDOW_POSITION_STORAGE_KEY,
  calculateAuxTerminalDefaultWindowLayout,
  readAuxTerminalWindowPosition
} from "../src/auxTerminalLayout";
import {
  projectFilesRoutePath,
  projectFilesRouteRequestFromUrl,
} from "../src/projectFileLinks";
import {
  projectTodoRoutePath,
  projectTodoRouteRequestFromUrl,
  readProjectTodoRouteRequest,
} from "../src/projectTodoLinks";

describe("app state helpers", () => {
  beforeEach(() => {
    window.localStorage.clear();
    window.history.replaceState(null, "", "/");
  });

  it("defaults invalid stored viewport and workspace modes", () => {
    window.localStorage.setItem(TERMINAL_VIEWPORT_STORAGE_KEY, "tablet");
    window.localStorage.setItem(WORKSPACE_MODE_STORAGE_KEY, "sidecar");

    expect(readTerminalViewportMode()).toBe("desktop");
    expect(readWorkspaceMode()).toBe("terminal");
  });

  it("restores the persisted kanban workspace mode", () => {
    window.localStorage.setItem(WORKSPACE_MODE_STORAGE_KEY, "kanban");

    expect(readWorkspaceMode()).toBe("kanban");
  });

  it("prefers explicit workspace routes over persisted workspace mode", () => {
    window.localStorage.setItem(WORKSPACE_MODE_STORAGE_KEY, "terminal");
    window.history.replaceState(null, "", "/clients/client-1/files?project_path=%2Fworkspace");

    expect(readWorkspaceMode()).toBe("files");
    expect(workspaceModeFromUrl("/clients/client-1/kanban?project_path=%2Fworkspace")).toBe("kanban");
    expect(workspaceModeFromUrl("/clients/client-1/terminals/window-1")).toBeNull();
  });

  it("parses encoded terminal route selections", () => {
    window.history.replaceState(null, "", "/clients/client%201/terminals/window%2F2");

    expect(readTerminalRouteSelection()).toEqual({
      clientId: "client 1",
      windowId: "window/2"
    });
    expect(terminalRoutePath("client 1", "window/2")).toBe("/clients/client%201/terminals/window%2F2");
  });

  it("normalizes persisted client window selections", () => {
    window.localStorage.setItem(CLIENT_WINDOW_SELECTION_STORAGE_KEY, JSON.stringify({
      "client-1": { windowId: "window-1", usedAt: 10 },
      "client-2": { windowId: 42, usedAt: "old" },
      ignored: null
    }));

    expect(readClientWindowSelections()).toEqual({
      "client-1": { windowId: "window-1", usedAt: 10 },
      "client-2": { windowId: null, usedAt: 0 }
    });
  });

  it("dedupes and caps client recency", () => {
    const seed = Array.from({ length: 105 }, (_, index) => `client-${index}`);
    window.localStorage.setItem(CLIENT_RECENCY_STORAGE_KEY, JSON.stringify(["client-2", 9, "client-1"]));

    expect(readClientRecency()).toEqual(["client-2", "client-1"]);
    expect(rememberClientRecency(seed, "client-2")).toHaveLength(100);
    expect(rememberClientRecency(["client-1", "client-2"], "client-2")).toEqual(["client-2", "client-1"]);
  });

  it("maps terminal connection status to toolbar labels", () => {
    expect(terminalStatusLabel("connected")).toBe("Terminal connected");
    expect(terminalStatusLabel("unavailable")).toBe("Client offline");
  });

  it("parses kanban project and todo routes", () => {
    window.history.replaceState(
      null,
      "",
      "/clients/client%201/kanban?project_path=%2Fworkspace%2Fapp&window_id=window%2F2&todo_id=todo%2F1"
    );

    expect(readProjectTodoRouteRequest()).toEqual({
      clientId: "client 1",
      windowId: "window/2",
      projectPath: "/workspace/app",
      todoId: "todo/1"
    });
    expect(projectTodoRoutePath({
      clientId: "client 1",
      windowId: "window/2",
      projectPath: "/workspace/app",
      todoId: "todo/1"
    })).toBe("/clients/client%201/kanban?project_path=%2Fworkspace%2Fapp&window_id=window%2F2&todo_id=todo%2F1");
  });

  it("parses legacy kanban routes", () => {
    expect(projectTodoRouteRequestFromUrl(
      "/clients/client%201/terminals/window%2F2?view=kanban&project_path=%2Fworkspace%2Fapp&todo_id=todo%2F1"
    )).toEqual({
      clientId: "client 1",
      windowId: "window/2",
      projectPath: "/workspace/app",
      todoId: "todo/1"
    });
  });

  it("parses files workspace routes", () => {
    expect(projectFilesRouteRequestFromUrl(
      "/clients/client%201/files?project_path=%2Fworkspace%2Fapp&window_id=window%2F2&browse_root=%2Ftmp%2Fworktree"
    )).toEqual({
      clientId: "client 1",
      windowId: "window/2",
      projectPath: "/workspace/app",
      browseRoot: "/tmp/worktree"
    });
    expect(projectFilesRoutePath({
      clientId: "client 1",
      windowId: "window/2",
      projectPath: "/workspace/app",
      browseRoot: null
    })).toBe("/clients/client%201/files?project_path=%2Fworkspace%2Fapp&window_id=window%2F2");
  });

  it("ignores non-kanban todo route URLs", () => {
    expect(projectTodoRouteRequestFromUrl("/clients/client-1?view=files&project_path=%2Fworkspace")).toBeNull();
    expect(projectTodoRouteRequestFromUrl("/?view=kanban&project_path=%2Fworkspace")).toBeNull();
    expect(projectTodoRouteRequestFromUrl("/clients/client-1?view=kanban")).toBeNull();
  });

  it("does not parse project workspace routes as terminal route selections", () => {
    expect(terminalRouteSelectionFromUrl(
      "/clients/client-1/kanban?project_path=%2Fworkspace&window_id=window-1&todo_id=todo-1"
    )).toEqual({ clientId: null, windowId: null });
    expect(terminalRouteSelectionFromUrl(
      "/clients/client-1/files?project_path=%2Fworkspace&window_id=window-1&file_path=README.md"
    )).toEqual({ clientId: null, windowId: null });
  });
});

describe("aux terminal layout helpers", () => {
  beforeEach(() => {
    window.localStorage.clear();
    Object.defineProperty(window, "innerWidth", { configurable: true, value: 1200 });
    Object.defineProperty(window, "innerHeight", { configurable: true, value: 800 });
  });

  it("ignores malformed persisted window positions", () => {
    window.localStorage.setItem(AUX_TERMINAL_WINDOW_POSITION_STORAGE_KEY, JSON.stringify({ x: "1", y: 2 }));

    expect(readAuxTerminalWindowPosition()).toBeNull();
  });

  it("fits the aux terminal in the workspace rect", () => {
    const workspace = document.createElement("section");
    workspace.getBoundingClientRect = () => ({
      x: 100,
      y: 100,
      left: 100,
      top: 100,
      right: 900,
      bottom: 700,
      width: 800,
      height: 600,
      toJSON: () => ({})
    } as DOMRect);

    expect(calculateAuxTerminalDefaultWindowLayout(workspace)).toEqual({
      metrics: { width: 800, height: 300, minHeight: 220 },
      position: { x: 100, y: 400 }
    });
  });
});
