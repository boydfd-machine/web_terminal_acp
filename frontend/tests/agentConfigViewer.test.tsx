import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, describe, expect, it, vi } from "vitest";

import { WindowDetail } from "../src/components/WindowDetail";
import type { VirtualWindow } from "../src/types";

globalThis.IS_REACT_ACT_ENVIRONMENT = true;

let root: Root | null = null;
let container: HTMLDivElement | null = null;
let queryClient: QueryClient | null = null;

const windowDetail: VirtualWindow = {
  id: "window-1",
  client_id: "client-1",
  title: "Codex terminal",
  folder_id: null,
  status: "ACTIVE",
  tmux_session: "test",
  tmux_window_id: "@1",
  tmux_window_index: "4",
  remote_session_id: null,
  remote_window_id: null,
  cwd: "/workspace/project",
  shell_command: "/bin/bash",
  summary: null,
  title_tags: [],
  runtime_tags: ["codex", "/workspace/project"],
  work_status: {
    state: "RECENT_ACTIVE",
    label: "recent active",
    color: "green",
    last_activity_at: "2026-05-29T00:00:00Z",
    last_working_activity_at: "2026-05-29T00:00:00Z"
  },
  title_manually_overridden: false,
  folder_manually_overridden: false,
  command_capture_supported: true,
  summary_job: null,
  created_at: "2026-05-29T00:00:00Z",
  last_terminal_command_at: "2026-05-29T00:00:00Z",
  last_agent_event_at: "2026-05-29T00:00:00Z",
  last_active_at: "2026-05-29T00:00:00Z"
};

function renderWindowDetail() {
  container = document.createElement("div");
  document.body.appendChild(container);
  root = createRoot(container);
  queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false }
    }
  });

  act(() => {
    root?.render(
      <QueryClientProvider client={queryClient as QueryClient}>
        <WindowDetail clientId="client-1" windowId="window-1" />
      </QueryClientProvider>
    );
  });
}

async function flushPromises() {
  await act(async () => {
    await Promise.resolve();
    await Promise.resolve();
  });
}

async function waitFor(assertion: () => void) {
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
  queryClient?.clear();
  queryClient = null;
  vi.restoreAllMocks();
  window.localStorage.clear();
});

