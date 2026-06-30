import type { ProjectFileEntry } from "./types";

export const MAX_PROJECT_FILE_TABS = 10;
export const PROJECT_FILE_TABS_STORAGE_KEY = "web-terminal-acp:project-file-tabs";

export type ProjectFileTabContext = {
  clientId: string;
  projectPath: string;
  browseRoot: string | null;
};

export type ProjectFileTab = ProjectFileTabContext & {
  key: string;
  name: string;
  path: string;
  size: number | null;
  mtime: number | null;
  line: number | null;
  openedAt: number;
  lastUsedAt: number;
};

export type ProjectFileTabsState = {
  tabs: ProjectFileTab[];
  activeKey: string | null;
};

export type CloseProjectFileTabResult = {
  state: ProjectFileTabsState;
  nextActiveTab: ProjectFileTab | null;
};

export type ProjectFileTabSwitchCandidate = ProjectFileTab & {
  active: boolean;
};

export function projectFileTabKey(context: ProjectFileTabContext, path: string): string {
  return JSON.stringify([
    context.clientId,
    context.projectPath,
    context.browseRoot ?? "",
    path,
  ]);
}

export function projectFileTabsForContext(
  state: ProjectFileTabsState,
  context: ProjectFileTabContext | null
): ProjectFileTab[] {
  if (context === null) {
    return [];
  }
  return state.tabs.filter((tab) => sameProjectFileTabContext(tab, context));
}

export function projectFileSwitchCandidates(
  state: ProjectFileTabsState,
  clientId: string | null,
  query: string
): ProjectFileTabSwitchCandidate[] {
  if (clientId === null) {
    return [];
  }
  const normalizedQuery = query.trim().toLocaleLowerCase();
  return state.tabs
    .filter((tab) => tab.clientId === clientId)
    .filter((tab) => {
      if (normalizedQuery.length === 0) {
        return true;
      }
      return [
        tab.name,
        tab.path,
        tab.projectPath,
        tab.browseRoot ?? "",
      ].some((field) => field.toLocaleLowerCase().includes(normalizedQuery));
    })
    .sort((left, right) => right.lastUsedAt - left.lastUsedAt || right.openedAt - left.openedAt)
    .map((tab) => ({
      ...tab,
      active: tab.key === state.activeKey,
    }));
}

export function openProjectFileTab(
  state: ProjectFileTabsState,
  context: ProjectFileTabContext,
  entry: ProjectFileEntry,
  line: number | null,
  openedAt: number
): ProjectFileTabsState {
  if (entry.kind !== "file") {
    return state;
  }

  const key = projectFileTabKey(context, entry.path);
  const existingTab = state.tabs.find((tab) => tab.key === key);
  const nextLine = line ?? existingTab?.line ?? null;
  if (
    existingTab !== undefined
    && state.activeKey === key
    && existingTab.name === entry.name
    && existingTab.size === entry.size
    && existingTab.mtime === entry.mtime
    && existingTab.line === nextLine
  ) {
    return state;
  }
  const nextTab: ProjectFileTab = {
    ...context,
    key,
    name: entry.name,
    path: entry.path,
    size: entry.size,
    mtime: entry.mtime,
    line: nextLine,
    openedAt: existingTab?.openedAt ?? openedAt,
    lastUsedAt: openedAt,
  };
  const updatedTabs = [...state.tabs.filter((tab) => tab.key !== key), nextTab];
  return {
    tabs: trimProjectFileTabs(updatedTabs, context),
    activeKey: key,
  };
}

export function selectProjectFileTab(
  state: ProjectFileTabsState,
  key: string,
  selectedAt: number
): ProjectFileTabsState {
  let found = false;
  const tabs = state.tabs.map((tab) => {
    if (tab.key !== key) {
      return tab;
    }
    found = true;
    return {
      ...tab,
      lastUsedAt: selectedAt,
    };
  });

  return found ? { tabs, activeKey: key } : state;
}

export function nextProjectFileTab(
  state: ProjectFileTabsState,
  context: ProjectFileTabContext | null,
  activeKey: string | null
): ProjectFileTab | null {
  const tabs = projectFileTabsForContext(state, context);
  if (tabs.length === 0) {
    return null;
  }
  const activeIndex = tabs.findIndex((tab) => tab.key === activeKey);
  const nextIndex = activeIndex === -1 ? 0 : (activeIndex + 1) % tabs.length;
  return tabs[nextIndex] ?? null;
}

