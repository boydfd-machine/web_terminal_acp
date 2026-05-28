import type { ProjectSummary, TreeFolder, TreeWindow } from "./types";

export type TerminalGroupingMode = "project-topic" | "topic" | "time-topic" | "project-time-topic";

export type SwitcherWindowNode = {
  type: "window";
  key: string;
  window: TreeWindow;
  topicPath: string;
};

export type SwitcherGroupNode = {
  type: "group";
  key: string;
  label: string;
  count: number;
  children: SwitcherNode[];
  projectPath?: string;
  topicPath?: string;
};

export type SwitcherNode = SwitcherGroupNode | SwitcherWindowNode;

export type ProjectSummaryLookup = Map<string, ProjectSummary>;

type TreeWindowEntry = {
  window: TreeWindow;
  topicPath: string;
};

type TimeParts = {
  month: string;
  day: string;
};

export const UNASSIGNED_PROJECT_PATH = "/未指定";

export function projectPathFromRuntimeTags(runtimeTags: string[]): string {
  for (const tag of runtimeTags) {
    if (tag.startsWith("/")) {
      return tag;
    }
  }

  return UNASSIGNED_PROJECT_PATH;
}

export function projectGroupLabel(projectPath: string, summaries: ProjectSummaryLookup): string {
  const summary = summaries.get(projectPath);
  if (summary?.display_name) {
    return summary.display_name;
  }

  return projectPath;
}

export function collectProjectPaths(folders: TreeFolder[]): string[] {
  const paths = new Set<string>();

  const visit = (folder: TreeFolder) => {
    for (const window of folder.windows) {
      paths.add(projectPathFromRuntimeTags(window.runtime_tags));
    }

    for (const child of folder.folders) {
      visit(child);
    }
  };

  for (const folder of folders) {
    visit(folder);
  }

  return Array.from(paths).sort((left, right) => left.localeCompare(right));
}

export function isCreatableProjectPath(projectPath: string): boolean {
  return projectPath.startsWith("/") && projectPath !== UNASSIGNED_PROJECT_PATH;
}

export function collectCreatableProjectPaths(folders: TreeFolder[]): string[] {
  return collectProjectPaths(folders).filter(isCreatableProjectPath);
}

export function terminalGroupingModeHasProjectRoot(mode: TerminalGroupingMode): boolean {
  return mode === "project-topic" || mode === "project-time-topic";
}

export function buildTerminalSwitcherTree(
  folders: TreeFolder[],
  mode: TerminalGroupingMode,
  summaries: ProjectSummaryLookup,
  query: string
): SwitcherNode[] {
  if (mode === "topic") {
    return buildTopicSwitcherTree(folders, query);
  }

  if (mode === "time-topic") {
    return buildTimeTopicSwitcherTree(folders, query);
  }

  if (mode === "project-time-topic") {
    return buildProjectTimeTopicSwitcherTree(folders, summaries, query);
  }

  return buildProjectTopicSwitcherTree(folders, summaries, query);
}

export function buildTopicSwitcherTree(folders: TreeFolder[], query: string): SwitcherNode[] {
  const normalizedQuery = query.trim().toLocaleLowerCase();

  const convert = (folder: TreeFolder): SwitcherGroupNode | null => {
    const childGroups = folder.folders
      .map((child: TreeFolder) => convert(child))
      .filter((node): node is SwitcherGroupNode => node !== null);
    const windowNodes = folder.windows
      .filter((window) => matchesWindow(window, folder.path, normalizedQuery))
      .map((window): SwitcherWindowNode => ({
        type: "window",
        key: `window:${window.id}`,
        window,
        topicPath: folder.path
      }));
    const children: SwitcherNode[] = [...childGroups, ...windowNodes];
    const count = countWindows(children);

    if (count === 0) {
      return null;
    }

    return {
      type: "group",
      key: `topic:${folder.path}`,
      label: folder.name,
      count,
      topicPath: folder.path,
      children
    };
  };

  return folders.map(convert).filter((node): node is SwitcherGroupNode => node !== null);
}

export function buildProjectTopicSwitcherTree(
  folders: TreeFolder[],
  summaries: ProjectSummaryLookup,
  query: string
): SwitcherNode[] {
  const projectPaths = collectProjectPaths(folders);

  const nodes: SwitcherGroupNode[] = [];
  for (const projectPath of projectPaths) {
    const children = buildTopicSwitcherTreeForProject(folders, projectPath, query);
    const count = countWindows(children);
    if (count === 0) {
      continue;
    }

    nodes.push({
      type: "group",
      key: `project:${projectPath}`,
      label: projectGroupLabel(projectPath, summaries),
      projectPath,
      count,
      children
    });
  }

  return nodes;
}

