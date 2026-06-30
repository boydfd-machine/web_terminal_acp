import { useCallback } from "react";
import type { QueryClient } from "@tanstack/react-query";

import { agentDirectSubmitInput } from "../terminalQuickKeys";
import { useAppCommandActions } from "./useAppCommandActions";
import type { useAppUiState } from "./useAppUiState";
import type { useAuthenticatedAppQueries } from "./useAuthenticatedAppQueries";
import type { useAgentPreviewFollowups } from "./useAgentPreviewFollowups";
import type { useAgentRecordData } from "./useAgentRecordData";
import type { useTerminalNotificationsState } from "./useTerminalNotificationsState";
import type { useAuxTerminalWindow } from "./useAuxTerminalWindow";
import { useOnboardingActions } from "./useOnboardingActions";
import { useTerminalArtifactDrawer } from "./useTerminalArtifactDrawer";
import { useTerminalCreateActions } from "./useTerminalCreateActions";
import { useTerminalCreationMutations } from "./useTerminalCreationMutations";
import { useTerminalDeleteActions } from "./useTerminalDeleteActions";
import { useTerminalDeletionMutations } from "./useTerminalDeletionMutations";
import { useProjectFileOpenRequests } from "./useProjectFileOpenRequests";
import { useProjectTodoRouteRequests } from "./useProjectTodoRouteRequests";
import { useTerminalNotificationActions } from "./useTerminalNotificationActions";
import { useTerminalSelectionActions } from "./useTerminalSelectionActions";
import { useTerminalSelectionEffects } from "./useTerminalSelectionEffects";

type EnsureAuxTerminalReady = (variables: { clientId: string; windowId: string }) => void;

type UseAppDomainControllerArgs = {
  auxTerminalWindow: ReturnType<typeof useAuxTerminalWindow>;
  agentRecordModal: ReturnType<typeof useAgentRecordData>;
  ensureAuxTerminalReady: EnsureAuxTerminalReady;
  focusSelectedTerminal: () => void;
  isMobileLayout: boolean;
  queryClient: QueryClient;
  queries: ReturnType<typeof useAuthenticatedAppQueries>;
  scheduleAgentPreviewFollowupSubmits: ReturnType<typeof useAgentPreviewFollowups>["scheduleAgentPreviewFollowupSubmits"];
  terminalNotificationsState: ReturnType<typeof useTerminalNotificationsState>;
  toggleTerminalSwitcherMode: () => void;
  ui: ReturnType<typeof useAppUiState>;
};

