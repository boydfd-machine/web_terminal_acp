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
  waitForLabeledButton,
  waitForRequests
} from "./projectTodoTestHarness";
import { ProjectTodoPanel } from "../src/components/ProjectTodoPanel";
import type { ProjectTodo } from "../src/types";
import type { AgentChatMessage } from "../src/types/agent";

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

function agentChatMessage(overrides: Partial<AgentChatMessage>): AgentChatMessage {
  return {
    id: "message-1",
    ai_session_id: "session-1",
    source_type: "codex",
    source_id: "session.jsonl",
    role: "agent",
    body: "Agent response",
    body_format: "markdown",
    agent_message_type: "agent",
    subagent_id: null,
    subagent_tool_use_id: null,
    target_session_id: null,
    target_session_source_id: null,
    created_at: "2026-06-05T00:00:00Z",
    ...overrides
  };
}

describe("ProjectTodoPanel agent status and records", () => {
  it("renders board card dispatch, comment, and terminal icon actions", async () => {
    const onOpenTerminalWindow = vi.fn();
    const onSelectWindow = vi.fn();
    apiMocks.fetchProjectTodos.mockResolvedValue({
      todos: [
        todo,
        {
          ...todo,
          id: "todo-2",
          title: "Linked todo",
          status: "DISPATCHED",
          assigned_window_id: "window-2",
          assigned_agent: "codex"
        }
      ]
    });
    renderWithQuery(
      <ProjectTodoPanel
        clientId="client-1"
        projectPath="/workspace"
        viewMode="board"
        onOpenTerminalWindow={onOpenTerminalWindow}
        onSelectWindow={onSelectWindow}
      />
    );

    const dispatchButton = await waitForLabeledButton("Dispatch Fix dispatch");
    const linkedCard = await waitForElementText(".project-todo-card", "Linked todo");
    const unassignedCard = await waitForElementText(".project-todo-card", "Fix dispatch");
    const linkedActions = Array.from(linkedCard.querySelectorAll(".project-todo-card-actions button"));
    const unassignedActions = Array.from(unassignedCard.querySelectorAll(".project-todo-card-actions button"));

    expect(dispatchButton.disabled).toBe(false);
    expect(linkedCard.textContent).not.toContain("Terminal");
    expect(unassignedActions.map((button) => button.getAttribute("aria-label"))).toEqual([
      "Create child card under Fix dispatch",
      "Upload file to Fix dispatch",
      "Dispatch Fix dispatch"
    ]);
    expect(linkedActions.map((button) => button.getAttribute("aria-label"))).toEqual([
      "Create child card under Linked todo",
      "Open Agent conversation for Linked todo",
      "Comment Linked todo",
      "Open terminal for Linked todo"
    ]);

    const terminalButton = linkedActions[3];
    expect(terminalButton?.classList.contains("project-todo-terminal-button")).toBe(true);
    act(() => {
      (terminalButton as HTMLButtonElement).click();
    });

    expect(onOpenTerminalWindow).toHaveBeenCalledWith("window-2", "/workspace", "Linked todo");
    expect(onSelectWindow).not.toHaveBeenCalled();
  });

  it("keeps board cards terminal-light and shows periodic new-terminal runs in detail", async () => {
    const onOpenTerminalWindow = vi.fn();
    const onSelectWindow = vi.fn();
    const periodicTodo: ProjectTodo = {
      ...todo,
      title: "Recurring automation",
      status: "DISPATCHED",
      assigned_window_id: "window-run-2",
      assigned_agent: "codex",
      dispatch_prompt: "Latest card prompt",
      execution_kind: "PERIODIC",
      terminal_policy: "NEW_TERMINAL",
      execution_run_count: 2,
      assigned_terminal: {
        id: "window-latest",
        title: "Latest assigned terminal",
        summary: "Latest run summary",
        title_tags: ["automation"],
        runtime_tags: ["codex", "/workspace"],
        work_status: { state: "LONG_IDLE", label: "Idle", color: "gray" },
        topic_path: "/Automation",
        git_worktree: null,
        parent_window_id: null,
        root_window_id: null,
        derived_mode: null,
        created_at: "2026-06-05T00:02:00Z"
      },
      execution_runs: [
        {
          id: "run-2",
          todo_id: "todo-1",
          window_id: "window-run-2",
          run_number: 2,
          trigger_strategy: "CRON",
          trigger_reason: "cron",
          terminal_policy: "NEW_TERMINAL",
          dispatch_mode: "submit",
          prompt: "Run two prompt",
          status: "DISPATCHED",
          started_at: "2026-06-05T00:02:00Z",
          dispatched_at: "2026-06-05T00:02:10Z",
          completed_at: null,
          last_error: null,
          assigned_terminal: {
            id: "window-run-2",
            title: "Run two terminal",
            summary: null,
            title_tags: [],
            runtime_tags: [],
            work_status: { state: "WORKING", label: "Working", color: "green" },
            topic_path: "/Automation",
            git_worktree: null,
            parent_window_id: null,
            root_window_id: null,
            derived_mode: null,
            created_at: "2026-06-05T00:02:00Z"
          },
          created_at: "2026-06-05T00:02:00Z",
          updated_at: "2026-06-05T00:02:10Z"
        },
        {
          id: "run-1",
          todo_id: "todo-1",
          window_id: "window-run-1",
          run_number: 1,
          trigger_strategy: "MANUAL",
          trigger_reason: "manual",
          terminal_policy: "NEW_TERMINAL",
          dispatch_mode: "submit",
          prompt: "Run one prompt",
          status: "COMPLETED",
          started_at: "2026-06-05T00:01:00Z",
          dispatched_at: "2026-06-05T00:01:10Z",
          completed_at: "2026-06-05T00:01:30Z",
          last_error: null,
          assigned_terminal: {
            id: "window-run-1",
            title: "Run one terminal",
            summary: null,
            title_tags: [],
            runtime_tags: [],
            work_status: { state: "LONG_IDLE", label: "Idle", color: "gray" },
            topic_path: "/Automation",
            git_worktree: null,
            parent_window_id: null,
            root_window_id: null,
            derived_mode: null,
            created_at: "2026-06-05T00:01:00Z"
          },
          created_at: "2026-06-05T00:01:00Z",
          updated_at: "2026-06-05T00:01:30Z"
        }
      ]
    };
    apiMocks.fetchProjectTodos.mockResolvedValue({ todos: [periodicTodo] });
    apiMocks.fetchAgentRecordChat.mockResolvedValue({
      window_id: "window-run-2",
      messages: [
        agentChatMessage({
          id: "agent-run-2",
          body: "Run two agent preview",
          created_at: "2026-06-05T00:02:20Z"
        })
      ],
      messages_total: 1,
      messages_limit: 30,
      messages_offset: 0,
      messages_has_more: false
    });
    renderWithQuery(
      <ProjectTodoPanel
        clientId="client-1"
        projectPath="/workspace"
        viewMode="board"
        onOpenTerminalWindow={onOpenTerminalWindow}
        onSelectWindow={onSelectWindow}
      />
    );

    const card = await waitForElementText(".project-todo-card", "Recurring automation");

    expect(card.textContent).not.toContain("Latest assigned terminal");
    expect(card.textContent).not.toContain("Run two terminal");
    expect(card.querySelector(".project-todo-run-list")).toBeNull();

    const terminalButton = await waitForLabeledButton("Open terminal for Recurring automation");
    act(() => terminalButton.click());
    expect(onOpenTerminalWindow).toHaveBeenCalledWith("window-run-2", "/workspace", "Latest assigned terminal");
    expect(onSelectWindow).not.toHaveBeenCalled();
    onOpenTerminalWindow.mockClear();

    if (!(card instanceof HTMLElement)) {
      throw new Error("Board card was not rendered as an HTMLElement");
    }
    act(() => card.click());

    const runList = await waitForElement(".project-todo-execution-terminal-list");
    expect(runList.textContent).toContain("#2");
    expect(runList.textContent).toContain("Run two terminal");
    expect(runList.textContent).toContain("#1");
    expect(document.body.textContent).not.toContain("Run two prompt");
    expect(document.body.textContent).toContain("Agent preview");
    await waitForElementText(".project-todo-agent-record", "Run two agent preview");
    expect(apiMocks.fetchAgentRecordChat).toHaveBeenCalledWith("client-1", "window-run-2", 30, 0, "all", null, "latest");

    const openRunTerminal = await waitForButton("Open terminal", ".project-todo-execution-terminal-detail button");
    act(() => openRunTerminal.click());

    expect(onSelectWindow).toHaveBeenCalledWith("window-run-2", "/workspace");
  });

  it("shows the linked agent work status in the list row and detail", async () => {
    apiMocks.fetchProjectTodos.mockResolvedValue({
      todos: [{
        ...todo,
        assigned_window_id: "window-2",
        assigned_agent: "codex"
      }]
    });
    apiMocks.fetchWindowActivity.mockResolvedValue({
      windows: [{
        window_id: "window-2",
        work_status: {
          state: "WORKING",
          label: "Working",
          color: "green",
          last_activity_at: "2026-06-05T00:06:00Z"
        },
        runtime_tags: []
      }]
    });
    renderWithQuery(<ProjectTodoPanel clientId="client-1" projectPath="/workspace" onSelectWindow={() => {}} />);

    const rowStatus = await waitForElement(".project-todo-list-row .project-todo-agent-status-icon.green");
    expect(rowStatus.getAttribute("aria-label")).toContain("Working");
    expect(apiMocks.fetchWindowActivity).toHaveBeenCalledWith("client-1", { projectPath: "/workspace" });

    const row = await waitForButton("Fix dispatchTodo");
    act(() => row.click());
    const detailStatus = await waitForElement(".project-todo-detail-badges .project-todo-agent-status-icon.green");

    expect(detailStatus.getAttribute("aria-label")).toContain("Working");
  });

  it("updates the detail agent work status from the loaded detail card", async () => {
    apiMocks.fetchProjectTodos.mockResolvedValue({
      todos: [{
        ...todo,
        assigned_window_id: null,
        assigned_terminal: null,
        assigned_agent: "codex"
      }]
    });
    apiMocks.fetchProjectTodo.mockResolvedValue({
      ...todo,
      assigned_window_id: "window-detail",
      assigned_agent: "codex",
      assigned_terminal: {
        id: "window-detail",
        title: "Detail terminal",
        summary: null,
        title_tags: [],
        runtime_tags: [],
        work_status: {
          state: "WORKING",
          label: "Working",
          color: "green",
          last_activity_at: "2026-06-05T00:06:00Z"
        },
        topic_path: "/workspace",
        git_worktree: null,
        parent_window_id: null,
        root_window_id: null,
        derived_mode: null,
        created_at: "2026-06-05T00:00:00Z"
      }
    });
    renderWithQuery(<ProjectTodoPanel clientId="client-1" projectPath="/workspace" onSelectWindow={() => {}} />);

    const row = await waitForButton("Fix dispatchTodo");
    act(() => row.click());
    const detailStatus = await waitForElement(".project-todo-detail-badges .project-todo-agent-status-icon.green");

    expect(detailStatus.getAttribute("aria-label")).toContain("Working");
  });

  it("shows the linked agent work status on board cards", async () => {
    apiMocks.fetchProjectTodos.mockResolvedValue({
      todos: [{
        ...todo,
        status: "DISPATCHED",
        assigned_window_id: "window-2",
        assigned_agent: "codex"
      }]
    });
    apiMocks.fetchWindowActivity.mockResolvedValue({
      windows: [{
        window_id: "window-2",
        work_status: {
          state: "RECENT_ACTIVE",
          label: "Recently active",
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

    const cardStatus = await waitForElement(".project-todo-card .project-todo-agent-status-icon.orange");

    expect(cardStatus.getAttribute("aria-label")).toContain("Recently active");
  });

  it("shows backend dispatch stages on board cards", async () => {
    apiMocks.fetchProjectTodos.mockResolvedValue({
      todos: [
        {
          ...todo,
          dispatch_stage: "WINDOW_CREATED",
          assigned_agent: "codex"
        },
        {
          ...todo,
          id: "todo-2",
          title: "Terminal ready",
          sort_order: 2,
          assigned_window_id: "window-2",
          assigned_agent: "codex",
          dispatch_stage: "TERMINAL_READY"
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

    const creatingDispatch = await waitForLabeledButton("Dispatching Fix dispatch");
    const terminalReadyDispatch = await waitForLabeledButton("Dispatching Terminal ready");

    expect(creatingDispatch.disabled).toBe(true);
    expect(creatingDispatch.querySelector(".project-todo-card-action-spinner.gray")).not.toBeNull();
    expect(terminalReadyDispatch.disabled).toBe(true);
    expect(terminalReadyDispatch.querySelector(".project-todo-card-action-spinner.orange")).not.toBeNull();
    expect(
      document.body.querySelector(".project-todo-card .project-todo-agent-status-icon.orange.dispatch-active")
    ).not.toBeNull();
  });

  it("shows backend dispatch failures on board cards", async () => {
    apiMocks.fetchProjectTodos.mockResolvedValue({
      todos: [{
        ...todo,
        dispatch_stage: "FAILED",
        dispatch_error: "agent did not start working"
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

    const dispatchButton = await waitForLabeledButton("Dispatch Fix dispatch");

    expect(dispatchButton.disabled).toBe(false);
    expect(document.body.querySelector(".project-todo-card-dispatch-error")?.textContent).toBe(
      "agent did not start working"
    );
    expect(document.body.querySelector(".project-todo-card .project-todo-agent-status-icon.red")).not.toBeNull();
  });

});
