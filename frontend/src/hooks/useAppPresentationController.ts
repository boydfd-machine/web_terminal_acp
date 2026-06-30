import { useCallback, useEffect, useMemo } from "react";
import { themeSkinClassName } from "../themeSkins";
import {
  projectFileLinkContextForWindow,
  writeProjectFileRoute,
  writeProjectFilesRoute,
} from "../projectFileLinks";
import { writeProjectTodoRoute } from "../projectTodoLinks";
import { projectTodoArtifactToTerminalArtifact } from "../components/projectTodoArtifacts";
import { useAppOverlayProps } from "./useAppOverlayProps";
import { useProjectFileTabController } from "./useProjectFileTabController";
import { useAppShellProps } from "./useAppShellProps";
import { useAppViewModel } from "./useAppViewModel";
import { translate, type AppLocale } from "../i18n";
import type { TerminalConnectionStatus } from "../components/TerminalPane";
import type { ProjectTodoArtifact } from "../types";
import type { UseAppPresentationControllerArgs } from "./appPresentationControllerTypes";
import { isMobileShortcutVisible } from "./appMobileShortcutVisibility";

export function useAppPresentationController({
  appLocale,
  authEnabled,
  agentRecordModal,
  auxTerminalStarting,
  auxTerminalUnavailable,
  auxTerminalWindow,
  closeClientSwitcher,
  closeTerminalSwitcher,
  commandActions,
  creation,
  customQuickKeysState,
  deletion,
  deleteActions,
  drawer,
  focusSelectedTerminal,
  handleKeyboardShortcutBindingsChange,
  isMobileLayout,
  lifecycle,
  notifications,
  notificationActions,
  onboardingActions,
  onLogout,
  onAppLocaleChange,
  onAppPreferencesSave,
  onFocusProjectTodo,
  onOpenProjectTodoBoard,
  onSelectWorkspaceMode,
  queries,
  selection,
  submitAgentPreviewQuickInput,
  submitMobileShortcutDirection,
  terminalCreateActions,
  toggleTerminalSwitcherMode,
  toggleVirtualKeysVisibility,
  toggleWorkspaceMode,
  ui,
  virtualKeysVisible,
}: UseAppPresentationControllerArgs) {
  const toggleNotificationCenter = useCallback(() => {
    ui.setNotificationCenterOpen((open) => !open);
  }, [ui]);
  const setDetailPanelOpen = useCallback((open: boolean) => {
    ui.setDetailPanelOpen(open);
    if (open) {
      ui.setDetailPanelCollapsed(false);
    }
  }, [ui]);
  const projectFileTabs = useProjectFileTabController({
    projectFileTabsState: ui.projectFileTabsState,
    selectedClientId: ui.selectedClientId,
    selectedProjectBrowseRoot: ui.selectedProjectBrowseRoot,
    selectedProjectPath: ui.selectedProjectPath,
    selectedWindowId: ui.selectedWindowId,
    setProjectFileTabsState: ui.setProjectFileTabsState,
    setSelectedClientId: ui.setSelectedClientId,
    setSelectedProjectBrowseRoot: ui.setSelectedProjectBrowseRoot,
    setSelectedProjectFile: ui.setSelectedProjectFile,
    setSelectedProjectFileLine: ui.setSelectedProjectFileLine,
    setSelectedProjectPath: ui.setSelectedProjectPath,
    setWorkspaceMode: ui.setWorkspaceMode,
  });
  useEffect(() => {
    if (
      ui.workspaceMode !== "files"
      || projectFileTabs.context === null
      || ui.selectedProjectFile !== null
      || projectFileTabs.activeKey === null
    ) {
      return;
    }

    const activeTab = projectFileTabs.visibleTabs.find((tab) => tab.key === projectFileTabs.activeKey) ?? null;
    if (activeTab === null) {
      return;
    }

    ui.setSelectedProjectFile({
      name: activeTab.name,
      path: activeTab.path,
      kind: "file",
      size: activeTab.size,
      mtime: activeTab.mtime,
    });
    ui.setSelectedProjectFileLine(activeTab.line);
  }, [
    projectFileTabs.activeKey,
    projectFileTabs.context,
    projectFileTabs.visibleTabs,
    ui,
  ]);
  const projectFileContext = useMemo(() => projectFileLinkContextForWindow({
    clientId: ui.selectedClientId,
    windowId: ui.selectedWindowId,
    projectPath: ui.selectedProjectPath,
    browseRoot: ui.selectedProjectBrowseRoot,
    window: queries.selectedWindowQuery.data ?? queries.selectedWindow,
  }), [
    queries.selectedWindow,
    queries.selectedWindowQuery.data,
    ui.selectedClientId,
    ui.selectedProjectBrowseRoot,
    ui.selectedProjectPath,
    ui.selectedWindowId,
  ]);

  const viewModel = useAppViewModel({
    auxTerminalOpen: drawer.auxTerminalOpen,
    cloneMutationError: creation.cloneMutation.error,
    cloneMutationVariables: creation.cloneMutation.variables,
    cloneTerminalStatus: creation.cloneTerminalStatus,
    createMutationError: creation.createMutation.error,
    customQuickKeys: customQuickKeysState.customQuickKeys,
    deleteClientMutationError: deletion.deleteClientMutation.error,
    deleteClientMutationVariables: deletion.deleteClientMutation.variables,
    deleteMutationError: deletion.deleteMutation.error,
    deleteMutationVariables: deletion.deleteMutation.variables,
    generateTraceMutationError: drawer.generateTraceMutation.error,
    keyboardShortcutBindings: ui.keyboardShortcutBindings,
    selectedClientId: ui.selectedClientId,
    selectedClientOffline: queries.selectedClientOffline,
    selectedProject: queries.selectedProject,
    selectedProjectFile: ui.selectedProjectFile,
    selectedProjectPath: ui.selectedProjectPath,
    selectedWindowId: ui.selectedWindowId,
    selectedWindowTitle: queries.selectedWindowTitle,
    terminalCloneBusy: creation.terminalCloneBusy,
    terminalConnectionStatus: ui.terminalConnectionStatus,
    terminalCreateBusy: creation.terminalCreateBusy,
    terminalGroupingMode: ui.terminalGroupingMode,
    terminalNotifications: notifications,
    terminalSwitcherFolders: queries.terminalSwitcherFolders,
    terminalSwitcherRecentScope: ui.terminalSwitcherRecentScope,
    treeFolders: queries.treeFolders,
    workspaceMode: ui.workspaceMode,
    onCloneTerminal: commandActions.triggerCloneTerminal,
    onClientSwitch: commandActions.triggerClientSwitcherShortcut,
    onExpandRecord: commandActions.triggerAgentRecordExpand,
    onGitDiff: commandActions.triggerGitDiffBrowser,
    onGlobalTerminalSwitch: commandActions.triggerGlobalTerminalSwitcherShortcut,
    onLocateSelectedTerminal: commandActions.triggerLocateSelectedTerminal,
    onNewTerminal: terminalCreateActions.triggerNewTerminalShortcut,
    onNewTerminalProject: terminalCreateActions.triggerNewTerminalByProjectShortcut,
    onOpenArtifacts: drawer.triggerArtifactQuickOpen,
    onOpenProjectTodoBoard,
    onQuickInput: commandActions.triggerQuickInput,
    onRelatedTerminalSwitch: commandActions.triggerRelatedTerminalSwitch,
    onSettings: commandActions.toggleSettings,
    onSubmitCustomQuickKey: customQuickKeysState.submitCustomQuickKey,
    onSwitchTerminal: commandActions.triggerClientScopedTerminalSwitcherShortcut,
    onToggleAuxTerminal: drawer.toggleAuxTerminal,
    onToggleNotificationCenter: toggleNotificationCenter,
    onToggleWorkspaceMode: toggleWorkspaceMode,
  });

  const hasUnreadNotification = (windowId: string) =>
    notifications.some((notification) => notification.windowId === windowId && !notification.read);
  const openProjectTodoArtifact = useCallback((artifact: ProjectTodoArtifact, projectPath?: string | null) => {
    const terminalArtifact = projectTodoArtifactToTerminalArtifact(artifact, projectPath);
    if (terminalArtifact.status.toUpperCase() === "SUCCEEDED") {
      drawer.openArtifactResult(terminalArtifact);
      return;
    }
    drawer.openArtifactTerminal(terminalArtifact);
  }, [drawer]);
  const handleTerminalConnectionStatusChange = useCallback((status: TerminalConnectionStatus) => {
    ui.setTerminalConnectionStatus(status);
    if (
      status !== "connected"
      || ui.terminalRecoveryIntent === null
      || ui.terminalRecoveryIntent.clientId !== ui.selectedClientId
      || ui.terminalRecoveryIntent.windowId !== ui.selectedWindowId
    ) {
      return;
    }
    ui.setTerminalRecoveryIntent(null);
  }, [ui]);

  const appShell = useAppShellProps({
    addClientPending: lifecycle.bootstrapMutation.isPending,
    activeAuxTerminalTab: drawer.activeAuxTerminalTab,
    agentPreviewCanSendQuickInput: viewModel.agentPreviewCanSendQuickInput,
    artifactTerminalStatus: drawer.artifactTerminalStatus,
    artifactTerminalTitle: drawer.artifactTerminalTitle,
    artifactTerminalWindowId: drawer.artifactTerminalWindowId,
    auxTerminalOpen: drawer.auxTerminalOpen,
    auxTerminalPaneLayoutVersion: drawer.terminalPaneLayoutVersion,
    auxTerminalPaneRef: ui.auxTerminalPaneRef,
    auxTerminalStarting,
    auxTerminalUnavailable,
    auxTerminalWindow,
    auxTerminalShortcutLabel: viewModel.auxTerminalShortcutLabel,
    cloneErrorMessage: viewModel.cloneErrorMessage,
    cloneMutationError: creation.cloneMutation.isError,
    cloneTerminalShortcutLabel: viewModel.cloneTerminalShortcutLabel,
    cloneTerminalStatus: creation.cloneTerminalStatus,
    clients: queries.clientsQuery.data,
    clientsCollapsed: ui.clientsCollapsed,
    clientsQuery: queries.clientsQuery,
    createErrorMessage: viewModel.createErrorMessage,
    createMutationError: creation.createMutation.isError,
    customQuickKeys: customQuickKeysState.customQuickKeys,
    deleteClientErrorMessage: viewModel.deleteClientErrorMessage,
    deleteClientId: viewModel.deleteClientId,
    deleteClientMutationError: deletion.deleteClientMutation.isError,
    deleteErrorMessage: viewModel.deleteErrorMessage,
    deleteMutationError: deletion.deleteMutation.isError,
    deletePending: deletion.deleteMutation.isPending,
    deletingWindowId: viewModel.deletingWindowId,
    detailContext: ui.detailContext,
    detailPanelCollapsed: ui.detailPanelCollapsed,
    detailPanelOpen: ui.detailPanelOpen,
    generateTraceErrorMessage: viewModel.generateTraceErrorMessage,
    generateTraceMutationError: drawer.generateTraceMutation.isError,
    generateTracePending: drawer.generateTraceMutation.isPending,
    gitDiffShortcutLabel: viewModel.gitDiffShortcutLabel,
    hasUnreadNotification,
    keyboardShortcutBindings: ui.keyboardShortcutBindings,
    loadingSelectedProject: ui.selectedProjectPath !== null && (queries.treeQuery.isLoading || queries.windowActivityQuery.isLoading),
    mobileTerminalActive: ui.mobileTerminalActive,
    newTerminalShortcutLabel: viewModel.newTerminalShortcutLabel,
    notificationCenterOpen: ui.notificationCenterOpen,
    pendingTerminalCreate: creation.pendingTerminalCreate,
    projectTodoCreationPendingRequest: ui.projectTodoCreationPendingRequest,
    projectFileContext,
    projectFileTabsBarProps: {
      activeKey: projectFileTabs.activeKey,
      tabs: projectFileTabs.visibleTabs,
      onCloseTab: projectFileTabs.closeTab,
      onSelectTab: projectFileTabs.activateTab,
    },
    projectListCollapsed: ui.projectListCollapsed,
    projectFilePreviewMode: ui.projectFilePreviewMode,
    projectTodoDateFilter: ui.projectTodoDateFilter,
    projectTodoFocusRequest: ui.projectTodoFocusRequest,
    projectBrowseRootOptions: queries.projectBrowseRootOptions,
    projects: queries.projects,
    quickInputShortcutLabel: viewModel.quickInputShortcutLabel,
    relatedTerminalShortcutLabel: viewModel.relatedTerminalShortcutLabel,
    selectedClientId: ui.selectedClientId,
    selectedClientOffline: queries.selectedClientOffline,
    selectedProject: queries.selectedProject,
    selectedProjectFile: ui.selectedProjectFile,
    selectedProjectFileLine: ui.selectedProjectFileLine,
    selectedProjectBrowseRoot: ui.selectedProjectBrowseRoot,
    selectedProjectPath: ui.selectedProjectPath,
    selectedTreeWindow: queries.selectedTreeWindow,
    selectedWindowId: ui.selectedWindowId,
    selectedWindowTitle: queries.selectedWindowTitle,
    settingsShortcutLabel: viewModel.settingsShortcutLabel,
    summaryOutputLanguage: ui.summaryOutputLanguage,
    terminalCloneBusy: creation.terminalCloneBusy,
    terminalConnectionStatus: ui.terminalConnectionStatus,
    terminalControlsOpen: ui.terminalControlsOpen,
    terminalControlsRef: ui.terminalControlsRef,
    terminalCreateBusy: creation.terminalCreateBusy,
    auxTerminalTabsVisible: drawer.auxTerminalTabsVisible,
    terminalDrawerMode: drawer.terminalDrawerMode,
    terminalDrawerOpen: drawer.terminalDrawerOpen,
    terminalWindowClientId: drawer.terminalWindowClientId,
    terminalWindowId: drawer.terminalWindowId,
    terminalWindowPaneRef: drawer.terminalWindowPaneRef,
    terminalWindowProjectPath: drawer.terminalWindowProjectPath,
    terminalWindowTitle: drawer.terminalWindowTitle,
    terminalGroupingMode: ui.terminalGroupingMode,
    terminalImmersive: ui.terminalImmersive,
    terminalListLocateSignal: ui.terminalListLocateSignal,
    terminalPaneRef: ui.terminalPaneRef,
    terminalProjects: queries.terminalProjects,
    terminalProjectsQuery: queries.terminalProjectsQuery,
    terminalQuickInputDraft: ui.terminalQuickInputDraft,
    terminalQuickInputOpen: ui.terminalQuickInputOpen,
    terminalRecoveryIntent: ui.terminalRecoveryIntent,
    terminalTheme: queries.terminalTheme,
    terminalTimeRange: ui.terminalTimeRange,
    terminalViewportMode: ui.terminalViewportMode,
    toolbarSubtitle: viewModel.toolbarSubtitle,
    toolbarTitle: viewModel.toolbarTitle,
    treeFolders: queries.treeFolders,
    treeQuery: queries.treeQuery,
    unreadNotificationCount: viewModel.unreadNotificationCount,
    updateFailed: ui.updateFailed,
    updateMessage: ui.updateMessage,
    updatingClientId: lifecycle.updateMutation.isPending ? lifecycle.updateMutation.variables ?? null : null,
    reregisteringClientId: lifecycle.reregisterClientMutation.isPending
      ? lifecycle.reregisterClientMutation.variables?.id ?? null
      : null,
    virtualKeysVisible,
    workspaceMode: ui.workspaceMode,
    workspaceModeShortcutLabel: viewModel.workspaceModeShortcutLabel,
    onCloseDetails: () => ui.setDetailPanelOpen(false),
    onConfirmDeleteTerminal: deleteActions.confirmDeleteTerminal,
    onConfigureTerminalAtGroup: terminalCreateActions.handleConfigureTerminalAtGroup,
    onCreateTerminalAtGroup: terminalCreateActions.handleCreateTerminalAtGroup,
    onCustomQuickKeySubmit: customQuickKeysState.submitCustomQuickKey,
    onDeleteClient: deleteActions.requestDeleteClient,
    onDeleteWindow: deleteActions.requestDeleteWindow,
    onEnterTerminal: () => ui.setMobileTerminalActive(true),
    onGenerateTrace: drawer.triggerGenerateTrace,
    onFocusProjectTodo,
    onOpenAddClient: lifecycle.openAddClientModal,
    onOpenArtifactTerminal: drawer.openArtifactTerminal,
    onOpenProjectTodoArtifact: openProjectTodoArtifact,
    onOpenProjectTodoTerminalWindow: (windowId, projectPath, title) => {
      if (ui.selectedClientId === null) {
        return;
      }
      drawer.openTerminalWindow({
        clientId: ui.selectedClientId,
        windowId,
        projectPath,
        title: title ?? null,
      });
    },
    onOpenProjectTodoBoard,
    onSelectGlobalSearchWindow: selection.selectWindow,
    onOpenProjectDetail: (projectPath: string) => {
      ui.setRouteSelectionRequest(null);
      ui.setDeferredTreeSelection(null);
      ui.setSelectedProjectPath(projectPath);
      ui.setSelectedProjectBrowseRoot(null);
      ui.setSelectedProjectFile(null);
      ui.setSelectedProjectFileLine(null);
      ui.setDetailContext("project");
      setDetailPanelOpen(true);
      ui.setMobileTerminalActive(false);
    },
    onOpenSettings: ui.setSettingsOpen,
    onQuickInputDraftChange: ui.setTerminalQuickInputDraft,
    onQuickInputOpenChange: ui.setTerminalQuickInputOpen,
    onQuickInputSubmit: submitAgentPreviewQuickInput,
    onSelectClient: selection.selectClient,
    onSelectProjectBrowseRoot: (option) => {
      ui.setRouteSelectionRequest(null);
      ui.setDeferredTreeSelection(null);
      ui.setSelectedProjectPath(option.projectPath);
      ui.setSelectedProjectBrowseRoot(option.browseRoot);
      ui.setSelectedProjectFile(null);
      ui.setSelectedProjectFileLine(null);
      ui.setDetailContext("project");
      if (ui.workspaceMode === "files" && ui.selectedClientId !== null) {
        writeProjectFilesRoute({
          clientId: ui.selectedClientId,
          windowId: ui.selectedWindowId,
          projectPath: option.projectPath,
          browseRoot: option.browseRoot,
        }, "push");
      }
    },
    onSelectProject: (projectPath: string) => {
      ui.setRouteSelectionRequest(null);
      ui.setDeferredTreeSelection(null);
      ui.setSelectedProjectPath(projectPath);
      ui.setSelectedProjectBrowseRoot(null);
      ui.setSelectedProjectFile(null);
      ui.setSelectedProjectFileLine(null);
      if (ui.workspaceMode === "kanban" && ui.selectedClientId !== null) {
        writeProjectTodoRoute({ clientId: ui.selectedClientId, windowId: ui.selectedWindowId, projectPath, todoId: null }, "push");
      }
      if (ui.workspaceMode === "files" && ui.selectedClientId !== null) {
        writeProjectFilesRoute({
          clientId: ui.selectedClientId,
          windowId: ui.selectedWindowId,
          projectPath,
          browseRoot: null,
        }, "push");
      }
    },
    onSelectWorkspaceMode,
    onSelectProjectFile: (entry) => {
      ui.setSelectedProjectFile(entry);
      ui.setSelectedProjectFileLine(null);
      projectFileTabs.openCurrentTab(entry, null);
      if (
        ui.workspaceMode !== "files"
        || ui.selectedClientId === null
        || ui.selectedProjectPath === null
      ) {
        return;
      }
      if (entry?.kind === "file") {
        writeProjectFileRoute({
          clientId: ui.selectedClientId,
          windowId: ui.selectedWindowId,
          projectPath: ui.selectedProjectPath,
          browseRoot: ui.selectedProjectBrowseRoot,
          path: entry.path,
          line: null,
        }, "push");
        return;
      }
      writeProjectFilesRoute({
        clientId: ui.selectedClientId,
        windowId: ui.selectedWindowId,
        projectPath: ui.selectedProjectPath,
        browseRoot: ui.selectedProjectBrowseRoot,
      }, "push");
    },
    onSelectProjectWindow: selection.selectProjectWindow,
    onSelectWindow: selection.selectWindow,
    onSetClientsCollapsed: ui.setClientsCollapsed,
    onSetDetailPanelCollapsed: ui.setDetailPanelCollapsed,
    onSetDetailPanelOpen: setDetailPanelOpen,
    onSetMobileTerminalActive: ui.setMobileTerminalActive,
    onSetProjectListCollapsed: ui.setProjectListCollapsed,
    onSetProjectFilePreviewMode: ui.setProjectFilePreviewMode,
    onSetProjectTodoDateFilter: ui.setProjectTodoDateFilter,
    onSetTerminalControlsOpen: ui.setTerminalControlsOpen,
    onSetTerminalImmersive: ui.setTerminalImmersive,
    onSetTerminalSwitcherOpen: ui.setTerminalSwitcherOpen,
    onSetTerminalTimeRange: ui.setTerminalTimeRange,
    onSetTerminalViewportMode: ui.setTerminalViewportMode,
    onTerminalConnectionStatusChange: handleTerminalConnectionStatusChange,
    onTerminalDrawerClose: drawer.closeTerminalDrawer,
    onTerminalDrawerOpenTerminalTab: (clientId, windowId, projectPath) => {
      drawer.closeTerminalDrawer();
      selection.selectProjectWindow(windowId, projectPath, clientId);
    },
    onTerminalDrawerSelectAuxTerminalTab: drawer.selectAuxTerminalTab,
    onTerminalSelection: selection.handleTerminalPaneSelection,
    onToggleAuxTerminal: drawer.toggleAuxTerminal,
    onToggleNotificationCenter: toggleNotificationCenter,
    onToggleVirtualKeysVisibility: toggleVirtualKeysVisibility,
    onToggleWorkspaceMode: toggleWorkspaceMode,
    onTriggerAgentRecordExpand: commandActions.triggerAgentRecordExpand,
    onTriggerCloneTerminal: commandActions.triggerCloneTerminal,
    onTriggerGitDiffBrowser: commandActions.triggerGitDiffBrowser,
    onTriggerNewTerminal: terminalCreateActions.triggerNewTerminalShortcut,
    onTriggerQuickInput: commandActions.triggerQuickInput,
    onTriggerRelatedTerminalSwitch: commandActions.triggerRelatedTerminalSwitch,
    onUpdateClient: (clientId: string) => lifecycle.updateMutation.mutate(clientId),
    onReregisterClient: (client) => lifecycle.reregisterClientMutation.mutate(client),
  });

  const appOverlayProps = useAppOverlayProps({
    activeTerminalSwitcherShortcut: viewModel.activeTerminalSwitcherShortcut,
    addClientInitialMode: ui.addClientInitialMode,
    addClientModalOpen: ui.addClientModalOpen,
    agentClients: queries.agentClients,
    agentPreviewCanSendQuickInput: viewModel.agentPreviewCanSendQuickInput,
    agentRecordModal,
    agentRecordModalOpen: ui.agentRecordModalOpen,
    artifactMonitorArtifacts: queries.artifactMonitorArtifacts,
    artifactQuickOpenOpen: ui.artifactQuickOpenOpen,
    artifactResultViewerArtifact: drawer.artifactResultViewerArtifact,
    artifactTerminalMonitorError: queries.artifactTerminalMonitorQuery.isError,
    artifactTerminalMonitorLoading: queries.artifactTerminalMonitorQuery.isLoading,
    authEnabled,
    appLocale,
    bootstrapFailed: ui.bootstrapFailed,
    bootstrapPending: lifecycle.bootstrapMutation.isPending,
    clientSwitcherOpen: ui.clientSwitcherOpen,
    clients: queries.clientsQuery.data ?? [],
    createTerminalDisabled: queries.selectedClientOffline,
    customQuickKeys: customQuickKeysState.customQuickKeys,
    desktopNotificationsEnabled: ui.desktopNotificationsEnabled,
    focusSelectedTerminal,
    gitDiffBrowserOpen: ui.gitDiffBrowserOpen,
    gitDiffShortcutLabel: viewModel.gitDiffShortcutLabel,
    handleCustomQuickKeysChange: customQuickKeysState.handleCustomQuickKeysChange,
    handleKeyboardShortcutBindingsChange,
    isMobileLayout,
    keyboardShortcutBindings: ui.keyboardShortcutBindings,
    mobileShortcutActions: viewModel.mobileShortcutActions,
    mobileShortcutVisible: isMobileShortcutVisible(isMobileLayout, ui, drawer),
    notificationCenterOpen: ui.notificationCenterOpen,
    notifications,
    onboardingSteps: viewModel.onboardingSteps,
    projectPaths: queries.projectPaths,
    projects: queries.projects,
    projectFileContext,
    projectFileSearchOpen: ui.projectFileSearchOpen,
    projectFileSwitcherActiveKey: ui.projectFileTabsState.activeKey,
    projectFileSwitcherOpen: ui.projectFileSwitcherOpen,
    projectFileTabsState: ui.projectFileTabsState,
    projectPickerLoading: queries.terminalProjectsQuery.isFetching,
    projectSummaries: queries.projectSummariesQuery.data ?? [],
    projectTerminalPickerOpen: ui.projectTerminalPickerOpen,
    recentClientIds: selection.recentClientIds,
    relatedSwitcherWindows: queries.relatedSwitcherWindows,
    registrationKey: lifecycle.registrationKeyMutation.data?.key ?? null,
    registrationKeyError: lifecycle.registrationKeyMutation.isError ? translate(appLocale, "registration.generateFailed") : null,
    registrationKeyPending: lifecycle.registrationKeyMutation.isPending,
    selectedClientId: ui.selectedClientId,
    selectedProjectPath: ui.selectedProjectPath,
    selectedWindowId: ui.selectedWindowId,
    settingsInitialView: ui.settingsInitialView,
    settingsOpen: ui.settingsOpen,
    summaryOutputLanguage: ui.summaryOutputLanguage,
    terminalConnectionStatus: ui.terminalConnectionStatus,
    terminalCreateBusy: creation.terminalCreateBusy,
    terminalCreateContext: ui.terminalCreateContext,
    terminalGroupingMode: ui.terminalGroupingMode,
    terminalTimeRange: ui.terminalTimeRange,
    terminalPaneRef: ui.terminalPaneRef,
    terminalQuickInputDraft: ui.terminalQuickInputDraft,
    terminalSwitcherActivityLoading: (
      ui.terminalSwitcherRecentScope === "related"
      && ui.terminalSwitcherOpen
      && (queries.terminalSwitcherTreeQuery.isFetching || queries.terminalSwitcherActivityQuery.isFetching)
    ),
    terminalSwitcherFolders: queries.terminalSwitcherFolders,
    terminalSwitcherMode: ui.terminalSwitcherMode,
    terminalSwitcherOpen: ui.terminalSwitcherOpen,
    terminalSwitcherRecentScope: ui.terminalSwitcherRecentScope,
    themeSkin: ui.themeSkin,
    onAddClientClose: lifecycle.closeAddClientModal,
    onAppLocaleChange,
    onAppPreferencesSave,
    onBootstrapSubmit: lifecycle.submitBootstrap,
    onClientSwitcherClose: closeClientSwitcher,
    onClearNotifications: notificationActions.handleClearNotifications,
    onConfigureTerminalAtProjectPath: terminalCreateActions.handleConfigureTerminalAtProjectPath,
    onCreateTerminalAtGroup: terminalCreateActions.handleCreateTerminalAtGroup,
    onCreateTerminalAtProjectPath: terminalCreateActions.handleCreateTerminalAtProjectPath,
    onDeleteNotification: notificationActions.handleDeleteNotification,
    onDirectionInput: submitMobileShortcutDirection,
    onGenerateRegistrationKey: (label) => lifecycle.registrationKeyMutation.mutate(label),
    onLogout,
    onOpenArtifactResult: drawer.openArtifactResult,
    onOpenArtifactTerminal: drawer.openArtifactTerminal,
    onProjectFileSwitcherSelectTab: projectFileTabs.activateTab,
    onQuickInputSubmit: submitAgentPreviewQuickInput,
    onRunOnboardingAction: onboardingActions.runOnboardingAction,
    onSelectClient: selection.selectClient,
    onSelectNotification: notificationActions.handleSelectNotification,
    onSelectWindow: selection.selectWindow,
    onStartOnboarding: onboardingActions.startOnboardingFromSettings,
    onSummaryOutputLanguageChange: ui.setSummaryOutputLanguage,
    onTerminalCreateSubmit: terminalCreateActions.handleCreateTerminalSubmit,
    onTerminalGroupingModeChange: ui.setTerminalGroupingMode,
    onTerminalSwitcherClose: closeTerminalSwitcher,
    onTerminalSwitcherCreateConfig: terminalCreateActions.handleConfigureTerminalAtGroup,
    onTerminalSwitcherToggleModeShortcut: ui.terminalSwitcherRecentScope === "related" ? undefined : toggleTerminalSwitcherMode,
    onThemeSkinChange: ui.setThemeSkin,
    onToggleDesktopNotifications: ui.setDesktopNotificationsEnabled,
    setAgentRecordModalOpen: ui.setAgentRecordModalOpen,
    setArtifactQuickOpenOpen: ui.setArtifactQuickOpenOpen,
    setArtifactResultViewerArtifact: drawer.setArtifactResultViewerArtifact,
    setGitDiffBrowserOpen: ui.setGitDiffBrowserOpen,
    setNotificationCenterOpen: ui.setNotificationCenterOpen,
    setProjectFileSearchOpen: ui.setProjectFileSearchOpen,
    setProjectFileSwitcherOpen: ui.setProjectFileSwitcherOpen,
    setProjectTerminalPickerOpen: ui.setProjectTerminalPickerOpen,
    setSettingsOpen: ui.setSettingsOpen,
    setTerminalCreateContext: ui.setTerminalCreateContext,
  });

  return {
    appClassName: ["app-shell", themeSkinClassName(ui.themeSkin), ui.mobileTerminalActive ? "mobile-terminal-active" : "", ui.detailPanelCollapsed ? "detail-panel-collapsed" : "", ui.detailPanelOpen ? "detail-panel-open" : "", ui.terminalImmersive ? "terminal-immersive" : ""].filter(Boolean).join(" "),
    appOverlayProps,
    appShell,
  };
}
