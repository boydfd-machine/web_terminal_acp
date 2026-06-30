import { act } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  cleanupProjectTodoTest,
  renderWithQuery,
  setupProjectTodoTest,
  todo,
  waitForButton,
  waitForElement,
  waitForRequests
} from "./projectTodoTestHarness";
import { ProjectTodoPanel } from "../src/components/ProjectTodoPanel";
import type { Project, ProjectTodo } from "../src/types";

const apiMocks = vi.hoisted(() => ({
  commentProjectTodo: vi.fn(),
  createProjectTodo: vi.fn(),
  createTerminalArtifact: vi.fn(),
  deleteProjectTodo: vi.fn(),
  deleteProjectTodoAttachment: vi.fn(),
  downloadProjectTodoAttachment: vi.fn(),
  dispatchProjectTodo: vi.fn(),
  dispatchProjectTodoReview: vi.fn(),
  fetchAgentClients: vi.fn(),
  fetchAgentProfileConfig: vi.fn(),
  fetchAgentProfiles: vi.fn(),
  fetchArtifactPlugins: vi.fn(),
  fetchAgentRecordChat: vi.fn(),
  fetchAgentRecordDetail: vi.fn(),
  fetchClientAgentConfig: vi.fn(),
  fetchProjectTodoTypes: vi.fn(),
  fetchProjectTodo: vi.fn(),
  fetchProjectTodoHistory: vi.fn(),
  fetchProjectTodos: vi.fn(),
  fetchSystemModelPresets: vi.fn(),
  fetchWindow: vi.fn(),
  fetchWindowActivity: vi.fn(),
  linkProjectTodoArtifact: vi.fn(),
  retryProjectTodoArtifact: vi.fn(),
  restoreProjectTodoVersion: vi.fn(),
  uploadProjectTodoAttachmentImage: vi.fn(),
  upsertSystemProjectTodoType: vi.fn(),
  updateSystemProjectTodoType: vi.fn(),
  deleteSystemProjectTodoType: vi.fn(),
  updateProjectTodo: vi.fn()
}));

vi.mock("../src/api", () => apiMocks);

beforeEach(() => setupProjectTodoTest(apiMocks));
afterEach(cleanupProjectTodoTest);

