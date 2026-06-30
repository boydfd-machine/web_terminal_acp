import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { fetchProjectSummaries, summarizeProject } from "../api";
import { useI18n } from "../i18n";
import type { SummaryOutputLanguage } from "../userPreferences";
import { keyboardShortcutMatches, type KeyboardShortcut } from "../keyboardShortcuts";
import {
  type SwitcherGroupNode,
  type SwitcherNode
} from "../terminalGrouping";
import type { TerminalGroupingMode } from "../userPreferences";
import type { GlobalTerminalRecent, ProjectSummary, TerminalRecent, TreeFolder, TreeWindow } from "../types";
import { useOverlayFocus } from "./useOverlayFocus";
import { TerminalSwitcherChrome } from "./TerminalSwitcherChrome";
import { TerminalSwitcherRecentList } from "./TerminalSwitcherRecentList";
import { TerminalSwitcherTreeList } from "./TerminalSwitcherTreeList";
import { useTerminalSwitcherDerived } from "./useTerminalSwitcherDerived";
import { useTerminalSwitcherPageState } from "./useTerminalSwitcherPageState";
import {
  RECENT_PROJECT_ALL_KEY,
  isGlobalTerminalRecent,
  recentItemKey,
  relatedRecentItemKey,
  scopedRecentItemKey,
  type TerminalEntry,
} from "./terminalSwitcherData";

export type TerminalSwitcherMode = "recent" | "tree";
export type TerminalSwitcherRecentScope = "client" | "global" | "related";

type TerminalSwitcherProps = {
  clientId: string | null;
  folders: TreeFolder[] | undefined;
  relatedWindows?: TreeWindow[];
  relatedLoading?: boolean;
  selectedWindowId: string | null;
  mode: TerminalSwitcherMode;
  recentScope?: TerminalSwitcherRecentScope;
  terminalGroupingMode: TerminalGroupingMode;
  summaryOutputLanguage: SummaryOutputLanguage;
  isOpen: boolean;
  hasUnreadNotification?: (windowId: string) => boolean;
  onClose: () => void;
  onSelectWindow: (windowId: string, clientId?: string) => void;
  onToggleModeShortcut?: () => void;
  onCreateTerminalAtGroup?: (node: SwitcherGroupNode) => void;
  onConfigureTerminalAtGroup?: (node: SwitcherGroupNode) => void;
  creatingTerminal?: boolean;
  createTerminalDisabled?: boolean;
  switchShortcut?: KeyboardShortcut | null;
  switchShortcutLabel?: string;
};