export function closeProjectFileTab(
  state: ProjectFileTabsState,
  key: string,
  context: ProjectFileTabContext | null,
  closedAt: number
): CloseProjectFileTabResult {
  const tabsInContext = projectFileTabsForContext(state, context);
  const closedIndex = tabsInContext.findIndex((tab) => tab.key === key);
  const tabs = state.tabs.filter((tab) => tab.key !== key);
  let nextActiveTab: ProjectFileTab | null = null;

  if (state.activeKey === key && context !== null && closedIndex !== -1) {
    const nextTabsInContext = tabsInContext.filter((tab) => tab.key !== key);
    nextActiveTab = nextTabsInContext[closedIndex] ?? nextTabsInContext[closedIndex - 1] ?? null;
  } else if (state.activeKey !== null) {
    nextActiveTab = tabs.find((tab) => tab.key === state.activeKey) ?? null;
  }

  const nextState = nextActiveTab === null
    ? { tabs, activeKey: state.activeKey === key ? null : state.activeKey }
    : selectProjectFileTab({ tabs, activeKey: state.activeKey }, nextActiveTab.key, closedAt);
  return {
    state: nextState,
    nextActiveTab,
  };
}

export function readProjectFileTabsState(): ProjectFileTabsState {
  if (typeof window === "undefined") {
    return emptyProjectFileTabsState();
  }

  try {
    return normalizeProjectFileTabsState(
      JSON.parse(window.localStorage.getItem(PROJECT_FILE_TABS_STORAGE_KEY) ?? "{}")
    );
  } catch {
    return emptyProjectFileTabsState();
  }
}

export function writeProjectFileTabsState(state: ProjectFileTabsState): void {
  if (typeof window === "undefined") {
    return;
  }
  window.localStorage.setItem(PROJECT_FILE_TABS_STORAGE_KEY, JSON.stringify(state));
}

export function sameProjectFileTabContext(
  tab: ProjectFileTabContext,
  context: ProjectFileTabContext
): boolean {
  return tab.clientId === context.clientId
    && tab.projectPath === context.projectPath
    && tab.browseRoot === context.browseRoot;
}

export function projectFileEntryForTab(tab: ProjectFileTab): ProjectFileEntry {
  return {
    name: tab.name,
    path: tab.path,
    kind: "file",
    size: tab.size,
    mtime: tab.mtime,
  };
}

function emptyProjectFileTabsState(): ProjectFileTabsState {
  return { tabs: [], activeKey: null };
}

function trimProjectFileTabs(tabs: ProjectFileTab[], context: ProjectFileTabContext): ProjectFileTab[] {
  const tabsInContext = tabs.filter((tab) => sameProjectFileTabContext(tab, context));
  if (tabsInContext.length <= MAX_PROJECT_FILE_TABS) {
    return tabs;
  }

  const keysToDrop = new Set(
    [...tabsInContext]
      .sort((left, right) => left.openedAt - right.openedAt)
      .slice(0, tabsInContext.length - MAX_PROJECT_FILE_TABS)
      .map((tab) => tab.key)
  );
  return tabs.filter((tab) => !keysToDrop.has(tab.key));
}

function normalizeProjectFileTabsState(value: unknown): ProjectFileTabsState {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    return emptyProjectFileTabsState();
  }
  const record = value as Record<string, unknown>;
  const tabs = Array.isArray(record.tabs)
    ? record.tabs.map(normalizeProjectFileTab).filter((tab): tab is ProjectFileTab => tab !== null)
    : [];
  const activeKey = typeof record.activeKey === "string" && tabs.some((tab) => tab.key === record.activeKey)
    ? record.activeKey
    : null;
  return { tabs, activeKey };
}

function normalizeProjectFileTab(value: unknown): ProjectFileTab | null {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    return null;
  }
  const record = value as Record<string, unknown>;
  if (
    typeof record.clientId !== "string"
    || typeof record.projectPath !== "string"
    || (typeof record.browseRoot !== "string" && record.browseRoot !== null)
    || typeof record.name !== "string"
    || typeof record.path !== "string"
  ) {
    return null;
  }
  const context = {
    clientId: record.clientId,
    projectPath: record.projectPath,
    browseRoot: record.browseRoot,
  };
  const key = projectFileTabKey(context, record.path);
  return {
    ...context,
    key,
    name: record.name,
    path: record.path,
    size: finiteNumberOrNull(record.size),
    mtime: finiteNumberOrNull(record.mtime),
    line: finiteNumberOrNull(record.line),
    openedAt: finiteNumberOrZero(record.openedAt),
    lastUsedAt: finiteNumberOrZero(record.lastUsedAt),
  };
}

function finiteNumberOrNull(value: unknown): number | null {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function finiteNumberOrZero(value: unknown): number {
  return typeof value === "number" && Number.isFinite(value) ? value : 0;
}