describe("ProjectTodoPanel detail column move", () => {
  const currentProject: Project = {
    client_id: "client-1",
    path: "/workspace",
    display_name: "Current Project",
    summary_status: null,
    summary_updated_at: null,
    window_count: 1
  };
  const targetProject: Project = {
    client_id: "client-1",
    path: "/workspace/target",
    display_name: "Target Project",
    summary_status: null,
    summary_updated_at: null,
    window_count: 1
  };

  it("moves a card to another board column from the detail dialog", async () => {
    const doneTodo: ProjectTodo = {
      ...todo,
      id: "todo-done",
      title: "Already done",
      status: "DONE",
      sort_order: 8
    };
    apiMocks.fetchProjectTodos.mockResolvedValue({ todos: [todo, doneTodo] });
    apiMocks.updateProjectTodo.mockResolvedValue({ ...todo, status: "DONE", sort_order: 9 });
    renderWithQuery(<ProjectTodoPanel clientId="client-1" projectPath="/workspace" onSelectWindow={() => {}} />);

    const row = await waitForButton("Fix dispatchTodo");
    act(() => row.click());
    const selector = await waitForElement(
      ".project-todo-detail-dialog .project-todo-move-column-select"
    ) as HTMLSelectElement;

    expect(selector.value).toBe("TODO");
    expect(Array.from(selector.options).map((option) => option.textContent)).toEqual([
      "Todo",
      "Running",
      "Review",
      "Done",
      "Blocked"
    ]);

    act(() => {
      selector.value = "DONE";
      selector.dispatchEvent(new Event("change", { bubbles: true }));
    });
    await waitForRequests();

    expect(apiMocks.updateProjectTodo).toHaveBeenCalledWith("client-1", "/workspace", "todo-1", {
      status: "DONE",
      sort_order: 9
    });
  });

  it("moves a pending queued card back to the todo column from the detail dialog", async () => {
    const queuedTodo: ProjectTodo = {
      ...todo,
      queued_dispatch: true
    };
    const todoColumnCard: ProjectTodo = {
      ...todo,
      id: "todo-open",
      title: "Open card",
      sort_order: 8
    };
    apiMocks.fetchProjectTodos.mockResolvedValue({ todos: [queuedTodo, todoColumnCard] });
    apiMocks.updateProjectTodo.mockResolvedValue({ ...queuedTodo, queued_dispatch: false, sort_order: 9 });
    renderWithQuery(<ProjectTodoPanel clientId="client-1" projectPath="/workspace" onSelectWindow={() => {}} />);

    const row = await waitForButton("Fix dispatchTodo");
    act(() => row.click());
    const selector = await waitForElement(
      ".project-todo-detail-dialog .project-todo-move-column-select"
    ) as HTMLSelectElement;

    expect(selector.value).toBe("PENDING");
    expect(selector.options[0].disabled).toBe(true);
    expect(Array.from(selector.options).map((option) => option.textContent)).toEqual([
      "Pending",
      "Todo",
      "Running",
      "Review",
      "Done",
      "Blocked"
    ]);

    act(() => {
      selector.value = "TODO";
      selector.dispatchEvent(new Event("change", { bubbles: true }));
    });
    await waitForRequests();

    expect(apiMocks.updateProjectTodo).toHaveBeenCalledWith("client-1", "/workspace", "todo-1", {
      status: "TODO",
      sort_order: 9
    });
  });

  it("moves a todo card to another project from the detail dialog", async () => {
    const movedTodo: ProjectTodo = { ...todo, project_path: "/workspace/target", sort_order: 1 };
    apiMocks.fetchProjectTodos.mockResolvedValue({ todos: [todo] });
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(JSON.stringify(movedTodo), {
      status: 200,
      headers: { "Content-Type": "application/json" }
    }));
    renderWithQuery(
      <ProjectTodoPanel
        clientId="client-1"
        projectPath="/workspace"
        projects={[currentProject, targetProject]}
        onSelectWindow={() => {}}
      />
    );

    const row = await waitForButton("Fix dispatchTodo");
    act(() => row.click());
    const selector = await waitForElement(
      ".project-todo-detail-dialog .project-todo-move-project-select"
    ) as HTMLSelectElement;

    expect(Array.from(selector.options).map((option) => option.textContent)).toEqual([
      "Select project",
      "Target Project"
    ]);

    apiMocks.fetchProjectTodos.mockResolvedValue({ todos: [] });
    act(() => {
      selector.value = "/workspace/target";
      selector.dispatchEvent(new Event("change", { bubbles: true }));
    });
    await waitForRequests();

    const call = fetchMock.mock.calls.at(-1);
    expect(call).toBeDefined();
    const url = new URL(String(call?.[0]));
    expect(url.pathname).toBe("/api/clients/client-1/projects/todos/todo-1/move-project");
    expect(url.searchParams.get("project_path")).toBe("/workspace");
    expect(call?.[1]?.method).toBe("POST");
    expect(JSON.parse(String(call?.[1]?.body))).toEqual({
      project_path: "/workspace/target"
    });
    expect(document.body.querySelector(".project-todo-detail-dialog")).toBeNull();
    expect(document.body.textContent).not.toContain("Fix dispatchTodo");
  });

  it("does not show the project move selector for non-todo cards", async () => {
    const doneTodo: ProjectTodo = {
      ...todo,
      status: "DONE"
    };
    apiMocks.fetchProjectTodos.mockResolvedValue({ todos: [doneTodo] });
    renderWithQuery(
      <ProjectTodoPanel
        clientId="client-1"
        projectPath="/workspace"
        projects={[currentProject, targetProject]}
        onSelectWindow={() => {}}
      />
    );

    const row = await waitForButton("Fix dispatchDone");
    act(() => row.click());
    await waitForElement(".project-todo-detail-dialog");

    expect(document.body.querySelector(".project-todo-move-project-select")).toBeNull();
  });
});
