import { act } from "react";
import { describe, expect, it } from "vitest";

import type { PageAnnotationHost } from "../src/pageAnnotation";
import { projectTodoDetail, projectTodoListItem } from "./appTestFixtures";
import {
  currentContainer,
  fetchMock,
  renderApp,
  waitForBodyElement,
  waitForButtonText,
  waitForNewTerminalButton,
  waitForRequests
} from "./appTestHarness";

describe("App page annotation host bridge", () => {
  it("registers selected app context and creates a focused todo", async () => {
    renderApp();
    await waitForNewTerminalButton();

    const host = await waitForAnnotationHostContext();
    expect(host).toBeDefined();
    expect(host?.getContext()).toMatchObject({
      clientId: "client-1",
      projectPath: "/workspace",
      windowId: "window-1",
      workspaceMode: "terminal"
    });

    const createdTodo = {
      ...projectTodoDetail,
      id: "todo-debug",
      client_id: "client-1",
      project_path: "/workspace",
      title: "UI: Fix selected area",
      description: "Source: Debug page annotation"
    };
    fetchMock.mockImplementationOnce((input: RequestInfo | URL, init?: RequestInit) => {
      expect(new URL(input.toString()).pathname).toBe("/api/clients/client-1/projects/todos");
      expect(init?.method).toBe("POST");
      expect(JSON.parse(String(init?.body))).toMatchObject({
        title: "UI: Fix selected area",
        description: "Source: Debug page annotation",
        todo_type_id: "default"
      });
      return Promise.resolve(new Response(JSON.stringify(createdTodo), {
        status: 200,
        headers: { "Content-Type": "application/json" }
      }));
    });

    let todo = null as Awaited<ReturnType<PageAnnotationHost["createTodo"]>> | null;
    await act(async () => {
      todo = await host?.createTodo({
        title: "UI: Fix selected area",
        description: "Source: Debug page annotation"
      }) ?? null;
      host?.focusTodo?.(todo);
    });
    await waitForRequests();

    expect(todo?.id).toBe("todo-debug");
    expect(currentContainer()?.querySelector(".project-kanban-workspace")).not.toBeNull();
  });

  it("opens a kanban pending page while an annotation card is being created", async () => {
    renderApp();
    await waitForNewTerminalButton();

    const host = await waitForAnnotationHostContext();
    let pendingCreation: ReturnType<NonNullable<PageAnnotationHost["beginTodoCreation"]>> | null = null;
    await act(async () => {
      pendingCreation = host.beginTodoCreation?.({
        title: "UI: Fix selected area",
        description: "Source: Debug page annotation"
      }) ?? null;
    });

    const dialog = await waitForBodyElement(".project-todo-creation-pending-dialog", (element): element is HTMLElement => (
      element instanceof HTMLElement
    ));
    expect(pendingCreation).not.toBeNull();
    expect(dialog.textContent).toContain("Creating card...");
    expect(window.location.pathname).toBe("/clients/client-1/kanban");
    expect(new URLSearchParams(window.location.search).get("project_path")).toBe("/workspace");

    act(() => {
      pendingCreation?.onFailed();
    });
    expect(document.body.querySelector(".project-todo-creation-pending-dialog")).toBeNull();
  });

  it("opens one kanban detail and one dispatch modal for annotation-created todos", async () => {
    renderApp();
    await waitForNewTerminalButton();

    const host = await waitForAnnotationHostContext();
    const createdTodo = {
      ...projectTodoDetail,
      id: "todo-debug",
      client_id: "client-1",
      project_path: "/workspace",
      title: "UI: Fix selected area",
      description: "Source: Debug page annotation",
      assigned_window_id: null
    };
    const defaultFetch = fetchMock.getMockImplementation();
    fetchMock.mockImplementation((input: RequestInfo | URL, init?: RequestInit) => {
      const url = new URL(input.toString());
      if (url.pathname === "/api/clients/client-1/projects/todos" && init?.method === "POST") {
        return Promise.resolve(new Response(JSON.stringify(createdTodo), {
          status: 200,
          headers: { "Content-Type": "application/json" }
        }));
      }
      if (url.pathname === "/api/clients/client-1/projects/todos") {
        return Promise.resolve(new Response(JSON.stringify({
          todos: [
            projectTodoListItem,
            {
              ...projectTodoListItem,
              id: "todo-debug",
              title: "UI: Fix selected area",
              assigned_window_id: null
            }
          ]
        }), {
          status: 200,
          headers: { "Content-Type": "application/json" }
        }));
      }
      if (url.pathname === "/api/clients/client-1/projects/todos/todo-debug") {
        return Promise.resolve(new Response(JSON.stringify(createdTodo), {
          status: 200,
          headers: { "Content-Type": "application/json" }
        }));
      }
      return defaultFetch?.(input, init) ?? Promise.resolve(new Response("{}"));
    });

    await act(async () => {
      const todo = await host.createTodo({
        title: "UI: Fix selected area",
        description: "Source: Debug page annotation"
      });
      host.focusTodo?.(todo);
    });
    await waitForBodyElement(".project-todo-detail-dialog", (element): element is HTMLElement => (
      element instanceof HTMLElement
    ));

    expect(document.body.querySelectorAll(".project-todo-detail-dialog")).toHaveLength(1);

    const dispatchButton = await waitForButtonText("Dispatch", true);
    act(() => dispatchButton.click());
    await waitForRequests();

    expect(document.body.querySelectorAll(".project-todo-detail-dialog")).toHaveLength(0);
    expect(document.body.querySelectorAll(".terminal-create-modal")).toHaveLength(1);
    expect(document.body.querySelector(".terminal-create-modal")?.textContent).toContain("UI: Fix selected area");
  });

  it("lists current project todos and appends annotation context without using comments", async () => {
    renderApp();
    await waitForNewTerminalButton();

    const host = await waitForAnnotationHostContext();
    const todos = await host.listTodos?.();
    expect(todos?.map((todo) => [todo.id, todo.title])).toEqual([["todo-1", "Fix board drag"]]);

    const annotatedTodo = {
      ...projectTodoDetail,
      description: "Drag regression context\n\n---\n\nSource: Debug page annotation"
    };
    fetchMock.mockImplementationOnce((input: RequestInfo | URL, init?: RequestInit) => {
      const url = new URL(input.toString());
      expect(url.pathname).toBe("/api/clients/client-1/projects/todos/todo-1/annotations");
      expect(url.searchParams.get("project_path")).toBe("/workspace");
      expect(init?.method).toBe("POST");
      expect(JSON.parse(String(init?.body))).toEqual({
        annotation: "Source: Debug page annotation"
      });
      return Promise.resolve(new Response(JSON.stringify(annotatedTodo), {
        status: 200,
        headers: { "Content-Type": "application/json" }
      }));
    });

    let todo = null as Awaited<ReturnType<NonNullable<PageAnnotationHost["appendAnnotation"]>>> | null;
    await act(async () => {
      todo = await host.appendAnnotation?.("todo-1", {
        annotation: "Source: Debug page annotation"
      }) ?? null;
      host.focusTodo?.(todo);
    });
    await waitForRequests();

    expect(todo?.id).toBe("todo-1");
    expect(fetchMock.mock.calls.map(([input]) => new URL(input.toString()).pathname)).not.toContain(
      "/api/clients/client-1/projects/todos/todo-1/comment"
    );
    expect(currentContainer()?.querySelector(".project-kanban-workspace")).not.toBeNull();
  });

  it("uploads annotation screenshots through project todo image attachments", async () => {
    renderApp();
    await waitForNewTerminalButton();

    const host = await waitForAnnotationHostContext();
    const defaultFetch = fetchMock.getMockImplementation();
    const file = new File(["png"], "debug-annotation.png", { type: "image/png" });
    fetchMock.mockImplementation((input: RequestInfo | URL, init?: RequestInit) => {
      const url = new URL(input.toString());
      if (url.pathname === "/api/clients/client-1/projects/todos/todo-1/attachments") {
        expect(url.searchParams.get("project_path")).toBe("/workspace");
        expect(init?.method).toBe("POST");
        expect(JSON.parse(String(init?.body))).toEqual({
          filename: "debug-annotation.png",
          content_type: "image/png",
          size_bytes: 3
        });
        return Promise.resolve(new Response(JSON.stringify({
          attachment: {
            id: "attachment-debug",
            todo_id: "todo-1",
            filename: "debug-annotation.png",
            content_type: "image/png",
            size_bytes: 3,
            status: "pending",
            uploaded_at: null,
            created_at: "2026-06-08T00:00:00Z",
            updated_at: "2026-06-08T00:00:00Z"
          },
          upload_url: "https://objects.example/debug-annotation.png",
          upload_headers: { "Content-Type": "image/png" },
          expires_at: "2026-06-08T00:15:00Z"
        }), {
          status: 200,
          headers: { "Content-Type": "application/json" }
        }));
      }
      if (input.toString() === "https://objects.example/debug-annotation.png") {
        expect(init?.method).toBe("PUT");
        expect(init?.headers).toEqual({ "Content-Type": "image/png" });
        expect(init?.body).toBe(file);
        return Promise.resolve(new Response(null, { status: 200 }));
      }
      if (url.pathname === "/api/clients/client-1/projects/todos/todo-1/attachments/attachment-debug/complete") {
        expect(init?.method).toBe("POST");
        return Promise.resolve(new Response(JSON.stringify({
          id: "attachment-debug",
          todo_id: "todo-1",
          filename: "debug-annotation.png",
          content_type: "image/png",
          size_bytes: 3,
          status: "uploaded",
          uploaded_at: "2026-06-08T00:01:00Z",
          created_at: "2026-06-08T00:00:00Z",
          updated_at: "2026-06-08T00:01:00Z"
        }), {
          status: 200,
          headers: { "Content-Type": "application/json" }
        }));
      }
      return defaultFetch?.(input, init) ?? Promise.resolve(new Response("{}"));
    });

    await act(async () => {
      await host.uploadImage?.("todo-1", file);
    });
    await waitForRequests();

    const requestedUrls = fetchMock.mock.calls.map(([input]) => input.toString());
    expect(requestedUrls).toContain("https://objects.example/debug-annotation.png");
    expect(fetchMock.mock.calls.map(([input]) => new URL(input.toString()).pathname)).toContain(
      "/api/clients/client-1/projects/todos/todo-1/attachments/attachment-debug/complete"
    );
  });
});

async function waitForAnnotationHostContext(): Promise<PageAnnotationHost> {
  for (let attempt = 0; attempt < 20; attempt += 1) {
    await waitForRequests();
    const host = window.__WEB_TERMINAL_PAGE_ANNOTATION_HOST__ as PageAnnotationHost | undefined;
    if (host?.getContext().projectPath !== null) {
      return host;
    }
  }
  throw new Error("Page annotation host did not publish selected project context.");
}
