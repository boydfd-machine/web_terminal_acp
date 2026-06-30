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
  isApiFailure: vi.fn(() => false),
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
  it("shows artifact agent status below the implementation agent on board cards", async () => {
    apiMocks.fetchProjectTodos.mockResolvedValue({
      todos: [{
        ...todo,
        status: "DISPATCHED",
        assigned_window_id: "window-1",
        assigned_agent: "codex",
        assigned_terminal: {
          id: "window-1",
          title: "Implementation terminal",
          summary: null,
          title_tags: [],
          runtime_tags: ["codex", "/workspace"],
          work_status: { state: "LONG_IDLE", label: "Idle", color: "gray" },
          topic_path: "/Web Terminal ACP/Artifacts",
          git_worktree: null,
          parent_window_id: null,
          root_window_id: null,
          derived_mode: null,
          created_at: "2026-06-05T00:00:00Z"
        },
        artifacts: [{
          id: "todo-artifact-link-1",
          artifact_id: "artifact-1",
          client_id: "client-1",
          window_id: "window-1",
          source_window_id: "window-1",
          ephemeral_window_id: "artifact-window-1",
          artifact_scope: "terminal",
          project_path: null,
          review_run_id: null,
          created_by_window_id: "window-1",
          title: "Fix dispatch - Agent Trace Graph",
          artifact_kind: "agent_trace_graph",
          status: "RUNNING",
          purpose: "todo_artifact",
          agent_name: "codex",
          agent_status: {
            state: "WORKING",
            label: "Working",
            color: "green",
            last_activity_at: null
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
    renderWithQuery(
      <ProjectTodoPanel
        clientId="client-1"
        projectPath="/workspace"
        viewMode="board"
        onSelectWindow={() => {}}
      />
    );

    const card = await waitForElementText(".project-todo-card", "Fix dispatch");
    const implementationIcon = card.querySelector(".project-todo-card-agent > .project-todo-agent-status-icon");
    const artifactIcon = card.querySelector(
      ".project-todo-card-artifact-agent .project-todo-agent-status-icon"
    );

    expect(implementationIcon?.getAttribute("title")).toBe("Agent codex: Idle");
    expect(artifactIcon?.getAttribute("title")).toBe("codex artifact: Working");
    expect(card.querySelector(".project-todo-card-artifact-agent")?.textContent).toContain("running");
  });

  it("shows git attention without review status tags on board cards", async () => {
    apiMocks.fetchProjectTodos.mockResolvedValue({
      todos: [{
        ...todo,
        status: "AWAITING_REVIEW",
        review_status: "PENDING",
        implementation_worktree: {
          worktree_root: "/workspace/.worktrees/todo-1",
          branch: "agent/todo-1",
          merge_status: "conflict",
          merge_attention_required: true,
          main_branch: "main",
          unmerged_files: ["frontend/src/App.tsx"]
        }
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

    const badges = await waitForElement(".project-todo-card-badges");

    expect(badges.textContent).not.toContain("Review requested");
    expect(badges.textContent).toContain("Git");
    expect(badges.querySelector(".project-todo-review-pill")).toBeNull();
    expect(badges.querySelector(".git-merge-status-badge.conflict")).not.toBeNull();
  });

  it("shows waiting dispatch cards in Pending and keeps Blocked after Done", async () => {
    apiMocks.fetchProjectTodos.mockResolvedValue({
      todos: [
        {
          ...todo,
          queued_dispatch: true,
          assigned_agent: "codex"
        },
        {
          ...todo,
          id: "todo-2",
          title: "Manual stop",
          status: "BLOCKED",
          sort_order: 2
        },
        {
          ...todo,
          id: "todo-3",
          title: "Complete work",
          status: "DONE",
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

    const pendingCard = await waitForElementText(".project-todo-column[aria-label='Pending'] .project-todo-card", "Fix dispatch");
    await waitForElementText(".project-todo-column[aria-label='Done'] .project-todo-card", "Complete work");
    await waitForElementText(".project-todo-column[aria-label='Blocked'] .project-todo-card", "Manual stop");
    const columnLabels = Array.from(document.body.querySelectorAll(".project-todo-column")).map(
      (column) => column.getAttribute("aria-label")
    );
    expect(columnLabels).toEqual(["Todo", "Pending", "Running", "Review", "Done", "Blocked"]);
    expect(pendingCard.querySelector(".project-todo-dispatch-button")).toBeNull();
  });

  it("shows a board card spinner while dispatch is pending without blocking other card actions", async () => {
    let resolveDispatch: ((value: ProjectTodo) => void) | null = null;
    apiMocks.fetchProjectTodos.mockResolvedValue({
      todos: [
        todo,
        { ...todo, id: "todo-2", title: "Second todo", sort_order: 2 }
      ]
    });
    apiMocks.dispatchProjectTodo.mockReturnValue(new Promise<ProjectTodo>((resolve) => {
      resolveDispatch = resolve;
    }));
    renderWithQuery(
      <ProjectTodoPanel
        clientId="client-1"
        projectPath="/workspace"
        viewMode="board"
        onSelectWindow={() => {}}
      />
    );

    const firstDispatch = await waitForLabeledButton("Dispatch Fix dispatch");
    act(() => firstDispatch.click());
    expect(apiMocks.dispatchProjectTodo).not.toHaveBeenCalled();
    await waitForElement(".terminal-create-modal");
    const modalDispatch = await waitForButton("Dispatch", ".terminal-create-actions button");
    act(() => modalDispatch.click());
    const dispatchingButton = await waitForLabeledButton("Dispatching Fix dispatch");
    const secondDispatch = await waitForLabeledButton("Dispatch Second todo");

    expect(dispatchingButton.disabled).toBe(true);
    expect(dispatchingButton.querySelector(".project-todo-card-action-spinner")).not.toBeNull();
    expect(document.body.querySelector(".terminal-create-modal")).toBeNull();
    expect(secondDispatch.disabled).toBe(false);

    act(() => {
      resolveDispatch?.({
        ...todo,
        dispatch_stage: "STARTING",
        assigned_agent: "codex"
      });
    });
    await waitForRequests();

    expect(document.body.querySelector(".project-todo-dispatch-toast.success")?.textContent).toBe(
      "Dispatch started for Fix dispatch."
    );
  });

  it("sends a comment to an assigned board card terminal", async () => {
    const assignedTodo: ProjectTodo = {
      ...todo,
      assigned_window_id: "window-2",
      assigned_agent: "codex"
    };
    apiMocks.fetchProjectTodos.mockResolvedValue({ todos: [assignedTodo] });
    apiMocks.commentProjectTodo.mockResolvedValue(assignedTodo);
    renderWithQuery(
      <ProjectTodoPanel
        clientId="client-1"
        projectPath="/workspace"
        viewMode="board"
        onSelectWindow={() => {}}
      />
    );

    const commentButton = await waitForLabeledButton("Comment Fix dispatch");
    act(() => commentButton.click());
    const textarea = await waitForElement("textarea[aria-label='Comment']");
    if (!(textarea instanceof HTMLTextAreaElement)) {
      throw new Error("Comment textarea was not rendered");
    }
    setValue(textarea, "Please check the recovered terminal session.");
    const sendButton = await waitForButton("Send", ".project-todo-comment-actions button");
    act(() => sendButton.click());
    await waitForRequests();

    expect(apiMocks.commentProjectTodo).toHaveBeenCalledWith("client-1", "/workspace", "todo-1", {
      comment: "Please check the recovered terminal session."
    });
    expect(document.body.querySelector(".project-todo-dispatch-toast.success")?.textContent).toBe(
      "Comment sent to Fix dispatch."
    );
  });

  it("shows dispatch failures on the board card and in the toast", async () => {
    apiMocks.dispatchProjectTodo.mockRejectedValue(new Error("Dispatch exploded"));
    renderWithQuery(
      <ProjectTodoPanel
        clientId="client-1"
        projectPath="/workspace"
        viewMode="board"
        onSelectWindow={() => {}}
      />
    );

    const dispatchButton = await waitForLabeledButton("Dispatch Fix dispatch");
    act(() => dispatchButton.click());
    expect(apiMocks.dispatchProjectTodo).not.toHaveBeenCalled();
    await waitForElement(".terminal-create-modal");
    const modalDispatch = await waitForButton("Dispatch", ".terminal-create-actions button");
    act(() => modalDispatch.click());
    await waitForRequests();

    const card = await waitForElement(".project-todo-card");
    const footer = card.querySelector(".project-todo-card-footer");
    const actions = card.querySelector(".project-todo-card-actions");
    expect(document.body.querySelector(".project-todo-card-dispatch-error")?.textContent).toBe("Dispatch exploded");
    expect(card.lastElementChild?.classList.contains("project-todo-card-footer")).toBe(true);
    expect(footer?.querySelector("time")?.getAttribute("dateTime")).toBe(todo.created_at);
    expect(actions?.parentElement).toBe(footer);
    expect(document.body.querySelector(".project-todo-dispatch-toast.error")?.textContent).toBe("Dispatch exploded");
    expect(await waitForLabeledButton("Dispatch Fix dispatch")).toBeInstanceOf(HTMLButtonElement);
  });

  it("does not expose review status actions from an awaiting review card", async () => {
    const onSelectWindow = vi.fn();
    const reviewTodo: ProjectTodo = {
      ...todo,
      status: "AWAITING_REVIEW",
      assigned_window_id: "window-2",
      awaiting_review_at: "2026-06-05T00:05:00Z",
      review_status: "PENDING",
      implementation_worktree: {
        worktree_root: "/workspace/.worktrees/todo-1",
        branch: "agent/todo-1",
        commits: [{ short_sha: "abc1234", subject: "Fix dispatch flow" }]
      }
    };
    apiMocks.fetchProjectTodos.mockResolvedValue({ todos: [reviewTodo] });
    renderWithQuery(<ProjectTodoPanel clientId="client-1" projectPath="/workspace" onSelectWindow={onSelectWindow} />);

    const row = await waitForButton("Fix dispatchReview");
    act(() => row.click());
    await waitForElement(".project-todo-detail-dialog");

    const actionRail = await waitForElement(".project-todo-action-rail");
    expect(actionRail.querySelector(".project-todo-review-actions")).toBeNull();
    expect(actionRail.querySelector(".project-todo-action-approve")).toBeNull();
    expect(actionRail.querySelector(".project-todo-action-request")).toBeNull();
    expect(actionRail.querySelector(".project-todo-action-human")).toBeNull();
    expect(actionRail.querySelector(".project-todo-artifact-actions")).not.toBeNull();
    expect(apiMocks.dispatchProjectTodoReview).not.toHaveBeenCalled();
    expect(onSelectWindow).not.toHaveBeenCalled();
  });

  it("generates and links a review artifact from the review panel", async () => {
    const reviewTodo: ProjectTodo = {
      ...todo,
      status: "AWAITING_REVIEW",
      assigned_window_id: "window-2",
      review_status: "REVIEWED"
    };
    apiMocks.fetchProjectTodos.mockResolvedValue({ todos: [reviewTodo] });
    apiMocks.linkProjectTodoArtifact.mockResolvedValue({
      ...reviewTodo,
      artifacts: [{
        id: "todo-artifact-1",
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
        status: "PENDING",
        purpose: "todo_artifact",
        agent_name: null,
        agent_status: null,
        metadata_json: { project_todo_id: "todo-1", purpose: "todo_artifact" },
        last_error: null,
        started_at: null,
        completed_at: null,
        created_at: "2026-06-05T00:10:00Z",
        updated_at: "2026-06-05T00:10:00Z"
      }]
    });
    renderWithQuery(<ProjectTodoPanel clientId="client-1" projectPath="/workspace" onSelectWindow={() => {}} />);

    const row = await waitForButton("Fix dispatchReview");
    act(() => row.click());
    const artifactButton = await waitForButton("Generate artifact", ".project-todo-generate-artifact-control button");
    act(() => artifactButton.click());
    await waitForRequests();

    expect(apiMocks.createTerminalArtifact).toHaveBeenCalledWith("client-1", "window-2", {
      artifact_kind: "agent_trace_graph",
      artifact_scope: "terminal",
      project_path: null,
      title: "Fix dispatch - Agent Trace Graph",
      metadata_json: { project_todo_id: "todo-1", purpose: "todo_artifact" }
    });
    expect(apiMocks.linkProjectTodoArtifact).toHaveBeenCalledWith("client-1", "/workspace", "todo-1", {
      artifact_id: "artifact-1",
      purpose: "todo_artifact"
    });
  });

  it("opens and focuses an asynchronously loaded todo from an overview link request", async () => {
    renderWithQuery(
      <ProjectTodoPanel
        clientId="client-1"
        focusRequest={{ clientId: "client-1", projectPath: "/workspace", todoId: "todo-1", nonce: 1 }}
        projectPath="/workspace"
        onSelectWindow={() => {}}
      />
    );
    await waitForElement(".project-todo-detail-dialog");

    expect(document.body.querySelector(".project-todo-detail-dialog")).not.toBeNull();
    expect(HTMLElement.prototype.scrollIntoView).toHaveBeenCalled();
  });

});
