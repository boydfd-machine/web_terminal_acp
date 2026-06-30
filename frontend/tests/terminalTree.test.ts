import { describe, expect, it } from "vitest";

import {
  DEFAULT_WORK_STATUS,
  firstProjectPath,
  mergeTreeWithActivity,
  nextRelatedTerminalId,
  projectListContains,
  projectPathForWindow,
  relatedTerminalRecentWindows,
  relatedTerminalWindows,
  windowActivityMap
} from "../src/terminalTree";
import type { TreeFolderCore } from "../src/types";

const sampleTree: TreeFolderCore[] = [
  {
    id: "folder-1",
    name: "Project",
    path: "/project",
    folders: [],
    windows: [
      {
        id: "window-1",
        title: "Terminal",
        status: "ACTIVE",
        created_at: "2026-05-24T00:00:00Z"
      }
    ]
  }
];

describe("terminalTree", () => {
  it("merges activity into tree windows", () => {
    const gitWorktree = {
      worktree_root: "/repo/.worktrees/feature",
      main_repo_root: "/repo",
      branch: "agent/feature",
      pending_commit: true
    };
    const activity = windowActivityMap({
      windows: [
        {
          window_id: "window-1",
          work_status: { state: "WORKING", label: "Working", color: "orange" },
          runtime_tags: ["/workspace/project"],
          todo_title: "Fix dispatch summary",
          last_agent_task_completed_at: "2026-05-24T01:00:00Z",
          last_agent_task_status: "FINISHED",
          last_agent_task_status_at: "2026-05-24T01:00:00Z",
          git_worktree: gitWorktree,
          parent_window_id: "root-window",
          root_window_id: "root-window",
          derived_mode: "linked"
        }
      ]
    });

    const merged = mergeTreeWithActivity(sampleTree, activity);
    expect(merged?.[0]?.windows[0]?.work_status.state).toBe("WORKING");
    expect(merged?.[0]?.windows[0]?.runtime_tags).toEqual(["/workspace/project"]);
    expect(merged?.[0]?.windows[0]?.todo_title).toBe("Fix dispatch summary");
    expect(merged?.[0]?.windows[0]?.last_agent_task_completed_at).toBe("2026-05-24T01:00:00Z");
    expect(merged?.[0]?.windows[0]?.last_agent_task_status).toBe("FINISHED");
    expect(merged?.[0]?.windows[0]?.last_agent_task_status_at).toBe("2026-05-24T01:00:00Z");
    expect(merged?.[0]?.windows[0]?.git_worktree).toEqual(gitWorktree);
    expect(merged?.[0]?.windows[0]?.parent_window_id).toBe("root-window");
    expect(merged?.[0]?.windows[0]?.root_window_id).toBe("root-window");
    expect(merged?.[0]?.windows[0]?.derived_mode).toBe("linked");
  });

  it("uses defaults when activity is missing", () => {
    const merged = mergeTreeWithActivity(sampleTree, new Map());
    expect(merged?.[0]?.windows[0]?.work_status).toEqual(DEFAULT_WORK_STATUS);
    expect(merged?.[0]?.windows[0]?.runtime_tags).toEqual([]);
    expect(merged?.[0]?.windows[0]?.git_worktree).toBeNull();
  });

  it("resolves the selected project from runtime tags before cwd", () => {
    expect(projectPathForWindow({
      cwd: "/tmp/fallback",
      runtime_tags: ["codex", "/workspace/project"]
    })).toBe("/workspace/project");
    expect(projectPathForWindow({ cwd: "/tmp/fallback", runtime_tags: ["codex"] })).toBe("/tmp/fallback");
    expect(projectPathForWindow(null)).toBeNull();
  });

  it("handles terminal project lists", () => {
    const projects = [
      { project_path: "/workspace/a", window_count: 2 },
      { project_path: "/workspace/b", window_count: 1 }
    ];

    expect(firstProjectPath(projects)).toBe("/workspace/a");
    expect(projectListContains(projects, "/workspace/b")).toBe(true);
    expect(projectListContains(projects, "/workspace/missing")).toBe(false);
  });

  it("cycles through related terminal groups", () => {
    const tree = mergeTreeWithActivity([
      {
        id: "folder-1",
        name: "Project",
        path: "/project",
        folders: [],
        windows: [
          {
            id: "root",
            title: "Root",
            status: "ACTIVE",
            created_at: "2026-05-24T00:00:00Z"
          },
          {
            id: "child-2",
            title: "Child 2",
            status: "ACTIVE",
            created_at: "2026-05-24T02:00:00Z",
            parent_window_id: "root",
            root_window_id: "root",
            derived_mode: "linked"
          },
          {
            id: "child-1",
            title: "Child 1",
            status: "ACTIVE",
            created_at: "2026-05-24T01:00:00Z",
            parent_window_id: "root",
            root_window_id: "root",
            derived_mode: "linked"
          },
          {
            id: "other",
            title: "Other",
            status: "ACTIVE",
            created_at: "2026-05-24T03:00:00Z"
          }
        ]
      }
    ], new Map([
      [
        "child-1",
        {
          work_status: DEFAULT_WORK_STATUS,
          runtime_tags: [],
          todo_title: "Fix checkout flow"
        }
      ]
    ]));

    expect(relatedTerminalWindows(tree, "child-1").map((window) => window.id)).toEqual([
      "root",
      "child-2",
      "child-1"
    ]);
    expect(nextRelatedTerminalId(tree, "root")).toBe("child-1");
    expect(nextRelatedTerminalId(tree, "child-1")).toBe("child-2");
    expect(nextRelatedTerminalId(tree, "child-2")).toBe("root");
    expect(nextRelatedTerminalId(tree, "other")).toBeNull();
    expect(relatedTerminalRecentWindows(tree, "root").map((window) => window.id)).toEqual([
      "child-2",
      "child-1",
      "root"
    ]);
    expect(relatedTerminalRecentWindows(tree, "root", "Child 1").map((window) => window.id)).toEqual(["child-1"]);
    expect(relatedTerminalRecentWindows(tree, "root", "checkout").map((window) => window.id)).toEqual(["child-1"]);
  });
});
