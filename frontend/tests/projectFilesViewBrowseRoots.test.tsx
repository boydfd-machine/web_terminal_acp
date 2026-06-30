import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, type ReactElement } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ProjectBrowseRootSelector } from "../src/components/ProjectBrowseRootSelector";
import {
  buildProjectBrowseRootOptions,
  preferredFilesProjectContext
} from "../src/projectBrowseRoots";

globalThis.IS_REACT_ACT_ENVIRONMENT = true;

let root: Root | null = null;
let container: HTMLDivElement | null = null;
let queryClient: QueryClient | null = null;

async function renderWithQueryClient(element: ReactElement): Promise<void> {
  container = document.createElement("div");
  document.body.appendChild(container);
  root = createRoot(container);
  queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false }
    }
  });

  await act(async () => {
    root?.render(
      <QueryClientProvider client={queryClient as QueryClient}>
        {element}
      </QueryClientProvider>
    );
  });
}

async function clickButtonWithText(text: string): Promise<void> {
  const button = Array.from(container?.querySelectorAll("button") ?? []).find(
    (candidate) => candidate.textContent?.trim() === text
  );
  if (!(button instanceof HTMLButtonElement)) {
    throw new Error(`button not found: ${text}`);
  }
  await act(async () => {
    button.click();
  });
}

async function clickButtonContainingText(text: string): Promise<void> {
  const button = Array.from(container?.querySelectorAll("button") ?? []).find(
    (candidate) => candidate.textContent?.includes(text)
  );
  if (!(button instanceof HTMLButtonElement)) {
    throw new Error(`button not found: ${text}`);
  }
  await act(async () => {
    button.click();
  });
}

function setInputValue(input: HTMLInputElement, value: string): void {
  const descriptor = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value");
  act(() => {
    descriptor?.set?.call(input, value);
    input.dispatchEvent(new Event("input", { bubbles: true }));
  });
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
});

describe("project browse roots", () => {
  it("builds worktree options with branch labels and defaults files mode to the selected terminal worktree", () => {
    const options = buildProjectBrowseRootOptions({
      browseRoots: [
        {
          kind: "main",
          project_path: "/workspace/project",
          browse_root: null,
          pending_commit: false
        },
        {
          kind: "worktree",
          project_path: "/workspace/project",
          browse_root: "/workspace/project/.worktrees/feature",
          branch: "feature/files",
          pending_commit: true
        }
      ],
      projectPath: "/workspace/project"
    });

    expect(options.map((option) => option.label)).toEqual([
      "no-worktree [main directory]",
      "feature/files"
    ]);
    expect(options[1]).toMatchObject({
      browseRoot: "/workspace/project/.worktrees/feature",
      pendingCommit: true
    });
    expect(preferredFilesProjectContext({
      git_worktree: {
        main_repo_root: "/workspace/project",
        worktree_root: "/workspace/project/.worktrees/feature",
        branch: "feature/files",
        pending_commit: true
      }
    }, "/fallback")).toEqual({
      projectPath: "/workspace/project",
      browseRoot: "/workspace/project/.worktrees/feature"
    });
  });

  it("filters worktree options and selects a branch from the toolbar dropdown", async () => {
    const onSelect = vi.fn();
    const options = buildProjectBrowseRootOptions({
      browseRoots: [
        {
          kind: "main",
          project_path: "/workspace/project",
          browse_root: null,
          pending_commit: false
        },
        {
          kind: "worktree",
          project_path: "/workspace/project",
          browse_root: "/workspace/project/.worktrees/feature",
          branch: "feature/files",
          pending_commit: true
        }
      ],
      projectPath: "/workspace/project"
    });

    await renderWithQueryClient(
      <ProjectBrowseRootSelector
        options={options}
        selectedBrowseRoot={null}
        selectedProjectPath="/workspace/project"
        onSelect={onSelect}
      />
    );

    await clickButtonWithText("no-worktree [main directory]");
    const searchInput = container?.querySelector("input[type='search']");
    expect(searchInput).toBeInstanceOf(HTMLInputElement);
    setInputValue(searchInput as HTMLInputElement, "feature");
    const optionList = container?.querySelector(".project-browse-root-options");
    expect(optionList?.textContent).toContain("feature/files");
    expect(optionList?.textContent).not.toContain("no-worktree [main directory]");
    await clickButtonContainingText("feature/files");

    expect(onSelect).toHaveBeenCalledWith(expect.objectContaining({
      browseRoot: "/workspace/project/.worktrees/feature",
      label: "feature/files"
    }));
  });
});
