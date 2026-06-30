import { act } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  cleanupProjectTodoTest,
  renderWithQuery,
  setupProjectTodoTest,
  setValue,
  todo,
  waitForButton,
  waitForElement,
  waitForElementText,
  waitForRequests
} from "./projectTodoTestHarness";
import { ProjectTodoPanel } from "../src/components/ProjectTodoPanel";
import type { ArtifactPluginDescriptor, ProjectTodoStatus } from "../src/types";

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

const artifactPlugin: ArtifactPluginDescriptor = {
  domain: "terminal",
  artifact_kind: "agent_trace_graph",
  label: "Agent Trace Graph",
  default_title: "Agent Trace Graph",
  origin: "built_in",
  editable: false,
  plugin_format: "legacy_python",
  downloadable: false
};
const listButtonTextByStatus: Record<ProjectTodoStatus, string> = {
  TODO: "Fix dispatchTodo",
  BLOCKED: "Fix dispatchBlocked",
  DISPATCHED: "Fix dispatchRunning",
  AWAITING_REVIEW: "Fix dispatchReview",
  DONE: "Fix dispatchDone"
};

describe("ProjectTodoPanel detail comments", () => {
  it("sends selected artifact kinds with a detail comment", async () => {
    apiMocks.fetchArtifactPlugins.mockResolvedValue({ plugins: [artifactPlugin] });
    apiMocks.fetchProjectTodos.mockResolvedValue({
      todos: [{ ...todo, status: "AWAITING_REVIEW", assigned_window_id: "window-2" }]
    });
    apiMocks.commentProjectTodo.mockResolvedValue({
      ...todo,
      status: "TODO",
      assigned_window_id: "window-2",
      artifact_kinds: ["agent_trace_graph"]
    });
    renderWithQuery(<ProjectTodoPanel clientId="client-1" projectPath="/workspace" onSelectWindow={() => {}} />);

    const row = await waitForButton(listButtonTextByStatus.AWAITING_REVIEW);
    act(() => row.click());
    const commentButton = await waitForElementText(
      ".project-todo-detail-dialog .project-todo-terminal-actions button",
      "Comment"
    ) as HTMLButtonElement;
    act(() => commentButton.click());
    const input = await waitForElement(
      ".project-todo-comment-modal .project-todo-comment-artifacts .project-todo-artifact-select-input"
    ) as HTMLInputElement;
    act(() => input.focus());
    const artifactOption = await waitForElement(
      ".project-todo-comment-modal .project-todo-comment-artifacts input[type='checkbox']"
    ) as HTMLInputElement;
    const commentInput = await waitForElement(".project-todo-comment-modal textarea") as HTMLTextAreaElement;

    act(() => artifactOption.click());
    setValue(commentInput, "Please generate a trace for this follow-up.");
    const sendButton = await waitForElementText(".project-todo-comment-actions button", "Send") as HTMLButtonElement;
    act(() => sendButton.click());
    await waitForRequests();

    expect(apiMocks.commentProjectTodo).toHaveBeenCalledWith("client-1", "/workspace", "todo-1", {
      comment: "Please generate a trace for this follow-up.",
      artifact_kinds: ["agent_trace_graph"]
    });
  });
});
