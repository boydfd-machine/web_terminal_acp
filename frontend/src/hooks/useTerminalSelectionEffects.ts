import { useEffect, useRef } from "react";

import type {
  ClientWindowSelections,
  DetailContext,
  TerminalRouteSelection,
  WorkspaceMode,
} from "../appState";
import { readTerminalRouteSelection, workspaceModeFromUrl, writeTerminalRoute } from "../appState";
import {
  readProjectFileRouteRequest,
  writeProjectFileRoute,
  writeProjectFilesRoute,
} from "../projectFileLinks";
import { readProjectTodoRouteRequest, writeProjectTodoRoute } from "../projectTodoLinks";
import {
  flattenTreeWindows,
  firstProjectPath,
  projectListContains,
  projectPathForWindow,
} from "../terminalTree";
import {
  treeContainsWindow,
} from "../terminalTreeSelection";
import type {
  Client,
  TerminalProject,
  TreeFolder,
} from "../types";

type ProjectPathSourceWindow = {
  cwd?: string | null;
  git_worktree?: {
    main_repo_root: string;
    worktree_root: string;
  } | null;
  runtime_tags?: string[] | null;
};

type UseTerminalSelectionEffectsArgs = {
  clientWindowSelections: ClientWindowSelections;
  clients: Client[] | undefined;
  deferredTreeSelection: TerminalRouteSelection | null;
  isMobileLayout: boolean;
  rememberClientUse: (clientId: string) => void;
  rememberClientWindowSelection: (clientId: string, windowId: string | null) => void;
  routeSelectionRequest: TerminalRouteSelection | null;
  selectedClientId: string | null;
  selectedProjectBrowseRoot: string | null;
  selectedProjectFileLine: number | null;
  selectedProjectFilePath: string | null;
  selectedProjectPath: string | null;
  selectedWindow: ProjectPathSourceWindow | null;
  selectedWindowId: string | null;
  terminalProjects: TerminalProject[];
  terminalProjectsReady: boolean;
  treeFolders: TreeFolder[] | undefined;
  treeFetching: boolean;
  setAgentRecordModalOpen: (open: boolean) => void;
  setDeferredTreeSelection: (selection: TerminalRouteSelection | null) => void;
  setDetailContext: (context: DetailContext) => void;
  setMobileTerminalActive: (active: boolean) => void;
  setRouteSelectionRequest: (selection: TerminalRouteSelection | null) => void;
  setSelectedClientId: (clientId: string | null) => void;
  setSelectedProjectFile: (file: null) => void;
  setSelectedProjectFileLine: (line: null) => void;
  setSelectedProjectBrowseRoot: (browseRoot: string | null) => void;
  setSelectedProjectPath: (path: string | null | ((path: string | null) => string | null)) => void;
  setSelectedWindowId: (windowId: string | null) => void;
  setWorkspaceMode: (mode: WorkspaceMode) => void;
  workspaceMode: WorkspaceMode;
};

function writeRouteForSyncedProjectWindow({
  browseRoot,
  clientId,
  fileLine,
  filePath,
  projectPath,
  windowId,
  workspaceMode,
}: {
  browseRoot: string | null;
  clientId: string;
  fileLine: number | null;
  filePath: string | null;
  projectPath: string;
  windowId: string | null;
  workspaceMode: WorkspaceMode;
}) {
  if (workspaceMode === "terminal") {
    writeTerminalRoute(clientId, windowId, "replace");
    return;
  }

  if (workspaceMode === "files") {
    if (filePath !== null) {
      writeProjectFileRoute({ clientId, windowId, projectPath, browseRoot, path: filePath, line: fileLine }, "replace");
      return;
    }
    writeProjectFilesRoute({ clientId, windowId, projectPath, browseRoot }, "replace");
    return;
  }

  const currentTodoRoute = readProjectTodoRouteRequest();
  const todoId = currentTodoRoute?.clientId === clientId && currentTodoRoute.projectPath === projectPath
    ? currentTodoRoute.todoId
    : null;
  writeProjectTodoRoute({ clientId, windowId, projectPath, todoId }, "replace");
}

