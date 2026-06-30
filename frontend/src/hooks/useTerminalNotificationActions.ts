import { useCallback } from "react";

import {
  writeTerminalRoute,
  type DetailContext,
  type TerminalRouteSelection,
  type WorkspaceMode,
} from "../appState";
import type { TerminalNotification } from "../terminalNotifications";
import type { TerminalNotificationsState } from "./useTerminalNotificationsState";

type UseTerminalNotificationActionsArgs = {
  focusSelectedTerminal: () => void;
  rememberClientUse: (clientId: string) => void;
  rememberClientWindowSelection: (clientId: string, windowId: string | null) => void;
  selectedClientId: string | null;
  terminalNotificationsState: TerminalNotificationsState;
  setAgentRecordModalOpen: (open: boolean) => void;
  setDeferredTreeSelection: (selection: TerminalRouteSelection | null) => void;
  setDetailContext: (context: DetailContext) => void;
  setDetailPanelOpen: (open: boolean) => void;
  setMobileTerminalActive: (active: boolean) => void;
  setNotificationCenterOpen: (open: boolean) => void;
  setRouteSelectionRequest: (selection: TerminalRouteSelection | null) => void;
  setSelectedClientId: (clientId: string) => void;
  setSelectedProjectBrowseRoot: (browseRoot: string | null) => void;
  setSelectedProjectPath: (path: string | null) => void;
  setSelectedWindowId: (windowId: string) => void;
  setWorkspaceMode: (mode: WorkspaceMode) => void;
};

export function useTerminalNotificationActions({
  focusSelectedTerminal,
  rememberClientUse,
  rememberClientWindowSelection,
  selectedClientId,
  terminalNotificationsState,
  setAgentRecordModalOpen,
  setDeferredTreeSelection,
  setDetailContext,
  setDetailPanelOpen,
  setMobileTerminalActive,
  setNotificationCenterOpen,
  setRouteSelectionRequest,
  setSelectedClientId,
  setSelectedProjectBrowseRoot,
  setSelectedProjectPath,
  setSelectedWindowId,
  setWorkspaceMode,
}: UseTerminalNotificationActionsArgs) {
  const handleSelectNotification = useCallback((notification: TerminalNotification) => {
    terminalNotificationsState.markNotificationRead(notification);
    setNotificationCenterOpen(false);
    if (notification.clientId !== selectedClientId) {
      setRouteSelectionRequest(null);
      setDeferredTreeSelection(null);
      setSelectedClientId(notification.clientId);
    }
    setSelectedProjectBrowseRoot(null);
    setSelectedProjectPath(null);
    setDeferredTreeSelection(null);
    setSelectedWindowId(notification.windowId);
    rememberClientUse(notification.clientId);
    rememberClientWindowSelection(notification.clientId, notification.windowId);
    setDetailPanelOpen(false);
    setAgentRecordModalOpen(false);
    setMobileTerminalActive(true);
    setDetailContext("terminal");
    setWorkspaceMode("terminal");
    writeTerminalRoute(notification.clientId, notification.windowId, "push");
    focusSelectedTerminal();
  }, [
    focusSelectedTerminal,
    rememberClientUse,
    rememberClientWindowSelection,
    selectedClientId,
    setAgentRecordModalOpen,
    setDeferredTreeSelection,
    setDetailContext,
    setDetailPanelOpen,
    setMobileTerminalActive,
    setNotificationCenterOpen,
    setRouteSelectionRequest,
    setSelectedClientId,
    setSelectedProjectBrowseRoot,
    setSelectedProjectPath,
    setSelectedWindowId,
    setWorkspaceMode,
    terminalNotificationsState,
  ]);

  const handleDeleteNotification = useCallback((notification: TerminalNotification) => {
    terminalNotificationsState.deleteNotification(notification);
  }, [terminalNotificationsState]);

  const handleClearNotifications = useCallback(() => {
    terminalNotificationsState.clearNotifications();
  }, [terminalNotificationsState]);

  return {
    handleClearNotifications,
    handleDeleteNotification,
    handleSelectNotification,
  };
}