export function buildTimeTopicSwitcherTree(folders: TreeFolder[], query: string): SwitcherNode[] {
  return buildTimeTopicSwitcherTreeForFilter(folders, query, "time-topic", () => true);
}

export function buildProjectTimeTopicSwitcherTree(
  folders: TreeFolder[],
  summaries: ProjectSummaryLookup,
  query: string
): SwitcherNode[] {
  const projectPaths = collectProjectPaths(folders);

  const nodes: SwitcherGroupNode[] = [];
  for (const projectPath of projectPaths) {
    const children = buildTimeTopicSwitcherTreeForFilter(
      folders,
      query,
      `project-time-topic:${projectPath}`,
      (window) => projectPathFromRuntimeTags(window.runtime_tags ?? []) === projectPath
    );
    const count = countWindows(children);
    if (count === 0) {
      continue;
    }

    nodes.push({
      type: "group",
      key: `project-time-topic:${projectPath}`,
      label: projectGroupLabel(projectPath, summaries),
      projectPath,
      count,
      children
    });
  }

  return nodes;
}

function buildTopicSwitcherTreeForProject(
  folders: TreeFolder[],
  projectPath: string,
  query: string
): SwitcherNode[] {
  const normalizedQuery = query.trim().toLocaleLowerCase();

  const convert = (folder: TreeFolder): SwitcherGroupNode | null => {
    const childGroups = folder.folders
      .map((child: TreeFolder) => convert(child))
      .filter((node): node is SwitcherGroupNode => node !== null);
    const windowNodes = folder.windows
      .filter((window) => projectPathFromRuntimeTags(window.runtime_tags ?? []) === projectPath)
      .filter((window) => matchesWindow(window, folder.path, normalizedQuery))
      .map((window): SwitcherWindowNode => ({
        type: "window",
        key: `window:${window.id}`,
        window,
        topicPath: folder.path
      }));
    const children: SwitcherNode[] = [...childGroups, ...windowNodes];
    const count = countWindows(children);

    if (count === 0) {
      return null;
    }

    return {
      type: "group",
      key: `project-topic:${projectPath}:topic:${folder.path}`,
      label: folder.name,
      count,
      projectPath,
      topicPath: folder.path,
      children
    };
  };

  return folders.map(convert).filter((node): node is SwitcherGroupNode => node !== null);
}

function buildTimeTopicSwitcherTreeForFilter(
  folders: TreeFolder[],
  query: string,
  keyPrefix: string,
  includeWindow: (window: TreeWindow) => boolean
): SwitcherNode[] {
  const normalizedQuery = query.trim().toLocaleLowerCase();
  const entries = flattenTreeWindows(folders)
    .filter((entry) => includeWindow(entry.window))
    .filter((entry) => matchesWindow(entry.window, entry.topicPath, normalizedQuery));
  const byMonth = new Map<string, Map<string, TreeWindowEntry[]>>();

  for (const entry of entries) {
    const { month, day } = timeParts(entry.window.created_at);
    const monthGroup = byMonth.get(month) ?? new Map<string, TreeWindowEntry[]>();
    const dayEntries = monthGroup.get(day) ?? [];
    dayEntries.push(entry);
    monthGroup.set(day, dayEntries);
    byMonth.set(month, monthGroup);
  }

  return sortedMapEntries(byMonth).map(([month, days]) => ({
    type: "group",
    key: `${keyPrefix}:time:${month}`,
    label: month,
    count: countEntriesInDayMap(days),
    children: sortedMapEntries(days).map(([day, dayEntries]) => ({
      type: "group",
      key: `${keyPrefix}:time:${month}:${day}`,
      label: day,
      count: dayEntries.length,
      children: buildTopicTreeForEntryIds(
        folders,
        new Set(dayEntries.map((entry) => entry.window.id)),
        `${keyPrefix}:time:${month}:${day}`
      )
    }))
  }));
}

