import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, describe, expect, it, vi } from "vitest";

import { TerminalSwitcher } from "../src/components/TerminalSwitcher";
import type { TreeFolder, TreeWindow } from "../src/types";

globalThis.IS_REACT_ACT_ENVIRONMENT = true;

const fetchTerminalRecentsMock = vi.fn();
const fetchGlobalTerminalRecentsMock = vi.fn();
const fetchProjectSummariesMock = vi.fn();
const summarizeProjectMock = vi.fn();

vi.mock("../src/api", () => ({
  fetchTerminalRecents: (...args: unknown[]) => fetchTerminalRecentsMock(...args),
  fetchGlobalTerminalRecents: (...args: unknown[]) => fetchGlobalTerminalRecentsMock(...args),
  fetchProjectSummaries: (...args: unknown[]) => fetchProjectSummariesMock(...args),
  summarizeProject: (...args: unknown[]) => summarizeProjectMock(...args)
}));

let root: Root | null = null;
let container: HTMLDivElement | null = null;
let queryClient: QueryClient | null = null;

function testWindow(id: string, title: string, projectPath: string, lastActivity: string): TreeWindow {
  return {
    id,
    title,
    status: "ACTIVE",
    title_tags: [],
    created_at: lastActivity,
    parent_window_id: null,
    root_window_id: null,
    derived_mode: null,
    work_status: {
      state: "RECENT_ACTIVE",
      label: "recent active",
      color: "green",
      last_activity_at: lastActivity,
      last_working_activity_at: null
    },
    runtime_tags: ["codex", projectPath],
    last_agent_task_completed_at: null,
    last_agent_task_status: null,
    last_agent_task_status_at: null,
    git_worktree: null
  };
}

const alphaWindow = testWindow("window-alpha", "Alpha terminal", "/workspace/alpha", "2026-06-03T10:00:00Z");
const betaWindow = testWindow("window-beta", "Beta terminal", "/workspace/beta", "2026-06-03T11:00:00Z");
const alphaOlderWindow = testWindow("window-alpha-old", "Alpha old terminal", "/workspace/alpha", "2026-06-03T09:00:00Z");

const folders: TreeFolder[] = [
  {
    id: "folder-root",
    name: "Root",
    path: "/workspace",
    folders: [],
    windows: [alphaWindow, betaWindow, alphaOlderWindow]
  }
];

function renderSwitcher(props: Partial<Parameters<typeof TerminalSwitcher>[0]> = {}) {
  container = document.createElement("div");
  document.body.appendChild(container);
  queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false }
    }
  });
  root = createRoot(container);
  act(() => {
    root?.render(
      <QueryClientProvider client={queryClient as QueryClient}>
        <TerminalSwitcher
          clientId="client-1"
          folders={folders}
          selectedWindowId="window-alpha"
          mode="recent"
          terminalGroupingMode="project-topic"
          summaryOutputLanguage="zh-CN"
          isOpen
          onClose={() => {}}
          onSelectWindow={() => {}}
          {...props}
        />
      </QueryClientProvider>
    );
  });
}

async function waitForRequests(): Promise<void> {
  await act(async () => {
    await Promise.resolve();
  });
}

async function waitForProjectTabs(): Promise<HTMLButtonElement[]> {
  for (let attempt = 0; attempt < 20; attempt += 1) {
    await waitForRequests();
    const tabs = projectTabs();
    if (tabs.length > 0) {
      return tabs;
    }
  }

  throw new Error("project tabs were not ready");
}

async function waitForWindowTitles(): Promise<string[]> {
  for (let attempt = 0; attempt < 20; attempt += 1) {
    await waitForRequests();
    const titles = visibleWindowTitles();
    if (titles.length > 0) {
      return titles;
    }
  }

  throw new Error("window titles were not ready");
}

function projectTabs(): HTMLButtonElement[] {
  return Array.from(container?.querySelectorAll(".terminal-switcher-project-tabs button") ?? [])
    .filter((button): button is HTMLButtonElement => button instanceof HTMLButtonElement);
}

function visibleWindowTitles(): string[] {
  return Array.from(container?.querySelectorAll(".terminal-switcher .switcher-window-title") ?? [])
    .map((element) => element.textContent ?? "");
}

