import { act } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  cleanupProjectTodoTest,
  renderWithQuery,
  setupProjectTodoTest,
  todo,
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

const reviewTodo = {
  ...todo,
  status: "AWAITING_REVIEW",
  awaiting_review_at: "2026-06-05T00:05:00Z",
  review_status: "PENDING",
  review_unseen: true
} as const;

beforeEach(() => {
  setupProjectTodoTest(apiMocks);
  apiMocks.fetchProjectTodos
    .mockResolvedValueOnce({ todos: [reviewTodo] })
    .mockResolvedValue({ todos: [{ ...reviewTodo, review_unseen: false }] });
  apiMocks.updateProjectTodo.mockResolvedValue({ ...reviewTodo, review_unseen: false });
});

afterEach(cleanupProjectTodoTest);

describe("project todo unseen review marker", () => {
  it("shows a red dot on unseen review cards and clears it when the card is opened", async () => {
    renderWithQuery(
      <ProjectTodoPanel
        clientId="client-1"
        projectPath="/workspace"
        viewMode="board"
        onSelectWindow={() => {}}
      />
    );

    const card = await waitForElementText(".project-todo-card", "Fix dispatch");
    expect(card.querySelector(".project-todo-review-unseen-dot")).not.toBeNull();
    if (!(card instanceof HTMLElement)) {
      throw new Error("Board card was not rendered as an HTMLElement");
    }

    act(() => card.click());
    await waitForRequests();

    expect(apiMocks.updateProjectTodo).toHaveBeenCalledWith("client-1", "/workspace", "todo-1", {
      review_unseen: false
    });
    expect(document.body.querySelector(".project-todo-review-unseen-dot")).toBeNull();
    expect(document.body.querySelector(".project-todo-detail-dialog")).not.toBeNull();
  });
});
