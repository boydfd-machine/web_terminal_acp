import { act } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  cleanupProjectTodoTest,
  renderWithQuery,
  setupProjectTodoTest,
  todo,
  waitForButton,
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

describe("ProjectTodoPanel agent status links", () => {
  it("shows git merge attention on todo list and detail", async () => {
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
    renderWithQuery(<ProjectTodoPanel clientId="client-1" projectPath="/workspace" onSelectWindow={() => {}} />);

    await waitForElementText(".project-todo-list-row .git-merge-status-badge", "Git");
    const row = await waitForButton("Fix dispatchReview");
    act(() => row.click());
    await waitForElementText(".project-todo-merge-status", "Merge into main has conflicts: backend/app.py");
  });

  it("routes project file links from todo Agent Preview through the assigned worktree", async () => {
    apiMocks.fetchProjectTodos.mockResolvedValue({
      todos: [{
        ...todo,
        assigned_window_id: "window-2",
        assigned_agent: "codex",
        assigned_terminal: {
          id: "window-2",
          title: "Todo terminal",
          summary: null,
          title_tags: [],
          runtime_tags: ["codex", "/workspace"],
          work_status: { state: "LONG_IDLE", label: "Idle", color: "gray" },
          topic_path: "/workspace",
          git_worktree: {
            main_repo_root: "/workspace",
            worktree_root: "/workspace/.worktrees/todo-1",
            branch: "agent/todo-1",
            pending_commit: true
          },
          parent_window_id: null,
          root_window_id: null,
          derived_mode: null,
          created_at: "2026-06-05T00:00:00Z"
        }
      }]
    });
    apiMocks.fetchAgentRecordChat.mockResolvedValue({
      window_id: "window-2",
      messages: [
        agentChatMessage({
          id: "agent-final",
          body: "[App file](src/App.tsx:4)",
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
    await waitForElementText(".agent-record-modal", "App file");

    const link = document.body.querySelector<HTMLAnchorElement>(".agent-record-modal .agent-event-markdown a");
    expect(link?.getAttribute("href")).toBe(
      "/clients/client-1/files?project_path=%2Fworkspace&window_id=window-2&browse_root=%2Fworkspace%2F.worktrees%2Ftodo-1&file_path=src%2FApp.tsx&line=4"
    );
  });
});
