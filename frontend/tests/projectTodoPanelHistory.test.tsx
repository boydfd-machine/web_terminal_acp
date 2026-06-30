import { act } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  cleanupProjectTodoTest,
  renderWithQuery,
  setupProjectTodoTest,
  todo,
  waitForButton,
  waitForElementText,
  waitForLabeledButton,
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
  fetchProjectTodo: vi.fn(),
  fetchProjectTodoHistory: vi.fn(),
  fetchProjectTodos: vi.fn(),
  fetchProjectTodoTypes: vi.fn(),
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

describe("ProjectTodoPanel history", () => {
  it("shows card history and restores an earlier title and description version", async () => {
    apiMocks.fetchProjectTodoHistory.mockResolvedValue({
      todo_id: "todo-1",
      versions: [
        {
          id: "version-2",
          todo_id: "todo-1",
          version_number: 2,
          title: "Fix dispatch",
          description: "Old details",
          actor_type: "user",
          actor_id: "user-1",
          actor_display: "Operator",
          created_at: "2026-06-05T00:02:00Z"
        },
        {
          id: "version-1",
          todo_id: "todo-1",
          version_number: 1,
          title: "Restore dispatch copy",
          description: "Recovered details",
          actor_type: "agent",
          actor_id: "window-2",
          actor_display: "Codex",
          created_at: "2026-06-05T00:01:00Z"
        }
      ],
      audit_logs: [
        {
          id: "audit-2",
          todo_id: "todo-1",
          action: "updated",
          fields: ["title", "description"],
          actor_type: "agent",
          actor_id: "window-2",
          actor_display: "Codex",
          restored_version_number: null,
          created_at: "2026-06-05T00:02:00Z"
        },
        {
          id: "audit-1",
          todo_id: "todo-1",
          action: "created",
          fields: ["title", "description"],
          actor_type: "user",
          actor_id: "user-1",
          actor_display: "Operator",
          restored_version_number: null,
          created_at: "2026-06-05T00:00:00Z"
        }
      ]
    });
    apiMocks.restoreProjectTodoVersion.mockResolvedValue({
      ...todo,
      title: "Restore dispatch copy",
      description: "Recovered details"
    });
    renderWithQuery(<ProjectTodoPanel clientId="client-1" projectPath="/workspace" onSelectWindow={() => {}} />);

    const row = await waitForButton("Fix dispatchTodo");
    act(() => row.click());
    await waitForElementText(".project-todo-history-panel", "Version 1");
    await waitForElementText(".project-todo-history-panel", "Audit log");
    await waitForElementText(".project-todo-history-panel", "Codex");

    const restoreButton = await waitForLabeledButton("Restore version 1");
    act(() => restoreButton.click());
    const confirmButton = await waitForButton("Restore", ".app-prompt-actions button");
    act(() => confirmButton.click());
    await waitForRequests();

    expect(apiMocks.restoreProjectTodoVersion).toHaveBeenCalledWith("client-1", "/workspace", "todo-1", 1);
    await waitForElementText(".project-todo-detail-heading", "Restore dispatch copy");
    await waitForElementText(".project-todo-detail-description", "Recovered details");
  });

  it("shows an empty history when the history payload omits item lists", async () => {
    apiMocks.fetchProjectTodoHistory.mockResolvedValue({ todo_id: "todo-1" });
    renderWithQuery(<ProjectTodoPanel clientId="client-1" projectPath="/workspace" onSelectWindow={() => {}} />);

    const row = await waitForButton("Fix dispatchTodo");
    act(() => row.click());

    await waitForElementText(".project-todo-history-panel", "No title or description versions yet.");
    expect(document.body.querySelector(".project-todo-detail-dialog")).not.toBeNull();
  });
});
