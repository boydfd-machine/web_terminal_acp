import { act } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ProjectTodoPanel } from "../src/components/ProjectTodoPanel";
import {
  cleanupProjectTodoTest,
  renderWithQuery,
  setupProjectTodoTest,
  todo,
  waitForElement,
  waitForElementText,
  waitForLabeledButton,
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
  fetchProjectTodo: vi.fn(),
  fetchProjectTodoHistory: vi.fn(),
  fetchProjectTodoTypes: vi.fn(),
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

describe("ProjectTodoPanel child creation", () => {
  it("opens board child creation with the parent card selected", async () => {
    renderWithQuery(
      <ProjectTodoPanel clientId="client-1" projectPath="/workspace" viewMode="board" onSelectWindow={() => {}} />
    );

    const button = await waitForLabeledButton("Create child card under Fix dispatch");
    act(() => button.click());

    expect(await selectedParentTodoId()).toBe("todo-1");
  });

  it("opens list child creation with the parent card selected", async () => {
    renderWithQuery(<ProjectTodoPanel clientId="client-1" projectPath="/workspace" onSelectWindow={() => {}} />);

    const button = await waitForLabeledButton("Create child card under Fix dispatch");
    act(() => button.click());

    expect(await selectedParentTodoId()).toBe("todo-1");
  });

  it("opens detail child creation with the parent card selected", async () => {
    apiMocks.fetchProjectTodos.mockResolvedValue({ todos: [todo] });
    renderWithQuery(<ProjectTodoPanel clientId="client-1" projectPath="/workspace" onSelectWindow={() => {}} />);

    const row = await waitForElementText(".project-todo-list-main", "Fix dispatch");
    act(() => (row as HTMLButtonElement).click());
    await waitForElement(".project-todo-detail-dialog");
    const button = await waitForLabeledButton("Create child card under Fix dispatch");
    act(() => button.click());

    expect(await selectedParentTodoId()).toBe("todo-1");
  });
});

async function selectedParentTodoId(): Promise<string> {
  await waitForRequests();
  const select = await waitForElement(".project-todo-create-dialog .project-todo-parent-selector select");
  if (!(select instanceof HTMLSelectElement)) {
    throw new Error("Parent selector was not rendered");
  }
  return select.value;
}
