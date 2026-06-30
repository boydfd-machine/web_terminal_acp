import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";

import { fetchGlobalTerminalRecents, fetchTerminalRecents } from "../api";
import type { TranslateFn } from "../i18n";
import { buildTerminalSwitcherTree, matchesSwitcherWindow } from "../terminalGrouping";
import type { TerminalGroupingMode } from "../userPreferences";
import type { GlobalTerminalRecent, ProjectSummary, TerminalRecent, TreeFolder, TreeWindow } from "../types";
import {
  RECENT_PROJECT_ALL_KEY,
  SWITCHER_VISIBLE_PAGE_SIZE,
  collectGroupKeys,
  collectWindowProjects,
  flattenVisibleTreeItems,
  projectPathFromRuntimeTags,
  projectTabLabel,
  recentProjectKey,
  relatedRecentItemKey,
  relatedTerminalActivityTime,
  scopedRecentItemKey,
  type RecentProjectTab,
  type VisibleTreeItem
} from "./terminalSwitcherData";
import type { TerminalSwitcherMode, TerminalSwitcherRecentScope } from "./TerminalSwitcher";

type UseTerminalSwitcherDerivedArgs = {
  activeRecentProjectKey: string;
  clientId: string | null;
  expandedKeys: Set<string>;
  folders: TreeFolder[] | undefined;
  isOpen: boolean;
  mode: TerminalSwitcherMode;
  projectSummaryLookup: Map<string, ProjectSummary>;
  query: string;
  recentPage: number;
  recentScope: TerminalSwitcherRecentScope;
  relatedWindows: TreeWindow[];
  t: TranslateFn;
  terminalGroupingMode: TerminalGroupingMode;
};