describe("Agent config viewer", () => {
  it("shows the tmux window index in the overview tab", async () => {
    globalThis.fetch = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url.endsWith("/api/clients/client-1/windows/window-1")) {
        return new Response(JSON.stringify(windowDetail), { status: 200, headers: { "Content-Type": "application/json" } });
      }
      throw new Error(`unexpected request: ${url}`);
    }) as never;

    renderWindowDetail();
    await flushPromises();

    await waitFor(() => {
      expect(container?.textContent).toContain("tmux window index");
      expect(container?.textContent).toContain("4");
    });
  });

  it("updates manual work status from the overview tab", async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url.endsWith("/api/clients/client-1/windows/window-1/work-status")) {
        expect(init?.method).toBe("PATCH");
        expect(init?.body).toBe(JSON.stringify({ state: "WORKING" }));
        return new Response(JSON.stringify({
          state: "WORKING",
          label: "Agent 工作中",
          color: "orange",
          source: "manual",
          manual_updated_at: "2026-06-05T00:00:00Z",
          last_activity_at: windowDetail.work_status.last_activity_at,
          last_working_activity_at: windowDetail.work_status.last_working_activity_at
        }), { status: 200, headers: { "Content-Type": "application/json" } });
      }
      if (url.endsWith("/api/clients/client-1/windows/window-1")) {
        return new Response(JSON.stringify(windowDetail), { status: 200, headers: { "Content-Type": "application/json" } });
      }
      throw new Error(`unexpected request: ${url}`);
    });
    globalThis.fetch = fetchMock as never;

    renderWindowDetail();
    await flushPromises();

    let statusSelect: HTMLSelectElement | null = null;
    await waitFor(() => {
      statusSelect = container!.querySelector('select[aria-label="Manual work status"]');
      expect(statusSelect).toBeInstanceOf(HTMLSelectElement);
    });

    await act(async () => {
      statusSelect!.value = "WORKING";
      statusSelect!.dispatchEvent(new Event("change", { bubbles: true }));
    });

    await waitFor(() => {
      expect(container?.textContent).toContain("Agent working");
      expect(container?.textContent).toContain("Manual");
    });
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining("/work-status"),
      expect.objectContaining({ method: "PATCH" })
    );
  });

  it("renders config sections under the Agent tab and toggles enablement", async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url.includes("/agent-config/skills/docker")) {
        expect(init?.method).toBe("PATCH");
        expect(init?.body).toBe(JSON.stringify({ enabled: false }));
        return new Response(JSON.stringify({
          agent: "codex",
          sections: [
            { id: "skills", name: "Skills", items: [{ id: "docker", name: "docker", enabled: false }] },
            { id: "plugins", name: "Plugins", items: [] },
            { id: "hooks", name: "Hooks", items: [] },
            { id: "mcp", name: "MCP Servers", items: [{ id: "filesystem", name: "filesystem", enabled: true }] }
          ]
        }), { status: 200, headers: { "Content-Type": "application/json" } });
      }
      if (url.endsWith("/api/clients/client-1/windows/window-1/agent-config")) {
        return new Response(JSON.stringify({
          agent: "codex",
          sections: [
            { id: "skills", name: "Skills", items: [{ id: "docker", name: "docker", enabled: true }] },
            { id: "plugins", name: "Plugins", items: [{ id: "superpowers@openai-curated", name: "Superpowers", enabled: false }] },
            { id: "hooks", name: "Hooks", items: [] },
            { id: "mcp", name: "MCP Servers", items: [{ id: "filesystem", name: "filesystem", enabled: true }] }
          ]
        }), { status: 200, headers: { "Content-Type": "application/json" } });
      }
      if (url.endsWith("/api/clients/client-1/windows/window-1")) {
        return new Response(JSON.stringify(windowDetail), { status: 200, headers: { "Content-Type": "application/json" } });
      }
      throw new Error(`unexpected request: ${url}`);
    });
    globalThis.fetch = fetchMock as never;

    renderWindowDetail();
    await flushPromises();

    let agentTab: HTMLButtonElement | undefined;
    await waitFor(() => {
      agentTab = [...container!.querySelectorAll("button")].find((button) => button.textContent === "Agent");
      expect(agentTab).toBeTruthy();
    });
    act(() => {
      agentTab?.dispatchEvent(new MouseEvent("click", { bubbles: true }));
    });

    let configTab: HTMLButtonElement | undefined;
    await waitFor(() => {
      configTab = [...container!.querySelectorAll("button")].find((button) => button.textContent === "Config");
      expect(configTab).toBeTruthy();
    });
    act(() => {
      configTab?.dispatchEvent(new MouseEvent("click", { bubbles: true }));
    });

    await waitFor(() => {
      expect(container?.textContent).toContain("Skills");
    });
    expect(container?.textContent).toContain("docker");
    expect(container?.textContent).toContain("Plugins");
    expect(container?.textContent).toContain("Superpowers");
    expect(container?.textContent).toContain("Hooks");
    expect(container?.textContent).toContain("MCP Servers");
    expect(container?.textContent).toContain("filesystem");

    const dockerToggle = container!.querySelector('input[aria-label="Disable docker"]');
    expect(dockerToggle).toBeInstanceOf(HTMLInputElement);
    await act(async () => {
      dockerToggle?.dispatchEvent(new MouseEvent("click", { bubbles: true }));
    });

    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining("/agent-config/skills/docker"),
      expect.objectContaining({ method: "PATCH" })
    );
  });

  it("shows title summary snapshots under the History title tab", async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url.includes("/title-history")) {
        return new Response(JSON.stringify({
          window_id: "window-1",
          items: [
            {
              id: "history-2",
              title: "Investigate build failure",
              summary: "The terminal moved from setup into build triage.",
              source: "summary",
              created_at: "2026-05-29T00:10:00Z"
            },
            {
              id: "history-1",
              title: "Codex terminal",
              summary: null,
              source: "initial",
              created_at: "2026-05-29T00:00:00Z"
            }
          ],
          total: 2,
          limit: 100,
          offset: 0,
          has_more: false
        }), { status: 200, headers: { "Content-Type": "application/json" } });
      }
      if (url.endsWith("/api/clients/client-1/windows/window-1")) {
        return new Response(JSON.stringify(windowDetail), { status: 200, headers: { "Content-Type": "application/json" } });
      }
      throw new Error(`unexpected request: ${url}`);
    });
    globalThis.fetch = fetchMock as never;

    renderWindowDetail();
    await flushPromises();

    let historyTab: HTMLButtonElement | undefined;
    await waitFor(() => {
      historyTab = [...container!.querySelectorAll("button")].find((button) => button.textContent === "History");
      expect(historyTab).toBeTruthy();
    });
    act(() => {
      historyTab?.dispatchEvent(new MouseEvent("click", { bubbles: true }));
    });

    let titleTab: HTMLButtonElement | undefined;
    await waitFor(() => {
      titleTab = [...container!.querySelectorAll("button")].find((button) => button.textContent === "Title");
      expect(titleTab).toBeTruthy();
    });
    act(() => {
      titleTab?.dispatchEvent(new MouseEvent("click", { bubbles: true }));
    });

    await waitFor(() => {
      expect(container?.textContent).toContain("Investigate build failure");
    });
    expect(container?.textContent).toContain("The terminal moved from setup into build triage.");
    expect(container?.textContent).toContain("Codex terminal");
    expect(fetchMock.mock.calls.some(([input]) => String(input).includes("/title-history?"))).toBe(true);
  });

  it("renders terminal artifact HTML through iframe srcdoc fetched with bearer auth", async () => {
    window.localStorage.setItem("web-terminal-acp:auth-token", "token-1");
    const artifactList = {
      window_id: "window-1",
      artifacts: [
        {
          id: "artifact-1",
          client_id: "client-1",
          virtual_window_id: "window-1",
          source_window_id: "window-1",
          ephemeral_window_id: null,
          artifact_kind: "agent_trace_graph",
          title: "Trace graph",
          status: "SUCCEEDED",
          content_json: null,
          display_html: null,
          metadata_json: null,
          last_error: null,
          started_at: null,
          completed_at: "2026-05-29T00:10:00Z",
          created_at: "2026-05-29T00:00:00Z",
          updated_at: "2026-05-29T00:10:00Z"
        }
      ],
      total: 1,
      limit: 50,
      offset: 0,
      has_more: false
    };
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url.includes("/artifacts/artifact-1/html")) {
        expect(new Headers(init?.headers).get("Authorization")).toBe("Bearer token-1");
        expect(new URL(url).searchParams.has("auth_token")).toBe(false);
        return new Response("<html><head></head><body>trace</body></html>", {
          status: 200,
          headers: { "Content-Type": "text/html" }
        });
      }
      if (url.includes("/artifacts?")) {
        return new Response(JSON.stringify(artifactList), {
          status: 200,
          headers: { "Content-Type": "application/json" }
        });
      }
      if (url.endsWith("/api/clients/client-1/windows/window-1")) {
        return new Response(JSON.stringify(windowDetail), { status: 200, headers: { "Content-Type": "application/json" } });
      }
      throw new Error(`unexpected request: ${url}`);
    });
    globalThis.fetch = fetchMock as never;

    renderWindowDetail();
    await flushPromises();

    let artifactsTab: HTMLButtonElement | undefined;
    await waitFor(() => {
      artifactsTab = [...container!.querySelectorAll("button")].find((button) => button.textContent === "Artifacts");
      expect(artifactsTab).toBeTruthy();
    });
    act(() => {
      artifactsTab?.dispatchEvent(new MouseEvent("click", { bubbles: true }));
    });

    await waitFor(() => {
      const iframe = container!.querySelector("iframe");
      expect(iframe).toBeInstanceOf(HTMLIFrameElement);
      expect(iframe?.getAttribute("src")).toBeNull();
      expect(iframe?.getAttribute("srcdoc")).toContain("Content-Security-Policy");
      expect(iframe?.getAttribute("srcdoc")).toContain("<body>trace</body>");
    });
  });
});
