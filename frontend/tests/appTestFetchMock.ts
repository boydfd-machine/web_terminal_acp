import { vi } from "vitest";

import {
  clonedTreeWindow,
  clonedWindowActivity,
  clonedWindowDetail,
  codexWindowActivity,
  codexWindowDetail,
  createdWindow,
  defaultTodoType,
  otherTreeWindow,
  otherWindowActivity,
  otherWindowDetail,
  projectTodoDetail,
  projectTodoListItem,
  runningArtifact,
  treeWindow
} from "./appTestFixtures";

function jsonResponse(body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status: 200,
    headers: { "Content-Type": "application/json" }
  });
}

function pathFor(input: RequestInfo | URL): string {
  return new URL(input.toString()).pathname;
}

function searchParamFor(input: RequestInfo | URL, name: string): string | null {
  return new URL(input.toString()).searchParams.get(name);
}

function createAppTestFetchMock(): ReturnType<typeof vi.fn> {
  return vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
    const path = pathFor(input);

    if (path === "/api/auth/status") {
      return Promise.resolve(jsonResponse({ enabled: false }));
    }
    if (path === "/api/clients") {
      return Promise.resolve(jsonResponse([{
        id: "client-1",
        name: "local",
        status: "ONLINE",
        hostname: "localhost",
        install_path: null,
        version: null,
        last_update_at: null,
        runtime: "local",
        last_seen_at: null,
        connected_at: "2026-05-31T00:00:00Z",
        created_at: "2026-05-31T00:00:00Z",
        updated_at: "2026-05-31T00:00:00Z"
      }]));
    }
    if (path === "/api/clients/client-1/terminal-projects" && searchParamFor(input, "range") === "7d") {
      return Promise.resolve(jsonResponse([{ project_path: "/workspace", window_count: 1 }, { project_path: "/other", window_count: 1 }]));
    }
    if (path === "/api/clients/client-1/projects" && searchParamFor(input, "range") === "7d") {
      return Promise.resolve(jsonResponse([{ client_id: "client-1", path: "/workspace", display_name: null, summary_status: null, summary_updated_at: null, window_count: 1 }, { client_id: "client-1", path: "/other", display_name: null, summary_status: null, summary_updated_at: null, window_count: 1 }]));
    }
    if (path === "/api/clients/client-1/tree" && searchParamFor(input, "range") === "7d") {
      const projectPath = searchParamFor(input, "project_path");
      if (projectPath === "/workspace") {
        return Promise.resolve(jsonResponse([{
          id: "folder-1",
          name: "Root",
          path: "/workspace",
          folders: [],
          windows: [treeWindow, clonedTreeWindow]
        }]));
      }
      if (projectPath === "/other") {
        return Promise.resolve(jsonResponse([{
          id: "folder-2",
          name: "Other",
          path: "/other",
          folders: [],
          windows: [otherTreeWindow]
        }]));
      }
      return Promise.resolve(jsonResponse([
        {
          id: "folder-1",
          name: "Root",
          path: "/workspace",
          folders: [],
          windows: [treeWindow, clonedTreeWindow]
        },
        {
          id: "folder-2",
          name: "Other",
          path: "/other",
          folders: [],
          windows: [otherTreeWindow]
        }
      ]));
    }
    if (path === "/api/clients/client-1/windows/activity") {
      if (searchParamFor(input, "project_path") === "/other") {
        return Promise.resolve(jsonResponse({ windows: [otherWindowActivity] }));
      }
      if (searchParamFor(input, "project_path") === null) {
        return Promise.resolve(jsonResponse({ windows: [codexWindowActivity, clonedWindowActivity, otherWindowActivity] }));
      }
      return Promise.resolve(jsonResponse({ windows: [codexWindowActivity, clonedWindowActivity] }));
    }
    if (path === "/api/clients/client-1/terminal-notifications") {
      return Promise.resolve(jsonResponse({ notifications: [] }));
    }
    if (path === "/api/clients/client-1/projects/files") {
      return Promise.resolve(jsonResponse({ project_path: searchParamFor(input, "project_path"), path: searchParamFor(input, "path") ?? ".", browse_root: searchParamFor(input, "browse_root"), entries: [] }));
    }
    if (path === "/api/clients/client-1/projects/files/content") {
      const filePath = searchParamFor(input, "path") ?? "";
      return Promise.resolve(jsonResponse({
        project_path: searchParamFor(input, "project_path"),
        path: filePath,
        content: `content for ${filePath}`,
        encoding: "utf-8",
        truncated: false,
        size: filePath.length
      }));
    }
    if (path === "/api/clients/client-1/projects/files/search") {
      return Promise.resolve(jsonResponse({
        query: searchParamFor(input, "q") ?? "",
        results: [
          {
            project_path: searchParamFor(input, "project_path") ?? "/workspace",
            path: "src/App.tsx",
            line: 4,
            snippet: "const needle = true;",
            matches: [{ field: "snippet", start: 6, end: 12 }]
          }
        ],
        total: 1,
        limit: Number(searchParamFor(input, "limit") ?? "25"),
        offset: Number(searchParamFor(input, "offset") ?? "0"),
        has_more: false,
        scanned_files: 2,
        truncated: false
      }));
    }
    if (path === "/api/artifact-plugins") {
      return Promise.resolve(jsonResponse({ plugins: [] }));
    }
    if (path === "/api/clients/client-1/projects/todo-types") {
      return Promise.resolve(jsonResponse({ todo_types: [defaultTodoType] }));
    }
    if (path === "/api/clients/client-1/projects/todos") {
      return Promise.resolve(jsonResponse({ todos: [projectTodoListItem] }));
    }
    const todoHistoryMatch = path.match(/^\/api\/clients\/client-1\/projects\/todos\/([^/]+)\/history$/);
    if (todoHistoryMatch !== null) {
      return Promise.resolve(jsonResponse({
        todo_id: decodeURIComponent(todoHistoryMatch[1]),
        versions: [],
        audit_logs: []
      }));
    }
    if (path === "/api/clients/client-1/projects/todos/todo-1") {
      return Promise.resolve(jsonResponse(projectTodoDetail));
    }
    if (path === "/api/clients/client-1/project-summaries") {
      return Promise.resolve(jsonResponse([]));
    }
    if (path === "/api/clients/client-1/terminal-recents") {
      return Promise.resolve(jsonResponse({
        items: [
          { window_id: "window-3", title: "Other window", last_used_at: "2026-05-31T00:00:00Z" },
          { window_id: "window-1", title: "Codex window", last_used_at: "2026-05-31T00:00:00Z" }
        ],
        page: 1,
        page_size: 20,
        total: 2,
        total_pages: 1,
        has_next: false,
        has_previous: false
      }));
    }
    if (path === "/api/ui-settings/custom-quick-keys") {
      return Promise.resolve(jsonResponse({ quick_keys: [] }));
    }
    if (path === "/api/clients/client-1/windows" && init?.method === "POST") {
      return Promise.resolve(jsonResponse(createdWindow));
    }
    if (path === "/api/clients/client-1/windows/window-1/clone" && init?.method === "POST") {
      return Promise.resolve(jsonResponse(clonedWindowDetail));
    }
    if (path === "/api/clients/client-1/windows/window-2") {
      return Promise.resolve(jsonResponse(clonedWindowDetail));
    }
    if (path === "/api/clients/client-1/windows/window-1") {
      return Promise.resolve(jsonResponse(codexWindowDetail));
    }
    if (path === "/api/clients/client-1/windows/window-3") {
      return Promise.resolve(jsonResponse(otherWindowDetail));
    }
    if (path === "/api/clients/client-1/windows/window-1/aux-terminal/ensure" && init?.method === "POST") {
      return Promise.resolve(jsonResponse({ status: "ready", cwd: "/workspace" }));
    }
    if (path === "/api/clients/client-1/windows/window-1/artifacts") {
      return Promise.resolve(jsonResponse({
        window_id: "window-1",
        artifacts: [runningArtifact],
        total: 1,
        limit: 100,
        offset: 0,
        has_more: false
      }));
    }
    if (path === "/api/clients/client-1/windows/window-1/agent-record/chat") {
      return Promise.resolve(jsonResponse({
        window_id: "window-1",
        messages: [],
        messages_total: 0,
        messages_limit: 30,
        messages_offset: 0,
        messages_has_more: false
      }));
    }
    if (path === "/api/clients/client-1/windows/window-1/agent-record/detail") {
      return Promise.resolve(jsonResponse({
        window_id: "window-1",
        sessions: [],
        events: [],
        events_total: 0,
        events_limit: 100,
        events_offset: 0,
        events_has_more: false
      }));
    }

    return Promise.resolve(jsonResponse({}));
  });
}

export {
  createAppTestFetchMock,
  pathFor,
  searchParamFor
};