export function useAppDomainController({
  auxTerminalWindow,
  agentRecordModal,
  ensureAuxTerminalReady,
  focusSelectedTerminal,
  isMobileLayout,
  queryClient,
  queries,
  scheduleAgentPreviewFollowupSubmits,
  terminalNotificationsState,
  toggleTerminalSwitcherMode,
  ui,
}: UseAppDomainControllerArgs) {
  const selection = useTerminalSelectionActions({
    focusSelectedTerminal,
    queryClient,
    selectedClientId: ui.selectedClientId,
    selectedWindowId: ui.selectedWindowId,
    selectedWindowTitle: queries.selectedWindowTitle,
    terminalSwitcherFolders: queries.terminalSwitcherFolders,
    treeFolders: queries.treeFolders,
    setAgentRecordModalOpen: ui.setAgentRecordModalOpen,
    setDeferredTreeSelection: ui.setDeferredTreeSelection,
    setDetailContext: ui.setDetailContext,
    setDetailPanelOpen: ui.setDetailPanelOpen,
    setMobileTerminalActive: ui.setMobileTerminalActive,
    setRouteSelectionRequest: ui.setRouteSelectionRequest,
    setSelectedClientId: ui.setSelectedClientId,
    setSelectedProjectBrowseRoot: ui.setSelectedProjectBrowseRoot,
    setSelectedProjectPath: ui.setSelectedProjectPath,
    setSelectedWindowId: ui.setSelectedWindowId,
    setTerminalImmersive: ui.setTerminalImmersive,
    setTerminalRecoveryIntent: ui.setTerminalRecoveryIntent,
    setWorkspaceMode: ui.setWorkspaceMode,
  });

  const notificationActions = useTerminalNotificationActions({
    focusSelectedTerminal,
    rememberClientUse: selection.rememberClientUse,
    rememberClientWindowSelection: selection.rememberClientWindowSelection,
    selectedClientId: ui.selectedClientId,
    terminalNotificationsState,
    setAgentRecordModalOpen: ui.setAgentRecordModalOpen,
    setDeferredTreeSelection: ui.setDeferredTreeSelection,
    setDetailContext: ui.setDetailContext,
    setDetailPanelOpen: ui.setDetailPanelOpen,
    setMobileTerminalActive: ui.setMobileTerminalActive,
    setNotificationCenterOpen: ui.setNotificationCenterOpen,
    setRouteSelectionRequest: ui.setRouteSelectionRequest,
    setSelectedClientId: ui.setSelectedClientId,
    setSelectedProjectBrowseRoot: ui.setSelectedProjectBrowseRoot,
    setSelectedProjectPath: ui.setSelectedProjectPath,
    setSelectedWindowId: ui.setSelectedWindowId,
    setWorkspaceMode: ui.setWorkspaceMode,
  });

  const onboardingActions = useOnboardingActions({
    selectedClientId: ui.selectedClientId,
    selectedClientOffline: queries.selectedClientOffline,
    selectedWindowId: ui.selectedWindowId,
    terminalPaneRef: ui.terminalPaneRef,
    setAddClientInitialMode: ui.setAddClientInitialMode,
    setAddClientModalOpen: ui.setAddClientModalOpen,
    setBootstrapFailed: ui.setBootstrapFailed,
    setDetailPanelOpen: ui.setDetailPanelOpen,
    setGitDiffBrowserOpen: ui.setGitDiffBrowserOpen,
    setMobileTerminalActive: ui.setMobileTerminalActive,
    setNotificationCenterOpen: ui.setNotificationCenterOpen,
    setProjectTerminalPickerOpen: ui.setProjectTerminalPickerOpen,
    setSettingsInitialView: ui.setSettingsInitialView,
    setSettingsOpen: ui.setSettingsOpen,
    setTerminalControlsOpen: ui.setTerminalControlsOpen,
    setTerminalCreateContext: ui.setTerminalCreateContext,
    setTerminalQuickInputOpen: ui.setTerminalQuickInputOpen,
    setTerminalSwitcherMode: ui.setTerminalSwitcherMode,
    setTerminalSwitcherOpen: ui.setTerminalSwitcherOpen,
    setTerminalSwitcherRecentScope: ui.setTerminalSwitcherRecentScope,
  });

  const drawer = useTerminalArtifactDrawer({
    artifactQuickOpenOpen: ui.artifactQuickOpenOpen,
    artifactTerminalCarrier: queries.artifactTerminalCarrier,
    artifactTerminalMonitorQuery: queries.artifactTerminalMonitorQuery,
    auxTerminalPaneRef: ui.auxTerminalPaneRef,
    auxTerminalWindowMetrics: auxTerminalWindow.layout.metrics,
    ensureAuxTerminalReady,
    focusSelectedTerminal,
    queryClient,
    selectedArtifactTerminalId: ui.selectedArtifactTerminalId,
    selectedClientId: ui.selectedClientId,
    selectedWindowId: ui.selectedWindowId,
    setAgentRecordModalOpen: ui.setAgentRecordModalOpen,
    setArtifactQuickOpenOpen: ui.setArtifactQuickOpenOpen,
    setClientSwitcherOpen: ui.setClientSwitcherOpen,
    setGitDiffBrowserOpen: ui.setGitDiffBrowserOpen,
    setNotificationCenterOpen: ui.setNotificationCenterOpen,
    setProjectTerminalPickerOpen: ui.setProjectTerminalPickerOpen,
    setSelectedArtifactTerminalId: ui.setSelectedArtifactTerminalId,
    setSettingsOpen: ui.setSettingsOpen,
    setTerminalControlsOpen: ui.setTerminalControlsOpen,
    setTerminalSwitcherOpen: ui.setTerminalSwitcherOpen,
  });

  const submitAgentPreviewQuickInput = useCallback((draft: string) => {
    if (draft.length === 0) {
      return false;
    }

    const submitted = ui.terminalPaneRef.current?.submitQuickInput(
      `${draft}${agentDirectSubmitInput(queries.selectedWindowRuntimeTags)}`
    ) ?? false;
    if (submitted) {
      scheduleAgentPreviewFollowupSubmits(queries.selectedWindowRuntimeTags);
    }
    return submitted;
  }, [queries.selectedWindowRuntimeTags, scheduleAgentPreviewFollowupSubmits, ui.terminalPaneRef]);

  const creation = useTerminalCreationMutations({
    focusSelectedTerminal,
    persistTerminalRecent: selection.persistTerminalRecent,
    queryClient,
    rememberClientUse: selection.rememberClientUse,
    rememberClientWindowSelection: selection.rememberClientWindowSelection,
    setAgentRecordModalOpen: ui.setAgentRecordModalOpen,
    setDeferredTreeSelection: ui.setDeferredTreeSelection,
    setDetailContext: ui.setDetailContext,
    setMobileTerminalActive: ui.setMobileTerminalActive,
    setPendingTerminalCreateSurfaceClosed: () => {
      ui.setProjectTerminalPickerOpen(false);
      ui.setTerminalCreateContext(null);
    },
    setRouteSelectionRequest: ui.setRouteSelectionRequest,
    setSelectedClientId: ui.setSelectedClientId,
    setSelectedProjectPath: ui.setSelectedProjectPath,
    setSelectedWindowId: ui.setSelectedWindowId,
    setTerminalControlsOpen: ui.setTerminalControlsOpen,
  });

  const deletion = useTerminalDeletionMutations({
    queryClient,
    rememberClientWindowSelection: selection.rememberClientWindowSelection,
    selectedClientId: ui.selectedClientId,
    setAgentRecordModalOpen: ui.setAgentRecordModalOpen,
    setClientWindowSelections: selection.setClientWindowSelections,
    setDeferredTreeSelection: ui.setDeferredTreeSelection,
    setDetailContext: ui.setDetailContext,
    setDetailPanelOpen: ui.setDetailPanelOpen,
    setMobileTerminalActive: ui.setMobileTerminalActive,
    setRecentClientIds: selection.setRecentClientIds,
    setRouteSelectionRequest: ui.setRouteSelectionRequest,
    setSelectedClientId: ui.setSelectedClientId,
    setSelectedProjectPath: ui.setSelectedProjectPath,
    setSelectedWindowId: ui.setSelectedWindowId,
    setTerminalImmersive: ui.setTerminalImmersive,
    terminalNotificationsState,
  });

  const deleteActions = useTerminalDeleteActions({
    deleteClientMutation: deletion.deleteClientMutation,
    deleteMutation: deletion.deleteMutation,
    selectedClientId: ui.selectedClientId,
    selectedWindowId: ui.selectedWindowId,
    selectedWindowTitle: queries.selectedWindowTitle,
    treeFolders: queries.treeFolders,
    setTerminalControlsOpen: ui.setTerminalControlsOpen,
    setUpdateFailed: ui.setUpdateFailed,
    setUpdateMessage: ui.setUpdateMessage,
  });

  useTerminalSelectionEffects({
    clientWindowSelections: selection.clientWindowSelections,
    clients: queries.clientsQuery.data,
    deferredTreeSelection: ui.deferredTreeSelection,
    isMobileLayout,
    rememberClientUse: selection.rememberClientUse,
    rememberClientWindowSelection: selection.rememberClientWindowSelection,
    routeSelectionRequest: ui.routeSelectionRequest,
    selectedClientId: ui.selectedClientId,
    selectedProjectBrowseRoot: ui.selectedProjectBrowseRoot,
    selectedProjectFileLine: ui.selectedProjectFileLine,
    selectedProjectFilePath: ui.selectedProjectFile?.path ?? null,
    selectedProjectPath: ui.selectedProjectPath,
    selectedWindow: queries.selectedWindow,
    selectedWindowId: ui.selectedWindowId,
    terminalProjects: queries.terminalProjects,
    terminalProjectsReady: queries.terminalProjectsQuery.isSuccess,
    treeFetching: queries.treeQuery.isFetching,
    treeFolders: queries.treeFolders,
    workspaceMode: ui.workspaceMode,
    setAgentRecordModalOpen: ui.setAgentRecordModalOpen,
    setDeferredTreeSelection: ui.setDeferredTreeSelection,
    setDetailContext: ui.setDetailContext,
    setMobileTerminalActive: ui.setMobileTerminalActive,
    setRouteSelectionRequest: ui.setRouteSelectionRequest,
    setSelectedClientId: ui.setSelectedClientId,
    setSelectedProjectFile: ui.setSelectedProjectFile,
    setSelectedProjectFileLine: ui.setSelectedProjectFileLine,
    setSelectedProjectBrowseRoot: ui.setSelectedProjectBrowseRoot,
    setSelectedProjectPath: ui.setSelectedProjectPath,
    setSelectedWindowId: ui.setSelectedWindowId,
    setWorkspaceMode: ui.setWorkspaceMode,
  });

  useProjectFileOpenRequests({
    clients: queries.clientsQuery.data,
    selectedClientId: ui.selectedClientId,
    selectedProjectBrowseRoot: ui.selectedProjectBrowseRoot,
    selectedProjectFileLine: ui.selectedProjectFileLine,
    selectedProjectFilePath: ui.selectedProjectFile?.path ?? null,
    selectedProjectPath: ui.selectedProjectPath,
    projectFileTabsState: ui.projectFileTabsState,
    selectedWindowId: ui.selectedWindowId,
    setAgentRecordModalOpen: ui.setAgentRecordModalOpen,
    setClientsCollapsed: ui.setClientsCollapsed,
    setDeferredTreeSelection: ui.setDeferredTreeSelection,
    setDetailContext: ui.setDetailContext,
    setMobileTerminalActive: ui.setMobileTerminalActive,
    setProjectListCollapsed: ui.setProjectListCollapsed,
    setProjectFileTabsState: ui.setProjectFileTabsState,
    setRouteSelectionRequest: ui.setRouteSelectionRequest,
    setSelectedClientId: ui.setSelectedClientId,
    setSelectedProjectBrowseRoot: ui.setSelectedProjectBrowseRoot,
    setSelectedProjectFile: ui.setSelectedProjectFile,
    setSelectedProjectFileLine: ui.setSelectedProjectFileLine,
    setSelectedProjectPath: ui.setSelectedProjectPath,
    setSelectedWindowId: ui.setSelectedWindowId,
    setTerminalControlsOpen: ui.setTerminalControlsOpen,
    setWorkspaceMode: ui.setWorkspaceMode,
  });

  useProjectTodoRouteRequests({
    clients: queries.clientsQuery.data,
    setAgentRecordModalOpen: ui.setAgentRecordModalOpen,
    setClientsCollapsed: ui.setClientsCollapsed,
    setDeferredTreeSelection: ui.setDeferredTreeSelection,
    setDetailContext: ui.setDetailContext,
    setMobileTerminalActive: ui.setMobileTerminalActive,
    setProjectListCollapsed: ui.setProjectListCollapsed,
    setProjectTodoFocusRequest: ui.setProjectTodoFocusRequest,
    setRouteSelectionRequest: ui.setRouteSelectionRequest,
    setSelectedClientId: ui.setSelectedClientId,
    setSelectedProjectBrowseRoot: ui.setSelectedProjectBrowseRoot,
    setSelectedProjectFile: ui.setSelectedProjectFile,
    setSelectedProjectFileLine: ui.setSelectedProjectFileLine,
    setSelectedProjectPath: ui.setSelectedProjectPath,
    setSelectedWindowId: ui.setSelectedWindowId,
    setTerminalControlsOpen: ui.setTerminalControlsOpen,
    setWorkspaceMode: ui.setWorkspaceMode,
  });

  const terminalCreateActions = useTerminalCreateActions({
    createMutation: creation.createMutation,
    selectedClientId: ui.selectedClientId,
    selectedClientOffline: queries.selectedClientOffline,
    terminalCreateBusy: creation.terminalCreateBusy,
    terminalCreateContext: ui.terminalCreateContext,
    setProjectTerminalPickerOpen: ui.setProjectTerminalPickerOpen,
    setTerminalCreateContext: ui.setTerminalCreateContext,
    setTerminalSwitcherOpen: ui.setTerminalSwitcherOpen,
  });

  const commandActions = useAppCommandActions({
    agentRecordModal,
    cloneMutation: creation.cloneMutation,
    selectedClientId: ui.selectedClientId,
    selectedClientOffline: queries.selectedClientOffline,
    selectedWindow: queries.selectedWindow,
    selectedWindowId: ui.selectedWindowId,
    terminalCloneBusy: creation.terminalCloneBusy,
    terminalCreateBusy: creation.terminalCreateBusy,
    terminalSwitcherOpen: ui.terminalSwitcherOpen,
    terminalSwitcherRecentScope: ui.terminalSwitcherRecentScope,
    toggleTerminalSwitcherMode,
    setAgentRecordModalOpen: ui.setAgentRecordModalOpen,
    setClientSwitcherOpen: ui.setClientSwitcherOpen,
    setDetailPanelOpen: ui.setDetailPanelOpen,
    setGitDiffBrowserOpen: ui.setGitDiffBrowserOpen,
    setMobileTerminalActive: ui.setMobileTerminalActive,
    setNotificationCenterOpen: ui.setNotificationCenterOpen,
    setProjectTerminalPickerOpen: ui.setProjectTerminalPickerOpen,
    setSelectedProjectPath: ui.setSelectedProjectPath,
    setSettingsInitialView: ui.setSettingsInitialView,
    setSettingsOpen: ui.setSettingsOpen,
    setTerminalControlsOpen: ui.setTerminalControlsOpen,
    setTerminalCreateContext: ui.setTerminalCreateContext,
    setTerminalImmersive: ui.setTerminalImmersive,
    setTerminalListLocateSignal: ui.setTerminalListLocateSignal,
    setTerminalSwitcherMode: ui.setTerminalSwitcherMode,
    setTerminalSwitcherOpen: ui.setTerminalSwitcherOpen,
    setTerminalSwitcherRecentScope: ui.setTerminalSwitcherRecentScope,
    terminalPaneRef: ui.terminalPaneRef,
  });

  return {
    commandActions,
    creation,
    deletion,
    deleteActions,
    drawer,
    notificationActions,
    onboardingActions,
    selection,
    submitAgentPreviewQuickInput,
    terminalCreateActions,
  };
}
