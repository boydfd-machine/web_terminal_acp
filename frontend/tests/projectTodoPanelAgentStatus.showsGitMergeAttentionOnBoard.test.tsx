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
  it("shows git merge attention on board cards", async () => {
    const conflictTodo: ProjectTodo = {
      ...todo,
      status: "AWAITING_REVIEW",
      review_status: "PENDING",
      implementation_worktree: {
        worktree_root: "/workspace/.worktrees/todo-1",
        branch: "agent/todo-1",
        end_head: "feature",
        merge_status: "conflict",
        merged_to_main: false,
        merge_attention_required: true,
        main_branch: "main",
        main_merge_in_progress: true,
        unmerged_files: ["backend/app.py"],
        commits: [{ short_sha: "abc1234", subject: "Fix dispatch flow" }]
      }
    };
    apiMocks.fetchProjectTodos.mockResolvedValue({ todos: [conflictTodo] });
    renderWithQuery(
      <ProjectTodoPanel
        clientId="client-1"
        projectPath="/workspace"
        viewMode="board"
        onSelectWindow={() => {}}
      />
    );
    await waitForElementText(".project-todo-card .git-merge-status-badge", "Git");
  });

  it("shows only user turns and final agent responses in the todo detail", async () => {
    apiMocks.fetchProjectTodos.mockResolvedValue({
      todos: [{
        ...todo,
        assigned_window_id: "window-2",
        assigned_agent: "codex"
      }]
    });
    apiMocks.fetchAgentRecordChat.mockResolvedValue({
      window_id: "window-2",
      messages: [
        agentChatMessage({
          id: "user-1",
          role: "user",
          body: "Implement the card detail change",
          created_at: "2026-06-05T00:01:00Z"
        }),
        agentChatMessage({
          id: "agent-draft",
          body: "Intermediate plan",
          created_at: "2026-06-05T00:02:00Z"
        }),
        agentChatMessage({
          id: "agent-final-1",
          body: "Ready for review",
          created_at: "2026-06-05T00:03:00Z"
        }),
        agentChatMessage({
          id: "user-2",
          role: "user",
          body: "Please adjust the icon",
          created_at: "2026-06-05T00:04:00Z"
        }),
        agentChatMessage({
          id: "agent-final-2",
          body: "Icon adjusted",
          created_at: "2026-06-05T00:05:00Z"
        })
      ],
      messages_total: 5,
      messages_limit: 200,
      messages_offset: 0,
      messages_has_more: false
    });
    renderWithQuery(<ProjectTodoPanel clientId="client-1" projectPath="/workspace" onSelectWindow={() => {}} />);

    const row = await waitForButton("Fix dispatchTodo");
    act(() => row.click());
    await waitForElement(".project-todo-agent-record-list");
    const recordText = document.body.querySelector(".project-todo-agent-record")?.textContent ?? "";

    expect(recordText).toContain("Implement the card detail change");
    expect(recordText).toContain("Ready for review");
    expect(recordText).toContain("Please adjust the icon");
    expect(recordText).toContain("Icon adjusted");
    expect(recordText).not.toContain("Intermediate plan");
    expect(apiMocks.fetchAgentRecordDetail).not.toHaveBeenCalled();
  });

  it("opens the expanded Agent Preview from the todo detail record", async () => {
    apiMocks.fetchProjectTodos.mockResolvedValue({
      todos: [{
        ...todo,
        assigned_window_id: "window-2",
        assigned_agent: "codex"
      }]
    });
    apiMocks.fetchAgentRecordChat.mockResolvedValue({
      window_id: "window-2",
      messages: [
        agentChatMessage({
          id: "agent-final",
          body: "Large preview content",
          created_at: "2026-06-05T00:03:00Z"
        })
      ],
      messages_total: 1,
      messages_limit: 200,
      messages_offset: 0,
      messages_has_more: false
    });
    renderWithQuery(<ProjectTodoPanel clientId="client-1" projectPath="/workspace" onSelectWindow={() => {}} />);

    const row = await waitForButton("Fix dispatchTodo");
    act(() => row.click());
    const previewButton = await waitForLabeledButton("Open Agent Preview for Agent preview");
    act(() => previewButton.click());
    await waitForElement(".agent-record-modal");
    await waitForElementText(".agent-record-modal", "Large preview content");

    expect(document.body.querySelector(".agent-record-modal")).not.toBeNull();
    expect(document.body.querySelector(".agent-record-modal")?.textContent).toContain("Large preview content");
    expect(apiMocks.fetchAgentRecordChat).toHaveBeenCalledWith("client-1", "window-2", 30, 0, "all", null, "latest");
    expect(apiMocks.fetchAgentRecordChat).toHaveBeenCalledWith("client-1", "window-2", 30, 0, "all", null);
    expect(apiMocks.fetchAgentRecordDetail).toHaveBeenCalledWith("client-1", "window-2", 100, 0, null);
  });

  it("closes only the expanded Agent Preview with Escape when opened from todo details", async () => {
    apiMocks.fetchProjectTodos.mockResolvedValue({
      todos: [{
        ...todo,
        assigned_window_id: "window-2",
        assigned_agent: "codex"
      }]
    });
    apiMocks.fetchAgentRecordChat.mockResolvedValue({
      window_id: "window-2",
      messages: [
        agentChatMessage({
          id: "agent-final",
          body: "Large preview content",
          created_at: "2026-06-05T00:03:00Z"
        })
      ],
      messages_total: 1,
      messages_limit: 200,
      messages_offset: 0,
      messages_has_more: false
    });
    renderWithQuery(<ProjectTodoPanel clientId="client-1" projectPath="/workspace" onSelectWindow={() => {}} />);

    const row = await waitForButton("Fix dispatchTodo");
    act(() => row.click());
    await waitForElement(".project-todo-detail-dialog");
    const previewButton = await waitForLabeledButton("Open Agent Preview for Agent preview");
    act(() => previewButton.click());
    const previewModal = await waitForElement(".agent-record-modal");
    await waitForElementText(".agent-record-modal", "Large preview content");

    act(() => {
      previewModal.dispatchEvent(new KeyboardEvent("keydown", {
        bubbles: true,
        cancelable: true,
        key: "Escape"
      }));
    });

    expect(document.body.querySelector(".agent-record-modal")).toBeNull();
    expect(document.body.querySelector(".project-todo-detail-dialog")).not.toBeNull();
  });

  it("expands inline user and agent messages from the todo detail record", async () => {
    apiMocks.fetchProjectTodos.mockResolvedValue({
      todos: [{
        ...todo,
        assigned_window_id: "window-2",
        assigned_agent: "codex"
      }]
    });
    apiMocks.fetchAgentRecordChat.mockResolvedValue({
      window_id: "window-2",
      messages: [
        agentChatMessage({
          id: "user-message",
          role: "user",
          body: "User prompt with **full markdown** content",
          created_at: "2026-06-05T00:01:00Z"
        }),
        agentChatMessage({
          id: "agent-message",
          body: "Agent answer with **full markdown** content",
          created_at: "2026-06-05T00:02:00Z"
        })
      ],
      messages_total: 2,
      messages_limit: 200,
      messages_offset: 0,
      messages_has_more: false
    });
    renderWithQuery(<ProjectTodoPanel clientId="client-1" projectPath="/workspace" onSelectWindow={() => {}} />);

    const row = await waitForButton("Fix dispatchTodo");
    act(() => row.click());
    await waitForElement(".project-todo-agent-record-list");

    const userExpand = await waitForLabeledButton("Expand User message");
    act(() => userExpand.click());
    const userOverlay = await waitForElement(".agent-chat-message-overlay");
    expect(userOverlay.getAttribute("role")).toBe("dialog");
    expect(userOverlay.textContent).toContain("User prompt with full markdown content");

    const userCollapse = await waitForLabeledButton("Collapse User message");
    act(() => userCollapse.click());
    await waitForRequests();
    expect(document.body.querySelector(".agent-chat-message-overlay")).toBeNull();

    const agentExpand = await waitForLabeledButton("Expand Agent message");
    act(() => agentExpand.click());
    const agentOverlay = await waitForElement(".agent-chat-message-overlay");
    expect(agentOverlay.getAttribute("role")).toBe("dialog");
    expect(agentOverlay.textContent).toContain("Agent answer with full markdown content");
  });

  it("closes only an expanded inline Agent Preview message with Escape when opened from todo details", async () => {
    apiMocks.fetchProjectTodos.mockResolvedValue({
      todos: [{
        ...todo,
        assigned_window_id: "window-2",
        assigned_agent: "codex"
      }]
    });
    apiMocks.fetchAgentRecordChat.mockResolvedValue({
      window_id: "window-2",
      messages: [
        agentChatMessage({
          id: "agent-message",
          body: "Agent answer with **full markdown** content",
          created_at: "2026-06-05T00:02:00Z"
        })
      ],
      messages_total: 1,
      messages_limit: 200,
      messages_offset: 0,
      messages_has_more: false
    });
    renderWithQuery(<ProjectTodoPanel clientId="client-1" projectPath="/workspace" onSelectWindow={() => {}} />);

    const row = await waitForButton("Fix dispatchTodo");
    act(() => row.click());
    await waitForElement(".project-todo-detail-dialog");
    const agentExpand = await waitForLabeledButton("Expand Agent message");
    act(() => agentExpand.click());
    const agentOverlay = await waitForElement(".agent-chat-message-overlay");

    act(() => {
      agentOverlay.dispatchEvent(new KeyboardEvent("keydown", {
        bubbles: true,
        cancelable: true,
        key: "Escape"
      }));
    });

    expect(document.body.querySelector(".agent-chat-message-overlay")).toBeNull();
    expect(document.body.querySelector(".project-todo-detail-dialog")).not.toBeNull();
  });

});
