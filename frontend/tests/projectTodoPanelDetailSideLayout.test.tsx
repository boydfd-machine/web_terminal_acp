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

describe("ProjectTodoPanel detail side column layout", () => {
  it("collapses the metadata summary by default and expands the editable fields on toggle", async () => {
    apiMocks.fetchProjectTodos.mockResolvedValue({ todos: [todo] });
    renderWithQuery(<ProjectTodoPanel clientId="client-1" projectPath="/workspace" onSelectWindow={() => {}} />);

    const row = await waitForButton("Fix dispatchTodo");
    act(() => row.click());
    const dialog = await waitForElement(".project-todo-detail-dialog");
    const summary = dialog.querySelector(".project-todo-detail-list-compact");
    expect(summary?.querySelectorAll(".project-todo-detail-summary-row").length).toBe(8);
    expect(dialog.querySelector(".project-todo-type-select")).toBeNull();
    const toggle = dialog.querySelector(".project-todo-metadata-toggle") as HTMLButtonElement;
    expect(toggle.getAttribute("aria-expanded")).toBe("false");
    act(() => toggle.click());
    await waitForElement(".project-todo-detail-dialog .project-todo-type-select");
    expect(toggle.getAttribute("aria-expanded")).toBe("true");
    expect(dialog.querySelector(".project-todo-detail-list-compact")).toBeNull();
  });

  it("places the terminal actions section above history and out of the action rail", async () => {
    const assignedTodo: ProjectTodo = { ...todo, assigned_window_id: "window-2" };
    apiMocks.fetchProjectTodos.mockResolvedValue({ todos: [assignedTodo] });
    apiMocks.fetchProjectTodo.mockResolvedValue(assignedTodo);
    renderWithQuery(<ProjectTodoPanel clientId="client-1" projectPath="/workspace" onSelectWindow={() => {}} />);
    await waitForRequests();
    const row = await waitForButton("Fix dispatchTodo");
    act(() => row.click());
    const dialog = await waitForElement(".project-todo-detail-dialog");
    const side = dialog.querySelector(".project-todo-detail-side") as HTMLElement;
    const kids = Array.from(side.children);
    const terminalsIndex = kids.findIndex((node) => node.querySelector(".project-todo-terminal-actions"));
    const historyIndex = kids.findIndex((node) => node.classList.contains("project-todo-history-panel"));
    expect(terminalsIndex).toBeGreaterThanOrEqual(0);
    expect(historyIndex).toBeGreaterThan(terminalsIndex);
    expect(dialog.querySelector(".project-todo-action-rail .project-todo-terminal-actions")).toBeNull();
  });
});