function buildTopicTreeForEntryIds(
  folders: TreeFolder[],
  allowedWindowIds: Set<string>,
  keyPrefix: string
): SwitcherNode[] {
  const convert = (folder: TreeFolder): SwitcherGroupNode | null => {
    const childGroups = folder.folders
      .map((child: TreeFolder) => convert(child))
      .filter((node): node is SwitcherGroupNode => node !== null);
    const windowNodes = folder.windows
      .filter((window) => allowedWindowIds.has(window.id))
      .map((window): SwitcherWindowNode => ({
        type: "window",
        key: `${keyPrefix}:window:${window.id}`,
        window,
        topicPath: folder.path
      }));
    const children: SwitcherNode[] = [...childGroups, ...windowNodes];
    const count = countWindows(children);

    if (count === 0) {
      return null;
    }

    return {
      type: "group",
      key: `${keyPrefix}:topic:${folder.path}`,
      label: folder.name,
      count,
      topicPath: folder.path,
      children
    };
  };

  return folders.map(convert).filter((node): node is SwitcherGroupNode => node !== null);
}

function flattenTreeWindows(folders: TreeFolder[]): TreeWindowEntry[] {
  const entries: TreeWindowEntry[] = [];

  const visit = (folder: TreeFolder) => {
    for (const window of folder.windows) {
      entries.push({ window, topicPath: folder.path });
    }

    for (const child of folder.folders) {
      visit(child);
    }
  };

  for (const folder of folders) {
    visit(folder);
  }

  return entries;
}

function matchesWindow(window: TreeWindow, topicPath: string, normalizedQuery: string): boolean {
  if (!normalizedQuery) {
    return true;
  }

  return [
    window.title,
    window.status,
    window.work_status?.label ?? "",
    topicPath,
    projectPathFromRuntimeTags(window.runtime_tags ?? []),
    ...(window.title_tags ?? []),
    ...(window.runtime_tags ?? [])
  ]
    .join(" ")
    .toLocaleLowerCase()
    .includes(normalizedQuery);
}

function countWindows(nodes: SwitcherNode[]): number {
  return nodes.reduce((total, node) => total + (node.type === "window" ? 1 : node.count), 0);
}

function countEntriesInDayMap(days: Map<string, TreeWindowEntry[]>): number {
  let count = 0;

  for (const entries of days.values()) {
    count += entries.length;
  }

  return count;
}

function sortedMapEntries<T>(map: Map<string, T>): Array<[string, T]> {
  return Array.from(map.entries()).sort(([left], [right]) => left.localeCompare(right));
}

function timeParts(value: string): TimeParts {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return { month: "unknown", day: "unknown" };
  }

  const match = /^(\d{4})-(\d{2})-(\d{2})/.exec(value);
  if (match) {
    const [, inputYear, inputMonth, inputDay] = match;
    if (!isValidDatePrefix(inputYear, inputMonth, inputDay)) {
      return { month: "unknown", day: "unknown" };
    }

    return { month: `${inputYear}-${inputMonth}`, day: `${inputMonth}-${inputDay}` };
  }

  const localYear = String(date.getFullYear()).padStart(4, "0");
  const localMonth = String(date.getMonth() + 1).padStart(2, "0");
  const localDay = String(date.getDate()).padStart(2, "0");

  return { month: `${localYear}-${localMonth}`, day: `${localMonth}-${localDay}` };
}

function isValidDatePrefix(year: string, month: string, day: string): boolean {
  const numericYear = Number(year);
  const numericMonth = Number(month);
  const numericDay = Number(day);

  if (numericMonth < 1 || numericMonth > 12 || numericDay < 1) {
    return false;
  }

  const daysInMonth = new Date(Date.UTC(numericYear, numericMonth, 0)).getUTCDate();
  return numericDay <= daysInMonth;
}

export function canCreateWindowAtGroupNode(node: SwitcherGroupNode): boolean {
  return node.projectPath !== undefined
    && node.topicPath === undefined
    && isCreatableProjectPath(node.projectPath);
}

export function createWindowInputForGroupNode(node: SwitcherGroupNode): {
  cwd?: string | null;
  folder_path?: string | null;
} {
  if (!canCreateWindowAtGroupNode(node)) {
    return {};
  }

  return { cwd: node.projectPath };
}

export function findPathToSwitcherWindow(nodes: SwitcherNode[], windowId: string): string[] {
  for (const node of nodes) {
    if (node.type === "window" && node.window.id === windowId) {
      return [node.key];
    }

    if (node.type === "group") {
      const childPath = findPathToSwitcherWindow(node.children, windowId);
      if (childPath.length > 0) {
        return [node.key, ...childPath];
      }
    }
  }

  return [];
}
