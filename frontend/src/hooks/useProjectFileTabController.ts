import { useCallback, useMemo, type Dispatch, type SetStateAction } from "react";

import {
  closeProjectFileTab,
  nextProjectFileTab,
  openProjectFileTab,
  projectFileEntryForTab,
  projectFileTabsForContext,
  selectProjectFileTab,
  type ProjectFileTab,
  type ProjectFileTabContext,
  type ProjectFileTabsState,
} from "../projectFileTabs";
import {
  writeProjectFileRoute,
  writeProjectFilesRoute,
} from "../projectFileLinks";
import type { ProjectFileEntry } from "../types";

type UseProjectFileTabControllerArgs = {
  projectFileTabsState: ProjectFileTabsState;
  selectedClientId: string | null;
  selectedProjectBrowseRoot: string | null;
  selectedProjectPath: string | null;
  selectedWindowId: string | null;
  setProjectFileTabsState: Dispatch<SetStateAction<ProjectFileTabsState>>;
  setSelectedClientId?: (clientId: string) => void;
  setSelectedProjectBrowseRoot?: (browseRoot: string | null) => void;
  setSelectedProjectFile: (entry: ProjectFileEntry | null) => void;
  setSelectedProjectFileLine: (line: number | null) => void;
  setSelectedProjectPath?: (projectPath: string) => void;
  setWorkspaceMode?: (mode: "files") => void;
};

export function useProjectFileTabController({
  projectFileTabsState,
  selectedClientId,
  selectedProjectBrowseRoot,
  selectedProjectPath,
  selectedWindowId,
  setProjectFileTabsState,
  setSelectedClientId,
  setSelectedProjectBrowseRoot,
  setSelectedProjectFile,
  setSelectedProjectFileLine,
  setSelectedProjectPath,
  setWorkspaceMode,
}: UseProjectFileTabControllerArgs) {
  const context = useMemo<ProjectFileTabContext | null>(() => {
    if (selectedClientId === null || selectedProjectPath === null) {
      return null;
    }
    return {
      clientId: selectedClientId,
      projectPath: selectedProjectPath,
      browseRoot: selectedProjectBrowseRoot,
    };
  }, [selectedClientId, selectedProjectBrowseRoot, selectedProjectPath]);

  const visibleTabs = useMemo(
    () => projectFileTabsForContext(projectFileTabsState, context),
    [context, projectFileTabsState]
  );
  const activeKey = visibleTabs.some((tab) => tab.key === projectFileTabsState.activeKey)
    ? projectFileTabsState.activeKey
    : null;

  const rememberTab = useCallback((
    tabContext: ProjectFileTabContext,
    entry: ProjectFileEntry,
    line: number | null,
    openedAt = Date.now()
  ) => {
    setProjectFileTabsState((currentState) => openProjectFileTab(currentState, tabContext, entry, line, openedAt));
  }, [setProjectFileTabsState]);

  const openCurrentTab = useCallback((entry: ProjectFileEntry | null, line: number | null) => {
    if (context === null || entry?.kind !== "file") {
      return;
    }
    rememberTab(context, entry, line);
  }, [context, rememberTab]);

  const activateTab = useCallback((tab: ProjectFileTab, mode: "push" | "replace" = "push") => {
    const selectedAt = Date.now();
    setSelectedClientId?.(tab.clientId);
    setSelectedProjectPath?.(tab.projectPath);
    setSelectedProjectBrowseRoot?.(tab.browseRoot);
    setSelectedProjectFile(projectFileEntryForTab(tab));
    setSelectedProjectFileLine(tab.line);
    setWorkspaceMode?.("files");
    setProjectFileTabsState((currentState) => selectProjectFileTab(currentState, tab.key, selectedAt));
    writeProjectFileRoute({
      clientId: tab.clientId,
      windowId: selectedWindowId,
      projectPath: tab.projectPath,
      browseRoot: tab.browseRoot,
      path: tab.path,
      line: tab.line,
    }, mode);
  }, [
    selectedWindowId,
    setProjectFileTabsState,
    setSelectedClientId,
    setSelectedProjectBrowseRoot,
    setSelectedProjectFile,
    setSelectedProjectFileLine,
    setSelectedProjectPath,
    setWorkspaceMode,
  ]);

  const closeTab = useCallback((key: string) => {
    if (context === null) {
      return;
    }
    const result = closeProjectFileTab(projectFileTabsState, key, context, Date.now());
    const closedActiveTab = projectFileTabsState.activeKey === key;
    setProjectFileTabsState(result.state);
    if (!closedActiveTab) {
      return;
    }
    if (result.nextActiveTab !== null) {
      setSelectedProjectFile(projectFileEntryForTab(result.nextActiveTab));
      setSelectedProjectFileLine(result.nextActiveTab.line);
      writeProjectFileRoute({
        clientId: result.nextActiveTab.clientId,
        windowId: selectedWindowId,
        projectPath: result.nextActiveTab.projectPath,
        browseRoot: result.nextActiveTab.browseRoot,
        path: result.nextActiveTab.path,
        line: result.nextActiveTab.line,
      }, "push");
      return;
    }
    setSelectedProjectFile(null);
    setSelectedProjectFileLine(null);
    writeProjectFilesRoute({
      clientId: context.clientId,
      windowId: selectedWindowId,
      projectPath: context.projectPath,
      browseRoot: context.browseRoot,
    }, "push");
  }, [
    context,
    projectFileTabsState,
    selectedWindowId,
    setProjectFileTabsState,
    setSelectedProjectFile,
    setSelectedProjectFileLine,
  ]);

  const switchToNextTab = useCallback(() => {
    const tab = nextProjectFileTab(projectFileTabsState, context, activeKey);
    if (tab !== null) {
      activateTab(tab);
    }
  }, [activateTab, activeKey, context, projectFileTabsState]);

  return {
    activeKey,
    activateTab,
    closeTab,
    context,
    openCurrentTab,
    rememberTab,
    switchToNextTab,
    visibleTabs,
  };
}
