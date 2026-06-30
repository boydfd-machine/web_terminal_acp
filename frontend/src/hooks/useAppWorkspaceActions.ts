import { useCallback, type Dispatch, type SetStateAction } from "react";

import {
  writeTerminalRoute,
  type DetailContext,
  type ProjectTodoCreationPendingRequest,
  type ProjectTodoFocusRequest,
  type TerminalRouteSelection,
  type WorkspaceMode,
} from "../appState";
import { preferredFilesProjectContext } from "../projectBrowseRoots";
import { writeProjectFilesRoute } from "../projectFileLinks";
import { writeProjectTodoRoute } from "../projectTodoLinks";
import { projectPathForWindow } from "../terminalTree";
import type { GitWorktreeActivity } from "../types";

type ProjectPathSourceWindow = {
  cwd?: string | null;
  git_worktree?: GitWorktreeActivity | null;
  runtime_tags?: string[] | null;
};

type UseAppWorkspaceActionsArgs = {
  auxTerminal: { setAuxTerminalOpen: (open: boolean) => void };
  selectedClientId: string | null;
  selectedProjectPath: string | null;
  selectedWindow: ProjectPathSourceWindow | null | undefined;
  selectedWindowId: string | null;
  setClientsCollapsed: (collapsed: boolean) => void;
  setDeferredTreeSelection: (selection: TerminalRouteSelection | null) => void;
  setDetailContext: (context: DetailContext) => void;
  setDetailPanelCollapsed: (collapsed: boolean) => void;
  setDetailPanelOpen: (open: boolean) => void;
  setMobileTerminalActive: (active: boolean) => void;
  setProjectListCollapsed: (collapsed: boolean) => void;
  setProjectTodoCreationPendingRequest: Dispatch<SetStateAction<ProjectTodoCreationPendingRequest | null>>;
  setProjectTodoFocusRequest: (request: ProjectTodoFocusRequest | null) => void;
  setRouteSelectionRequest: (selection: TerminalRouteSelection | null) => void;
  setSelectedProjectBrowseRoot: (browseRoot: string | null) => void;
  setSelectedProjectPath: (path: string | null) => void;
  setTerminalControlsOpen: (open: boolean) => void;
  setTerminalRecoveryIntent: (intent: { clientId: string; windowId: string; nonce: number } | null) => void;
  setWorkspaceMode: (mode: WorkspaceMode | ((mode: WorkspaceMode) => WorkspaceMode)) => void;
};

