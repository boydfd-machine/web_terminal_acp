import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from "react";

import { fetchProjectSummaries, summarizeProject } from "../api";
import { useI18n } from "../i18n";
import {
  buildTerminalSwitcherTree,
  findPathToSwitcherWindow,
  terminalGroupingModeHasProjectRoot,
  type SwitcherGroupNode,
  type TerminalGroupingMode
} from "../terminalGrouping";
import type { SummaryOutputLanguage } from "../userPreferences";
import type { TerminalTimeRange, TerminalTimeRangeOption } from "../terminalTimeRange";
import type { ProjectSummary, TerminalProject, TreeFolder, TreeWindow } from "../types";
import { DisplayTreeNode, ProjectCardList } from "./FolderTreeNodes";
import {
  collapsedStorageKey,
  loadCollapsedKeys,
  writeCollapsedKeys,
  type CollapsedState
} from "./folderTreeState";

type FolderTreeProps = {
  clientId: string | null;
  folders: TreeFolder[];
  projects?: TerminalProject[];
  selectedProjectPath?: string | null;
  loadingProjects?: boolean;
  loadingSelectedProject?: boolean;
  groupingMode: TerminalGroupingMode;
  timeRange: TerminalTimeRange;
  timeRangeOptions: TerminalTimeRangeOption[];
  summaryOutputLanguage: SummaryOutputLanguage;
  selectedWindowId: string | null;
  locateSelectedWindowSignal?: number;
  deletingWindowId?: string | null;
  hasUnreadNotification?: (windowId: string) => boolean;
  onSelectProject?: (projectPath: string) => void;
  onOpenProjectDetail?: (projectPath: string) => void;
  onSelectWindow: (window: TreeWindow) => void;
  onDeleteWindow: (window: TreeWindow) => void;
  onTimeRangeChange: (range: TerminalTimeRange) => void;
  onCreateTerminalAtGroup?: (node: SwitcherGroupNode) => void;
  onConfigureTerminalAtGroup?: (node: SwitcherGroupNode) => void;
  renderHeaderAction?: () => ReactNode;
  creatingTerminal?: boolean;
  createTerminalDisabled?: boolean;
};

