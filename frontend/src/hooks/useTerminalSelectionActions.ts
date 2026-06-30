import { useCallback, useEffect, useState, type Dispatch, type SetStateAction } from "react";
import type { QueryClient } from "@tanstack/react-query";

import {
  readClientRecency,
  readClientWindowSelections,
  rememberClientRecency,
  writeClientRecency,
  writeClientWindowSelections,
  writeTerminalRoute,
  type ClientWindowSelections,
  type DetailContext,
  type TerminalRouteSelection,
  type WorkspaceMode,
} from "../appState";
import { recordTerminalRecent } from "../api";
import { projectPathForWindow } from "../terminalTree";
import {
  findTreeWindow,
  findWindowTitle,
} from "../terminalTreeSelection";
import type { TreeFolder } from "../types";

type UseTerminalSelectionActionsArgs = {
  focusSelectedTerminal: () => void;
  queryClient: QueryClient;
  selectedClientId: string | null;
  selectedWindowId: string | null;
  selectedWindowTitle: string | null;
  terminalSwitcherFolders: TreeFolder[] | undefined;
  treeFolders: TreeFolder[] | undefined;
  setAgentRecordModalOpen: (open: boolean) => void;
  setDeferredTreeSelection: (selection: TerminalRouteSelection | null) => void;
  setDetailContext: (context: DetailContext) => void;
  setDetailPanelOpen: (open: boolean) => void;
  setMobileTerminalActive: (active: boolean) => void;
  setRouteSelectionRequest: (selection: TerminalRouteSelection | null) => void;
  setSelectedClientId: (clientId: string | null) => void;
  setSelectedProjectBrowseRoot: (browseRoot: string | null) => void;
  setSelectedProjectPath: (projectPath: string | null) => void;
  setSelectedWindowId: (windowId: string | null) => void;
  setTerminalImmersive: (immersive: boolean) => void;
  setTerminalRecoveryIntent: (intent: { clientId: string; windowId: string; nonce: number } | null) => void;
  setWorkspaceMode: Dispatch<SetStateAction<WorkspaceMode>>;
};

