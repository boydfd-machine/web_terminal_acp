import { act } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ProjectTodoDispatchToast } from "../src/components/ProjectTodoDispatchToast";
import {
  cleanupProjectTodoTest,
  dataTransferStub,
  dragEvent,
  renderWithQuery,
  setValue,
  setupProjectTodoTest,
  todo,
  waitForButton,
  waitForElement,
  waitForElementText,
  waitForLabeledButton,
  waitForRequests
} from "./projectTodoTestHarness";
import { ProjectTodoPanel } from "../src/components/ProjectTodoPanel";
import { WindowProjectTodoLinks } from "../src/components/WindowProjectTodoLinks";
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

describe("ProjectTodoPanel board and review flows", () => {
  it("moves a board card into another status column by drag and drop", async () => {
    const reviewTodo: ProjectTodo = {
      ...todo,
      id: "todo-2",
      title: "Review target",
      status: "AWAITING_REVIEW",
      sort_order: 7
    };
    const queuedTodo: ProjectTodo = {
      ...todo,
      id: "todo-3",
      title: "Queued dependency",
      queued_dispatch: true,
      sort_order: 3
    };
    apiMocks.fetchProjectTodos.mockResolvedValue({ todos: [todo, reviewTodo, queuedTodo] });
    apiMocks.updateProjectTodo
      .mockResolvedValueOnce({
        ...todo,
        status: "AWAITING_REVIEW",
        sort_order: 8
      })
      .mockResolvedValueOnce({
        ...queuedTodo,
        queued_dispatch: false
      });
    renderWithQuery(
      <ProjectTodoPanel
        clientId="client-1"
        projectPath="/workspace"
        viewMode="board"
        onSelectWindow={() => {}}
      />
    );
    const card = await waitForElementText(".project-todo-card", "Fix dispatch");
    const reviewColumn = await waitForElement(".project-todo-column[aria-label='Review']");
    const pendingColumn = await waitForElement(".project-todo-column[aria-label='Pending']");
    if (!(card instanceof HTMLElement) || !(reviewColumn instanceof HTMLElement) || !(pendingColumn instanceof HTMLElement)) {
      throw new Error("Board drag targets were not rendered");
    }
    const dataTransfer = dataTransferStub();

    let dragOverEvent: Event | null = null;
    act(() => {
      card.dispatchEvent(dragEvent("dragstart", dataTransfer));
    });
    expect(reviewColumn.classList.contains("drop-available")).toBe(true);
    expect(pendingColumn.classList.contains("drop-available")).toBe(false);
    expect(reviewColumn.classList.contains("drop-target")).toBe(false);

    act(() => {
      dragOverEvent = dragEvent("dragover", dataTransfer);
      reviewColumn.dispatchEvent(dragOverEvent);
    });
    expect(dragOverEvent?.defaultPrevented).toBe(true);
    expect(reviewColumn.classList.contains("drop-target")).toBe(true);
    act(() => {
      reviewColumn.dispatchEvent(dragEvent("drop", dataTransfer));
    });
    await waitForRequests();

    expect(apiMocks.updateProjectTodo).toHaveBeenCalledWith("client-1", "/workspace", "todo-1", {
      status: "AWAITING_REVIEW",
      sort_order: 8
    });

    const queuedCard = await waitForElementText(
      ".project-todo-column[aria-label='Pending'] .project-todo-card",
      "Queued dependency"
    );
    const todoColumn = await waitForElement(".project-todo-column[aria-label='Todo']");
    if (!(queuedCard instanceof HTMLElement) || !(todoColumn instanceof HTMLElement)) {
      throw new Error("Pending to Todo drag targets were not rendered");
    }
    const cancelTransfer = dataTransferStub();
    act(() => {
      queuedCard.dispatchEvent(dragEvent("dragstart", cancelTransfer));
      todoColumn.dispatchEvent(dragEvent("dragover", cancelTransfer));
      todoColumn.dispatchEvent(dragEvent("drop", cancelTransfer));
    });
    await waitForRequests();

    const lastCall = apiMocks.updateProjectTodo.mock.calls[apiMocks.updateProjectTodo.mock.calls.length - 1]!;
    expect(lastCall.slice(0, 3)).toEqual(["client-1", "/workspace", "todo-3"]);
    expect(lastCall[3]).toMatchObject({ status: "TODO" });
  });

  it("requires a three second hover and confirmation before merging board cards", async () => {
    const sourceTodo: ProjectTodo = {
      ...todo,
      title: "Source card",
      description: "Source details"
    };
    const targetTodo: ProjectTodo = {
      ...todo,
      id: "todo-2",
      title: "Target card",
      description: "Target details",
      sort_order: 2
    };
    apiMocks.fetchProjectTodos.mockResolvedValue({ todos: [sourceTodo, targetTodo] });
    apiMocks.fetchProjectTodo.mockImplementation((_clientId, _projectPath, todoId) => Promise.resolve(
      todoId === "todo-2" ? targetTodo : sourceTodo
    ));
    apiMocks.updateProjectTodo.mockResolvedValue({
      ...targetTodo,
      title: "Target card / Source card",
      description: "Target details\n\nSource details"
    });
    apiMocks.deleteProjectTodo.mockResolvedValue(undefined);
    renderWithQuery(
      <ProjectTodoPanel
        clientId="client-1"
        projectPath="/workspace"
        viewMode="board"
        onSelectWindow={() => {}}
      />
    );
    const sourceCard = await waitForElementText(".project-todo-card", "Source card");
    const targetCard = await waitForElementText(".project-todo-card", "Target card");
    if (!(sourceCard instanceof HTMLElement) || !(targetCard instanceof HTMLElement)) {
      throw new Error("Board cards were not rendered");
    }
    const dataTransfer = dataTransferStub();

    try {
      vi.useFakeTimers();
      act(() => {
        sourceCard.dispatchEvent(dragEvent("dragstart", dataTransfer));
        targetCard.dispatchEvent(dragEvent("dragenter", dataTransfer));
      });
      expect(document.body.querySelector(".project-todo-card.merge-target")?.textContent).toContain("Target card");
      await act(async () => {
        vi.advanceTimersByTime(2999);
        await Promise.resolve();
      });
      expect(document.body.querySelector('[role="alertdialog"]')).toBeNull();
      expect(apiMocks.updateProjectTodo).not.toHaveBeenCalled();

      await act(async () => {
        vi.advanceTimersByTime(1);
        await Promise.resolve();
      });
      vi.useRealTimers();
      const mergeButton = await waitForPromptAction("Merge");
      expect(document.body.querySelector('[role="alertdialog"]')?.textContent).toContain(
        'Merge "Source card" into "Target card"?'
      );
      await act(async () => {
        mergeButton.click();
      });
      await waitForRequests();

      expect(apiMocks.updateProjectTodo).toHaveBeenCalledWith("client-1", "/workspace", "todo-2", {
        title: "Target card / Source card",
        description: "Target details\n\nSource details"
      });
      expect(apiMocks.updateProjectTodo).toHaveBeenCalledTimes(1);
      expect(apiMocks.deleteProjectTodo).toHaveBeenCalledWith("client-1", "/workspace", "todo-1");
    } finally {
      vi.useRealTimers();
    }
  });

  it("does not merge board cards when the confirmation is cancelled", async () => {
    const sourceTodo: ProjectTodo = {
      ...todo,
      title: "Source card",
      description: "Source details"
    };
    const targetTodo: ProjectTodo = {
      ...todo,
      id: "todo-2",
      title: "Target card",
      description: "Target details",
      sort_order: 2
    };
    apiMocks.fetchProjectTodos.mockResolvedValue({ todos: [sourceTodo, targetTodo] });
    renderWithQuery(
      <ProjectTodoPanel
        clientId="client-1"
        projectPath="/workspace"
        viewMode="board"
        onSelectWindow={() => {}}
      />
    );
    const sourceCard = await waitForElementText(".project-todo-card", "Source card");
    const targetCard = await waitForElementText(".project-todo-card", "Target card");
    if (!(sourceCard instanceof HTMLElement) || !(targetCard instanceof HTMLElement)) {
      throw new Error("Board cards were not rendered");
    }
    const dataTransfer = dataTransferStub();

    try {
      vi.useFakeTimers();
      act(() => {
        sourceCard.dispatchEvent(dragEvent("dragstart", dataTransfer));
        targetCard.dispatchEvent(dragEvent("dragenter", dataTransfer));
      });
      await act(async () => {
        vi.advanceTimersByTime(3000);
        await Promise.resolve();
      });
      vi.useRealTimers();
      const cancelButton = await waitForPromptAction("Cancel");
      expect(document.body.querySelector('[role="alertdialog"]')?.textContent).toContain(
        'Merge "Source card" into "Target card"?'
      );
      await act(async () => {
        cancelButton.click();
      });
      await waitForRequests();

      expect(apiMocks.updateProjectTodo).not.toHaveBeenCalled();
      expect(apiMocks.deleteProjectTodo).not.toHaveBeenCalled();
    } finally {
      vi.useRealTimers();
    }
  });

  it("does not confirm or merge when a card is dropped before the hover delay", async () => {
    const sourceTodo: ProjectTodo = {
      ...todo,
      title: "Source card",
      description: "Source details"
    };
    const targetTodo: ProjectTodo = {
      ...todo,
      id: "todo-2",
      title: "Target card",
      description: "Target details",
      sort_order: 2
    };
    apiMocks.fetchProjectTodos.mockResolvedValue({ todos: [sourceTodo, targetTodo] });
    renderWithQuery(
      <ProjectTodoPanel
        clientId="client-1"
        projectPath="/workspace"
        viewMode="board"
        onSelectWindow={() => {}}
      />
    );
    const sourceCard = await waitForElementText(".project-todo-card", "Source card");
    const targetCard = await waitForElementText(".project-todo-card", "Target card");
    if (!(sourceCard instanceof HTMLElement) || !(targetCard instanceof HTMLElement)) {
      throw new Error("Board cards were not rendered");
    }
    const dataTransfer = dataTransferStub();

    try {
      vi.useFakeTimers();
      act(() => {
        sourceCard.dispatchEvent(dragEvent("dragstart", dataTransfer));
        targetCard.dispatchEvent(dragEvent("dragenter", dataTransfer));
        targetCard.dispatchEvent(dragEvent("drop", dataTransfer));
      });
      await act(async () => {
        vi.advanceTimersByTime(3000);
        await Promise.resolve();
      });
      vi.useRealTimers();
      await waitForRequests();

      expect(document.body.querySelector('[role="alertdialog"]')).toBeNull();
      expect(apiMocks.updateProjectTodo).not.toHaveBeenCalled();
      expect(apiMocks.deleteProjectTodo).not.toHaveBeenCalled();
    } finally {
      vi.useRealTimers();
    }
  });

  it("does not merge cards from plain text drag data", async () => {
    const sourceTodo: ProjectTodo = {
      ...todo,
      title: "Source card",
      description: "Source details"
    };
    const targetTodo: ProjectTodo = {
      ...todo,
      id: "todo-2",
      title: "Target card",
      description: "Target details",
      sort_order: 2
    };
    apiMocks.fetchProjectTodos.mockResolvedValue({ todos: [sourceTodo, targetTodo] });
    renderWithQuery(
      <ProjectTodoPanel
        clientId="client-1"
        projectPath="/workspace"
        viewMode="board"
        onSelectWindow={() => {}}
      />
    );
    const targetCard = await waitForElementText(".project-todo-card", "Target card");
    if (!(targetCard instanceof HTMLElement)) {
      throw new Error("Target board card was not rendered");
    }
    const dataTransfer = dataTransferStub();
    dataTransfer.setData("text/plain", "todo-1");

    try {
      vi.useFakeTimers();
      act(() => {
        targetCard.dispatchEvent(dragEvent("dragenter", dataTransfer));
      });
      await act(async () => {
        vi.advanceTimersByTime(3000);
        await Promise.resolve();
      });
      vi.useRealTimers();
      await waitForRequests();

      expect(document.body.querySelector('[role="alertdialog"]')).toBeNull();
      expect(apiMocks.updateProjectTodo).not.toHaveBeenCalled();
      expect(apiMocks.deleteProjectTodo).not.toHaveBeenCalled();
    } finally {
      vi.useRealTimers();
    }
  });

  it("does not merge when the dragged source card is outside the todo column", async () => {
    const sourceTodo: ProjectTodo = {
      ...todo,
      title: "Running source",
      description: "Running details",
      status: "DISPATCHED"
    };
    const targetTodo: ProjectTodo = {
      ...todo,
      id: "todo-2",
      title: "Target card",
      description: "Target details",
      sort_order: 2
    };
    apiMocks.fetchProjectTodos.mockResolvedValue({ todos: [sourceTodo, targetTodo] });
    renderWithQuery(
      <ProjectTodoPanel
        clientId="client-1"
        projectPath="/workspace"
        viewMode="board"
        onSelectWindow={() => {}}
      />
    );
    const sourceCard = await waitForElementText(".project-todo-card", "Running source");
    const targetCard = await waitForElementText(".project-todo-card", "Target card");
    if (!(sourceCard instanceof HTMLElement) || !(targetCard instanceof HTMLElement)) {
      throw new Error("Board cards were not rendered");
    }
    const dataTransfer = dataTransferStub();

    try {
      vi.useFakeTimers();
      act(() => {
        sourceCard.dispatchEvent(dragEvent("dragstart", dataTransfer));
        targetCard.dispatchEvent(dragEvent("dragenter", dataTransfer));
      });
      await act(async () => {
        vi.advanceTimersByTime(3000);
        await Promise.resolve();
      });
      vi.useRealTimers();
      await waitForRequests();

      expect(document.body.querySelector('[role="alertdialog"]')).toBeNull();
      expect(apiMocks.updateProjectTodo).not.toHaveBeenCalled();
      expect(apiMocks.deleteProjectTodo).not.toHaveBeenCalled();
    } finally {
      vi.useRealTimers();
    }
  });
});
