import { act } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ApiError } from "../src/apiCore";
import {
  cleanupProjectTodoTest,
  renderWithQuery,
  setValue,
  setupProjectTodoTest,
  defaultTodoType,
  todo,
  waitForButton,
  waitForElement,
  waitForElementText,
  waitForLabeledButton,
  waitForRequests
} from "./projectTodoTestHarness";
import { ProjectTodoPanel } from "../src/components/ProjectTodoPanel";
import type { ProjectTodo } from "../src/types";

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
  fetchSystemModelPresets: vi.fn(),
  fetchProjectTodo: vi.fn(),
  fetchProjectTodoHistory: vi.fn(),
  fetchProjectTodoTypes: vi.fn(),
  fetchProjectTodos: vi.fn(),
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

function placeCaretAtEnd(target: HTMLInputElement | HTMLTextAreaElement): void {
  act(() => {
    target.setSelectionRange(target.value.length, target.value.length);
    target.dispatchEvent(new KeyboardEvent("keyup", { bubbles: true, key: "End" }));
  });
}

describe("ProjectTodoPanel", () => {
  it("clears a stale kanban todo detail route when the card no longer exists", async () => {
    window.history.replaceState(
      null,
      "",
      "/clients/client-1/kanban?project_path=%2Fworkspace&window_id=window-1&todo_id=missing-todo"
    );
    apiMocks.fetchProjectTodo.mockRejectedValue(new ApiError(404, "Not Found", "todo not found"));
    renderWithQuery(
      <ProjectTodoPanel
        clientId="client-1"
        projectPath="/workspace"
        routeWindowId="window-1"
        viewMode="board"
        onSelectWindow={() => {}}
      />
    );

    await waitForRequests();
    await waitForElement(".project-todo-board-shell");
    for (let attempt = 0; attempt < 20 && apiMocks.fetchProjectTodo.mock.calls.length === 0; attempt += 1) {
      await waitForRequests();
    }
    for (let attempt = 0; attempt < 20 && document.body.querySelector(".project-todo-detail-dialog") !== null; attempt += 1) {
      await waitForRequests();
    }

    expect(apiMocks.fetchProjectTodo).toHaveBeenCalledWith("client-1", "/workspace", "missing-todo");
    expect(document.body.querySelector(".project-todo-detail-dialog")).toBeNull();
    expect(`${window.location.pathname}${window.location.search}`).toBe(
      "/clients/client-1/kanban?project_path=%2Fworkspace&window_id=window-1"
    );
  });

  it("keeps board management and quick creation out of the kanban workspace", async () => {
    renderWithQuery(
      <ProjectTodoPanel
        clientId="client-1"
        projectPath="/workspace"
        viewMode="board"
        onSelectWindow={() => {}}
      />
    );

    const panel = await waitForElement(".project-todos");

    expect(panel.querySelector(".project-todo-management-bar")).toBeNull();
    expect(panel.querySelector(".project-todo-form-quick")).toBeNull();
    expect(panel.querySelector(".project-todo-board-shell")).not.toBeNull();
  });

  it("filters the board to a parent card and its children from the parent card icon", async () => {
    const parentTodo: ProjectTodo = {
      ...todo,
      id: "todo-parent",
      title: "Parent feature",
      child_todos: [{
        id: "todo-child",
        title: "Child task",
        status: "TODO",
        completed_at: null
      }]
    };
    const childTodo: ProjectTodo = {
      ...todo,
      id: "todo-child",
      title: "Child task",
      parent_todo_id: "todo-parent",
      parent_todo: {
        id: "todo-parent",
        title: "Parent feature",
        status: "TODO",
        completed_at: null
      },
      sort_order: 2
    };
    const unrelatedTodo: ProjectTodo = {
      ...todo,
      id: "todo-other",
      title: "Unrelated task",
      sort_order: 3
    };
    apiMocks.fetchProjectTodos.mockResolvedValue({ todos: [parentTodo, childTodo, unrelatedTodo] });
    renderWithQuery(
      <ProjectTodoPanel
        clientId="client-1"
        projectPath="/workspace"
        viewMode="board"
        onSelectWindow={() => {}}
      />
    );

    const childFilterButton = await waitForLabeledButton("Show parent and child cards for Parent feature");
    act(() => childFilterButton.click());

    const cards = document.body.querySelectorAll(".project-todo-card");
    const parentCard = document.body.querySelector("[data-project-todo-id='todo-parent']");
    expect(cards).toHaveLength(2);
    expect(parentCard).toBeDefined();
    expect(parentCard?.classList.contains("child-filter-parent")).toBe(true);
    expect(document.body.textContent).toContain("Child task");
    expect(document.body.textContent).toContain("Parent feature and child cards");
    expect(document.body.textContent).not.toContain("Unrelated task");
  });

  it("shows child card title above parent card title on board cards", async () => {
    const parentTodo: ProjectTodo = {
      ...todo,
      id: "todo-parent",
      title: "Parent feature",
      sort_order: 1
    };
    const childTodo: ProjectTodo = {
      ...todo,
      id: "todo-child",
      title: "Child task",
      parent_todo_id: "todo-parent",
      parent_todo: {
        id: "todo-parent",
        title: "Parent feature",
        status: "TODO",
        completed_at: null
      },
      sort_order: 2
    };
    apiMocks.fetchProjectTodos.mockResolvedValue({ todos: [parentTodo, childTodo] });
    renderWithQuery(
      <ProjectTodoPanel
        clientId="client-1"
        projectPath="/workspace"
        viewMode="board"
        onSelectWindow={() => {}}
      />
    );

    const childCard = await waitForElement("[data-project-todo-id='todo-child']");
    const parentTitle = childCard.querySelector(".project-todo-card-parent-title");
    const childTitle = childCard.querySelector(".project-todo-card-child-title");

    expect(childTitle?.textContent).toBe("Child task");
    expect(parentTitle?.textContent).toBe("Parent feature");
    expect(childTitle?.tagName).toBe("SPAN");
    expect(parentTitle?.tagName).toBe("SMALL");
    expect(childTitle?.compareDocumentPosition(parentTitle as Node) ?? 0).toBe(Node.DOCUMENT_POSITION_FOLLOWING);
  });

  it("creates system card types and shows project-scoped types as read-only", async () => {
    apiMocks.fetchProjectTodoTypes.mockResolvedValue({
      todo_types: [
        defaultTodoType,
        {
          id: "bug",
          scope: "project",
          client_id: "client-1",
          project_path: "/workspace",
          name: "Bug",
          description: "Project bug cards",
          agent: "codex",
          agent_profile_id: "bug-profile",
          artifact_kinds: [],
          dispatch_template: null,
          created_at: "2026-06-05T00:00:00Z",
          updated_at: "2026-06-05T00:00:00Z"
        }
      ]
    });
    apiMocks.upsertSystemProjectTodoType.mockResolvedValue({
      ...defaultTodoType,
      id: "research",
      name: "Research",
      agent: "codex"
    });
    renderWithQuery(<ProjectTodoPanel clientId="client-1" projectPath="/workspace" onSelectWindow={() => {}} />);

    expect(document.body.querySelector(".project-todo-type-manager")).toBeNull();
    const manageButton = await waitForButton("Card type management");
    act(() => {
      manageButton.click();
    });
    await waitForElement(".project-todo-type-manager-modal");
    await waitForElementText(".project-todo-type-row.read-only", "Bug");
    expect(document.body.querySelector(".project-todo-type-row.read-only")?.textContent).toContain("Project");
    expect(document.body.querySelector(".project-todo-type-row.read-only button")).toBeNull();

    const idInput = document.body.querySelector(".project-todo-type-form input") as HTMLInputElement;
    const nameInput = document.body.querySelectorAll(".project-todo-type-form input")[1] as HTMLInputElement;
    const agentSelect = document.body.querySelector(".project-todo-type-form select") as HTMLSelectElement;
    setValue(idInput, "research");
    setValue(nameInput, "Research");
    act(() => {
      agentSelect.value = "codex";
      agentSelect.dispatchEvent(new Event("change", { bubbles: true }));
    });
    const createButton = await waitForButton("Create", ".project-todo-type-form button");
    act(() => createButton.click());
    await waitForRequests();

    expect(apiMocks.upsertSystemProjectTodoType).toHaveBeenCalledWith("client-1", {
      id: "research",
      name: "Research",
      description: null,
      agent: "codex",
      agent_profile_id: null,
      artifact_kinds: [],
      input_artifact_ids: [],
      dispatch_template: null
    });
  });

  it("queues dispatch after selected upstream todos", async () => {
    const onSelectWindow = vi.fn();
    const upstreamTodo: ProjectTodo = {
      ...todo,
      id: "todo-2",
      title: "Build API",
      sort_order: 2
    };
    apiMocks.fetchProjectTodos.mockResolvedValue({ todos: [todo, upstreamTodo] });
    apiMocks.dispatchProjectTodo.mockResolvedValue({
      ...todo,
      status: "TODO",
      assigned_agent: "codex",
      queued_dispatch: true,
      dependencies: [{
        id: "todo-2",
        title: "Build API",
        status: "TODO",
        completed_at: null
      }]
    });
    renderWithQuery(<ProjectTodoPanel clientId="client-1" projectPath="/workspace" onSelectWindow={onSelectWindow} />);

    const row = await waitForButton("Fix dispatchTodo");
    act(() => row.click());
    const cardDispatch = await waitForButton("Dispatch", ".project-todo-actions button");
    act(() => cardDispatch.click());
    const dependencyOption = await waitForElementText(".project-todo-dispatch-after-option", "Build API");
    const checkbox = dependencyOption.querySelector("input");
    if (!(checkbox instanceof HTMLInputElement)) {
      throw new Error("Dependency checkbox was not rendered");
    }
    act(() => checkbox.click());
    const modalDispatch = await waitForButton("Dispatch", ".terminal-create-actions button");
    act(() => modalDispatch.click());
    await waitForRequests();

    expect(apiMocks.dispatchProjectTodo).toHaveBeenCalledWith("client-1", "/workspace", "todo-1", {
      agent_launch: {
        agent: "codex",
        command: "codex",
        config: null,
        profile_id: null
      },
      dispatch_mode: "submit",
      dispatch_after_todo_ids: ["todo-2"],
      prompt: null
    });
    expect(onSelectWindow).not.toHaveBeenCalled();
  });

  it("filters dispatch dependencies by board column in board order", async () => {
    const dispatchTarget: ProjectTodo = {
      ...todo,
      dependencies: [{
        id: "todo-pending",
        title: "Queued work",
        status: "TODO",
        completed_at: null
      }]
    };
    const candidates: ProjectTodo[] = [
      {
        ...todo,
        id: "todo-done",
        title: "Done work",
        status: "DONE",
        sort_order: 4
      },
      {
        ...todo,
        id: "todo-todo-low",
        title: "Older todo",
        sort_order: 1
      },
      {
        ...todo,
        id: "todo-blocked",
        title: "Blocked work",
        status: "BLOCKED",
        sort_order: 5
      },
      {
        ...todo,
        id: "todo-pending",
        title: "Queued work",
        queued_dispatch: true,
        sort_order: 3
      },
      {
        ...todo,
        id: "todo-running",
        title: "Running work",
        status: "DISPATCHED",
        sort_order: 2
      },
      {
        ...todo,
        id: "todo-review",
        title: "Review work",
        status: "AWAITING_REVIEW",
        sort_order: 6
      },
      {
        ...todo,
        id: "todo-todo-high",
        title: "Newer todo",
        sort_order: 7
      }
    ];
    apiMocks.fetchProjectTodos.mockResolvedValue({ todos: [dispatchTarget, ...candidates] });
    apiMocks.dispatchProjectTodo.mockResolvedValue({
      ...todo,
      status: "TODO",
      assigned_agent: "codex",
      dependencies: [
        {
          id: "todo-pending",
          title: "Queued work",
          status: "TODO",
          completed_at: null
        }
      ]
    });
    renderWithQuery(<ProjectTodoPanel clientId="client-1" projectPath="/workspace" onSelectWindow={() => {}} />);

    const row = await waitForButton("Fix dispatchTodo");
    act(() => row.click());
    const cardDispatch = await waitForButton("Dispatch", ".project-todo-actions button");
    act(() => cardDispatch.click());
    await waitForElementText(".project-todo-dispatch-after-option", "Newer todo");

    const optionTitles = () => Array.from(
      document.body.querySelectorAll(".project-todo-dispatch-after-option strong")
    ).map((element) => element.textContent);

    expect(optionTitles()).toEqual([
      "Newer todo",
      "Older todo",
      "Queued work",
      "Running work",
      "Review work",
      "Done work",
      "Blocked work"
    ]);

    const pendingFilter = await waitForButton("Pending1", ".project-todo-dispatch-after-filters button");
    act(() => pendingFilter.click());

    expect(optionTitles()).toEqual(["Queued work"]);
    const queuedCheckbox = document.body.querySelector(".project-todo-dispatch-after-option input");
    expect(queuedCheckbox).toBeInstanceOf(HTMLInputElement);
    expect((queuedCheckbox as HTMLInputElement).checked).toBe(true);

    const todoFilter = await waitForButton("Todo2", ".project-todo-dispatch-after-filters button");
    act(() => todoFilter.click());

    expect(optionTitles()).toEqual(["Newer todo", "Older todo"]);
    const modalDispatch = await waitForButton("Dispatch", ".terminal-create-actions button");
    act(() => modalDispatch.click());
    await waitForRequests();

    expect(apiMocks.dispatchProjectTodo).toHaveBeenCalledWith("client-1", "/workspace", "todo-1", {
      agent_launch: {
        agent: "codex",
        command: "codex",
        config: null,
        profile_id: null
      },
      dispatch_mode: "submit",
      dispatch_after_todo_ids: ["todo-pending"],
      prompt: null
    });
  });

  it("renders referenced cards as description links that open the target card", async () => {
    const targetTodo: ProjectTodo = {
      ...todo,
      id: "todo-2",
      title: "Build API",
      description: "Coordinate backend contract",
      status: "BLOCKED",
      sort_order: 2
    };
    const sourceTodo: ProjectTodo = {
      ...todo,
      title: "Wire UI",
      description: "Use @[其它需求：$Build API] before dispatch",
      referenced_todos: [{
        id: "todo-2",
        title: "Build API",
        description: "Coordinate backend contract",
        status: "BLOCKED"
      }]
    };
    apiMocks.fetchProjectTodos.mockResolvedValue({ todos: [sourceTodo, targetTodo] });
    renderWithQuery(<ProjectTodoPanel clientId="client-1" projectPath="/workspace" onSelectWindow={() => {}} />);

    const row = await waitForButton("Wire UITodo");
    act(() => row.click());
    const referenceLink = await waitForElement(".project-todo-reference-link");
    const preview = await waitForElement(".project-todo-reference-preview");

    expect(referenceLink.textContent).toBe("Build API");
    expect(preview.textContent).toContain("Build API");
    expect(preview.textContent).toContain("Coordinate backend contract");

    act(() => {
      (referenceLink as HTMLButtonElement).click();
    });

    await waitForElementText(".project-todo-detail-dialog h2", "Build API");
  });

});
