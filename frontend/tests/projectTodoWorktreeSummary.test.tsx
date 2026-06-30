import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ProjectTodoWorktreeSummary } from "../src/components/ProjectTodoWorktreeSummary";
import { I18nProvider } from "../src/i18n";
import type { ProjectTodoWorktree } from "../src/types";

const apiMocks = vi.hoisted(() => ({
  fetchGitRuns: vi.fn()
}));

vi.mock("../src/api", () => apiMocks);

globalThis.IS_REACT_ACT_ENVIRONMENT = true;

let root: Root | null = null;
let container: HTMLDivElement | null = null;
let queryClient: QueryClient | null = null;

afterEach(() => {
  act(() => {
    root?.unmount();
  });
  container?.remove();
  root = null;
  container = null;
  queryClient?.clear();
  queryClient = null;
  vi.clearAllMocks();
});

function renderSummary(worktree: ProjectTodoWorktree): void {
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
        <I18nProvider initialLocale="en-US">
          <ProjectTodoWorktreeSummary clientId="client-1" worktree={worktree} />
        </I18nProvider>
      </QueryClientProvider>
    );
  });
}

async function waitForText(text: string): Promise<Element> {
  for (let attempt = 0; attempt < 20; attempt += 1) {
    await act(async () => {
      await new Promise((resolve) => setTimeout(resolve, 0));
    });
    const element = Array.from(document.body.querySelectorAll("*")).find((candidate) =>
      candidate.textContent?.includes(text)
    );
    if (element !== undefined) {
      return element;
    }
  }
  throw new Error(`Text ${text} was not ready`);
}

async function waitForButton(text: string): Promise<HTMLButtonElement> {
  for (let attempt = 0; attempt < 20; attempt += 1) {
    await act(async () => {
      await new Promise((resolve) => setTimeout(resolve, 0));
    });
    const button = Array.from(document.body.querySelectorAll("button")).find((candidate) =>
      candidate.textContent?.includes(text)
    );
    if (button instanceof HTMLButtonElement) {
      return button;
    }
  }
  throw new Error(`Button ${text} was not ready`);
}

describe("ProjectTodoWorktreeSummary", () => {
  it("opens archived todo diff from saved worktree runs", async () => {
    renderSummary({
      window_id: "window-1",
      worktree_root: "/repo/.worktrees/feature",
      branch: "agent/feature",
      end_head: "feature",
      merge_status: "merged",
      commits: [{ sha: "feature", short_sha: "feature", subject: "Keep todo diff" }],
      diff_runs: [{
        id: "run-1",
        virtual_window_id: "window-1",
        command_sequence: "12",
        agent_provider: "codex",
        status: "completed",
        run_type: "agent",
        worktree_root: "/repo/.worktrees/feature",
        main_repo_root: "/repo",
        discovery_method: "marker",
        start_snapshot_json: null,
        end_snapshot_json: null,
        session_diff_json: {
          commits: [{
            sha: "feature",
            short_sha: "feature",
            subject: "Keep todo diff",
            files: [{
              path: "backend/app.py",
              status: "modified",
              additions: 1,
              deletions: 1,
              patch: "@@ -1 +1 @@\n-old\n+new\n"
            }]
          }]
        },
        pending_commit: false,
        resolved_at: null,
        started_at: "2026-06-23T00:00:00Z",
        ended_at: "2026-06-23T00:01:00Z"
      }]
    });

    const button = await waitForButton("Git diff");
    act(() => {
      button.click();
    });

    await waitForText("backend/app.py");
    await waitForText("-old");
    expect(apiMocks.fetchGitRuns).not.toHaveBeenCalled();
  });

  it("opens saved todo diff when the archived worktree no longer has a top-level window id", async () => {
    renderSummary({
      worktree_root: "/repo/.worktrees/feature",
      branch: "agent/feature",
      end_head: "feature",
      merge_status: "merged",
      commits: [{ sha: "feature", short_sha: "feature", subject: "Keep todo diff" }],
      diff_runs: [{
        id: "run-1",
        virtual_window_id: "archived-window-1",
        command_sequence: "12",
        agent_provider: "codex",
        status: "completed",
        run_type: "agent",
        worktree_root: "/repo/.worktrees/feature",
        main_repo_root: "/repo",
        discovery_method: "marker",
        start_snapshot_json: null,
        end_snapshot_json: null,
        session_diff_json: {
          commits: [{
            sha: "feature",
            short_sha: "feature",
            subject: "Keep todo diff",
            files: [{
              path: "backend/app.py",
              status: "modified",
              additions: 1,
              deletions: 1,
              patch: "@@ -1 +1 @@\n-old\n+new\n"
            }]
          }]
        },
        pending_commit: false,
        resolved_at: null,
        started_at: "2026-06-23T00:00:00Z",
        ended_at: "2026-06-23T00:01:00Z"
      }]
    });

    const button = await waitForButton("Git diff");
    act(() => {
      button.click();
    });

    await waitForText("backend/app.py");
    await waitForText("-old");
    expect(apiMocks.fetchGitRuns).not.toHaveBeenCalled();
  });
});
