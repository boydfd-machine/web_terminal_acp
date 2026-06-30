import { useEffect, useState, type Dispatch, type SetStateAction } from "react";

import type { Client } from "../types";
import type { ProjectFileEntry } from "../types";
import type { DetailContext, TerminalRouteSelection, WorkspaceMode } from "../appState";
import {
  openProjectFileTab,
  projectFileTabKey,
  type ProjectFileTabsState,
} from "../projectFileTabs";
import {
  PROJECT_FILE_OPEN_EVENT,
  fileEntryForProjectPath,
  isProjectFileOpenEvent,
  readProjectFileRouteRequest,
  readProjectFilesRouteRequest,
  writeProjectFileRoute,
  type ProjectFilesRouteRequest,
  type ProjectFileOpenRequest,
} from "../projectFileLinks";

type UseProjectFileOpenRequestsArgs = {
  clients: Client[] | undefined;
  selectedClientId: string | null;
  selectedProjectBrowseRoot: string | null;
  selectedProjectFileLine: number | null;
  selectedProjectFilePath: string | null;
  selectedProjectPath: string | null;
  projectFileTabsState: ProjectFileTabsState;
  selectedWindowId: string | null;
  setAgentRecordModalOpen: (open: boolean) => void;
  setClientsCollapsed: (collapsed: boolean) => void;
  setDeferredTreeSelection: (selection: TerminalRouteSelection | null) => void;
  setDetailContext: (context: DetailContext) => void;
  setMobileTerminalActive: (active: boolean) => void;
  setProjectListCollapsed: (collapsed: boolean) => void;
  setProjectFileTabsState: Dispatch<SetStateAction<ProjectFileTabsState>>;
  setRouteSelectionRequest: (selection: TerminalRouteSelection | null) => void;
  setSelectedClientId: (clientId: string) => void;
  setSelectedProjectBrowseRoot: (browseRoot: string | null) => void;
  setSelectedProjectFile: (file: ProjectFileEntry | null) => void;
  setSelectedProjectFileLine: (line: number | null) => void;
  setSelectedProjectPath: (projectPath: string) => void;
  setSelectedWindowId: (windowId: string | null) => void;
  setTerminalControlsOpen: (open: boolean) => void;
  setWorkspaceMode: (mode: WorkspaceMode) => void;
};

export function useProjectFileOpenRequests({
  clients,
  selectedClientId,
  selectedProjectBrowseRoot,
  selectedProjectFileLine,
  selectedProjectFilePath,
  selectedProjectPath,
  projectFileTabsState,
  selectedWindowId,
  setAgentRecordModalOpen,
  setClientsCollapsed,
  setDeferredTreeSelection,
  setDetailContext,
  setMobileTerminalActive,
  setProjectListCollapsed,
  setProjectFileTabsState,
  setRouteSelectionRequest,
  setSelectedClientId,
  setSelectedProjectBrowseRoot,
  setSelectedProjectFile,
  setSelectedProjectFileLine,
  setSelectedProjectPath,
  setSelectedWindowId,
  setTerminalControlsOpen,
  setWorkspaceMode,
}: UseProjectFileOpenRequestsArgs) {
  const [pendingRequest, setPendingRequest] = useState<ProjectFileOpenRequest | ProjectFilesRouteRequest | null>(() => (
    readProjectFileRouteRequest() ?? readProjectFilesRouteRequest()
  ));

  useEffect(() => {
    const handleOpenRequest = (event: Event) => {
      if (!isProjectFileOpenEvent(event)) {
        return;
      }
      writeProjectFileRoute(event.detail, "push");
      setPendingRequest(event.detail);
    };
    const handlePopState = () => {
      setPendingRequest(readProjectFileRouteRequest() ?? readProjectFilesRouteRequest());
    };

    window.addEventListener(PROJECT_FILE_OPEN_EVENT, handleOpenRequest);
    window.addEventListener("popstate", handlePopState);
    return () => {
      window.removeEventListener(PROJECT_FILE_OPEN_EVENT, handleOpenRequest);
      window.removeEventListener("popstate", handlePopState);
    };
  }, []);

  useEffect(() => {
    if (pendingRequest === null || clients === undefined) {
      return;
    }
    if (!clients.some((client) => client.id === pendingRequest.clientId)) {
      setPendingRequest(null);
      return;
    }

    setRouteSelectionRequest(null);
    setDeferredTreeSelection(null);
    setSelectedClientId(pendingRequest.clientId);
    setSelectedWindowId(pendingRequest.windowId);
    setSelectedProjectPath(pendingRequest.projectPath);
    setSelectedProjectBrowseRoot(pendingRequest.browseRoot);
    const requestedEntry = "path" in pendingRequest ? fileEntryForProjectPath(pendingRequest.path) : null;
    setSelectedProjectFile(requestedEntry);
    setSelectedProjectFileLine("path" in pendingRequest ? pendingRequest.line : null);
    if (requestedEntry !== null) {
      const requestedKey = projectFileTabKey({
        clientId: pendingRequest.clientId,
        projectPath: pendingRequest.projectPath,
        browseRoot: pendingRequest.browseRoot,
      }, requestedEntry.path);
      if (
        projectFileTabsState.activeKey !== requestedKey
        || !projectFileTabsState.tabs.some((tab) => tab.key === requestedKey)
      ) {
        setProjectFileTabsState((currentState) => openProjectFileTab(
          currentState,
          {
            clientId: pendingRequest.clientId,
            projectPath: pendingRequest.projectPath,
            browseRoot: pendingRequest.browseRoot,
          },
          requestedEntry,
          "path" in pendingRequest ? pendingRequest.line : null,
          Date.now()
        ));
      }
    }
    setWorkspaceMode("files");
    setDetailContext("project");
    setClientsCollapsed(true);
    setProjectListCollapsed(true);
    setTerminalControlsOpen(false);
    setMobileTerminalActive(false);
    setAgentRecordModalOpen(false);

    if (
      selectedClientId === pendingRequest.clientId
      && selectedWindowId === pendingRequest.windowId
      && selectedProjectPath === pendingRequest.projectPath
      && selectedProjectBrowseRoot === pendingRequest.browseRoot
      && (!("path" in pendingRequest) || selectedProjectFilePath === pendingRequest.path)
      && (!("path" in pendingRequest) || selectedProjectFileLine === pendingRequest.line)
    ) {
      setPendingRequest(null);
    }
  }, [
    clients,
    pendingRequest,
    selectedClientId,
    selectedProjectBrowseRoot,
    selectedProjectFileLine,
    selectedProjectFilePath,
    selectedProjectPath,
    projectFileTabsState,
    selectedWindowId,
    setAgentRecordModalOpen,
    setClientsCollapsed,
    setDeferredTreeSelection,
    setDetailContext,
    setMobileTerminalActive,
    setProjectListCollapsed,
    setProjectFileTabsState,
    setRouteSelectionRequest,
    setSelectedClientId,
    setSelectedProjectBrowseRoot,
    setSelectedProjectFile,
    setSelectedProjectFileLine,
    setSelectedProjectPath,
    setSelectedWindowId,
    setTerminalControlsOpen,
    setWorkspaceMode,
  ]);
}
