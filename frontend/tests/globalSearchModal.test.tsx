import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, describe, expect, it, vi } from "vitest";

import { GlobalSearchModal } from "../src/components/GlobalSearchModal";
import { PROJECT_FILE_OPEN_EVENT, type ProjectFileOpenRequest } from "../src/projectFileLinks";

globalThis.IS_REACT_ACT_ENVIRONMENT = true;

let root: Root | null = null;
let container: HTMLDivElement | null = null;
let queryClient: QueryClient | null = null;

function jsonResponse(body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status: 200,
    headers: { "Content-Type": "application/json" }
  });
}

function requestPath(input: RequestInfo | URL): string {
  return new URL(input.toString()).pathname;
}

function requestParam(input: RequestInfo | URL, name: string): string | null {
  return new URL(input.toString()).searchParams.get(name);
}

async function waitForRequests(): Promise<void> {
  await act(async () => {
    await new Promise((resolve) => setTimeout(resolve, 0));
  });
}

async function waitForMarkText(text: string): Promise<HTMLElement> {
  for (let attempt = 0; attempt < 20; attempt += 1) {
    await waitForRequests();
    const mark = container?.querySelector<HTMLElement>("mark.search-highlight");
    if (mark?.textContent === text) {
      return mark;
    }
  }

  throw new Error(`Highlight ${text} was not rendered`);
}

async function waitForButtonContaining(text: string): Promise<HTMLButtonElement> {
  for (let attempt = 0; attempt < 20; attempt += 1) {
    await waitForRequests();
    const button = Array.from(container?.querySelectorAll("button") ?? []).find(
      (candidate) => candidate.textContent?.includes(text)
    );
    if (button instanceof HTMLButtonElement) {
      return button;
    }
  }

  throw new Error(`Button containing ${text} was not rendered`);
}

async function waitForText(text: string): Promise<void> {
  for (let attempt = 0; attempt < 20; attempt += 1) {
    await waitForRequests();
    if (container?.textContent?.includes(text)) {
      return;
    }
  }

  throw new Error(`Text ${text} was not rendered`);
}

function renderModal({
  onSelectWindow = vi.fn(),
  onFocusProjectTodo = vi.fn(),
  onClose = vi.fn()
}: {
  onSelectWindow?: (windowId: string, clientId?: string | null) => void;
  onFocusProjectTodo?: (projectPath: string, todoId: string) => void;
  onClose?: () => void;
} = {}) {
  container = document.createElement("div");
  document.body.appendChild(container);
  queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false }
    }
  });
  root = createRoot(container);
  act(() => {
    root?.render(
      <QueryClientProvider client={queryClient as QueryClient}>
        <GlobalSearchModal
          clientId="client-1"
          open
          onClose={onClose}
          onFocusProjectTodo={onFocusProjectTodo}
          onSelectWindow={onSelectWindow}
        />
      </QueryClientProvider>
    );
  });

  return { onClose, onFocusProjectTodo, onSelectWindow };
}

afterEach(() => {
  act(() => {
    root?.unmount();
  });
  document.body.replaceChildren();
  queryClient?.clear();
  root = null;
  container = null;
  queryClient = null;
  vi.restoreAllMocks();
});

