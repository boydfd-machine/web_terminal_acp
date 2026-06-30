import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ProjectTodoPanel } from "../src/components/ProjectTodoPanel";
import {
  cleanupProjectTodoTest,
  renderWithQuery,
  setupProjectTodoTest,
  todo,
  waitForElement
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

describe("ProjectTodoPanel artifact agent status", () => {
  it("retries failed requested artifacts from board cards", async () => {
    const failedArtifact = {
      id: "todo-artifact-link-1",
      artifact_id: "artifact-1",
      client_id: "client-1",
      window_id: "window-2",
      source_window_id: "window-2",
      ephemeral_window_id: null,
      artifact_scope: "terminal",
      project_path: null,
      review_run_id: null,
      created_by_window_id: "window-2",
      title: "Fix dispatch - Agent Trace Graph",
      artifact_kind: "agent_trace_graph",
      status: "FAILED",
      purpose: "todo_artifact",
      agent_name: null,
      agent_status: null,
      metadata_json: { project_todo_id: "todo-1", purpose: "todo_artifact" },
      last_error: "artifact generation timed out",
      started_at: "2026-06-05T00:01:00Z",
      completed_at: "2026-06-05T00:02:00Z",
      created_at: "2026-06-05T00:00:00Z",
      updated_at: "2026-06-05T00:02:00Z"
    };
    apiMocks.fetchProjectTodos.mockResolvedValue({
      todos: [{
        ...todo,
        status: "AWAITING_REVIEW",
        assigned_window_id: "window-2",
        assigned_agent: "codex",
        artifacts: [failedArtifact]
      }]
    });
    apiMocks.retryProjectTodoArtifact.mockResolvedValue({
      ...todo,
      status: "AWAITING_REVIEW",
      assigned_window_id: "window-2",
      artifacts: [{ ...failedArtifact, status: "PENDING", last_error: null }]
    });
    renderWithQuery(
      <ProjectTodoPanel
        clientId="client-1"
        projectPath="/workspace"
        viewMode="board"
        onSelectWindow={() => {}}
      />
    );

    const retryButton = await waitForElement(
      "button[aria-label='Retry artifact Fix dispatch - Agent Trace Graph']"
    ) as HTMLButtonElement;
    retryButton.click();
    await waitForElement("[data-project-todo-id='todo-1']");

    expect(apiMocks.retryProjectTodoArtifact).toHaveBeenCalledWith(
      "client-1",
      "/workspace",
      "todo-1",
      "todo-artifact-link-1"
    );
  });

  it("does not show retry for succeeded requested artifacts", async () => {
    apiMocks.fetchProjectTodos.mockResolvedValue({
      todos: [{
        ...todo,
        status: "AWAITING_REVIEW",
        assigned_window_id: "window-2",
        assigned_agent: "codex",
        artifacts: [{
          id: "todo-artifact-link-1",
          artifact_id: "artifact-1",
          client_id: "client-1",
          window_id: "window-2",
          source_window_id: "window-2",
          ephemeral_window_id: null,
          artifact_scope: "terminal",
          project_path: null,
          review_run_id: null,
          created_by_window_id: "window-2",
          title: "Fix dispatch - Agent Trace Graph",
          artifact_kind: "agent_trace_graph",
          status: "SUCCEEDED",
          purpose: "todo_artifact",
          agent_name: null,
          agent_status: null,
          metadata_json: { project_todo_id: "todo-1", purpose: "todo_artifact" },
          last_error: null,
          started_at: "2026-06-05T00:01:00Z",
          completed_at: "2026-06-05T00:02:00Z",
          created_at: "2026-06-05T00:00:00Z",
          updated_at: "2026-06-05T00:02:00Z"
        }]
      }]
    });
    renderWithQuery(
      <ProjectTodoPanel
        clientId="client-1"
        projectPath="/workspace"
        viewMode="board"
        onSelectWindow={() => {}}
      />
    );

    await waitForElement("[data-project-todo-id='todo-1']");

    expect(document.body.querySelector("button[aria-label^='Retry artifact']")).toBeNull();
  });

  it("uses live artifact agent work status on board cards", async () => {
    apiMocks.fetchProjectTodos.mockResolvedValue({
      todos: [{
        ...todo,
        status: "DISPATCHED",
        assigned_window_id: "window-2",
        assigned_agent: "codex",
        artifacts: [{
          id: "todo-artifact-link-1",
          artifact_id: "artifact-1",
          client_id: "client-1",
          window_id: "window-2",
          source_window_id: "window-2",
          ephemeral_window_id: "artifact-window-1",
          artifact_scope: "terminal",
          project_path: null,
          review_run_id: null,
          created_by_window_id: "window-2",
          title: "Fix dispatch - Agent Trace Graph",
          artifact_kind: "agent_trace_graph",
          status: "RUNNING",
          purpose: "todo_artifact",
          agent_name: "codex",
          agent_status: {
            state: "LONG_IDLE",
            label: "Idle",
            color: "gray",
            last_activity_at: "2026-06-05T00:00:00Z"
          },
          metadata_json: { project_todo_id: "todo-1", purpose: "todo_artifact" },
          last_error: null,
          started_at: "2026-06-05T00:01:00Z",
          completed_at: null,
          created_at: "2026-06-05T00:00:00Z",
          updated_at: "2026-06-05T00:01:00Z"
        }]
      }]
    });
    apiMocks.fetchWindowActivity.mockResolvedValue({
      windows: [{
        window_id: "artifact-window-1",
        work_status: {
          state: "WORKING",
          label: "Agent working",
          color: "orange",
          last_activity_at: "2026-06-05T00:06:00Z"
        },
        runtime_tags: []
      }]
    });
    renderWithQuery(
      <ProjectTodoPanel
        clientId="client-1"
        projectPath="/workspace"
        viewMode="board"
        onSelectWindow={() => {}}
      />
    );

    const artifactStatus = await waitForElement(
      ".project-todo-card-artifact-agent .project-todo-agent-status-icon.orange"
    );

    expect(artifactStatus.getAttribute("aria-label")).toContain("Agent working");
    expect(document.body.querySelector(".project-todo-card-artifact-agent .project-todo-agent-status-icon.gray")).toBeNull();
  });
});