export function useTerminalSelectionActions({
  focusSelectedTerminal,
  queryClient,
  selectedClientId,
  selectedWindowId,
  selectedWindowTitle,
  terminalSwitcherFolders,
  treeFolders,
  setAgentRecordModalOpen,
  setDeferredTreeSelection,
  setDetailContext,
  setDetailPanelOpen,
  setMobileTerminalActive,
  setRouteSelectionRequest,
  setSelectedClientId,
  setSelectedProjectBrowseRoot,
  setSelectedProjectPath,
  setSelectedWindowId,
  setTerminalImmersive,
  setTerminalRecoveryIntent,
  setWorkspaceMode,
}: UseTerminalSelectionActionsArgs) {
  const [clientWindowSelections, setClientWindowSelections] = useState<ClientWindowSelections>(
    readClientWindowSelections
  );
  const [recentClientIds, setRecentClientIds] = useState<string[]>(readClientRecency);

  const persistTerminalRecent = useCallback((clientId: string, windowId: string, title: string) => {
    void recordTerminalRecent(clientId, { window_id: windowId, title })
      .then(() => {
        queryClient.invalidateQueries({ queryKey: ["terminal-recents", clientId] });
        queryClient.invalidateQueries({ queryKey: ["terminal-recents", "global"] });
      })
      .catch(() => {});
  }, [queryClient]);

  const rememberClientWindowSelection = useCallback((clientId: string, windowId: string | null) => {
    setClientWindowSelections((currentSelections) => {
      const nextSelections = {
        ...currentSelections,
        [clientId]: { windowId, usedAt: Date.now() },
      };
      writeClientWindowSelections(nextSelections);
      return nextSelections;
    });
  }, []);

  const rememberClientUse = useCallback((clientId: string) => {
    setRecentClientIds((currentClientIds) => {
      const nextClientIds = rememberClientRecency(currentClientIds, clientId);
      writeClientRecency(nextClientIds);
      return nextClientIds;
    });
  }, []);

  const markTerminalRecoveryIntent = useCallback((clientId: string, windowId: string | null) => {
    if (windowId === null) {
      return;
    }
    setTerminalRecoveryIntent({ clientId, windowId, nonce: Date.now() });
  }, [setTerminalRecoveryIntent]);

  const selectClient = useCallback((clientId: string) => {
    const rememberedWindowId = clientWindowSelections[clientId]?.windowId ?? null;
    setRouteSelectionRequest(null);
    setDeferredTreeSelection(null);
    setSelectedClientId(clientId);
    setSelectedWindowId(rememberedWindowId);
    markTerminalRecoveryIntent(clientId, rememberedWindowId);
    setSelectedProjectBrowseRoot(null);
    setSelectedProjectPath(null);
    rememberClientUse(clientId);
    setMobileTerminalActive(false);
    setDetailPanelOpen(false);
    setTerminalImmersive(false);
    setAgentRecordModalOpen(false);
    setDetailContext("terminal");
    writeTerminalRoute(clientId, rememberedWindowId, "push");
  }, [
    clientWindowSelections,
    markTerminalRecoveryIntent,
    rememberClientUse,
    setAgentRecordModalOpen,
    setDeferredTreeSelection,
    setDetailContext,
    setDetailPanelOpen,
    setMobileTerminalActive,
    setRouteSelectionRequest,
    setSelectedClientId,
    setSelectedProjectBrowseRoot,
    setSelectedProjectPath,
    setSelectedWindowId,
    setTerminalImmersive,
  ]);

  const selectWindow = useCallback((windowId: string, clientId = selectedClientId) => {
    if (clientId === null) {
      return;
    }
    const selectingCurrentClient = clientId === selectedClientId;
    const selectedTitle = selectingCurrentClient && windowId === selectedWindowId
      ? findWindowTitle(treeFolders, windowId)
      : null;
    const nextWindowProjectPath = selectingCurrentClient
      ? projectPathForWindow(
          findTreeWindow(treeFolders, windowId)
          ?? findTreeWindow(terminalSwitcherFolders, windowId)
        )
      : null;
    if (selectedTitle !== null && selectingCurrentClient) {
      persistTerminalRecent(clientId, windowId, selectedTitle);
    }

    setRouteSelectionRequest(null);
    setDeferredTreeSelection(null);
    setSelectedClientId(clientId);
    setSelectedWindowId(windowId);
    markTerminalRecoveryIntent(clientId, windowId);
    setSelectedProjectBrowseRoot(null);
    setSelectedProjectPath(selectingCurrentClient ? nextWindowProjectPath : null);
    rememberClientUse(clientId);
    rememberClientWindowSelection(clientId, windowId);
    setDetailPanelOpen(false);
    setAgentRecordModalOpen(false);
    setDetailContext("terminal");
    setWorkspaceMode("terminal");
    writeTerminalRoute(clientId, windowId, "push");
    focusSelectedTerminal();
  }, [
    focusSelectedTerminal,
    persistTerminalRecent,
    rememberClientUse,
    rememberClientWindowSelection,
    markTerminalRecoveryIntent,
    selectedClientId,
    selectedWindowId,
    terminalSwitcherFolders,
    treeFolders,
    setAgentRecordModalOpen,
    setDeferredTreeSelection,
    setDetailContext,
    setDetailPanelOpen,
    setRouteSelectionRequest,
    setSelectedClientId,
    setSelectedProjectBrowseRoot,
    setSelectedProjectPath,
    setSelectedWindowId,
    setWorkspaceMode,
  ]);

  const selectProjectWindow = useCallback((windowId: string, projectPath: string, clientId = selectedClientId) => {
    if (clientId === null) {
      return;
    }

    setRouteSelectionRequest(null);
    setDeferredTreeSelection({ clientId, windowId });
    setSelectedClientId(clientId);
    setSelectedWindowId(windowId);
    markTerminalRecoveryIntent(clientId, windowId);
    setSelectedProjectBrowseRoot(null);
    setSelectedProjectPath(projectPath);
    rememberClientUse(clientId);
    rememberClientWindowSelection(clientId, windowId);
    setDetailPanelOpen(false);
    setMobileTerminalActive(true);
    setAgentRecordModalOpen(false);
    setDetailContext("terminal");
    setWorkspaceMode("terminal");
    writeTerminalRoute(clientId, windowId, "push");
    focusSelectedTerminal();
  }, [
    focusSelectedTerminal,
    rememberClientUse,
    rememberClientWindowSelection,
    markTerminalRecoveryIntent,
    selectedClientId,
    setAgentRecordModalOpen,
    setDeferredTreeSelection,
    setDetailContext,
    setDetailPanelOpen,
    setMobileTerminalActive,
    setRouteSelectionRequest,
    setSelectedClientId,
    setSelectedProjectBrowseRoot,
    setSelectedProjectPath,
    setSelectedWindowId,
    setWorkspaceMode,
  ]);

  const handleTerminalPaneSelection = useCallback((windowId: string) => {
    if (selectedClientId === null) {
      return;
    }
    if (windowId === selectedWindowId) {
      return;
    }

    setRouteSelectionRequest(null);
    setDeferredTreeSelection(null);
    setSelectedWindowId(windowId);
    markTerminalRecoveryIntent(selectedClientId, windowId);
    setSelectedProjectBrowseRoot(null);
    setSelectedProjectPath(
      projectPathForWindow(
        findTreeWindow(treeFolders, windowId)
        ?? findTreeWindow(terminalSwitcherFolders, windowId)
      )
    );
    setDetailContext("terminal");
    setWorkspaceMode("terminal");
    rememberClientUse(selectedClientId);
    rememberClientWindowSelection(selectedClientId, windowId);
    setAgentRecordModalOpen(false);
    writeTerminalRoute(selectedClientId, windowId, "replace");
  }, [
    rememberClientUse,
    rememberClientWindowSelection,
    markTerminalRecoveryIntent,
    selectedClientId,
    selectedWindowId,
    terminalSwitcherFolders,
    treeFolders,
    setAgentRecordModalOpen,
    setDeferredTreeSelection,
    setDetailContext,
    setRouteSelectionRequest,
    setSelectedProjectBrowseRoot,
    setSelectedProjectPath,
    setSelectedWindowId,
    setWorkspaceMode,
  ]);

  useEffect(() => {
    if (selectedClientId === null || selectedWindowId === null || selectedWindowTitle === null) {
      return;
    }

    rememberClientUse(selectedClientId);
    rememberClientWindowSelection(selectedClientId, selectedWindowId);
    persistTerminalRecent(selectedClientId, selectedWindowId, selectedWindowTitle);
  }, [
    persistTerminalRecent,
    rememberClientUse,
    rememberClientWindowSelection,
    selectedClientId,
    selectedWindowId,
    selectedWindowTitle,
  ]);

  return {
    clientWindowSelections,
    handleTerminalPaneSelection,
    persistTerminalRecent,
    recentClientIds,
    rememberClientUse,
    rememberClientWindowSelection,
    selectClient,
    selectProjectWindow,
    selectWindow,
    setClientWindowSelections,
    setRecentClientIds,
  };
}
