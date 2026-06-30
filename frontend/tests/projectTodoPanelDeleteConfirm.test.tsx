import { act } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  cleanupProjectTodoTest,
  renderWithQuery,
  setupProjectTodoTest,
  waitForElement,
  waitForElementText,
  waitForRequests
} from "./projectTodoTestHarness";
import { ProjectTodoPanel } from "../src/components/ProjectTodoPanel";

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

async function openBoardCardDeletePrompt(): Promise<void> {
  renderWithQuery(
    <ProjectTodoPanel
      clientId="client-1"
      projectPath="/workspace"
      viewMode="board"
      onSelectWindow={() => {}}
    />
  );
  const card = await waitForElementText(".project-todo-card", "Fix dispatch");
  const mainButton = card.querySelector(".project-todo-card-main");
  if (!(mainButton instanceof HTMLButtonElement)) {
    throw new Error("Board card main button was not rendered");
  }
  act(() => mainButton.click());
  const deleteButton = await waitForElement(
    ".project-todo-detail-dialog .project-todo-detail-delete"
  ) as HTMLButtonElement;
  act(() => deleteButton.click());
}

async function waitForPromptAction(label: string): Promise<HTMLButtonElement> {
  for (let attempt = 0; attempt < 20; attempt += 1) {
    await waitForRequests();
    const dialog = document.body.querySelector('[role="alertdialog"]');
    const button = Array.from(dialog?.querySelectorAll("button") ?? [])
      .find((candidate) => candidate.textContent === label);
    if (button instanceof HTMLButtonElement) {
      return button;
    }
  }
  throw new Error(`Prompt action ${label} was not ready`);
}

describe("ProjectTodoPanel delete confirmation", () => {
  it("does not delete a board card when the confirmation is cancelled", async () => {
    await openBoardCardDeletePrompt();
    await waitForElementText('[role="alertdialog"]', 'Delete card "Fix dispatch"?');

    const cancelButton = await waitForPromptAction("Cancel");
    act(() => cancelButton.click());
    await waitForRequests();

    expect(apiMocks.deleteProjectTodo).not.toHaveBeenCalled();
    expect(document.body.querySelector(".project-todo-detail-dialog")).not.toBeNull();
  });

  it("deletes a board card only after confirmation", async () => {
    apiMocks.deleteProjectTodo.mockResolvedValue(undefined);
    await openBoardCardDeletePrompt();

    const confirmButton = await waitForPromptAction("Delete");
    act(() => confirmButton.click());
    await waitForRequests();

    expect(apiMocks.deleteProjectTodo).toHaveBeenCalledWith("client-1", "/workspace", "todo-1");
  });
});