function visibleTodoTitles(): string[] {
  return Array.from(container?.querySelectorAll(".terminal-switcher .switcher-window-todo-title") ?? [])
    .map((element) => element.textContent ?? "");
}

function visibleWindowButtons(): HTMLButtonElement[] {
  return Array.from(container?.querySelectorAll(".terminal-switcher .switcher-window") ?? [])
    .filter((button): button is HTMLButtonElement => button instanceof HTMLButtonElement);
}

afterEach(() => {
  act(() => {
    root?.unmount();
  });
  container?.remove();
  root = null;
  container = null;
  queryClient = null;
  vi.clearAllMocks();
});

describe("TerminalSwitcher project tabs", () => {
  it("shows all by default and orders project tabs by recent terminal order", async () => {
    fetchProjectSummariesMock.mockResolvedValue([
      { project_path: "/workspace/alpha", display_name: "Alpha", status: "SUCCEEDED", last_error: null, updated_at: "2026-06-03T10:00:00Z" },
      { project_path: "/workspace/beta", display_name: "Beta", status: "SUCCEEDED", last_error: null, updated_at: "2026-06-03T11:00:00Z" }
    ]);
    fetchTerminalRecentsMock.mockResolvedValue({
      items: [
        { window_id: "window-beta", title: "Beta terminal", last_used_at: "2026-06-03T11:00:00Z" },
        { window_id: "window-alpha", title: "Alpha terminal", last_used_at: "2026-06-03T10:00:00Z" },
        { window_id: "window-alpha-old", title: "Alpha old terminal", last_used_at: "2026-06-03T09:00:00Z" }
      ],
      page: 1,
      page_size: 100,
      total: 3,
      total_pages: 1
    });

    renderSwitcher();
    const tabs = await waitForProjectTabs();

    expect(fetchTerminalRecentsMock).toHaveBeenCalledWith("client-1", 1, 8, "");
    expect(tabs.map((button) => button.textContent)).toEqual(["All3", "Beta1", "Alpha2"]);
    expect(tabs[0]?.getAttribute("aria-selected")).toBe("true");
    expect(visibleWindowTitles()).toEqual(["Beta terminal", "Alpha terminal", "Alpha old terminal"]);
  });

  it("uses tab to switch projects and filters recent terminals", async () => {
    fetchProjectSummariesMock.mockResolvedValue([
      { project_path: "/workspace/alpha", display_name: "Alpha", status: "SUCCEEDED", last_error: null, updated_at: "2026-06-03T10:00:00Z" },
      { project_path: "/workspace/beta", display_name: "Beta", status: "SUCCEEDED", last_error: null, updated_at: "2026-06-03T11:00:00Z" }
    ]);
    fetchTerminalRecentsMock.mockResolvedValue({
      items: [
        { window_id: "window-beta", title: "Beta terminal", last_used_at: "2026-06-03T11:00:00Z" },
        { window_id: "window-alpha", title: "Alpha terminal", last_used_at: "2026-06-03T10:00:00Z" }
      ],
      page: 1,
      page_size: 100,
      total: 2,
      total_pages: 1
    });

    renderSwitcher();
    await waitForProjectTabs();

    const tabEvent = new KeyboardEvent("keydown", { key: "Tab", bubbles: true, cancelable: true });
    act(() => {
      window.dispatchEvent(tabEvent);
    });

    expect(tabEvent.defaultPrevented).toBe(true);
    expect(projectTabs()[1]?.getAttribute("aria-selected")).toBe("true");
    expect(visibleWindowTitles()).toEqual(["Beta terminal"]);

    act(() => {
      window.dispatchEvent(new KeyboardEvent("keydown", { key: "Tab", bubbles: true, cancelable: true }));
    });

    expect(projectTabs()[2]?.getAttribute("aria-selected")).toBe("true");
    expect(visibleWindowTitles()).toEqual(["Alpha terminal"]);
  });

  it("shows todo titles as compact subtitles in recent terminals", async () => {
    fetchProjectSummariesMock.mockResolvedValue([]);
    fetchTerminalRecentsMock.mockResolvedValue({
      items: [
        {
          window_id: "window-alpha",
          title: "Investigate auth flow",
          todo_title: "Fix login dispatch",
          last_used_at: "2026-06-03T10:00:00Z"
        },
        {
          window_id: "window-beta",
          title: "Beta terminal",
          todo_title: "Beta terminal",
          last_used_at: "2026-06-03T09:00:00Z"
        }
      ],
      page: 1,
      page_size: 100,
      total: 2,
      total_pages: 1
    });

    renderSwitcher();
    const titles = await waitForWindowTitles();

    expect(titles).toEqual(["Investigate auth flow", "Beta terminal"]);
    expect(visibleTodoTitles()).toEqual(["Fix login dispatch"]);
    expect(visibleWindowButtons()[0]?.title).toBe("Investigate auth flow\nFix login dispatch");
    expect(visibleWindowButtons()[1]?.title).toBe("Beta terminal");
  });

  it("shows one page of recent terminals and moves the overflow to the next page", async () => {
    fetchProjectSummariesMock.mockResolvedValue([]);
    fetchTerminalRecentsMock.mockImplementation((_clientId: string, page: number, pageSize: number) => {
      const allItems = Array.from({ length: 9 }, (_, index) => ({
        window_id: `window-${index + 1}`,
        title: `Terminal ${index + 1}`,
        last_used_at: `2026-06-03T10:${String(index).padStart(2, "0")}:00Z`
      }));
      const start = (page - 1) * pageSize;
      return Promise.resolve({
        items: allItems.slice(start, start + pageSize),
        page,
        page_size: pageSize,
        total: allItems.length,
        total_pages: 2
      });
    });

    renderSwitcher({ selectedWindowId: "window-1" });
    expect(await waitForWindowTitles()).toEqual([
      "Terminal 1",
      "Terminal 2",
      "Terminal 3",
      "Terminal 4",
      "Terminal 5",
      "Terminal 6",
      "Terminal 7",
      "Terminal 8"
    ]);

    const nextButton = Array.from(container?.querySelectorAll(".terminal-switcher-pagination button") ?? [])
      .find((button) => button.textContent === "Next") as HTMLButtonElement | undefined;
    expect(nextButton).toBeDefined();

    await act(async () => {
      nextButton?.click();
      await Promise.resolve();
    });

    expect(fetchTerminalRecentsMock).toHaveBeenLastCalledWith("client-1", 2, 8, "");
    expect(await waitForWindowTitles()).toEqual(["Terminal 9"]);
  });

  it("shows the full long title tip only for the active truncated terminal", async () => {
    const originalScrollWidth = Object.getOwnPropertyDescriptor(HTMLElement.prototype, "scrollWidth");
    const originalClientWidth = Object.getOwnPropertyDescriptor(HTMLElement.prototype, "clientWidth");
    Object.defineProperty(HTMLElement.prototype, "scrollWidth", {
      configurable: true,
      get() {
        return this.classList.contains("switcher-window-title") && (this.textContent ?? "").includes("very very long") ? 320 : 100;
      }
    });
    Object.defineProperty(HTMLElement.prototype, "clientWidth", {
      configurable: true,
      get() {
        return this.classList.contains("switcher-window-title") && (this.textContent ?? "").includes("very very long") ? 120 : 100;
      }
    });

    try {
      fetchProjectSummariesMock.mockResolvedValue([]);
      fetchTerminalRecentsMock.mockResolvedValue({
        items: [
          { window_id: "window-short", title: "Short terminal", last_used_at: "2026-06-03T11:00:00Z" },
          {
            window_id: "window-long",
            title: "A very very long terminal name that needs ellipsis",
            last_used_at: "2026-06-03T10:00:00Z"
          }
        ],
        page: 1,
        page_size: 8,
        total: 2,
        total_pages: 1
      });

      renderSwitcher({ selectedWindowId: "window-short" });
      await waitForWindowTitles();

      expect(container?.querySelector(".switcher-window-title-tip")).toBeNull();

      await act(async () => {
        window.dispatchEvent(new KeyboardEvent("keydown", { key: "ArrowDown", bubbles: true, cancelable: true }));
        await Promise.resolve();
      });

      expect(container?.querySelector(".switcher-window-title-tip")?.textContent).toBe("A very very long terminal name that needs ellipsis");
    } finally {
      if (originalScrollWidth) {
        Object.defineProperty(HTMLElement.prototype, "scrollWidth", originalScrollWidth);
      }
      if (originalClientWidth) {
        Object.defineProperty(HTMLElement.prototype, "clientWidth", originalClientWidth);
      }
    }
  });

  it("keeps long terminal metadata inside its fixed row budget", async () => {
    fetchProjectSummariesMock.mockResolvedValue([
      {
        project_path: "/workspace/projects/very-long-terminal-name-that-used-to-push-the-rest-of-the-row-away",
        display_name: "Very long terminal project name that used to push the row metadata away",
        status: "SUCCEEDED",
        last_error: null,
        updated_at: "2026-06-03T10:00:00Z"
      }
    ]);
    fetchTerminalRecentsMock.mockResolvedValue({
      items: [
        {
          window_id: "window-long-meta",
          title: "Readable terminal title",
          last_used_at: "2026-06-03T10:00:00Z"
        }
      ],
      page: 1,
      page_size: 8,
      total: 1,
      total_pages: 1
    });

    renderSwitcher({
      folders: [
        {
          id: "folder-long-meta",
          name: "Long meta folder",
          path: "/workspace/projects/very-long-terminal-name-that-used-to-push-the-rest-of-the-row-away",
          folders: [],
          windows: [
            testWindow(
              "window-long-meta",
              "Readable terminal title",
              "/workspace/projects/very-long-terminal-name-that-used-to-push-the-rest-of-the-row-away",
              "2026-06-03T10:00:00Z"
            )
          ]
        }
      ],
      selectedWindowId: "window-long-meta"
    });
    await waitForWindowTitles();

    const meta = container?.querySelector(".switcher-window-meta");
    const timeMeta = container?.querySelector(".switcher-window-meta-time");
    const projectMeta = container?.querySelector(".switcher-window-meta-project");

    expect(meta).toBeInstanceOf(HTMLElement);
    expect(timeMeta).toBeInstanceOf(HTMLTimeElement);
    expect(projectMeta).toBeInstanceOf(HTMLElement);
    expect(timeMeta?.textContent).toContain("06/03");
    expect(projectMeta?.textContent).toBe("Very long terminal project name that used to push the row metadata away");
    expect((projectMeta as HTMLElement).title).toBe("/workspace/projects/very-long-terminal-name-that-used-to-push-the-rest-of-the-row-away");
  });

  it("marks recent terminal rows with the layout columns they need", async () => {
    fetchProjectSummariesMock.mockResolvedValue([]);
    fetchTerminalRecentsMock.mockResolvedValue({
      items: [
        { window_id: "window-alpha", title: "Local with metadata", last_used_at: "2026-06-03T10:00:00Z" },
        { window_id: "window-missing", title: "Missing tree metadata", last_used_at: "2026-06-03T09:00:00Z" }
      ],
      page: 1,
      page_size: 8,
      total: 2,
      total_pages: 1
    });

    renderSwitcher();
    await waitForWindowTitles();

    const rows = visibleWindowButtons();
    expect(rows[0]?.className).toContain("with-meta");
    expect(rows[0]?.className).not.toContain("with-client-name");
    expect(rows[1]?.className).not.toContain("with-meta");
    expect(rows[1]?.className).not.toContain("with-client-name");
  });

  it("keeps global recent client names separate from metadata columns", async () => {
    fetchProjectSummariesMock.mockResolvedValue([]);
    fetchGlobalTerminalRecentsMock.mockResolvedValue({
      items: [
        {
          client_id: "client-2",
          client_name: "Remote client with long name",
          window_id: "window-alpha",
          title: "Global recent with local metadata",
          last_used_at: "2026-06-03T10:00:00Z"
        },
        {
          client_id: "client-3",
          client_name: "Detached client",
          window_id: "window-detached",
          title: "Global recent without local metadata",
          last_used_at: "2026-06-03T09:00:00Z"
        }
      ],
      page: 1,
      page_size: 8,
      total: 2,
      total_pages: 1
    });

    renderSwitcher({ recentScope: "global" });
    await waitForWindowTitles();

    const rows = visibleWindowButtons();
    expect(rows[0]?.className).toContain("with-client-name");
    expect(rows[0]?.className).toContain("with-meta");
    expect(rows[1]?.className).toContain("with-client-name");
    expect(rows[1]?.className).not.toContain("with-meta");
  });
});
