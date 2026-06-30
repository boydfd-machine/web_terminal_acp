import { useEffect, useState } from "react";

import type { Client, ProjectFileEntry } from "../types";
import type { DetailContext, ProjectTodoFocusRequest, TerminalRouteSelection, WorkspaceMode } from "../appState";
import {
  readProjectTodoRouteRequest,
  type ProjectTodoRouteRequest,
} from "../projectTodoLinks";

type UseProjectTodoRouteRequestsArgs = {
  clients: Client[] | undefined;
  setAgentRecordModalOpen: (open: boolean) => void;
  setClientsCollapsed: (collapsed: boolean) => void;
  setDeferredTreeSelection: (selection: TerminalRouteSelection | null) => void;
  setDetailContext: (context: DetailContext) => void;
  setMobileTerminalActive: (active: boolean) => void;
  setProjectListCollapsed: (collapsed: boolean) => void;
  setProjectTodoFocusRequest: (request: ProjectTodoFocusRequest | null) => void;
  setRouteSelectionRequest: (selection: TerminalRouteSelection | null) => void;
  setSelectedClientId: (clientId: string) => void;
  setSelectedProjectBrowseRoot: (browseRoot: string | null) => void;
  setSelectedProjectFile: (file: ProjectFileEntry | null) => void;
  setSelectedProjectFileLine: (line: null) => void;
  setSelectedProjectPath: (projectPath: string) => void;
  setSelectedWindowId: (windowId: string | null) => void;
  setTerminalControlsOpen: (open: boolean) => void;
  setWorkspaceMode: (mode: WorkspaceMode) => void;
};

export function useProjectTodoRouteRequests({
  clients,
  setAgentRecordModalOpen,
  setClientsCollapsed,
  setDeferredTreeSelection,
  setDetailContext,
  setMobileTerminalActive,
  setProjectListCollapsed,
  setProjectTodoFocusRequest,
  setRouteSelectionRequest,
  setSelectedClientId,
  setSelectedProjectBrowseRoot,
  setSelectedProjectFile,
  setSelectedProjectFileLine,
  setSelectedProjectPath,
  setSelectedWindowId,
  setTerminalControlsOpen,
  setWorkspaceMode,
}: UseProjectTodoRouteRequestsArgs) {
  const [pendingRequest, setPendingRequest] = useState<ProjectTodoRouteRequest | null>(readProjectTodoRouteRequest);

  useEffect(() => {
    const handlePopState = () => {
      setPendingRequest(readProjectTodoRouteRequest());
    };

    window.addEventListener("popstate", handlePopState);
    return () => window.removeEventListener("popstate", handlePopState);
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
    setSelectedProjectBrowseRoot(null);
    setSelectedProjectFile(null);
    setSelectedProjectFileLine(null);
    setWorkspaceMode("kanban");
    setDetailContext("project");
    setClientsCollapsed(false);
    setProjectListCollapsed(false);
    setTerminalControlsOpen(false);
    setMobileTerminalActive(false);
    setAgentRecordModalOpen(false);
    setProjectTodoFocusRequest(null);
    setPendingRequest(null);
  }, [
    clients,
    pendingRequest,
    setAgentRecordModalOpen,
    setClientsCollapsed,
    setDeferredTreeSelection,
    setDetailContext,
    setMobileTerminalActive,
    setProjectListCollapsed,
    setProjectTodoFocusRequest,
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
