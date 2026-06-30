import { act } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  cleanupProjectTodoTest,
  renderWithQuery,
  setupProjectTodoTest,
  todo,
  waitForButton,
  waitForElement,
  waitForElementText,
  waitForRequests
} from "./projectTodoTestHarness";
import { ProjectTodoPanel } from "../src/components/ProjectTodoPanel";
import type { ProjectTodo, ProjectTodoArtifact } from "../src/types";

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

describe("ProjectTodoPanel detail child cards", () => {
  it("shows child card details and opens linked terminal and artifacts", async () => {
    const onSelectWindow = vi.fn();
    const onOpenArtifact = vi.fn();
    const childArtifact = projectTodoArtifact();
    const parentTodo: ProjectTodo = {
      ...todo,
      child_todos: [{
        id: "todo-child",
        title: "Child implementation",
        status: "DISPATCHED",
        completed_at: null
      }]
    };
    const childTodo: ProjectTodo = {
      ...todo,
      id: "todo-child",
      title: "Child implementation",
      status: "DISPATCHED",
      assigned_window_id: "window-child",
      assigned_terminal: {
        id: "window-child",
        title: "Child terminal",
        summary: null,
        title_tags: [],
        runtime_tags: [],
        work_status: { state: "WORKING", label: "Working", color: "green", last_activity_at: null },
        topic_path: null,
        git_worktree: null,
        parent_window_id: null,
        root_window_id: null,
        derived_mode: null,
        created_at: "2026-06-05T00:00:00Z"
      },
      artifacts: [childArtifact]
    };
    apiMocks.fetchProjectTodos.mockResolvedValue({ todos: [parentTodo, childTodo] });
    apiMocks.fetchAgentRecordChat.mockResolvedValue({
      window_id: "window-child",
      messages: [{
        id: "message-1",
        ai_session_id: null,
        source_type: "codex",
        source_id: "session-1",
        role: "agent",
        body: "Implemented the child task.",
        body_format: "markdown",
        agent_message_type: null,
        subagent_id: null,
        subagent_tool_use_id: null,
        target_session_id: null,
        target_session_source_id: null,
        created_at: "2026-06-05T00:03:00Z"
      }],
      messages_total: 1,
      messages_limit: 30,
      messages_offset: 0,
      messages_has_more: false
    });
    renderWithQuery(
      <ProjectTodoPanel
        clientId="client-1"
        projectPath="/workspace"
        onOpenArtifact={onOpenArtifact}
        onSelectWindow={onSelectWindow}
      />
    );

    const row = await waitForButton("Fix dispatchTodo");
    act(() => row.click());
    await waitForElementText(".project-todo-child-cards-panel", "Child implementation");
    await waitForElementText(".project-todo-child-card-detail", "Running");
    await waitForElementText(".project-todo-child-agent-preview", "Implemented the child task.");
    const artifactButton = await waitForElementText(".project-todo-child-artifacts button", "Child Trace");
    act(() => {
      (artifactButton as HTMLButtonElement).click();
    });
    expect(onOpenArtifact).toHaveBeenCalledWith(childArtifact, "/workspace");

    const terminalButton = await waitForElement(
      '.project-todo-child-card-detail button[aria-label="Open terminal for Child implementation"]'
    ) as HTMLButtonElement;
    act(() => terminalButton.click());
    expect(onSelectWindow).toHaveBeenCalledWith("window-child", "/workspace");

    const openCardButton = await waitForElement(
      '.project-todo-child-card-detail button[aria-label="Open child card Child implementation"]'
    ) as HTMLButtonElement;
    act(() => openCardButton.click());
    await waitForRequests();
    expect(apiMocks.fetchProjectTodo).toHaveBeenCalledWith("client-1", "/workspace", "todo-child");
  });
});

function projectTodoArtifact(): ProjectTodoArtifact {
  return {
    id: "todo-artifact-link-child",
    artifact_id: "artifact-child",
    client_id: "client-1",
    window_id: "window-child",
    source_window_id: "window-child",
    ephemeral_window_id: "window-artifact-child",
    artifact_scope: "terminal",
    project_path: null,
    review_run_id: null,
    created_by_window_id: "window-child",
    title: "Child Trace",
    artifact_kind: "agent_trace_graph",
    status: "SUCCEEDED",
    purpose: "todo_artifact",
    agent_name: "codex",
    agent_status: {
      state: "FINISHED",
      label: "Finished",
      color: "green",
      last_activity_at: null
    },
    metadata_json: { project_todo_id: "todo-child", purpose: "todo_artifact" },
    last_error: null,
    started_at: "2026-06-05T00:01:00Z",
    completed_at: "2026-06-05T00:02:00Z",
    created_at: "2026-06-05T00:00:00Z",
    updated_at: "2026-06-05T00:02:00Z"
  };
}
