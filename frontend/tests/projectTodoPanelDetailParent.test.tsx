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

describe("ProjectTodoPanel detail parent selector", () => {
  it("updates the parent card from an open TODO detail dialog", async () => {
    const parentTodo: ProjectTodo = {
      ...todo,
      id: "todo-parent",
      title: "Parent feature",
      sort_order: 2
    };
    const childTodo: ProjectTodo = {
      ...todo,
      id: "todo-child",
      title: "Child task",
      sort_order: 1
    };
    apiMocks.fetchProjectTodos.mockResolvedValue({ todos: [childTodo, parentTodo] });
    apiMocks.updateProjectTodo.mockResolvedValue({
      ...childTodo,
      parent_todo_id: "todo-parent",
      parent_todo: {
        id: "todo-parent",
        title: "Parent feature",
        status: "TODO",
        completed_at: null
      }
    });
    renderWithQuery(<ProjectTodoPanel clientId="client-1" projectPath="/workspace" onSelectWindow={() => {}} />);

    const row = await waitForButton("Child taskTodo");
    act(() => row.click());
    const expandButton = await waitForElement(
      ".project-todo-detail-dialog .project-todo-metadata-toggle"
    ) as HTMLButtonElement;
    act(() => expandButton.click());
    const selector = await waitForElement(
      ".project-todo-detail-dialog .project-todo-detail-parent-selector select"
    ) as HTMLSelectElement;

    act(() => {
      selector.value = "todo-parent";
      selector.dispatchEvent(new Event("change", { bubbles: true }));
    });
    await waitForRequests();

    expect(apiMocks.updateProjectTodo).toHaveBeenCalledWith("client-1", "/workspace", "todo-child", {
      parent_todo_id: "todo-parent"
    });
  });
});