export function useAppWorkspaceActions({
  auxTerminal,
  selectedClientId,
  selectedProjectPath,
  selectedWindow,
  selectedWindowId,
  setClientsCollapsed,
  setDeferredTreeSelection,
  setDetailContext,
  setDetailPanelCollapsed,
  setDetailPanelOpen,
  setMobileTerminalActive,
  setProjectListCollapsed,
  setProjectTodoCreationPendingRequest,
  setProjectTodoFocusRequest,
  setRouteSelectionRequest,
  setSelectedProjectBrowseRoot,
  setSelectedProjectPath,
  setTerminalControlsOpen,
  setTerminalRecoveryIntent,
  setWorkspaceMode,
}: UseAppWorkspaceActionsArgs) {
  const markSelectedTerminalRecoveryIntent = useCallback(() => {
    if (selectedClientId === null || selectedWindowId === null) {
      return;
    }
    setTerminalRecoveryIntent({ clientId: selectedClientId, windowId: selectedWindowId, nonce: Date.now() });
  }, [selectedClientId, selectedWindowId, setTerminalRecoveryIntent]);

  const toggleWorkspaceMode = useCallback(() => {
    setWorkspaceMode((currentMode) => {
      const nextMode = currentMode === "terminal" ? "files" : "terminal";
      if (nextMode === "files") {
        const context = preferredFilesProjectContext(selectedWindow, selectedProjectPath);
        setSelectedProjectPath(context.projectPath);
        setSelectedProjectBrowseRoot(context.browseRoot);
        if (selectedClientId !== null && context.projectPath !== null) {
          writeProjectFilesRoute({
            clientId: selectedClientId,
            windowId: selectedWindowId,
            projectPath: context.projectPath,
            browseRoot: context.browseRoot,
          }, "push");
        }
        setClientsCollapsed(true);
        setProjectListCollapsed(true);
        setDetailContext("project");
        setTerminalControlsOpen(false);
        auxTerminal.setAuxTerminalOpen(false);
      } else {
        setDetailContext("terminal");
        markSelectedTerminalRecoveryIntent();
        writeTerminalRoute(selectedClientId, selectedWindowId, "push");
      }
      return nextMode;
    });
  }, [
    auxTerminal,
    markSelectedTerminalRecoveryIntent,
    selectedClientId,
    selectedProjectPath,
    selectedWindow,
    selectedWindowId,
    setClientsCollapsed,
    setDetailContext,
    setProjectListCollapsed,
    setSelectedProjectBrowseRoot,
    setSelectedProjectPath,
    setTerminalControlsOpen,
    setWorkspaceMode,
  ]);

  const selectWorkspaceMode = useCallback((nextMode: WorkspaceMode) => {
    if (nextMode === "terminal") {
      setWorkspaceMode("terminal");
      setDetailContext("terminal");
      markSelectedTerminalRecoveryIntent();
      writeTerminalRoute(selectedClientId, selectedWindowId, "push");
      return;
    }
    if (selectedClientId === null) {
      return;
    }
    if (nextMode === "files") {
      const context = preferredFilesProjectContext(selectedWindow, selectedProjectPath);
      if (context.projectPath === null) {
        return;
      }
      setSelectedProjectPath(context.projectPath);
      setSelectedProjectBrowseRoot(context.browseRoot);
      writeProjectFilesRoute({
        clientId: selectedClientId,
        windowId: selectedWindowId,
        projectPath: context.projectPath,
        browseRoot: context.browseRoot,
      }, "push");
    } else {
      const projectPath = selectedProjectPath ?? projectPathForWindow(selectedWindow);
      if (projectPath === null) {
        return;
      }
      setSelectedProjectPath(projectPath);
      setSelectedProjectBrowseRoot(null);
      setProjectTodoFocusRequest(null);
      writeProjectTodoRoute({ clientId: selectedClientId, windowId: selectedWindowId, projectPath, todoId: null }, "push");
    }
    setClientsCollapsed(nextMode === "files");
    setProjectListCollapsed(nextMode === "files");
    setDetailContext("project");
    setTerminalControlsOpen(false);
    auxTerminal.setAuxTerminalOpen(false);
    setWorkspaceMode(nextMode);
  }, [
    auxTerminal,
    markSelectedTerminalRecoveryIntent,
    selectedClientId,
    selectedProjectPath,
    selectedWindow,
    selectedWindowId,
    setClientsCollapsed,
    setDetailContext,
    setProjectListCollapsed,
    setProjectTodoFocusRequest,
    setSelectedProjectBrowseRoot,
    setSelectedProjectPath,
    setTerminalControlsOpen,
    setWorkspaceMode,
  ]);

  const openProjectTodoBoard = useCallback(() => {
    selectWorkspaceMode("kanban");
  }, [selectWorkspaceMode]);

  const focusProjectTodoCreation = useCallback((projectPath: string, title: string) => {
    if (selectedClientId === null) {
      return null;
    }
    const request: ProjectTodoCreationPendingRequest = {
      clientId: selectedClientId,
      projectPath,
      title,
      nonce: Date.now()
    };
    setRouteSelectionRequest(null);
    setDeferredTreeSelection(null);
    setSelectedProjectPath(projectPath);
    setSelectedProjectBrowseRoot(null);
    setProjectTodoFocusRequest(null);
    setProjectTodoCreationPendingRequest(request);
    if (selectedProjectPath !== projectPath || selectedProjectPath === null) {
      setDetailContext("project");
      setDetailPanelCollapsed(false);
      setDetailPanelOpen(true);
    }
    setMobileTerminalActive(false);
    setWorkspaceMode("kanban");
    writeProjectTodoRoute({ clientId: selectedClientId, windowId: selectedWindowId, projectPath, todoId: null }, "push");
    return request;
  }, [
    selectedClientId,
    selectedProjectPath,
    selectedWindowId,
    setDeferredTreeSelection,
    setDetailPanelCollapsed,
    setDetailContext,
    setDetailPanelOpen,
    setMobileTerminalActive,
    setProjectTodoCreationPendingRequest,
    setProjectTodoFocusRequest,
    setRouteSelectionRequest,
    setSelectedProjectBrowseRoot,
    setSelectedProjectPath,
    setWorkspaceMode,
  ]);

  const clearProjectTodoCreationPendingRequest = useCallback((request: ProjectTodoCreationPendingRequest) => {
    setProjectTodoCreationPendingRequest((current) => (
      current?.clientId === request.clientId
      && current.projectPath === request.projectPath
      && current.nonce === request.nonce
        ? null
        : current
    ));
  }, [setProjectTodoCreationPendingRequest]);

  const focusProjectTodo = useCallback((projectPath: string, todoId: string) => {
    if (selectedClientId === null) {
      return;
    }
    setRouteSelectionRequest(null);
    setDeferredTreeSelection(null);
    setSelectedProjectPath(projectPath);
    setSelectedProjectBrowseRoot(null);
    setProjectTodoCreationPendingRequest(null);
    setProjectTodoFocusRequest({ clientId: selectedClientId, projectPath, todoId, nonce: Date.now() });
    if (selectedProjectPath !== projectPath || selectedProjectPath === null) {
      setDetailContext("project");
      setDetailPanelCollapsed(false);
      setDetailPanelOpen(true);
    }
    setMobileTerminalActive(false);
    setWorkspaceMode("kanban");
    writeProjectTodoRoute({ clientId: selectedClientId, windowId: selectedWindowId, projectPath, todoId }, "push");
  }, [
    selectedClientId,
    selectedProjectPath,
    selectedWindowId,
    setDeferredTreeSelection,
    setDetailPanelCollapsed,
    setDetailContext,
    setDetailPanelOpen,
    setMobileTerminalActive,
    setProjectTodoCreationPendingRequest,
    setProjectTodoFocusRequest,
    setRouteSelectionRequest,
    setSelectedProjectBrowseRoot,
    setSelectedProjectPath,
    setWorkspaceMode,
  ]);

  return {
    clearProjectTodoCreationPendingRequest,
    focusProjectTodoCreation,
    focusProjectTodo,
    openProjectTodoBoard,
    selectWorkspaceMode,
    toggleWorkspaceMode,
  };
}
