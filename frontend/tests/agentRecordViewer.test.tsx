import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, describe, expect, it, vi } from "vitest";

import { AgentRecordViewer } from "../src/components/AgentRecordViewer";
import {
  PROJECT_FILE_OPEN_EVENT,
  type ProjectFileOpenRequest
} from "../src/projectFileLinks";
import type { AgentChatRecord } from "../src/types";

globalThis.IS_REACT_ACT_ENVIRONMENT = true;

const mermaidInitializeMock = vi.hoisted(() => vi.fn());
const mermaidRenderMock = vi.hoisted(() => vi.fn(async (id: string) => ({
  svg: `<svg data-mermaid-id="${id}"><text>Rendered diagram</text></svg>`,
  diagramType: "flowchart"
})));

vi.mock("mermaid", () => ({
  default: {
    initialize: mermaidInitializeMock,
    render: mermaidRenderMock
  }
}));

let root: Root | null = null;
let container: HTMLDivElement | null = null;

const baseMessage = {
  id: "message-1",
  ai_session_id: "session-1",
  source_type: "codex",
  source_id: "session.jsonl",
  role: "agent" as const,
  body: "Expanded message body with **markdown**.",
  body_format: "markdown" as const,
  agent_message_type: "agent" as const,
  subagent_id: null,
  subagent_tool_use_id: null,
  target_session_id: null,
  target_session_source_id: null,
  created_at: "2026-06-01T00:00:00Z"
};

const chatRecord: AgentChatRecord = {
  window_id: "window-1",
  messages: [baseMessage],
  messages_total: 1,
  messages_limit: 30,
  messages_offset: 0,
  messages_has_more: false
};

function renderViewer({
  record = chatRecord,
  searchRecord = null,
  searchQuery = "",
  onOpenSubagent,
  projectFileContext = null
}: {
  record?: AgentChatRecord;
  searchRecord?: Parameters<typeof AgentRecordViewer>[0]["searchRecord"];
  searchQuery?: string;
  onOpenSubagent?: (sessionId: string, originMessageId?: string) => void;
  projectFileContext?: Parameters<typeof AgentRecordViewer>[0]["projectFileContext"];
} = {}) {
  container = document.createElement("div");
  document.body.appendChild(container);
  root = createRoot(container);

  act(() => {
    root?.render(
      <AgentRecordViewer
        mode="chat"
        chatRoleFilter="all"
        chatRecord={record}
        detailRecord={null}
        sessions={[]}
        searchDraft={searchQuery}
        searchQuery={searchQuery}
        searchRecord={searchRecord}
        onSearchDraftChange={vi.fn()}
        onSearchSubmit={vi.fn()}
        onSearchClear={vi.fn()}
        projectFileContext={projectFileContext}
        onModeChange={vi.fn()}
        onChatRoleFilterChange={vi.fn()}
        onOpenSubagent={onOpenSubagent}
        onExpand={vi.fn()}
      />
    );
  });
}

function renderViewerWithQuickInput(onSubmit = vi.fn()) {
  container = document.createElement("div");
  document.body.appendChild(container);
  root = createRoot(container);

  act(() => {
    root?.render(
      <AgentRecordViewer
        mode="chat"
        chatRoleFilter="all"
        chatRecord={chatRecord}
        detailRecord={null}
        sessions={[]}
        onModeChange={vi.fn()}
        onChatRoleFilterChange={vi.fn()}
        onExpand={vi.fn()}
        quickInputDraft=""
        canSendQuickInput
        onQuickInputDraftChange={vi.fn()}
        onQuickInputSubmit={onSubmit}
      />
    );
  });

  return onSubmit;
}

