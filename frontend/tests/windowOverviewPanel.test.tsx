import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, describe, expect, it, vi } from "vitest";

import { WindowOverviewPanel } from "../src/components/WindowOverviewPanel";
import { I18nProvider } from "../src/i18n";
import type { VirtualWindow } from "../src/types";

globalThis.IS_REACT_ACT_ENVIRONMENT = true;

let root: Root | null = null;
let container: HTMLDivElement | null = null;

const baseWindow: VirtualWindow = {
  id: "window-1",
  client_id: "client-1",
  title: "Terminal",
  folder_id: null,
  parent_window_id: null,
  root_window_id: null,
  derived_mode: null,
  derived_context: null,
  status: "ACTIVE",
  tmux_session: "session",
  tmux_window_id: "@1",
  tmux_window_index: "1",
  remote_session_id: null,
  remote_window_id: null,
  cwd: "/workspace/project",
  shell_command: "codex",
  summary: null,
  title_tags: null,
  runtime_tags: [],
  git_worktree: null,
  agent_token_usage: {
    context: {
      input_tokens: 80,
      output_tokens: 10,
      total_tokens: 90,
      cached_input_tokens: 30,
      cache_creation_input_tokens: 0,
      reasoning_output_tokens: 2
    },
    total: {
      input_tokens: 100,
      output_tokens: 12,
      total_tokens: 112,
      cached_input_tokens: 40,
      cache_creation_input_tokens: 5,
      reasoning_output_tokens: 3
    },
    context_window: 258400,
    auto_compact_token_limit: 80,
    latest_event_at: "2026-06-08T12:00:00Z",
    providers: ["codex"],
    event_count: 1
  },
  work_status: {
    state: "WORKING",
    label: "Agent working",
    color: "orange",
    last_activity_at: "2026-06-08T12:00:00Z",
    last_working_activity_at: "2026-06-08T12:00:00Z",
    source: "activity",
    manual_updated_at: null
  },
  title_manually_overridden: false,
  folder_manually_overridden: false,
  command_capture_supported: true,
  summary_job: null,
  created_at: "2026-06-08T11:00:00Z",
  last_terminal_command_at: null,
  last_agent_event_at: "2026-06-08T12:00:00Z",
  last_active_at: "2026-06-08T12:00:00Z"
};

function renderPanel(item: VirtualWindow = baseWindow): void {
  container = document.createElement("div");
  document.body.appendChild(container);
  root = createRoot(container);
  act(() => {
    root?.render(
      <I18nProvider initialLocale="en-US">
        <WindowOverviewPanel
          allowTitleFolderOverride={false}
          clientId="client-1"
          gitWorktree={null}
          item={item}
          manualLocks={[]}
          manualWorkStatusError={false}
          manualWorkStatusPending={false}
          retryError={false}
          retryPending={false}
          showGitTab={false}
          status={{ label: "No summary job yet.", tone: "muted" }}
          tags={[]}
          windowId="window-1"
          onAllowTitleFolderOverrideChange={vi.fn()}
          onManualWorkStatusChange={vi.fn()}
          onRetrySummary={vi.fn()}
        />
      </I18nProvider>
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

describe("WindowOverviewPanel", () => {
  it("renders current context, total, and cached token usage", () => {
    renderPanel();

    expect(container?.textContent).toContain("Context tokens");
    expect(container?.textContent).toContain("90");
    expect(container?.textContent).toContain("258,400 (80)");
    expect(container?.textContent).not.toContain("context window");
    expect(container?.textContent).toContain("Total tokens");
    expect(container?.textContent).toContain("112");
    expect(container?.textContent).toContain("cached 45");
    expect(container?.textContent).toContain("codex");

    const progress = container?.querySelector(".token-usage-progress");
    expect(progress).not.toBeNull();
    expect(progress?.getAttribute("role")).toBe("progressbar");
    expect(progress?.getAttribute("aria-valuenow")).toBe("90");
    expect(progress?.getAttribute("aria-valuemax")).toBe("258400");
    expect(progress?.getAttribute("aria-valuetext")).toBe("90 / 258,400");
    expect(progress?.classList.contains("warning")).toBe(true);
    expect(progress?.querySelector(".token-usage-progress-warning-zone")).not.toBeNull();
    expect(progress?.querySelector<HTMLElement>(".token-usage-progress-fill")?.style.width).toBe(
      `${(90 / 258400) * 100}%`
    );
  });

  it("renders progress against the compact limit when no context window is available", () => {
    renderPanel({
      ...baseWindow,
      agent_token_usage: {
        ...baseWindow.agent_token_usage!,
        context: {
          ...baseWindow.agent_token_usage!.context!,
          total_tokens: 29254
        },
        total: {
          ...baseWindow.agent_token_usage!.total,
          input_tokens: 112838,
          output_tokens: 863,
          total_tokens: 113701
        },
        context_window: null,
        auto_compact_token_limit: 100000,
        providers: ["claude_code"],
        event_count: 4
      }
    });

    expect(container?.textContent).toContain("100,000 compact limit");
    const progress = container?.querySelector(".token-usage-progress");
    expect(progress).not.toBeNull();
    expect(progress?.getAttribute("aria-valuemax")).toBe("100000");
    expect(progress?.getAttribute("aria-valuenow")).toBe("29254");
    expect(progress?.getAttribute("aria-valuetext")).toBe("29,254 / 100,000");
    expect(progress?.querySelector(".token-usage-progress-warning-zone")).toBeNull();
    expect(progress?.querySelector<HTMLElement>(".token-usage-progress-fill")?.style.width).toBe("29.254%");
  });

  it("renders progress from total tokens when context usage is not available", () => {
    renderPanel({
      ...baseWindow,
      agent_token_usage: {
        ...baseWindow.agent_token_usage!,
        context: null,
        total: {
          ...baseWindow.agent_token_usage!.total,
          total_tokens: 113701
        },
        context_window: null,
        auto_compact_token_limit: 230000,
        providers: ["claude_code"],
        event_count: 4
      }
    });

    const progress = container?.querySelector(".token-usage-progress");
    expect(progress).not.toBeNull();
    expect(progress?.getAttribute("aria-valuemax")).toBe("230000");
    expect(progress?.getAttribute("aria-valuenow")).toBe("113701");
    expect(progress?.getAttribute("aria-valuetext")).toBe("113,701 / 230,000");
  });
});
