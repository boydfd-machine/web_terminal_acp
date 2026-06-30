import { act } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ProjectTodoDispatchToast } from "../src/components/ProjectTodoDispatchToast";
import {
  cleanupProjectTodoTest,
  dataTransferStub,
  dragEvent,
  renderWithQuery,
  setInputFiles,
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
  it("shows the latest board-added cards at the top instead of the newest created cards", async () => {
    apiMocks.fetchProjectTodos.mockResolvedValue({
      todos: [
        todo,
        {
          ...todo,
          id: "todo-2",
          title: "Latest board add",
          sort_order: 2,
          created_at: "2026-01-01T00:00:00Z",
          updated_at: "2026-01-01T00:00:00Z"
        }
      ]
    });
    renderWithQuery(
      <ProjectTodoPanel
        clientId="client-1"
        projectPath="/workspace"
        viewMode="board"
        onSelectWindow={() => {}}
      />
    );

    await waitForElementText(".project-todo-column[aria-label='Todo'] .project-todo-card", "Latest board add");
    const todoCards = Array.from(
      document.body.querySelectorAll(".project-todo-column[aria-label='Todo'] .project-todo-card")
    );

    expect(todoCards).toHaveLength(2);
    expect(todoCards[0]?.textContent).toContain("Latest board add");
    expect(todoCards[1]?.textContent).toContain("Fix dispatch");
  });

  it("shows each board column card count as a readable label", async () => {
    apiMocks.fetchProjectTodos.mockResolvedValue({
      todos: [
        todo,
        {
          ...todo,
          id: "todo-2",
          title: "Ready for review",
          status: "AWAITING_REVIEW",
          sort_order: 2
        },
        {
          ...todo,
          id: "todo-3",
          title: "Another todo",
          sort_order: 3
        }
      ]
    });
    renderWithQuery(
      <ProjectTodoPanel
        clientId="client-1"
        projectPath="/workspace"
        viewMode="board"
        onSelectWindow={() => {}}
      />
    );

    const todoColumn = await waitForElement(".project-todo-column[aria-label='Todo']");
    const reviewColumn = await waitForElement(".project-todo-column[aria-label='Review']");

    expect(todoColumn.querySelector("[data-debug-id='project-todo-column-card-count']")?.textContent).toBe("2 cards");
    expect(reviewColumn.querySelector("[data-debug-id='project-todo-column-card-count']")?.textContent).toBe("1 card");
  });

  it("keeps descriptions out of board list cards", async () => {
    renderWithQuery(
      <ProjectTodoPanel
        clientId="client-1"
        projectPath="/workspace"
        viewMode="board"
        onSelectWindow={() => {}}
      />
    );

    const card = await waitForElementText(".project-todo-card", "Fix dispatch");
    await waitForRequests();

    expect(card.textContent).not.toContain("Old details");
    expect(document.body.querySelector(".project-todo-card-description")).toBeNull();
    expect(document.body.querySelector('textarea[aria-label="Card description"]')).toBeNull();
  });

  it("opens board card details from the card body without hijacking footer actions", async () => {
    renderWithQuery(
      <ProjectTodoPanel
        clientId="client-1"
        projectPath="/workspace"
        viewMode="board"
        onSelectWindow={() => {}}
      />
    );

    const card = await waitForElementText(".project-todo-card", "Fix dispatch");
    if (!(card instanceof HTMLElement)) {
      throw new Error("Board card was not rendered as an HTMLElement");
    }
    act(() => card.click());
    await waitForElement(".project-todo-detail-dialog");

    const closeButton = await waitForLabeledButton("Close todo details");
    act(() => closeButton.click());
    expect(document.body.querySelector(".project-todo-detail-dialog")).toBeNull();

    const dispatchButton = await waitForLabeledButton("Dispatch Fix dispatch");
    act(() => dispatchButton.click());
    await waitForElement(".terminal-create-modal");

    expect(document.body.querySelector(".project-todo-detail-dialog")).toBeNull();
  });

  it("closes board card details with Escape even after an earlier capture listener prevents default", async () => {
    const earlierCaptureListener = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        event.preventDefault();
      }
    };
    window.addEventListener("keydown", earlierCaptureListener, { capture: true });

    try {
      renderWithQuery(
        <ProjectTodoPanel
          clientId="client-1"
          projectPath="/workspace"
          viewMode="board"
          onSelectWindow={() => {}}
        />
      );

      const card = await waitForElementText(".project-todo-card", "Fix dispatch");
      if (!(card instanceof HTMLElement)) {
        throw new Error("Board card was not rendered as an HTMLElement");
      }
      act(() => card.click());
      const dialog = await waitForElement(".project-todo-detail-dialog");

      act(() => {
        dialog.dispatchEvent(new KeyboardEvent("keydown", {
          bubbles: true,
          cancelable: true,
          key: "Escape"
        }));
      });

      expect(document.body.querySelector(".project-todo-detail-dialog")).toBeNull();
    } finally {
      window.removeEventListener("keydown", earlierCaptureListener, { capture: true });
    }
  });

  it("keeps board card details open when Escape is pressed while editing the title", async () => {
    renderWithQuery(
      <ProjectTodoPanel
        clientId="client-1"
        projectPath="/workspace"
        viewMode="board"
        onSelectWindow={() => {}}
      />
    );

    const card = await waitForElementText(".project-todo-card", "Fix dispatch");
    if (!(card instanceof HTMLElement)) {
      throw new Error("Board card was not rendered as an HTMLElement");
    }
    act(() => card.click());
    await waitForElement(".project-todo-detail-dialog");

    const titleButton = await waitForLabeledButton("Edit todo title");
    act(() => titleButton.click());
    const titleInput = await waitForElement('input[aria-label="Todo title"]');
    if (!(titleInput instanceof HTMLInputElement)) {
      throw new Error("Todo title input was not rendered");
    }

    act(() => {
      titleInput.dispatchEvent(new KeyboardEvent("keydown", {
        bubbles: true,
        cancelable: true,
        key: "Escape"
      }));
    });

    expect(document.body.querySelector(".project-todo-detail-dialog")).not.toBeNull();
    expect(document.body.querySelector('input[aria-label="Todo title"]')).not.toBeNull();
  });

  it("keeps board horizontal wheel scrolling available from inside a column", async () => {
    renderWithQuery(
      <ProjectTodoPanel
        clientId="client-1"
        projectPath="/workspace"
        viewMode="board"
        onSelectWindow={() => {}}
      />
    );

    const board = await waitForElement(".project-todo-board");
    const cards = await waitForElement(".project-todo-column[aria-label='Todo'] .project-todo-column-cards");
    if (!(board instanceof HTMLElement) || !(cards instanceof HTMLElement)) {
      throw new Error("Board scroll containers were not rendered as HTMLElements");
    }

    Object.defineProperty(board, "clientWidth", { configurable: true, value: 320 });
    Object.defineProperty(board, "scrollWidth", { configurable: true, value: 960 });
    board.scrollLeft = 24;

    const wheelEvent = new WheelEvent("wheel", {
      bubbles: true,
      cancelable: true,
      deltaX: 96,
      deltaY: 4
    });
    act(() => {
      cards.dispatchEvent(wheelEvent);
    });

    expect(board.scrollLeft).toBe(120);
  });

  it("cancels horizontal card-list wheel input from a non-passive listener", async () => {
    renderWithQuery(
      <ProjectTodoPanel
        clientId="client-1"
        projectPath="/workspace"
        viewMode="board"
        onSelectWindow={() => {}}
      />
    );

    const board = await waitForElement(".project-todo-board");
    const cards = await waitForElement(".project-todo-column[aria-label='Todo'] .project-todo-column-cards");
    if (!(board instanceof HTMLElement) || !(cards instanceof HTMLElement)) {
      throw new Error("Board scroll containers were not rendered as HTMLElements");
    }

    Object.defineProperty(board, "clientWidth", { configurable: true, value: 320 });
    Object.defineProperty(board, "scrollWidth", { configurable: true, value: 960 });
    board.scrollLeft = 24;

    const wheelEvent = new WheelEvent("wheel", {
      bubbles: true,
      cancelable: true,
      deltaX: 96,
      deltaY: 4
    });
    act(() => {
      cards.dispatchEvent(wheelEvent);
    });

    expect(board.scrollLeft).toBe(120);
    expect(wheelEvent.defaultPrevented).toBe(true);
  });

  it("does not start dragging a board card from the attachment upload button", async () => {
    renderWithQuery(
      <ProjectTodoPanel
        clientId="client-1"
        projectPath="/workspace"
        viewMode="board"
        onSelectWindow={() => {}}
      />
    );

    const uploadButton = await waitForLabeledButton("Upload file to Fix dispatch");
    const reviewColumn = await waitForElement(".project-todo-column[aria-label='Review']");
    const dataTransfer = dataTransferStub();

    act(() => {
      uploadButton.dispatchEvent(dragEvent("dragstart", dataTransfer));
    });

    expect(dataTransfer.setData).not.toHaveBeenCalled();
    expect(reviewColumn.classList.contains("drop-available")).toBe(false);
  });

  it("uploads non-image files from board cards", async () => {
    const file = new File(["pdf-bytes"], "requirements.pdf", { type: "application/pdf" });
    renderWithQuery(
      <ProjectTodoPanel
        clientId="client-1"
        projectPath="/workspace"
        viewMode="board"
        onSelectWindow={() => {}}
      />
    );

    const input = await waitForElement(".project-todo-attachment-file-input");
    expect(input).toBeInstanceOf(HTMLInputElement);
    act(() => {
      setInputFiles(input as HTMLInputElement, [file]);
    });

    for (let attempt = 0; attempt < 20 && apiMocks.uploadProjectTodoAttachmentImage.mock.calls.length === 0; attempt += 1) {
      await waitForRequests();
    }

    expect(apiMocks.uploadProjectTodoAttachmentImage).toHaveBeenCalledWith(
      "client-1",
      "/workspace",
      "todo-1",
      file
    );
  });

  it("groups board cards by assigned terminal topic path and filters by terminal tags", async () => {
    apiMocks.fetchProjectTodos.mockResolvedValue({
      todos: [
        {
          ...todo,
          assigned_window_id: "window-1",
          assigned_agent: "codex",
          agent_profile_id: "builtin/default",
          assigned_terminal: {
            id: "window-1",
            title: "Board grouping terminal",
            summary: "Implementing tree grouped project todos.",
            title_tags: ["kanban", "frontend"],
            runtime_tags: ["codex", "/workspace"],
            work_status: { state: "WORKING", label: "Working", color: "green" },
            topic_path: "/Web Terminal ACP/Frontend UI/Board",
            git_worktree: null,
            parent_window_id: null,
            root_window_id: null,
            derived_mode: null,
            created_at: "2026-06-05T00:00:00Z"
          }
        },
        {
          ...todo,
          id: "todo-2",
          title: "Document MCP",
          sort_order: 2,
          assigned_window_id: "window-2",
          assigned_agent: "claude",
          assigned_terminal: {
            id: "window-2",
            title: "MCP docs terminal",
            summary: "Document MCP settings.",
            title_tags: ["mcp"],
            runtime_tags: ["claude", "/workspace"],
            work_status: { state: "LONG_IDLE", label: "Idle", color: "gray" },
            topic_path: "/Skill and MCP/Docs",
            git_worktree: null,
            parent_window_id: null,
            root_window_id: null,
            derived_mode: null,
            created_at: "2026-06-05T00:01:00Z"
          }
        }
      ]
    });
    renderWithQuery(
      <ProjectTodoPanel
        clientId="client-1"
        projectPath="/workspace"
        viewMode="board"
        onSelectWindow={() => {}}
      />
    );

    await waitForElementText(".project-todo-board-group-toggle", "All tasks");
    const groupSelect = document.body.querySelector(".project-todo-board-filters label:first-child select");
    if (!(groupSelect instanceof HTMLSelectElement)) {
      throw new Error("Board group selector was not rendered");
    }
    expect(groupSelect.value).toBe("flat");
    await waitForElementText(".project-todo-card", "Web Terminal ACP / Frontend UI / Board");
    await waitForElementText(".project-todo-card-tags", "kanban");
    const groupedCard = await waitForElementText(".project-todo-card", "Fix dispatch");
    const statusIcon = groupedCard.querySelector(".project-todo-card-agent .project-todo-agent-status-icon");
    const tagRow = groupedCard.querySelector(".project-todo-card-tags");

    expect(groupedCard.textContent).not.toContain("Board grouping terminal");
    expect(groupedCard.querySelector(".project-todo-card-title-row strong small")).toBeNull();
    expect(groupedCard.querySelector(".project-todo-card-summary")).toBeNull();
    expect(statusIcon?.getAttribute("title")).toBe("Agent codex (builtin/default): Working");
    expect(tagRow?.textContent).toBe("builtin/defaultkanban...");
    expect(tagRow?.textContent).not.toContain("frontend");

    act(() => {
      groupSelect.value = "tree";
      groupSelect.dispatchEvent(new Event("change", { bubbles: true }));
    });
    await waitForElementText(".project-todo-board-group-toggle", "Web Terminal ACP");
    await waitForElementText(".project-todo-board-group-toggle", "Skill and MCP");

    const todoColumnTreeSwitch = document.body.querySelector(
      ".project-todo-column[aria-label='Todo'] .project-todo-column-view-toggle input[role='switch']"
    );
    if (!(todoColumnTreeSwitch instanceof HTMLInputElement)) {
      throw new Error("Todo column tree view switch was not rendered");
    }
    act(() => todoColumnTreeSwitch.click());
    await waitForElementText(".project-todo-tree-node-header", "Frontend UI");
    await waitForElementText(".project-todo-tree-node-header", "Docs");
    const treeCard = await waitForElementText(".project-todo-card.tree-card", "Fix dispatch");
    if (!(treeCard instanceof HTMLElement)) {
      throw new Error("Tree card was not rendered as an HTMLElement");
    }
    expect(treeCard.style.getPropertyValue("--tree-depth")).toBe("2");

    const tagFilter = document.body.querySelector(".project-todo-board-filters label:nth-child(4) select");
    if (!(tagFilter instanceof HTMLSelectElement)) {
      throw new Error("Tag filter was not rendered");
    }
    act(() => {
      tagFilter.value = "kanban";
      tagFilter.dispatchEvent(new Event("change", { bubbles: true }));
    });
    await waitForRequests();

    expect(document.body.textContent).toContain("Fix dispatch");
    expect(document.body.textContent).toContain("Web Terminal ACP");
    expect(document.body.textContent).not.toContain("Document MCP");
    expect(document.body.textContent).not.toContain("Skill and MCP");
  });

});