async function waitForAssertion(assertion: () => void): Promise<void> {
  let lastError: unknown = null;
  for (let index = 0; index < 20; index += 1) {
    try {
      assertion();
      return;
    } catch (error) {
      lastError = error;
      await act(async () => {
        await new Promise((resolve) => setTimeout(resolve, 0));
      });
    }
  }
  throw lastError;
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

describe("AgentRecordViewer", () => {
  it("renders scoped search results as highlighted agent cards", () => {
    renderViewer({
      searchQuery: "llama",
      searchRecord: {
        query: "llama",
        scope: "window",
        results: [
          {
            window_id: "window-1",
            session_id: "session-1",
            provider: "codex",
            message: {
              ...baseMessage,
              id: "search-message-1",
              body: "{\"raw\":\"json should not be shown\"} llama result",
              body_format: "json"
            },
            matches: [{ field: "body", start: 35, end: 40 }]
          }
        ],
        total: 1,
        limit: 25,
        offset: 0,
        has_more: false
      }
    });

    expect(container?.querySelectorAll(".agent-record-search-card-list .agent-chat-message")).toHaveLength(1);
    expect(container?.querySelector(".agent-record-search-card-list mark.search-highlight")?.textContent).toBe("llama");
    expect(container?.querySelector(".agent-record-search-card-list pre.agent-event-json")).toBeNull();
    expect(container?.textContent).toContain("json should not be shown");
    expect(container?.querySelector(".agent-record-body")?.textContent).not.toContain("Expanded message body");
  });

  it("expands and collapses a single chat message", () => {
    renderViewer();

    const expandButton = container?.querySelector<HTMLButtonElement>('button[aria-label="Expand Agent message"]');
    expect(expandButton).toBeInstanceOf(HTMLButtonElement);

    act(() => {
      expandButton?.dispatchEvent(new MouseEvent("click", { bubbles: true }));
    });

    const overlay = document.body.querySelector<HTMLElement>(".agent-chat-message-overlay");
    expect(overlay).not.toBeNull();
    expect(overlay?.getAttribute("role")).toBe("dialog");
    expect(overlay?.textContent).toContain("Expanded message body with markdown.");

    const collapseButton = overlay?.querySelector<HTMLButtonElement>('button[aria-label="Collapse Agent message"]');
    expect(collapseButton).toBeInstanceOf(HTMLButtonElement);

    act(() => {
      collapseButton?.dispatchEvent(new MouseEvent("click", { bubbles: true }));
    });

    expect(document.body.querySelector(".agent-chat-message-overlay")).toBeNull();
  });

  it("renders GFM markdown structures in agent messages", () => {
    renderViewer({
      record: {
        ...chatRecord,
        messages: [
          {
            ...baseMessage,
            body: [
              "# Plan",
              "",
              "- [x] render tables",
              "- [ ] keep task state visible",
              "",
              "| Area | Status |",
              "| --- | --- |",
              "| Preview | **better** |",
              "",
              "~~old~~ new",
              "line one",
              "line two"
            ].join("\n")
          }
        ]
      }
    });

    expect(container?.querySelector(".agent-event-markdown h1")?.textContent).toBe("Plan");
    expect(container?.querySelectorAll(".agent-event-markdown input[type=\"checkbox\"]")).toHaveLength(2);
    expect(container?.querySelector(".agent-event-markdown table")).not.toBeNull();
    expect(container?.querySelector(".agent-event-markdown del")?.textContent).toBe("old");
    expect(container?.querySelector(".agent-event-markdown p")?.innerHTML).toContain("<br>");
  });

  it("renders Mermaid fences through the shared markdown component", async () => {
    renderViewer({
      record: {
        ...chatRecord,
        messages: [
          {
            ...baseMessage,
            body: "```mermaid\ngraph TD\n  A --> B\n```"
          }
        ]
      }
    });

    await waitForAssertion(() => {
      expect(container?.querySelector(".agent-event-markdown-mermaid svg")?.textContent).toBe("Rendered diagram");
    });
    expect(mermaidInitializeMock).toHaveBeenCalledWith(expect.objectContaining({
      securityLevel: "strict",
      startOnLoad: false
    }));
    expect(mermaidRenderMock).toHaveBeenCalledWith(expect.stringContaining("agent-markdown-mermaid-"), "graph TD\n  A --> B");
    expect(container?.querySelector(".agent-event-markdown pre code.language-mermaid")).toBeNull();
  });

  it("sanitizes rendered Mermaid SVG before injecting it", async () => {
    mermaidRenderMock.mockResolvedValueOnce({
      svg: [
        '<svg onload="window.__agentRecordSvgInjected = true">',
        '<script>window.__agentRecordSvgScript = true</script>',
        '<a href="javascript:window.__agentRecordSvgLink = true"><text>Bad link</text></a>',
        '<foreignObject><div xmlns="http://www.w3.org/1999/xhtml" onclick="window.__agentRecordSvgClick = true">Label</div></foreignObject>',
        "</svg>"
      ].join(""),
      diagramType: "flowchart"
    });

    renderViewer({
      record: {
        ...chatRecord,
        messages: [
          {
            ...baseMessage,
            body: "```mermaid\ngraph TD\n  A[Bad] --> B\n```"
          }
        ]
      }
    });

    await waitForAssertion(() => {
      expect(container?.querySelector(".agent-event-markdown-mermaid svg")).not.toBeNull();
    });

    const diagram = container?.querySelector<SVGSVGElement>(".agent-event-markdown-mermaid svg");
    expect(diagram?.querySelector("script")).toBeNull();
    expect(diagram?.getAttribute("onload")).toBeNull();
    expect(diagram?.querySelector("a")?.getAttribute("href")).toBeNull();
    expect(diagram?.querySelector("foreignObject div")?.getAttribute("onclick")).toBeNull();
    expect((window as unknown as { __agentRecordSvgInjected?: boolean }).__agentRecordSvgInjected).toBeUndefined();
    expect((window as unknown as { __agentRecordSvgScript?: boolean }).__agentRecordSvgScript).toBeUndefined();
  });

  it("does not execute raw HTML or unsafe markdown links", () => {
    renderViewer({
      record: {
        ...chatRecord,
        messages: [
          {
            ...baseMessage,
            body: '<img src=x onerror="window.__agentRecordInjected = true"> [bad](javascript:alert(1)) [ok](https://example.com)'
          }
        ]
      }
    });

    expect((window as unknown as { __agentRecordInjected?: boolean }).__agentRecordInjected).toBeUndefined();
    expect(container?.querySelector(".agent-event-markdown img")).toBeNull();

    expect(container?.querySelector(".agent-event-markdown-link-text")?.textContent).toBe("bad");

    const links = [...(container?.querySelectorAll<HTMLAnchorElement>(".agent-event-markdown a") ?? [])];
    expect(links).toHaveLength(1);
    expect(links[0].getAttribute("href")).toBe("https://example.com");
    expect(links[0].getAttribute("target")).toBe("_blank");
    expect(links[0].getAttribute("rel")).toBe("noreferrer");
  });

  it("renders subagent call and result as distinct agent message types", () => {
    renderViewer({
      record: {
        ...chatRecord,
        messages: [
          {
            ...baseMessage,
            id: "message-call",
            body: "Return exactly: 1",
            agent_message_type: "subagent_call",
            subagent_id: "subagent-1",
            subagent_tool_use_id: "call-subagent-1",
            target_session_id: "sub-session-1",
            target_session_source_id: "agent-subagent-1"
          },
          {
            ...baseMessage,
            id: "message-result",
            body: "1",
            agent_message_type: "subagent_result",
            subagent_id: "subagent-1",
            subagent_tool_use_id: "call-subagent-1",
            target_session_id: "sub-session-1",
            target_session_source_id: "agent-subagent-1"
          }
        ],
        messages_total: 2
      },
      onOpenSubagent: vi.fn()
    });

    expect(container?.querySelector(".agent-chat-message-agent-group .agent-chat-message-content")?.getAttribute("aria-label")).toBe("Agent message group with 2 messages");
    expect(container?.querySelectorAll(".agent-chat-message-agent-group .agent-chat-avatar")).toHaveLength(1);
    expect(container?.querySelectorAll(".agent-chat-message-agent-group .agent-chat-message-body")).toHaveLength(2);
    const subagentCall = container?.querySelector(".agent-chat-message-group-item-subagent-call");
    const subagentResult = container?.querySelector(".agent-chat-message-group-item-subagent-result");
    expect(subagentCall?.getAttribute("aria-label")).toBe("Main Agent -> Subagent message");
    expect(subagentCall?.textContent).toContain("Return exactly: 1");
    expect(subagentCall?.textContent).not.toContain("Main Agent -> Subagent");
    expect(subagentResult?.getAttribute("aria-label")).toBe("Subagent -> Agent message");
    expect(subagentResult?.textContent).toContain("1");
    expect(subagentResult?.textContent).not.toContain("Subagent -> Agent");
    expect(container?.querySelectorAll(".agent-chat-message-subagent-button")).toHaveLength(2);
  });

  it("groups consecutive agent messages without changing user message boundaries", () => {
    renderViewer({
      record: {
        ...chatRecord,
        messages: [
          {
            ...baseMessage,
            id: "agent-1",
            body: "First agent response"
          },
          {
            ...baseMessage,
            id: "agent-2",
            body: "Second agent response"
          },
          {
            ...baseMessage,
            id: "user-1",
            role: "user",
            body: "User follow-up",
            agent_message_type: null
          },
          {
            ...baseMessage,
            id: "agent-3",
            body: "Final agent response"
          }
        ],
        messages_total: 4
      }
    });

    expect(container?.querySelectorAll(".agent-chat-events > .agent-chat-message")).toHaveLength(3);
    expect(container?.querySelector(".agent-chat-message-agent-group .agent-chat-message-content")?.getAttribute("aria-label")).toBe("Agent message group with 2 messages");
    expect(container?.querySelectorAll(".agent-chat-message-agent-group .agent-chat-avatar")).toHaveLength(1);
    expect(container?.querySelectorAll(".agent-chat-message-agent-group .agent-chat-message-body")).toHaveLength(2);
    expect(container?.textContent).toContain("First agent response");
    expect(container?.textContent).toContain("Second agent response");
    expect(container?.querySelector(".agent-chat-message-user")?.textContent).toContain("User follow-up");
    expect(container?.querySelectorAll(".agent-chat-events > .agent-chat-message-agent:not(.agent-chat-message-agent-group)")).toHaveLength(1);
    expect(container?.textContent).toContain("Final agent response");
  });

  it("marks chat totals as approximate when the backend has more pages without exact count", () => {
    renderViewer({
      record: {
        ...chatRecord,
        messages_total: 31,
        messages_total_exact: false,
        messages_has_more: true
      }
    });

    expect(container?.textContent).toContain("31+ chat messages");
    expect(container?.textContent).toContain("1-1 of 31+ messages");
  });

  it("submits quick input from the inline preview", () => {
    const onSubmit = renderViewerWithQuickInput();
    const textarea = container?.querySelector<HTMLTextAreaElement>(".agent-record-quick-input textarea");
    expect(textarea).toBeInstanceOf(HTMLTextAreaElement);

    const descriptor = Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype, "value");
    act(() => {
      descriptor?.set?.call(textarea, "fix this");
      textarea?.dispatchEvent(new Event("input", { bubbles: true }));
      textarea?.dispatchEvent(new KeyboardEvent("keydown", {
        bubbles: true,
        cancelable: true,
        key: "Enter"
      }));
    });

    expect(onSubmit).toHaveBeenCalledWith("fix this");
  });

  it("turns project markdown links into files routes and dispatches open requests", () => {
    const openRequests: ProjectFileOpenRequest[] = [];
    const handleOpenRequest = (event: Event) => {
      openRequests.push((event as CustomEvent<ProjectFileOpenRequest>).detail);
    };
    window.addEventListener(PROJECT_FILE_OPEN_EVENT, handleOpenRequest);

    renderViewer({
      record: {
        ...chatRecord,
        messages: [
          {
            ...baseMessage,
            body: "[App file](frontend/src/App.tsx:12)"
          }
        ]
      },
      projectFileContext: {
        clientId: "client-1",
        windowId: "window-1",
        projectPath: "/workspace/project",
        browseRoot: null,
        cwd: "/workspace/project"
      }
    });

    const link = container?.querySelector<HTMLAnchorElement>(".agent-event-markdown a");
    expect(link).toBeInstanceOf(HTMLAnchorElement);
    expect(link?.getAttribute("href")).toBe(
      "/clients/client-1/files?project_path=%2Fworkspace%2Fproject&window_id=window-1&file_path=frontend%2Fsrc%2FApp.tsx&line=12"
    );
    expect(link?.getAttribute("target")).toBeNull();

    act(() => {
      link?.dispatchEvent(new MouseEvent("click", { bubbles: true, cancelable: true }));
    });
    window.removeEventListener(PROJECT_FILE_OPEN_EVENT, handleOpenRequest);

    expect(openRequests).toEqual([
      {
        clientId: "client-1",
        windowId: "window-1",
        projectPath: "/workspace/project",
        browseRoot: null,
        path: "frontend/src/App.tsx",
        line: 12
      }
    ]);
  });
});