export function TerminalSwitcher({
  clientId,
  folders,
  relatedWindows = [],
  relatedLoading = false,
  selectedWindowId,
  mode,
  recentScope = "client",
  terminalGroupingMode,
  summaryOutputLanguage,
  isOpen,
  hasUnreadNotification,
  onClose,
  onSelectWindow,
  onToggleModeShortcut,
  onCreateTerminalAtGroup,
  onConfigureTerminalAtGroup,
  creatingTerminal,
  createTerminalDisabled,
  switchShortcut,
  switchShortcutLabel
}: TerminalSwitcherProps) {
  const { t } = useI18n();
  const queryClient = useQueryClient();
  const [query, setQuery] = useState("");
  const [activeKey, setActiveKey] = useState<string | null>(null);
  const [recentPage, setRecentPage] = useState(1);
  const [activeRecentProjectKey, setActiveRecentProjectKey] = useState(RECENT_PROJECT_ALL_KEY);
  const [expandedKeys, setExpandedKeys] = useState<Set<string>>(() => new Set());
  const [summarizingProjectPath, setSummarizingProjectPath] = useState<string | null>(null);
  const panelRef = useRef<HTMLDivElement | null>(null);
  const projectSummariesQuery = useQuery({
    queryKey: ["project-summaries", clientId],
    queryFn: () => fetchProjectSummaries(clientId as string),
    enabled: isOpen && clientId !== null
  });
  const projectSummaryLookup = useMemo(() => {
    const lookup = new Map<string, ProjectSummary>();
    for (const summary of projectSummariesQuery.data ?? []) {
      lookup.set(summary.project_path, summary);
    }
    return lookup;
  }, [projectSummariesQuery.data]);
  const summarizeMutation = useMutation({
    mutationFn: (projectPath: string) => summarizeProject(clientId as string, projectPath, summaryOutputLanguage),
    onMutate: (projectPath) => {
      setSummarizingProjectPath(projectPath);
    },
    onSettled: () => {
      setSummarizingProjectPath(null);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["project-summaries", clientId] });
    }
  });
  const {
    entries,
    groupKeys,
    isGlobalRecentMode,
    isRecentMode,
    isRelatedRecentMode,
    navigableKeys,
    normalizedQuery,
    recentError,
    recentItems,
    recentKeys,
    recentLoading,
    recentMatchCount,
    recentProjectKeys,
    recentProjectTabs,
    recentTotalPages,
    relatedRecentVisibleItems,
    showRecentProjectTabs,
    treeNodes,
    visibleTreeItems
  } = useTerminalSwitcherDerived({
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
  });
  const effectiveSwitchShortcutLabel = switchShortcutLabel ?? t("shortcut.defaultHint");

  useEffect(() => {
    setQuery("");
    setActiveKey(null);
    setRecentPage(1);
    setActiveRecentProjectKey(RECENT_PROJECT_ALL_KEY);
    setExpandedKeys(new Set());
  }, [isOpen, mode, recentScope]);

  const handleEscape = useCallback(() => {
    onClose();
  }, [onClose]);

  useOverlayFocus({
    isOpen,
    ref: panelRef,
    onEscape: handleEscape,
    initialFocusSelector: "input"
  });

  useTerminalSwitcherPageState({
    activeRecentProjectKey,
    isOpen,
    isRecentMode,
    normalizedQuery,
    recentTotalPages,
    setActiveRecentProjectKey,
    setRecentPage
  });

  useEffect(() => {
    if (!isOpen || !showRecentProjectTabs) {
      return;
    }

    if (!recentProjectKeys.includes(activeRecentProjectKey)) {
      setActiveRecentProjectKey(RECENT_PROJECT_ALL_KEY);
    }
  }, [activeRecentProjectKey, isOpen, recentProjectKeys, showRecentProjectTabs]);

  useEffect(() => {
    if (!isOpen || isRecentMode || normalizedQuery.length === 0) {
      return;
    }

    setExpandedKeys(new Set(groupKeys));
  }, [groupKeys, isOpen, isRecentMode, normalizedQuery]);

  useEffect(() => {
    if (!isOpen) {
      return;
    }

    setActiveKey((currentKey) => {
      if (isRecentMode) {
        if (currentKey !== null && recentKeys.includes(currentKey)) {
          return currentKey;
        }

        const selectedKey = selectedWindowId === null
          ? null
          : isRelatedRecentMode
            ? `related:${selectedWindowId}`
            : isGlobalRecentMode && clientId !== null
            ? `recent:${clientId}:${selectedWindowId}`
            : recentItemKey(selectedWindowId);
        if (selectedKey !== null && recentKeys.includes(selectedKey)) {
          return selectedKey;
        }

        return recentKeys[0] ?? null;
      }

      if (currentKey !== null && visibleTreeItems.some((item) => item.node.key === currentKey)) {
        return currentKey;
      }

      const selectedItem = visibleTreeItems.find(
        (item) => item.node.type === "window" && item.node.window.id === selectedWindowId
      );
      return selectedItem?.node.key ?? null;
    });
  }, [clientId, isGlobalRecentMode, isOpen, isRecentMode, isRelatedRecentMode, recentKeys, selectedWindowId, visibleTreeItems]);

  useEffect(() => {
    if (!isOpen) {
      return;
    }

    const handleKeyDown = (event: KeyboardEvent) => {
      if (keyboardShortcutMatches(event, switchShortcut ?? null)) {
        event.preventDefault();
        event.stopPropagation();
        onToggleModeShortcut?.();
        return;
      }

      if (event.key === "Tab" && showRecentProjectTabs && recentProjectKeys.length > 1) {
        event.preventDefault();
        event.stopPropagation();
        const activeProjectIndex = recentProjectKeys.indexOf(activeRecentProjectKey);
        const fallbackIndex = activeProjectIndex < 0 ? 0 : activeProjectIndex;
        const nextProjectIndex = event.shiftKey
          ? (fallbackIndex - 1 + recentProjectKeys.length) % recentProjectKeys.length
          : (fallbackIndex + 1) % recentProjectKeys.length;
        setActiveRecentProjectKey(recentProjectKeys[nextProjectIndex]);
        setActiveKey(null);
        return;
      }

      if (navigableKeys.length === 0) {
        return;
      }

      const activeIndex = activeKey === null ? -1 : navigableKeys.indexOf(activeKey);
      const activeItem = activeIndex >= 0 ? visibleTreeItems[activeIndex] : null;

      if (event.key === "ArrowDown") {
        event.preventDefault();
        const nextIndex = activeIndex < 0 ? 0 : (activeIndex + 1) % navigableKeys.length;
        setActiveKey(navigableKeys[nextIndex]);
        return;
      }

      if (event.key === "ArrowUp") {
        event.preventDefault();
        const nextIndex = activeIndex < 0 ? navigableKeys.length - 1 : (activeIndex - 1 + navigableKeys.length) % navigableKeys.length;
        setActiveKey(navigableKeys[nextIndex]);
        return;
      }

      if (!isRecentMode && event.key === "ArrowRight" && activeItem?.node.type === "group") {
        event.preventDefault();
        if (!expandedKeys.has(activeItem.node.key)) {
          setExpandedKeys((currentKeys) => new Set(currentKeys).add(activeItem.node.key));
        } else if (activeIndex + 1 < visibleTreeItems.length) {
          setActiveKey(visibleTreeItems[activeIndex + 1].node.key);
        }
        return;
      }

      if (!isRecentMode && event.key === "ArrowLeft" && activeItem !== null) {
        event.preventDefault();
        if (activeItem.node.type === "group" && expandedKeys.has(activeItem.node.key)) {
          setExpandedKeys((currentKeys) => {
            const nextKeys = new Set(currentKeys);
            nextKeys.delete(activeItem.node.key);
            return nextKeys;
          });
          return;
        }

        if (activeItem.parentKey !== null) {
          setActiveKey(activeItem.parentKey);
        }
        return;
      }

      if (event.key === "Enter") {
        if (activeKey === null) {
          return;
        }

        event.preventDefault();
        if (isRecentMode) {
          if (isRelatedRecentMode) {
            const item = relatedRecentVisibleItems.find((candidate) => relatedRecentItemKey(candidate) === activeKey);
            if (item === undefined) {
              return;
            }
            onSelectWindow(item.id);
            onClose();
            return;
          }
          const item = recentItems.find((candidate) => scopedRecentItemKey(candidate, isGlobalRecentMode) === activeKey);
          if (item === undefined) {
            return;
          }
          onSelectWindow(item.window_id, isGlobalTerminalRecent(item) ? item.client_id : undefined);
          onClose();
          return;
        }

        if (activeItem === null) {
          return;
        }

        if (activeItem.node.type === "group") {
          setExpandedKeys((currentKeys) => {
            const nextKeys = new Set(currentKeys);
            if (nextKeys.has(activeItem.node.key)) {
              nextKeys.delete(activeItem.node.key);
            } else {
              nextKeys.add(activeItem.node.key);
            }
            return nextKeys;
          });
        } else {
          onSelectWindow(activeItem.node.window.id);
          onClose();
        }
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [
    activeKey,
    expandedKeys,
    isOpen,
    navigableKeys,
    onClose,
    onSelectWindow,
    onToggleModeShortcut,
    activeRecentProjectKey,
    isRecentMode,
    isRelatedRecentMode,
    isGlobalRecentMode,
    switchShortcut,
    recentItems,
    recentProjectKeys,
    relatedRecentVisibleItems,
    showRecentProjectTabs,
    visibleTreeItems
  ]);

  if (!isOpen) {
    return null;
  }

  const selectEntry = (entry: TerminalEntry) => {
    onSelectWindow(entry.window.id);
    onClose();
  };
  const toggleGroup = (key: string) => {
    setActiveKey(key);
    setExpandedKeys((currentKeys) => {
      const nextKeys = new Set(currentKeys);
      if (nextKeys.has(key)) {
        nextKeys.delete(key);
      } else {
        nextKeys.add(key);
      }

      return nextKeys;
    });
  };
  const selectRecent = (item: TerminalRecent | GlobalTerminalRecent) => {
    onSelectWindow(item.window_id, isGlobalTerminalRecent(item) ? item.client_id : undefined);
    onClose();
  };
  const selectRelatedRecent = (window: TreeWindow) => {
    onSelectWindow(window.id);
    onClose();
  };
  return (
    <div
      className="terminal-switcher-backdrop"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) {
          onClose();
        }
      }}
    >
      <div
        aria-modal="true"
        className="terminal-switcher"
        data-onboarding-id="terminal-switcher"
        ref={panelRef}
        role="dialog"
      >
        <TerminalSwitcherChrome
          activeRecentProjectKey={activeRecentProjectKey}
          isGlobalRecentMode={isGlobalRecentMode}
          isRecentMode={isRecentMode}
          isRelatedRecentMode={isRelatedRecentMode}
          query={query}
          recentProjectTabs={recentProjectTabs}
          showRecentProjectTabs={showRecentProjectTabs}
          switchShortcutLabel={effectiveSwitchShortcutLabel}
          terminalGroupingMode={terminalGroupingMode}
          onClose={onClose}
          setActiveKey={setActiveKey}
          setActiveRecentProjectKey={setActiveRecentProjectKey}
          setExpandedKeys={setExpandedKeys}
          setQuery={setQuery}
        />

        {clientId === null && !isGlobalRecentMode && !isRelatedRecentMode && <p className="terminal-switcher-empty">{t("terminal.switcher.selectClient")}</p>}
        {clientId !== null && !isGlobalRecentMode && !isRecentMode && entries.length === 0 && (
          <p className="terminal-switcher-empty">{t("terminal.switcher.emptyClient")}</p>
        )}

        {(clientId !== null || isGlobalRecentMode || isRelatedRecentMode) && isRecentMode && (
          <TerminalSwitcherRecentList
            activeKey={activeKey}
            activeRecentProjectKey={activeRecentProjectKey}
            clientId={clientId}
            folders={folders ?? []}
            hasUnreadNotification={hasUnreadNotification}
            isGlobalRecentMode={isGlobalRecentMode}
            isRelatedRecentMode={isRelatedRecentMode}
            normalizedQuery={normalizedQuery}
            projectSummaryLookup={projectSummaryLookup}
            recentError={recentError}
            recentItems={recentItems}
            recentLoading={recentLoading}
            recentMatchCount={recentMatchCount}
            recentPage={recentPage}
            recentTotalPages={recentTotalPages}
            relatedLoading={relatedLoading}
            relatedRecentVisibleItems={relatedRecentVisibleItems}
            selectedWindowId={selectedWindowId}
            onSelectRecent={selectRecent}
            onSelectRelatedRecent={selectRelatedRecent}
            setRecentPage={setRecentPage}
          />
        )}

        {!isRecentMode && (
          <TerminalSwitcherTreeList
            activeKey={activeKey}
            clientId={clientId}
            createTerminalDisabled={createTerminalDisabled}
            creatingTerminal={creatingTerminal}
            entriesLength={entries.length}
            expandedKeys={expandedKeys}
            hasUnreadNotification={hasUnreadNotification}
            projectSummaryLookup={projectSummaryLookup}
            selectedWindowId={selectedWindowId}
            summarizingProjectPath={summarizingProjectPath}
            terminalGroupingMode={terminalGroupingMode}
            treeNodes={treeNodes}
            onConfigureTerminalAtGroup={onConfigureTerminalAtGroup}
            onCreateTerminalAtGroup={onCreateTerminalAtGroup}
            onSelectEntry={selectEntry}
            onSummarizeProject={(projectPath) => summarizeMutation.mutate(projectPath)}
            onToggleGroup={toggleGroup}
          />
        )}
      </div>
    </div>
  );
}
