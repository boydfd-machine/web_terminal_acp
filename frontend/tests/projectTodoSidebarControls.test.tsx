import { act } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ProjectTodoPanel } from "../src/components/ProjectTodoPanel";
import { ProjectTodoSidebarControls } from "../src/components/ProjectTodoSidebarControls";
import type { ProjectTodo } from "../src/types";
import {
  cleanupProjectTodoTest,
  renderWithQuery,
  setValue,
  setupProjectTodoTest,
  todo,
  waitForElement,
  waitForElementText,
  waitForRequests
} from "./projectTodoTestHarness";

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
  fetchClientSystemAgentConfig: vi.fn(),
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

describe("ProjectTodoSidebarControls", () => {
  it("shows sidebar direct-dispatch creations in the board pending column before dispatch returns", async () => {
    const dateFilter = { range: "30d" as const, customStart: "", customEnd: "" };
    const createdTodo: ProjectTodo = {
      ...todo,
      id: "todo-sidebar-direct",
      title: "Sidebar direct dispatch",
      description: "Launch from the sidebar",
      assigned_agent: "codex",
      sort_order: 2,
      updated_at: new Date().toISOString()
    };
    apiMocks.createProjectTodo.mockResolvedValue(createdTodo);
    apiMocks.dispatchProjectTodo.mockImplementation(() => new Promise(() => {}));

    renderWithQuery(
      <>
        <ProjectTodoSidebarControls
          clientId="client-1"
          dateFilter={dateFilter}
          projectPath="/workspace"
          onDateFilterChange={() => {}}
        />
        <ProjectTodoPanel
          clientId="client-1"
          dateFilter={dateFilter}
          projectPath="/workspace"
          viewMode="board"
          onSelectWindow={() => {}}
        />
      </>
    );

    await waitForElementText(".project-todo-card", "Fix dispatch");
    const form = await waitForElement(".project-todo-sidebar-controls .project-todo-form");
    const titleInput = form.querySelector("input") as HTMLInputElement;
    const descriptionInput = form.querySelector("textarea") as HTMLTextAreaElement;

    setValue(titleInput, "Sidebar direct dispatch");
    setValue(descriptionInput, "Launch from the sidebar");
    act(() => {
      (form.querySelector("button[data-create-action='direct-dispatch']") as HTMLButtonElement).click();
    });
    await waitForRequests();

    expect(apiMocks.createProjectTodo).toHaveBeenCalledWith("client-1", "/workspace", {
      title: "Sidebar direct dispatch",
      description: "Launch from the sidebar"
    });
    expect(apiMocks.dispatchProjectTodo).toHaveBeenCalledWith("client-1", "/workspace", "todo-sidebar-direct", {
      agent_launch: {
        agent: "codex",
        command: "codex",
        config: null,
        profile_id: null
      },
      dispatch_mode: "submit",
      dispatch_after_todo_ids: [],
      prompt: null
    });
    expect(await waitForElementText(
      "[data-project-todo-column='PENDING'] .project-todo-card",
      "Sidebar direct dispatch"
    )).toBeInstanceOf(HTMLElement);
  });
});
