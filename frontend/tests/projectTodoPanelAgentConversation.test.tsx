import { act } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  cleanupProjectTodoTest,
  renderWithQuery,
  setupProjectTodoTest,
  todo,
  waitForElement,
  waitForElementText,
  waitForLabeledButton
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

describe("ProjectTodoPanel agent conversation", () => {
  it("opens the latest agent response from the board card conversation button", async () => {
    const todoWithAgent: ProjectTodo = {
      ...todo,
      id: "todo-linked",
      title: "Linked todo",
      status: "DISPATCHED",
      assigned_window_id: "window-2",
      assigned_agent: "codex"
    };
    apiMocks.fetchProjectTodos.mockResolvedValue({ todos: [todoWithAgent] });
    apiMocks.fetchAgentRecordChat.mockResolvedValue({
      window_id: "window-2",
      messages: [
        agentChatMessage({
          id: "agent-final",
          body: "Latest agent response from the card",
          created_at: "2026-06-05T00:03:00Z"
        })
      ],
      messages_total: 1,
      messages_limit: 1,
      messages_offset: 0,
      messages_has_more: false
    });

    renderWithQuery(
      <ProjectTodoPanel
        clientId="client-1"
        projectPath="/workspace"
        viewMode="board"
        onSelectWindow={() => {}}
      />
    );

    const conversationButton = await waitForLabeledButton("Open Agent conversation for Linked todo");
    act(() => conversationButton.click());
    const dialog = await waitForElement(".project-todo-card-agent-conversation-dialog");
    await waitForElementText(".project-todo-card-agent-conversation-dialog", "Latest agent response from the card");
    expect(dialog.getAttribute("role")).toBe("dialog");
    expect(apiMocks.fetchAgentRecordChat).toHaveBeenCalledWith("client-1", "window-2", 1, 0, "agent", null, "latest");

    const previewButton = await waitForLabeledButton("Open Agent Preview for Agent conversation");
    act(() => previewButton.click());
    await waitForElement(".agent-record-modal");
    await waitForElementText(".agent-record-modal", "Latest agent response from the card");
    expect(document.body.querySelector(".project-todo-card-agent-conversation-dialog")).toBeNull();
    expect(apiMocks.fetchAgentRecordChat).toHaveBeenCalledWith("client-1", "window-2", 30, 0, "all", null);
  });

  it("keeps card conversation preview clicks inside the preview instead of opening todo details", async () => {
    const todoWithAgent: ProjectTodo = {
      ...todo,
      id: "todo-linked",
      title: "Linked todo",
      status: "DISPATCHED",
      assigned_window_id: "window-2",
      assigned_agent: "codex"
    };
    apiMocks.fetchProjectTodos.mockResolvedValue({ todos: [todoWithAgent] });
    apiMocks.fetchAgentRecordChat.mockResolvedValue({
      window_id: "window-2",
      messages: [
        agentChatMessage({
          id: "agent-final",
          body: "Latest agent response with [docs](https://example.com/docs)",
          created_at: "2026-06-05T00:03:00Z"
        })
      ],
      messages_total: 1,
      messages_limit: 1,
      messages_offset: 0,
      messages_has_more: false
    });

    renderWithQuery(
      <ProjectTodoPanel
        clientId="client-1"
        projectPath="/workspace"
        viewMode="board"
        onSelectWindow={() => {}}
      />
    );

    const conversationButton = await waitForLabeledButton("Open Agent conversation for Linked todo");
    act(() => conversationButton.click());
    const body = await waitForElementText(".project-todo-card-agent-conversation-dialog .agent-event-markdown", "Latest agent response");

    act(() => {
      body.dispatchEvent(new MouseEvent("click", { bubbles: true, cancelable: true }));
    });

    expect(document.body.querySelector(".project-todo-detail-dialog")).toBeNull();
    expect(document.body.querySelector(".project-todo-card-agent-conversation-dialog")).not.toBeNull();

    const link = document.body.querySelector<HTMLAnchorElement>(".project-todo-card-agent-conversation-dialog .agent-event-markdown a");
    expect(link?.getAttribute("href")).toBe("https://example.com/docs");
    expect(link?.getAttribute("target")).toBe("_blank");
  });
});
