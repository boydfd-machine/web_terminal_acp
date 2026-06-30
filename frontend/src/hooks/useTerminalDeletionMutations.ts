import { useMutation, type QueryClient } from "@tanstack/react-query";

import {
  deleteClient,
  deleteWindow,
} from "../api";
import type {
  ClientWindowSelections,
  DetailContext,
  TerminalRouteSelection,
} from "../appState";
import {
  writeClientRecency,
  writeClientWindowSelections,
  writeTerminalRoute,
} from "../appState";
import type { TerminalNotificationsState } from "./useTerminalNotificationsState";

export type DeleteWindowVariables = {
  clientId: string;
  windowId: string;
  nextWindowId: string | null;
};

export type DeleteClientVariables = {
  clientId: string;
};

type UseTerminalDeletionMutationsArgs = {
  queryClient: QueryClient;
  rememberClientWindowSelection: (clientId: string, windowId: string | null) => void;
  selectedClientId: string | null;
  setAgentRecordModalOpen: (open: boolean) => void;
  setClientWindowSelections: (
    updater: (currentSelections: ClientWindowSelections) => ClientWindowSelections,
  ) => void;
  setDeferredTreeSelection: (selection: TerminalRouteSelection | null) => void;
  setDetailContext: (context: DetailContext) => void;
  setDetailPanelOpen: (open: boolean) => void;
  setMobileTerminalActive: (active: boolean) => void;
  setRecentClientIds: (updater: (clientIds: string[]) => string[]) => void;
  setRouteSelectionRequest: (selection: TerminalRouteSelection | null) => void;
  setSelectedClientId: (clientId: string | null) => void;
  setSelectedProjectPath: (projectPath: string | null) => void;
  setSelectedWindowId: (updater: string | null | ((windowId: string | null) => string | null)) => void;
  setTerminalImmersive: (immersive: boolean) => void;
  terminalNotificationsState: TerminalNotificationsState;
};

export function useTerminalDeletionMutations({
  queryClient,
  rememberClientWindowSelection,
  selectedClientId,
  setAgentRecordModalOpen,
  setClientWindowSelections,
  setDeferredTreeSelection,
  setDetailContext,
  setDetailPanelOpen,
  setMobileTerminalActive,
  setRecentClientIds,
  setRouteSelectionRequest,
  setSelectedClientId,
  setSelectedProjectPath,
  setSelectedWindowId,
  setTerminalImmersive,
  terminalNotificationsState,
}: UseTerminalDeletionMutationsArgs) {
  const deleteMutation = useMutation({
    mutationFn: ({ clientId, windowId }: DeleteWindowVariables) => deleteWindow(clientId, windowId),
    onSuccess: (_result, { clientId, windowId, nextWindowId }) => {
      queryClient.invalidateQueries({ queryKey: ["tree", clientId], exact: false });
      queryClient.invalidateQueries({ queryKey: ["terminal-projects", clientId], exact: false });
      queryClient.invalidateQueries({ queryKey: ["projects", clientId], exact: false });
      queryClient.invalidateQueries({ queryKey: ["window-activity", clientId], exact: false });
      queryClient.invalidateQueries({ queryKey: ["terminal-recents", "global"] });
      terminalNotificationsState.removeWindowNotifications(windowId);
      setSelectedWindowId((currentWindowId) => {
        if (currentWindowId !== windowId) {
          return currentWindowId;
        }

        setDeferredTreeSelection(null);
        setRouteSelectionRequest(null);
        rememberClientWindowSelection(clientId, nextWindowId);
        writeTerminalRoute(clientId, nextWindowId, "replace");
        if (nextWindowId === null) {
          setMobileTerminalActive(false);
          setDetailPanelOpen(false);
          setTerminalImmersive(false);
          setAgentRecordModalOpen(false);
        }
        return nextWindowId;
      });
    },
  });

  const deleteClientMutation = useMutation({
    mutationFn: ({ clientId }: DeleteClientVariables) => deleteClient(clientId),
    onSuccess: (_result, { clientId }) => {
      queryClient.removeQueries({ queryKey: ["tree", clientId], exact: false });
      queryClient.removeQueries({ queryKey: ["terminal-projects", clientId], exact: false });
      queryClient.removeQueries({ queryKey: ["projects", clientId], exact: false });
      queryClient.removeQueries({ queryKey: ["window-activity", clientId], exact: false });
      queryClient.removeQueries({ queryKey: ["terminal-notifications", clientId] });
      queryClient.removeQueries({ queryKey: ["terminal-recents", clientId] });
      queryClient.invalidateQueries({ queryKey: ["terminal-recents", "global"] });
      queryClient.removeQueries({ queryKey: ["project-summaries", clientId] });
      queryClient.invalidateQueries({ queryKey: ["clients"] });
      terminalNotificationsState.removeClientNotifications(clientId);
      setClientWindowSelections((currentSelections) => {
        const nextSelections = { ...currentSelections };
        delete nextSelections[clientId];
        writeClientWindowSelections(nextSelections);
        return nextSelections;
      });
      setRecentClientIds((currentClientIds) => {
        const nextClientIds = currentClientIds.filter((candidate) => candidate !== clientId);
        writeClientRecency(nextClientIds);
        return nextClientIds;
      });
      if (selectedClientId !== clientId) {
        return;
      }

      setRouteSelectionRequest(null);
      setDeferredTreeSelection(null);
      setSelectedClientId(null);
      setSelectedWindowId(null);
      setSelectedProjectPath(null);
      setMobileTerminalActive(false);
      setDetailPanelOpen(false);
      setTerminalImmersive(false);
      setAgentRecordModalOpen(false);
      setDetailContext("terminal");
      writeTerminalRoute(null, null, "replace");
    },
  });

  return {
    deleteClientMutation,
    deleteMutation,
  };
}
