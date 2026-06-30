import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, describe, expect, it, vi } from "vitest";

import { AgentRecordModal } from "../src/components/AgentRecordViewer";
import type { AgentChatMessage, AgentChatRecord, AgentRecord, AgentSession } from "../src/types";

globalThis.IS_REACT_ACT_ENVIRONMENT = true;

let root: Root | null = null;
let container: HTMLDivElement | null = null;

const baseSession: AgentSession = {
  id: "session-1",
  provider: "codex",
  source_id: "codex-session-1",
  source_path: null,
  project_path: "/workspace/project",
  virtual_window_id: "window-1",
  title: null,
  tags: null,
  summary: null,
  created_at: "2026-06-01T00:00:00Z",
  updated_at: "2026-06-01T00:00:00Z"
};

const secondCodexSession: AgentSession = {
  ...baseSession,
  id: "session-2",
  source_id: "codex-session-2",
  created_at: "2026-06-01T00:00:01Z",
  updated_at: "2026-06-01T00:00:01Z"
};

const baseMessage: AgentChatMessage = {
  id: "message-1",
  ai_session_id: "session-1",
  source_type: "agent_tool_record",
  source_id: "codex-session-1",
  role: "agent",
  body: "Done.",
  body_format: "markdown",
  agent_message_type: "agent",
  subagent_id: null,
  subagent_tool_use_id: null,
  target_session_id: null,
  target_session_source_id: null,
  created_at: "2026-06-01T00:00:02Z"
};

function chatRecord(messages: AgentChatMessage[] = [baseMessage]): AgentChatRecord {
  return {
    window_id: "window-1",
    messages,
    messages_total: messages.length,
    messages_limit: 30,
    messages_offset: 0,
    messages_has_more: false
  };
}

function detailRecord(sessions: AgentSession[]): AgentRecord {
  return {
    window_id: "window-1",
    sessions,
    events: [],
    events_total: 0,
    events_limit: 100,
    events_offset: 0,
    events_has_more: false
  };
}

function renderModal({
  sessions = [baseSession, secondCodexSession],
  record = chatRecord()
}: {
  sessions?: AgentSession[];
  record?: AgentChatRecord;
} = {}) {
  container = document.createElement("div");
  document.body.appendChild(container);
  root = createRoot(container);

  act(() => {
    root?.render(
      <AgentRecordModal
        open
        mode="chat"
        chatRoleFilter="all"
        chatRecord={record}
        detailRecord={detailRecord(sessions)}
        sessions={sessions}
        onModeChange={vi.fn()}
        onChatRoleFilterChange={vi.fn()}
        onClose={vi.fn()}
      />
    );
  });
}

afterEach(() => {
  act(() => {
    root?.unmount();
  });
  container?.remove();
  root = null;
  container = null;
  vi.restoreAllMocks();
});

describe("AgentRecordModal session tabs", () => {
  it("does not render subagent tabs for unrelated Codex sessions", () => {
    renderModal();

    expect(document.body.querySelector(".agent-record-session-tabs")).toBeNull();
  });

  it("renders session tabs when the chat links to a subagent session", () => {
    renderModal({
      record: chatRecord([
        {
          ...baseMessage,
          agent_message_type: "subagent_call",
          subagent_id: "subagent-1",
          subagent_tool_use_id: "call-subagent-1",
          target_session_id: "session-2",
          target_session_source_id: "codex-session-2"
        }
      ])
    });

    const tabs = document.body.querySelectorAll(".agent-record-session-tabs button");
    expect(tabs).toHaveLength(2);
    expect(tabs[0].textContent).toBe("Main");
    expect(tabs[1].textContent).toBe("Sub 1");
  });
});