describe("GlobalSearchModal", () => {
  it("searches explicitly by type and jumps to matching targets", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(jsonResponse({
        query: "llama",
        scope: "global",
        results: [
          {
            window_id: "window-1",
            session_id: "session-1",
            provider: "codex",
            message: {
              id: "message-1",
              ai_session_id: "session-1",
              source_type: "codex",
              source_id: "session.jsonl",
              role: "agent",
              body: "Agent mentioned llama in the record.",
              body_format: "markdown",
              agent_message_type: "agent",
              subagent_id: null,
              subagent_tool_use_id: null,
              target_session_id: null,
              target_session_source_id: null,
              created_at: "2026-06-01T00:00:00Z"
            },
            matches: [{ field: "body", start: 16, end: 21 }]
          }
        ],
        total: 1,
        limit: 25,
        offset: 0,
        has_more: false
      }))
      .mockResolvedValueOnce(jsonResponse({
        query: "llama",
        results: [
          {
            id: "todo-1",
            client_id: "client-1",
            project_path: "/workspace/project",
            title: "Fix llama board card",
            description: "Kanban search result",
            status: "TODO",
            assigned_window_id: "window-1",
            assigned_agent: "codex",
            updated_at: "2026-06-01T00:00:00Z",
            matches: [{ field: "title", start: 4, end: 9 }]
          }
        ],
        total: 1,
        limit: 25,
        offset: 0,
        has_more: false
      }))
      .mockResolvedValueOnce(jsonResponse({
        query: "llama",
        results: [
          {
            project_path: "/workspace/project",
            path: "src/app.ts",
            line: 12,
            snippet: "const llama = true;",
            matches: [{ field: "snippet", start: 6, end: 11 }]
          }
        ],
        total: 1,
        limit: 25,
        offset: 0,
        has_more: false,
        scanned_files: 3,
        truncated: false
      }))
      .mockResolvedValueOnce(jsonResponse({
        query: "llama",
        results: [
          {
            project_path: "/workspace/project",
            path: "src/llama.config.ts",
            line: null,
            snippet: "src/llama.config.ts",
            matches: [{ field: "path", start: 4, end: 9 }]
          }
        ],
        total: 1,
        limit: 25,
        offset: 0,
        has_more: false,
        scanned_files: 3,
        truncated: false
      }));
    const handlers = renderModal();
    const fileOpenRequests: ProjectFileOpenRequest[] = [];
    window.addEventListener(PROJECT_FILE_OPEN_EVENT, (event) => {
      fileOpenRequests.push((event as CustomEvent<ProjectFileOpenRequest>).detail);
    }, { once: true });

    expect(fetchMock).not.toHaveBeenCalled();

    const input = container?.querySelector<HTMLInputElement>('input[type="search"]');
    expect(input).toBeInstanceOf(HTMLInputElement);
    const valueSetter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value")?.set;
    act(() => {
      valueSetter?.call(input, "llama");
      input?.dispatchEvent(new Event("input", { bubbles: true }));
      container?.querySelector("form")?.dispatchEvent(new Event("submit", { bubbles: true, cancelable: true }));
    });
    await waitForRequests();

    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(requestPath(fetchMock.mock.calls[0][0])).toBe("/api/clients/client-1/agent-record/search");
    expect(requestParam(fetchMock.mock.calls[0][0], "q")).toBe("llama");
    await waitForMarkText("llama");

    const openWindowButton = await waitForButtonContaining("Open terminal");
    act(() => {
      openWindowButton?.dispatchEvent(new MouseEvent("click", { bubbles: true }));
    });
    expect(handlers.onSelectWindow).toHaveBeenCalledWith("window-1", "client-1");
    expect(handlers.onClose).toHaveBeenCalledTimes(1);

    const kanbanTab = Array.from(container?.querySelectorAll("button") ?? []).find(
      (button) => button.textContent === "Kanban"
    );
    expect(kanbanTab).toBeInstanceOf(HTMLButtonElement);
    act(() => {
      kanbanTab?.dispatchEvent(new MouseEvent("click", { bubbles: true }));
    });
    await waitForRequests();

    expect(fetchMock).toHaveBeenCalledTimes(2);
    expect(requestPath(fetchMock.mock.calls[1][0])).toBe("/api/clients/client-1/projects/todos/search");
    expect(requestParam(fetchMock.mock.calls[1][0], "q")).toBe("llama");
    await waitForMarkText("llama");

    const openKanbanButton = await waitForButtonContaining("Open kanban");
    act(() => {
      openKanbanButton?.dispatchEvent(new MouseEvent("click", { bubbles: true }));
    });

    expect(handlers.onFocusProjectTodo).toHaveBeenCalledWith("/workspace/project", "todo-1");

    const contentsTab = Array.from(container?.querySelectorAll("button") ?? []).find(
      (button) => button.textContent === "File contents"
    );
    expect(contentsTab).toBeInstanceOf(HTMLButtonElement);
    act(() => {
      contentsTab?.dispatchEvent(new MouseEvent("click", { bubbles: true }));
    });
    await waitForRequests();

    expect(fetchMock).toHaveBeenCalledTimes(3);
    expect(requestPath(fetchMock.mock.calls[2][0])).toBe("/api/clients/client-1/projects/files/search");
    expect(requestParam(fetchMock.mock.calls[2][0], "q")).toBe("llama");
    expect(requestParam(fetchMock.mock.calls[2][0], "mode")).toBe("content");
    await waitForMarkText("llama");
    expect(container?.textContent).toContain("Line 12");

    const filenamesTab = Array.from(container?.querySelectorAll("button") ?? []).find(
      (button) => button.textContent === "Filenames"
    );
    expect(filenamesTab).toBeInstanceOf(HTMLButtonElement);
    act(() => {
      filenamesTab?.dispatchEvent(new MouseEvent("click", { bubbles: true }));
    });
    await waitForRequests();

    expect(fetchMock).toHaveBeenCalledTimes(4);
    expect(requestPath(fetchMock.mock.calls[3][0])).toBe("/api/clients/client-1/projects/files/search");
    expect(requestParam(fetchMock.mock.calls[3][0], "q")).toBe("llama");
    expect(requestParam(fetchMock.mock.calls[3][0], "mode")).toBe("filename");
    await waitForText("Path match");
    expect(container?.textContent).toContain("Path match");

    const openFileButton = await waitForButtonContaining("Open file");
    act(() => {
      openFileButton?.dispatchEvent(new MouseEvent("click", { bubbles: true }));
    });

    expect(fileOpenRequests).toEqual([
      {
        clientId: "client-1",
        windowId: null,
        projectPath: "/workspace/project",
        browseRoot: null,
        path: "src/llama.config.ts",
        line: null
      }
    ]);
  });
});