export function useTerminalSwitcherDerived({
  activeRecentProjectKey,
  clientId,
  expandedKeys,
  folders,
  isOpen,
  mode,
  projectSummaryLookup,
  query,
  recentPage,
  recentScope,
  relatedWindows,
  t,
  terminalGroupingMode
}: UseTerminalSwitcherDerivedArgs) {
  const entries = useMemo(
    () => buildTerminalSwitcherTree(folders ?? [], terminalGroupingMode, projectSummaryLookup, ""),
    [folders, projectSummaryLookup, terminalGroupingMode]
  );
  const windowProjectLookup = useMemo(() => collectWindowProjects(folders ?? []), [folders]);
  const normalizedQuery = query.trim().toLocaleLowerCase();
  const isRecentMode = mode === "recent";
  const isGlobalRecentMode = isRecentMode && recentScope === "global";
  const isRelatedRecentMode = isRecentMode && recentScope === "related";
  const recentsQuery = useQuery({
    queryKey: ["terminal-recents", isGlobalRecentMode ? "global" : clientId, isRecentMode ? { page: recentPage, query: normalizedQuery || null } : null],
    queryFn: () => {
      if (isGlobalRecentMode) {
        return fetchGlobalTerminalRecents(recentPage, SWITCHER_VISIBLE_PAGE_SIZE, normalizedQuery);
      }
      return fetchTerminalRecents(clientId as string, recentPage, SWITCHER_VISIBLE_PAGE_SIZE, normalizedQuery);
    },
    enabled: isOpen && isRecentMode && !isRelatedRecentMode && (isGlobalRecentMode || clientId !== null),
    staleTime: 0
  });
  const treeNodes = useMemo(() => {
    if (clientId === null || isRecentMode) {
      return [];
    }
    return buildTerminalSwitcherTree(folders ?? [], terminalGroupingMode, projectSummaryLookup, query);
  }, [clientId, folders, isRecentMode, projectSummaryLookup, query, terminalGroupingMode]);
  const groupKeys = useMemo(() => collectGroupKeys(treeNodes), [treeNodes]);
  const visibleTreeItems = useMemo(() => flattenVisibleTreeItems(treeNodes, expandedKeys), [expandedKeys, treeNodes]);
  const relatedRecentItems = useMemo(() => {
    if (!isRelatedRecentMode) {
      return [];
    }
    return relatedWindows
      .filter((window) => matchesSwitcherWindow(window, "", normalizedQuery))
      .slice()
      .sort((left, right) => {
        const leftTime = relatedTerminalActivityTime(left);
        const rightTime = relatedTerminalActivityTime(right);
        if (leftTime === rightTime) {
          return left.title.localeCompare(right.title) || left.id.localeCompare(right.id);
        }
        return rightTime.localeCompare(leftTime);
      });
  }, [isRelatedRecentMode, normalizedQuery, relatedWindows]);
  const relatedRecentProjectItems = useMemo(() => {
    if (activeRecentProjectKey === RECENT_PROJECT_ALL_KEY) {
      return relatedRecentItems;
    }
    return relatedRecentItems.filter((window) => recentProjectKey(projectPathFromRuntimeTags(window.runtime_tags)) === activeRecentProjectKey);
  }, [activeRecentProjectKey, relatedRecentItems]);
  const relatedRecentTotalPages = Math.max(1, Math.ceil(relatedRecentProjectItems.length / SWITCHER_VISIBLE_PAGE_SIZE));
  const relatedRecentVisibleItems = useMemo(() => {
    const startIndex = (recentPage - 1) * SWITCHER_VISIBLE_PAGE_SIZE;
    return relatedRecentProjectItems.slice(startIndex, startIndex + SWITCHER_VISIBLE_PAGE_SIZE);
  }, [recentPage, relatedRecentProjectItems]);
  const rawRecentItems: Array<TerminalRecent | GlobalTerminalRecent> = isRelatedRecentMode ? [] : recentsQuery.data?.items ?? [];
  const showRecentProjectTabs = isRecentMode && !isGlobalRecentMode;
  const recentProjectTabs = useMemo((): RecentProjectTab[] => {
    if (!showRecentProjectTabs) {
      return [];
    }
    const projectTabs = new Map<string, RecentProjectTab>();
    const windows = isRelatedRecentMode ? relatedRecentItems : rawRecentItems;
    for (const item of windows) {
      const windowId = isRelatedRecentMode ? (item as TreeWindow).id : (item as TerminalRecent).window_id;
      const projectPath = isRelatedRecentMode
        ? projectPathFromRuntimeTags((item as TreeWindow).runtime_tags)
        : windowProjectLookup.get(windowId) ?? null;
      const key = recentProjectKey(projectPath);
      const existing = projectTabs.get(key);
      if (existing) {
        existing.count += 1;
        continue;
      }
      projectTabs.set(key, { key, label: projectTabLabel(projectPath, projectSummaryLookup, t), projectPath, count: 1 });
    }
    return [{ key: RECENT_PROJECT_ALL_KEY, label: t("terminal.switcher.allProjects"), projectPath: null, count: windows.length }, ...projectTabs.values()];
  }, [isRelatedRecentMode, projectSummaryLookup, rawRecentItems, relatedRecentItems, showRecentProjectTabs, t, windowProjectLookup]);
  const recentProjectKeys = useMemo(() => recentProjectTabs.map((tab) => tab.key), [recentProjectTabs]);
  const recentItems: Array<TerminalRecent | GlobalTerminalRecent> = useMemo(() => {
    if (isRelatedRecentMode || activeRecentProjectKey === RECENT_PROJECT_ALL_KEY) {
      return rawRecentItems;
    }
    return rawRecentItems.filter((item) => recentProjectKey(windowProjectLookup.get(item.window_id) ?? null) === activeRecentProjectKey);
  }, [activeRecentProjectKey, isRelatedRecentMode, rawRecentItems, windowProjectLookup]);
  const recentTotalPages = isRelatedRecentMode ? relatedRecentTotalPages : recentsQuery.data?.total_pages ?? 0;
  const recentMatchCount = isRelatedRecentMode ? relatedRecentProjectItems.length : recentsQuery.data?.total ?? 0;
  const recentKeys = useMemo(
    () => isRelatedRecentMode
      ? relatedRecentVisibleItems.map(relatedRecentItemKey)
      : recentItems.map((item) => scopedRecentItemKey(item, isGlobalRecentMode)),
    [isGlobalRecentMode, isRelatedRecentMode, recentItems, relatedRecentVisibleItems]
  );
  const navigableKeys = isRecentMode ? recentKeys : visibleTreeItems.map((item) => item.node.key);
  return {
    entries,
    groupKeys,
    isGlobalRecentMode,
    isRecentMode,
    isRelatedRecentMode,
    navigableKeys,
    normalizedQuery,
    recentError: !isRelatedRecentMode && recentsQuery.isError,
    recentItems,
    recentKeys,
    recentLoading: !isRelatedRecentMode && recentsQuery.isLoading,
    recentMatchCount,
    recentProjectKeys,
    recentProjectTabs,
    recentTotalPages,
    relatedRecentVisibleItems,
    showRecentProjectTabs,
    treeNodes,
    visibleTreeItems: visibleTreeItems as VisibleTreeItem[]
  };
}
