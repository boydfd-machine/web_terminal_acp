import { matchesSwitcherWindow } from "./terminalGrouping";
import type { TerminalProject, TreeFolder, TreeFolderCore, TreeWindow, WindowActivity, WorkStatus } from "./types";

export const DEFAULT_WORK_STATUS: WorkStatus = {
  state: "LONG_IDLE",
  label: "长时间没有工作了",
  color: "gray"
};

export const DEFAULT_WINDOW_ACTIVITY: WindowActivity = {
  work_status: DEFAULT_WORK_STATUS,
  runtime_tags: []
};

export function windowActivityMap(
  activity: { windows: WindowActivityRecord[] } | undefined
): Map<string, WindowActivity> {
  const map = new Map<string, WindowActivity>();
  if (!activity) {
    return map;
  }

  for (const item of activity.windows) {
    map.set(item.window_id, {
      work_status: item.work_status,
      runtime_tags: item.runtime_tags,
      todo_title: item.todo_title ?? null,
      last_agent_task_completed_at: item.last_agent_task_completed_at ?? null,
      last_agent_task_status: item.last_agent_task_status ?? null,
      last_agent_task_status_at: item.last_agent_task_status_at ?? null,
      git_worktree: item.git_worktree ?? null,
      parent_window_id: item.parent_window_id ?? null,
      root_window_id: item.root_window_id ?? null,
      derived_mode: item.derived_mode ?? null
    });
  }
  return map;
}

export type WindowActivityRecord = {
  window_id: string;
  work_status: WorkStatus;
  runtime_tags: string[];
  todo_title?: string | null;
  last_agent_task_completed_at?: string | null;
  last_agent_task_status?: "FINISHED" | "ABORTED" | "FAILED" | null;
  last_agent_task_status_at?: string | null;
  git_worktree?: import("./types").GitWorktreeActivity | null;
  parent_window_id?: string | null;
  root_window_id?: string | null;
  derived_mode?: string | null;
};

export function mergeTreeWithActivity(
  folders: TreeFolderCore[] | undefined,
  activityByWindowId: Map<string, WindowActivity>
): TreeFolder[] | undefined {
  if (!folders) {
    return undefined;
  }

  const mergeWindow = (window: TreeFolderCore["windows"][number]): TreeWindow => {
    const activity = activityByWindowId.get(window.id) ?? DEFAULT_WINDOW_ACTIVITY;
    return {
      ...window,
      work_status: activity.work_status,
      runtime_tags: activity.runtime_tags,
      todo_title: activity.todo_title ?? null,
      last_agent_task_completed_at: activity.last_agent_task_completed_at ?? null,
      last_agent_task_status: activity.last_agent_task_status ?? null,
      last_agent_task_status_at: activity.last_agent_task_status_at ?? null,
      git_worktree: activity.git_worktree ?? null,
      parent_window_id: window.parent_window_id ?? activity.parent_window_id ?? null,
      root_window_id: window.root_window_id ?? activity.root_window_id ?? null,
      derived_mode: window.derived_mode ?? activity.derived_mode ?? null
    };
  };

  const mergeFolder = (folder: TreeFolderCore): TreeFolder => ({
    ...folder,
    folders: folder.folders.map(mergeFolder),
    windows: folder.windows.map(mergeWindow)
  });

  return folders.map(mergeFolder);
}

export function activityHasWorkingTerminal(
  activity: { windows: WindowActivityRecord[] } | undefined
): boolean {
  if (!activity) {
    return false;
  }

  return activity.windows.some((window) => window.work_status.state === "WORKING");
}

export function projectPathFromRuntimeTags(runtimeTags: string[] | null | undefined): string | null {
  for (const tag of runtimeTags ?? []) {
    if (tag.startsWith("/")) {
      return tag;
    }
  }

  return null;
}

export function projectPathForWindow(window: {
  cwd?: string | null;
  runtime_tags?: string[] | null;
} | null | undefined): string | null {
  if (!window) {
    return null;
  }

  return projectPathFromRuntimeTags(window.runtime_tags) ?? window.cwd ?? null;
}

export function firstProjectPath(projects: TerminalProject[] | undefined): string | null {
  return projects?.[0]?.project_path ?? null;
}

export function projectListContains(projects: TerminalProject[] | undefined, projectPath: string | null): boolean {
  return projectPath !== null && (projects ?? []).some((project) => project.project_path === projectPath);
}

export function relatedTerminalGroupKey(window: {
  id: string;
  parent_window_id?: string | null;
  root_window_id?: string | null;
  derived_mode?: string | null;
} | null | undefined): string | null {
  if (!window) {
    return null;
  }
  return window.root_window_id ?? window.parent_window_id ?? (window.derived_mode === "linked" ? window.id : null);
}

export function flattenTreeWindows(folders: TreeFolder[] | undefined): TreeFolder["windows"][number][] {
  if (!folders) {
    return [];
  }

  const windows: TreeFolder["windows"][number][] = [];
  const visit = (folder: TreeFolder) => {
    windows.push(...folder.windows);
    for (const child of folder.folders) {
      visit(child);
    }
  };
  for (const folder of folders) {
    visit(folder);
  }
  return windows;
}

export function relatedTerminalWindows(
  folders: TreeFolder[] | undefined,
  selectedWindowId: string | null
): TreeFolder["windows"][number][] {
  const windows = flattenTreeWindows(folders);
  const selected = windows.find((window) => window.id === selectedWindowId);
  let groupKey = relatedTerminalGroupKey(selected);
  if (groupKey === null && selectedWindowId !== null) {
    const hasChildren = windows.some((window) => relatedTerminalGroupKey(window) === selectedWindowId);
    groupKey = hasChildren ? selectedWindowId : null;
  }
  if (groupKey === null) {
    return [];
  }
  return windows.filter((window) => {
    if (window.id === groupKey) {
      return true;
    }
    return relatedTerminalGroupKey(window) === groupKey;
  });
}

function relatedTerminalActivityTime(window: TreeWindow): string {
  return window.work_status.last_activity_at
    ?? window.last_agent_task_status_at
    ?? window.last_agent_task_completed_at
    ?? window.created_at;
}

export function relatedTerminalRecentWindows(
  folders: TreeFolder[] | undefined,
  selectedWindowId: string | null,
  query = ""
): TreeWindow[] {
  const windows = relatedTerminalWindows(folders, selectedWindowId);
  const normalizedQuery = query.trim().toLocaleLowerCase();
  const filtered = normalizedQuery.length === 0
    ? windows
    : windows.filter((window) => matchesSwitcherWindow(window, "", normalizedQuery));

  return filtered
    .slice()
    .sort((left, right) => {
      const leftTime = relatedTerminalActivityTime(left);
      const rightTime = relatedTerminalActivityTime(right);
      if (leftTime === rightTime) {
        return left.title.localeCompare(right.title) || left.id.localeCompare(right.id);
      }
      return rightTime.localeCompare(leftTime);
    });
}

export function nextRelatedTerminalId(
  folders: TreeFolder[] | undefined,
  selectedWindowId: string | null
): string | null {
  const group = relatedTerminalWindows(folders, selectedWindowId)
    .slice()
    .sort((left, right) => {
      if (left.created_at === right.created_at) {
        return left.id.localeCompare(right.id);
      }
      return left.created_at.localeCompare(right.created_at);
    });
  if (group.length < 2 || selectedWindowId === null) {
    return null;
  }
  const index = group.findIndex((window) => window.id === selectedWindowId);
  if (index === -1) {
    return group[0]?.id ?? null;
  }
  return group[(index + 1) % group.length]?.id ?? null;
}
