import type { SwitcherNode } from "../terminalGrouping";
import type { TranslateFn } from "../i18n";
import type { TerminalGroupingMode } from "../userPreferences";
import type { GlobalTerminalRecent, ProjectSummary, TerminalRecent, TreeFolder, TreeWindow } from "../types";

export const SWITCHER_VISIBLE_PAGE_SIZE = 8;
export const RECENT_PROJECT_ALL_KEY = "all";
export const RECENT_PROJECT_UNASSIGNED_KEY = "unassigned";

export const AGENT_TAG_LABELS: Record<string, string> = {
  codex: "codex",
  claude_code: "claude code",
  cursor_cli: "cursor"
};

export function terminalGroupingDescription(mode: TerminalGroupingMode, t: TranslateFn): string {
  if (mode === "topic") {
    return t("terminal.group.topic");
  }
  if (mode === "time-topic") {
    return t("terminal.group.timeTopic");
  }
  if (mode === "project-time-topic") {
    return t("terminal.group.projectTimeTopic");
  }
  return t("terminal.group.projectTopic");
}

export type TerminalSwitcherMode = "recent" | "tree";
export type TerminalSwitcherRecentScope = "client" | "global" | "related";

export type TerminalEntry = {
  window: TreeWindow;
  topicPath: string;
};

export type TerminalMeta = {
  agentLabel: string;
  projectLabel: string | null;
  projectPath: string | null;
  timeValue: string;
  timeLabel: string;
  timeTitle: string;
};

export type RecentProjectTab = {
  key: string;
  label: string;
  projectPath: string | null;
  count: number;
};

export type VisibleTreeItem = {
  node: SwitcherNode;
  parentKey: string | null;
};

export function recentItemKey(windowId: string): string {
  return `recent:${windowId}`;
}

export function recentProjectKey(projectPath: string | null): string {
  return projectPath === null ? RECENT_PROJECT_UNASSIGNED_KEY : projectPath;
}

export function scopedRecentItemKey(item: TerminalRecent | GlobalTerminalRecent, globalScope: boolean): string {
  if (globalScope) {
    return `recent:${(item as GlobalTerminalRecent).client_id}:${item.window_id}`;
  }
  return recentItemKey(item.window_id);
}

export function isGlobalTerminalRecent(item: TerminalRecent | GlobalTerminalRecent): item is GlobalTerminalRecent {
  return "client_id" in item;
}

export function relatedRecentItemKey(window: TreeWindow): string {
  return `related:${window.id}`;
}

export function collectGroupKeys(nodes: SwitcherNode[]): string[] {
  const keys: string[] = [];

  const visit = (node: SwitcherNode) => {
    if (node.type === "window") {
      return;
    }

    keys.push(node.key);
    for (const child of node.children) {
      visit(child);
    }
  };

  for (const node of nodes) {
    visit(node);
  }

  return keys;
}

export function flattenVisibleTreeItems(nodes: SwitcherNode[], expandedKeys: Set<string>): VisibleTreeItem[] {
  const items: VisibleTreeItem[] = [];

  const visit = (node: SwitcherNode, parentKey: string | null) => {
    items.push({ node, parentKey });
    if (node.type === "window" || !expandedKeys.has(node.key)) {
      return;
    }

    for (const child of node.children) {
      visit(child, node.key);
    }
  };

  for (const node of nodes) {
    visit(node, null);
  }

  return items;
}

export function findWindowInTree(folders: TreeFolder[], windowId: string): TreeWindow | null {
  for (const folder of folders) {
    const window = folder.windows.find((candidate) => candidate.id === windowId);
    if (window) {
      return window;
    }

    const childWindow = findWindowInTree(folder.folders, windowId);
    if (childWindow) {
      return childWindow;
    }
  }

  return null;
}

export function agentLabelFromRuntimeTags(runtimeTags: string[] | null | undefined, t: TranslateFn): string {
  for (const tag of runtimeTags ?? []) {
    const normalized = tag.trim().toLocaleLowerCase();
    const label = AGENT_TAG_LABELS[normalized];
    if (label) {
      return label;
    }
  }

  return t("terminal.group.none");
}

export function projectPathFromRuntimeTags(runtimeTags: string[] | null | undefined): string | null {
  for (const tag of runtimeTags ?? []) {
    const normalized = tag.trim();
    if (normalized.startsWith("/")) {
      return normalized;
    }
  }

  return null;
}

export function projectFallbackLabel(projectPath: string): string | null {
  const segments = projectPath.split("/").filter(Boolean);
  return segments[segments.length - 1] ?? null;
}

export function projectTabLabel(projectPath: string | null, projectSummaryLookup: Map<string, ProjectSummary>, t: TranslateFn): string {
  if (projectPath === null) {
    return t("terminal.switcher.noProject");
  }

  const summaryLabel = projectSummaryLookup.get(projectPath)?.display_name?.trim();
  return summaryLabel || projectFallbackLabel(projectPath) || projectPath;
}

export function formatTerminalTime(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }

  return date.toLocaleString(undefined, {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit"
  });
}

export function formatTerminalTimeTitle(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }

  return date.toLocaleString();
}

export function relatedTerminalActivityTime(window: TreeWindow): string {
  return window.work_status.last_activity_at
    ?? window.last_agent_task_status_at
    ?? window.last_agent_task_completed_at
    ?? window.created_at;
}

export function collectWindowProjects(folders: TreeFolder[]): Map<string, string | null> {
  const lookup = new Map<string, string | null>();

  const visit = (folder: TreeFolder) => {
    for (const window of folder.windows) {
      lookup.set(window.id, projectPathFromRuntimeTags(window.runtime_tags));
    }

    for (const child of folder.folders) {
      visit(child);
    }
  };

  for (const folder of folders) {
    visit(folder);
  }

  return lookup;
}

export function terminalMeta(
  window: Pick<TreeWindow, "created_at" | "runtime_tags">,
  projectSummaryLookup: Map<string, ProjectSummary>,
  t: TranslateFn
): TerminalMeta {
  const projectPath = projectPathFromRuntimeTags(window.runtime_tags);
  const summary = projectPath ? projectSummaryLookup.get(projectPath) : undefined;
  const displayName = summary?.display_name?.trim() || null;

  return {
    agentLabel: agentLabelFromRuntimeTags(window.runtime_tags, t),
    projectLabel: projectPath === null ? null : displayName ?? projectFallbackLabel(projectPath),
    projectPath,
    timeValue: window.created_at,
    timeLabel: formatTerminalTime(window.created_at),
    timeTitle: formatTerminalTimeTitle(window.created_at)
  };
}