export function useTerminalSelectionEffects({
  clientWindowSelections,
  clients,
  deferredTreeSelection,
  isMobileLayout,
  rememberClientUse,
  rememberClientWindowSelection,
  routeSelectionRequest,
  selectedClientId,
  selectedProjectBrowseRoot,
  selectedProjectFileLine,
  selectedProjectFilePath,
  selectedProjectPath,
  selectedWindow,
  selectedWindowId,
  terminalProjects,
  terminalProjectsReady,
  treeFolders,
  treeFetching,
  setAgentRecordModalOpen,
  setDeferredTreeSelection,
  setDetailContext,
  setMobileTerminalActive,
  setRouteSelectionRequest,
  setSelectedClientId,
  setSelectedProjectFile,
  setSelectedProjectFileLine,
  setSelectedProjectBrowseRoot,
  setSelectedProjectPath,
  setSelectedWindowId,
  setWorkspaceMode,
  workspaceMode,
}: UseTerminalSelectionEffectsArgs) {
  const selectedProjectFilePathRef = useRef(selectedProjectFilePath);
  selectedProjectFilePathRef.current = selectedProjectFilePath;

  useEffect(() => {
    const handlePopState = () => {
      if (workspaceModeFromUrl(`${window.location.pathname}${window.location.search}${window.location.hash}`) !== null) {
        return;
      }
      setRouteSelectionRequest(readTerminalRouteSelection());
    };

    window.addEventListener("popstate", handlePopState);
    return () => window.removeEventListener("popstate", handlePopState);
  }, [setRouteSelectionRequest]);

  useEffect(() => {
    if (!clients) {
      return;
    }

    if (clients.length === 0) {
      if (selectedClientId !== null) {
        setSelectedClientId(null);
        setSelectedWindowId(null);
        setSelectedProjectPath(null);
        setDeferredTreeSelection(null);
        setAgentRecordModalOpen(false);
        setDetailContext("terminal");
        writeTerminalRoute(null, null, "replace");
      }
      return;
    }

    if (routeSelectionRequest !== null) {
      const requestedClient = routeSelectionRequest.clientId === null
        ? null
        : clients.find((client) => client.id === routeSelectionRequest.clientId) ?? null;
      const currentClient = selectedClientId === null
        ? null
        : clients.find((client) => client.id === selectedClientId) ?? null;
      const nextClient = requestedClient ?? currentClient ?? clients.find((client) => client.runtime === "local") ?? clients[0];
      setSelectedClientId(nextClient.id);
      rememberClientUse(nextClient.id);
      const nextWindowId = requestedClient
        ? routeSelectionRequest.windowId
        : clientWindowSelections[nextClient.id]?.windowId ?? null;
      setSelectedWindowId(nextWindowId);
      setSelectedProjectPath(null);
      setDeferredTreeSelection(null);
      setAgentRecordModalOpen(false);
      setDetailContext("terminal");
      if (requestedClient === null && routeSelectionRequest.clientId !== null) {
        writeTerminalRoute(nextClient.id, nextWindowId, "replace");
      }
      setRouteSelectionRequest(null);
      return;
    }

    if (selectedClientId !== null && clients.some((client) => client.id === selectedClientId)) {
      return;
    }

    const preferredClient = clients.find((client) => client.runtime === "local") ?? clients[0];
    setSelectedClientId(preferredClient.id);
    rememberClientUse(preferredClient.id);
    setSelectedWindowId(clientWindowSelections[preferredClient.id]?.windowId ?? null);
    setSelectedProjectPath(null);
    setDeferredTreeSelection(null);
    setAgentRecordModalOpen(false);
    setDetailContext("terminal");
  }, [
    clientWindowSelections,
    clients,
    rememberClientUse,
    routeSelectionRequest,
    selectedClientId,
    setAgentRecordModalOpen,
    setDeferredTreeSelection,
    setDetailContext,
    setRouteSelectionRequest,
    setSelectedClientId,
    setSelectedProjectPath,
    setSelectedWindowId,
  ]);

  useEffect(() => {
    const projectFileRouteRequest = readProjectFileRouteRequest();
    if (
      projectFileRouteRequest !== null
      && projectFileRouteRequest.clientId === selectedClientId
      && projectFileRouteRequest.windowId === selectedWindowId
      && projectFileRouteRequest.projectPath === selectedProjectPath
      && projectFileRouteRequest.browseRoot === selectedProjectBrowseRoot
      && projectFileRouteRequest.path === selectedProjectFilePathRef.current
    ) {
      return;
    }
    setSelectedProjectFile(null);
    setSelectedProjectFileLine(null);
  }, [
    selectedClientId,
    selectedProjectBrowseRoot,
    selectedProjectPath,
    selectedWindowId,
    setSelectedProjectFile,
    setSelectedProjectFileLine,
  ]);

  useEffect(() => {
    if (selectedClientId === null) {
      setSelectedProjectBrowseRoot(null);
      setSelectedProjectPath(null);
    }
  }, [selectedClientId, setSelectedProjectBrowseRoot, setSelectedProjectPath]);

  useEffect(() => {
    if (!terminalProjectsReady) {
      return;
    }

    setSelectedProjectPath((currentProjectPath) => {
      if (workspaceMode !== "terminal" && currentProjectPath !== null) {
        return currentProjectPath;
      }

      if (projectListContains(terminalProjects, currentProjectPath)) {
        return currentProjectPath;
      }

      const selectedWindowProjectPath = projectPathForWindow(selectedWindow);
      if (projectListContains(terminalProjects, selectedWindowProjectPath)) {
        return selectedWindowProjectPath;
      }

      if (selectedWindowId !== null && selectedWindow === null) {
        return currentProjectPath;
      }

      return firstProjectPath(terminalProjects);
    });
  }, [
    selectedClientId,
    selectedWindow,
    selectedWindowId,
    workspaceMode,
    setSelectedProjectPath,
    terminalProjects,
    terminalProjectsReady,
  ]);

  useEffect(() => {
    if (
      deferredTreeSelection !== null &&
      deferredTreeSelection.clientId !== null &&
      deferredTreeSelection.windowId !== null &&
      selectedClientId === deferredTreeSelection.clientId &&
      selectedWindowId === deferredTreeSelection.windowId
    ) {
      if (!treeContainsWindow(treeFolders, selectedWindowId)) {
        return;
      }
      rememberClientWindowSelection(deferredTreeSelection.clientId, deferredTreeSelection.windowId);
      setDeferredTreeSelection(null);
    }

    if (
      routeSelectionRequest !== null ||
      selectedClientId === null ||
      selectedProjectPath === null ||
      treeFolders === undefined ||
      treeFetching ||
      !projectListContains(terminalProjects, selectedProjectPath)
    ) {
      return;
    }

    if (treeContainsWindow(treeFolders, selectedWindowId)) {
      return;
    }

    const nextWindowId = flattenTreeWindows(treeFolders)[0]?.id ?? null;
    if (nextWindowId === selectedWindowId) {
      setDeferredTreeSelection(null);
      setAgentRecordModalOpen(false);
      return;
    }

    setSelectedWindowId(nextWindowId);
    setDeferredTreeSelection(null);
    setAgentRecordModalOpen(false);
    rememberClientWindowSelection(selectedClientId, nextWindowId);
    writeRouteForSyncedProjectWindow({
      browseRoot: selectedProjectBrowseRoot,
      clientId: selectedClientId,
      fileLine: selectedProjectFileLine,
      filePath: selectedProjectFilePath,
      projectPath: selectedProjectPath,
      windowId: nextWindowId,
      workspaceMode,
    });
  }, [
    deferredTreeSelection,
    rememberClientWindowSelection,
    routeSelectionRequest,
    selectedClientId,
    selectedProjectBrowseRoot,
    selectedProjectFileLine,
    selectedProjectFilePath,
    selectedWindowId,
    selectedProjectPath,
    setAgentRecordModalOpen,
    setDeferredTreeSelection,
    setSelectedWindowId,
    terminalProjects,
    treeFetching,
    treeFolders,
    workspaceMode,
  ]);

  useEffect(() => {
    if (workspaceMode !== "terminal" && selectedProjectPath === null) {
      setWorkspaceMode("terminal");
      setDetailContext("terminal");
    }
  }, [selectedProjectPath, setDetailContext, setWorkspaceMode, workspaceMode]);

  useEffect(() => {
    if (!isMobileLayout || selectedClientId === null || selectedWindowId === null) {
      return;
    }

    const routeSelection = readTerminalRouteSelection();
    if (routeSelection.clientId === selectedClientId && routeSelection.windowId === selectedWindowId) {
      setMobileTerminalActive(true);
    }
  }, [isMobileLayout, selectedClientId, selectedWindowId, setMobileTerminalActive]);
}
