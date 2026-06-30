import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, describe, expect, it, vi } from "vitest";

import { GitRunViewer } from "../src/components/GitRunViewer";
import { I18nProvider } from "../src/i18n";
import type { GitWorktreeRunList } from "../src/types";

const apiMocks = vi.hoisted(() => ({
  fetchGitRuns: vi.fn()
}));

vi.mock("../src/api", () => apiMocks);

globalThis.IS_REACT_ACT_ENVIRONMENT = true;

let root: Root | null = null;
let container: HTMLDivElement | null = null;
let queryClient: QueryClient | null = null;

function gitRunsFixture(): GitWorktreeRunList {
  return {
    supported: true,
    total: 1,
    limit: 50,
    offset: 0,
    runs: [{
      id: "run-1",
      virtual_window_id: "window-1",
      command_sequence: "worktree:1",
      agent_provider: null,
      status: "completed",
      run_type: "tracking",
      worktree_root: "/repo/.worktrees/window-1",
      main_repo_root: "/repo",
      discovery_method: "osc",
      start_snapshot_json: null,
      end_snapshot_json: null,
      session_diff_json: {
        has_changes: true,
        head_moved: true,
        start_head: "5fdb169",
        end_head: "1aacef3",
        commits: [{
          sha: "1aacef3356e0f90d5599dd53877686e1c19838f0",
          short_sha: "1aacef3",
          subject: "feat: replace robot favicon with a rabbit icon",
          authored_at: "2026-06-29T06:22:26Z",
          files: [
            {
              path: "frontend/index.html",
              status: "modified",
              additions: 1,
              deletions: 1,
              patch: "diff --git a/frontend/index.html b/frontend/index.html\n@@ -3,7 +3,7 @@\n-    <link rel=\"icon\" type=\"image/svg+xml\" href=\"/robot.svg\" />\n+    <link rel=\"icon\" type=\"image/svg+xml\" href=\"/rabbit.svg\" />"
            },
            {
              path: "frontend/public/rabbit.svg",
              status: "added",
              additions: 21,
              deletions: 0,
              patch: "diff --git a/frontend/public/rabbit.svg b/frontend/public/rabbit.svg\n@@ -0,0 +1,2 @@\n+<svg role=\"img\">\n+</svg>"
            }
          ]
        }]
      },
      pending_commit: false,
      resolved_at: null,
      started_at: "2026-06-29T06:19:58Z",
      ended_at: "2026-06-29T07:10:34Z"
    }]
  };
}

async function renderGitRunViewer(): Promise<void> {
  apiMocks.fetchGitRuns.mockResolvedValue(gitRunsFixture());
  container = document.createElement("div");
  document.body.appendChild(container);
  queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false }
    }
  });
  root = createRoot(container);
  await act(async () => {
    root?.render(
      <QueryClientProvider client={queryClient as QueryClient}>
        <I18nProvider initialLocale="en-US">
          <GitRunViewer clientId="client-1" windowId="window-1" />
        </I18nProvider>
      </QueryClientProvider>
    );
  });
}

async function waitForText(text: string): Promise<void> {
  for (let attempt = 0; attempt < 20; attempt += 1) {
    if (document.body.textContent?.includes(text)) {
      return;
    }
    await act(async () => {
      await new Promise((resolve) => setTimeout(resolve, 0));
    });
  }
  throw new Error(`Timed out waiting for text: ${text}`);
}

async function waitForButtonText(text: string): Promise<HTMLButtonElement> {
  for (let attempt = 0; attempt < 20; attempt += 1) {
    const button = Array.from(document.body.querySelectorAll("button")).find((candidate) =>
      candidate.textContent?.includes(text)
    );
    if (button instanceof HTMLButtonElement) {
      return button;
    }
    await act(async () => {
      await new Promise((resolve) => setTimeout(resolve, 0));
    });
  }
  throw new Error(`Timed out waiting for button: ${text}`);
}

afterEach(() => {
  act(() => {
    root?.unmount();
  });
  container?.remove();
  queryClient?.clear();
  root = null;
  container = null;
  queryClient = null;
  vi.clearAllMocks();
});

describe("GitRunViewer", () => {
  it("shows the first captured file patch directly in the Git tab", async () => {
    await renderGitRunViewer();

    await waitForText("frontend/index.html");
    await waitForText("href=\"/robot.svg\"");
    await waitForText("href=\"/rabbit.svg\"");
    expect(document.body.querySelector(".git-diff-modal")).toBeNull();
  });

  it("switches the inline patch when a changed file is selected", async () => {
    await renderGitRunViewer();
    const button = await waitForButtonText("rabbit.svg");

    act(() => {
      button.click();
    });

    await waitForText("frontend/public/rabbit.svg");
    await waitForText("<svg role=\"img\">");
  });
});