export function FolderTree({
  clientId,
  folders,
  projects = [],
  selectedProjectPath = null,
  loadingProjects,
  loadingSelectedProject,
  groupingMode,
  timeRange,
  timeRangeOptions,
  summaryOutputLanguage,
  selectedWindowId,
  locateSelectedWindowSignal = 0,
  deletingWindowId,
  hasUnreadNotification,
  onSelectProject = () => {},
  onOpenProjectDetail = () => {},
  onSelectWindow,
  onDeleteWindow,
  onTimeRangeChange,
  onCreateTerminalAtGroup,
  onConfigureTerminalAtGroup,
  renderHeaderAction,
  creatingTerminal,
  createTerminalDisabled
}: FolderTreeProps) {
  const { t } = useI18n();
  const queryClient = useQueryClient();
  const [summarizingProjectPath, setSummarizingProjectPath] = useState<string | null>(null);
  const [locatingWindowId, setLocatingWindowId] = useState<string | null>(null);
  const [projectListCollapsed, setProjectListCollapsed] = useState(false);
  const windowButtonRefs = useRef(new Map<string, HTMLButtonElement>());
  const locateClearTimeoutRef = useRef<number | null>(null);
  const handledLocateSignalRef = useRef(0);
  const projectSummariesQuery = useQuery({
    queryKey: ["project-summaries", clientId],
    queryFn: () => fetchProjectSummaries(clientId as string),
    enabled: clientId !== null
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
  const displayTree = useMemo(
    () => buildTerminalSwitcherTree(folders, groupingMode, projectSummaryLookup, ""),
    [folders, groupingMode, projectSummaryLookup]
  );
  const storageKey = collapsedStorageKey(clientId, `${groupingMode}:${selectedProjectPath ?? "no-project"}`);
  const [collapsedState, setCollapsedState] = useState<CollapsedState>(() => ({
    storageKey,
    keys: loadCollapsedKeys(storageKey, displayTree)
  }));
  const collapsedKeys = collapsedState.storageKey === storageKey ? collapsedState.keys : loadCollapsedKeys(storageKey, displayTree);
  const selectedPathKeys = useMemo(
    () => new Set(selectedWindowId === null ? [] : findPathToSwitcherWindow(displayTree, selectedWindowId)),
    [displayTree, selectedWindowId]
  );

  const registerWindowButton = useCallback((windowId: string, element: HTMLButtonElement | null) => {
    if (element === null) {
      windowButtonRefs.current.delete(windowId);
      return;
    }

    windowButtonRefs.current.set(windowId, element);
  }, []);

  useEffect(() => {
    setCollapsedState({ storageKey, keys: loadCollapsedKeys(storageKey, displayTree) });
  }, [displayTree, storageKey]);

  useEffect(() => {
    if (collapsedState.storageKey === storageKey) {
      writeCollapsedKeys(storageKey, collapsedState.keys);
    }
  }, [collapsedState, storageKey]);

  useEffect(() => {
    if (locateClearTimeoutRef.current !== null) {
      window.clearTimeout(locateClearTimeoutRef.current);
      locateClearTimeoutRef.current = null;
    }

    return () => {
      if (locateClearTimeoutRef.current !== null) {
        window.clearTimeout(locateClearTimeoutRef.current);
      }
    };
  }, []);

  useEffect(() => {
    if (locateSelectedWindowSignal === 0 || selectedWindowId === null) {
      return;
    }
    if (handledLocateSignalRef.current === locateSelectedWindowSignal) {
      return;
    }

    const frame = window.requestAnimationFrame(() => {
      const selectedButton = windowButtonRefs.current.get(selectedWindowId);
      if (!selectedButton) {
        return;
      }

      handledLocateSignalRef.current = locateSelectedWindowSignal;
      selectedButton.scrollIntoView({ block: "center", inline: "nearest", behavior: "smooth" });
      setLocatingWindowId(selectedWindowId);

      if (locateClearTimeoutRef.current !== null) {
        window.clearTimeout(locateClearTimeoutRef.current);
      }
      locateClearTimeoutRef.current = window.setTimeout(() => {
        setLocatingWindowId((currentId) => (currentId === selectedWindowId ? null : currentId));
        locateClearTimeoutRef.current = null;
      }, 1200);
    });

    return () => window.cancelAnimationFrame(frame);
  }, [locateSelectedWindowSignal, selectedWindowId, selectedPathKeys]);

  const toggleGroup = (key: string) => {
    setCollapsedState((currentState) => {
      const nextKeys = new Set(currentState.storageKey === storageKey ? currentState.keys : loadCollapsedKeys(storageKey, displayTree));
      if (nextKeys.has(key)) {
        nextKeys.delete(key);
      } else {
        nextKeys.add(key);
      }

      return { storageKey, keys: nextKeys };
    });
  };

  return (
    <div data-onboarding-id="terminal-tree">
      <div className="tree-header">
        <h2>{t("terminal.tree.title")}</h2>
        <div className="tree-header-actions">
          <label className="terminal-range-control">
            <span>{t("terminal.tree.range")}</span>
            <select
              value={timeRange}
              aria-label={t("terminal.tree.timeRange")}
              onChange={(event) => onTimeRangeChange(event.target.value as TerminalTimeRange)}
            >
              {timeRangeOptions.map((option) => (
                <option key={option.value} value={option.value}>
                  {t(option.labelKey)}
                </option>
              ))}
            </select>
          </label>
          {renderHeaderAction?.()}
        </div>
      </div>
      <div className="terminal-project-section">
        <button
          type="button"
          className="section-collapse-button terminal-project-section-header"
          aria-expanded={!projectListCollapsed}
          onClick={() => setProjectListCollapsed((collapsed) => !collapsed)}
        >
          <span>{t("terminal.tree.projects")}</span>
          <span aria-hidden="true">{projectListCollapsed ? "+" : "-"}</span>
        </button>
        {!projectListCollapsed && (
          <ProjectCardList
            projects={projects}
            selectedProjectPath={selectedProjectPath}
            projectSummaryLookup={projectSummaryLookup}
            loadingProjects={loadingProjects}
            onOpenProjectDetail={onOpenProjectDetail}
            onSelectProject={onSelectProject}
          />
        )}
      </div>
      {selectedProjectPath !== null && loadingSelectedProject && (
        <div className="terminal-tree-loading" role="status" aria-live="polite">
          <span className="terminal-project-spinner" aria-hidden="true" />
          <span>{t("terminal.tree.loadingProjectTree")}</span>
        </div>
      )}
      {selectedProjectPath !== null && !loadingSelectedProject && displayTree.length === 0 && (
        <p className="muted terminal-project-empty">{t("terminal.tree.noProjectTerminals")}</p>
      )}
      <ul className="tree-root">
        {displayTree.map((node) => (
          <DisplayTreeNode
            key={node.key}
            node={node}
            collapsedKeys={collapsedKeys}
            selectedPathKeys={selectedPathKeys}
            selectedWindowId={selectedWindowId}
            locatingWindowId={locatingWindowId}
            registerWindowButton={registerWindowButton}
            deletingWindowId={deletingWindowId}
            summarizingProjectPath={summarizingProjectPath}
            hasUnreadNotification={hasUnreadNotification}
            onSelectWindow={onSelectWindow}
            onDeleteWindow={onDeleteWindow}
            onToggleGroup={toggleGroup}
            onSummarizeProject={
              terminalGroupingModeHasProjectRoot(groupingMode) && clientId !== null
                ? (projectPath) => summarizeMutation.mutate(projectPath)
                : undefined
            }
            onCreateTerminalAtGroup={onCreateTerminalAtGroup}
            onConfigureTerminalAtGroup={onConfigureTerminalAtGroup}
            creatingTerminal={creatingTerminal}
            createTerminalDisabled={createTerminalDisabled}
          />
        ))}
      </ul>
    </div>
  );
}
