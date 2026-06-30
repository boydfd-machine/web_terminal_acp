import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useCallback, useEffect } from "react";

import { ensureAuxTerminal } from "./api";
import { AppAuthGate } from "./AppAuthGate";
import { AppOverlayLayer } from "./components/AppOverlayLayer";
import { AppShellMain } from "./components/AppShellMain";
import type { MobileShortcutDirection } from "./components/MobileShortcutFab";
import { useAgentRecordData } from "./hooks/useAgentRecordData";
import { useAgentPreviewFollowups } from "./hooks/useAgentPreviewFollowups";
import { useAuthenticatedAppQueries } from "./hooks/useAuthenticatedAppQueries";
import { useAppDomainController } from "./hooks/useAppDomainController";
import { useAppPreferences } from "./hooks/useAppPreferences";
import { useAppPresentationController } from "./hooks/useAppPresentationController";
import { useAppRuntimeEffects } from "./hooks/useAppRuntimeEffects";
import { useAppUiState } from "./hooks/useAppUiState";
import { useAppWorkspaceActions } from "./hooks/useAppWorkspaceActions";
import { useAuxTerminalWindow } from "./hooks/useAuxTerminalWindow";
import { useClientLifecycleActions } from "./hooks/useClientLifecycleActions";
import { useCustomQuickKeys } from "./hooks/useCustomQuickKeys";
import { useMobileLayout } from "./hooks/useMobileLayout";
import { usePageAnnotationHost } from "./hooks/usePageAnnotationHost";
import { useProjectFileTabController } from "./hooks/useProjectFileTabController";
import { useTerminalVirtualKeysPreference } from "./hooks/useTerminalVirtualKeysPreference";
import { useTerminalNotificationsState } from "./hooks/useTerminalNotificationsState";
import { useUiInvalidationSocket } from "./hooks/useUiInvalidationSocket";
import { useVisualViewportHeightCssVariable } from "./hooks/useVisualViewportHeightCssVariable";
import { useI18n } from "./i18n";
import type { KeyboardShortcutBindings } from "./keyboardShortcuts";
import { themeSkinClassName, THEME_SKINS } from "./themeSkins";

const MOBILE_SHORTCUT_DIRECTION_INPUT: Record<MobileShortcutDirection, string> = {
  up: "\x1b[A",
  down: "\x1b[B",
  left: "\x1b[D",
  right: "\x1b[C"
};

export default function App() {
  return (
    <AppAuthGate>
      {({ authEnabled, onLogout }) => <AuthenticatedApp authEnabled={authEnabled} onLogout={onLogout} />}
    </AppAuthGate>
  );
}

function AuthenticatedApp({
  authEnabled,
  onLogout
}: {
  authEnabled: boolean;
  onLogout: () => void;
}) {
  useVisualViewportHeightCssVariable();

  const ui = useAppUiState();
  const { locale: appLocale, setLocale: setAppLocale, t } = useI18n();
  const {
    addClientInitialMode, setAddClientInitialMode,
    addClientModalOpen, setAddClientModalOpen,
    agentRecordModalOpen, setAgentRecordModalOpen,
    artifactQuickOpenOpen, setArtifactQuickOpenOpen,
    auxTerminalPaneRef,
    bootstrapFailed, setBootstrapFailed,
    clientSwitcherOpen, setClientSwitcherOpen,
    clientsCollapsed, setClientsCollapsed,
    deferredTreeSelection, setDeferredTreeSelection,
    desktopNotificationsEnabled, setDesktopNotificationsEnabled,
    detailContext, setDetailContext,
    detailPanelCollapsed, setDetailPanelCollapsed,
    detailPanelOpen, setDetailPanelOpen,
    gitDiffBrowserOpen, setGitDiffBrowserOpen,
    keyboardShortcutBindings, setKeyboardShortcutBindings,
    mobileTerminalActive, setMobileTerminalActive,
    notificationCenterOpen, setNotificationCenterOpen,
    projectListCollapsed, setProjectListCollapsed,
    setProjectFileSearchOpen,
    setProjectFileSwitcherOpen,
    projectFileTabsState, setProjectFileTabsState,
    setProjectTodoCreationPendingRequest,
    projectTodoFocusRequest, setProjectTodoFocusRequest,
    projectTerminalPickerOpen, setProjectTerminalPickerOpen,
    routeSelectionRequest, setRouteSelectionRequest,
    selectedArtifactTerminalId, setSelectedArtifactTerminalId,
    selectedClientId, setSelectedClientId,
    selectedProjectFile, setSelectedProjectFile,
    setSelectedProjectFileLine,
    selectedProjectBrowseRoot, setSelectedProjectBrowseRoot,
    selectedProjectPath, setSelectedProjectPath,
    selectedWindowId, setSelectedWindowId,
    settingsInitialView, setSettingsInitialView,
    settingsOpen, setSettingsOpen,
    summaryOutputLanguage, setSummaryOutputLanguage,
    terminalConnectionStatus, setTerminalConnectionStatus,
    terminalControlsOpen, setTerminalControlsOpen,
    terminalControlsRef,
    terminalCreateContext, setTerminalCreateContext,
    terminalGroupingMode, setTerminalGroupingMode,
    terminalImmersive, setTerminalImmersive,
    terminalListLocateSignal, setTerminalListLocateSignal,
    terminalPaneRef,
    terminalQuickInputDraft, setTerminalQuickInputDraft,
    terminalQuickInputOpen, setTerminalQuickInputOpen,
    setTerminalRecoveryIntent,
    terminalSwitcherMode, setTerminalSwitcherMode,
    terminalSwitcherOpen, setTerminalSwitcherOpen,
    terminalSwitcherRecentScope, setTerminalSwitcherRecentScope,
    terminalTimeRange, setTerminalTimeRange,
    terminalViewportMode, setTerminalViewportMode,
    themeSkin, setThemeSkin,
    updateFailed, setUpdateFailed,
    updateMessage, setUpdateMessage,
    workspaceMode, setWorkspaceMode,
    workspaceRef,
  } = ui;
  useEffect(() => {
    const skinClasses = THEME_SKINS.map((skin) => skin.cssClass);
    document.body.classList.remove(...skinClasses);
    document.body.classList.add(themeSkinClassName(themeSkin));
    return () => {
      document.body.classList.remove(...skinClasses);
    };
  }, [themeSkin]);
  const queryClient = useQueryClient();
  const { saveAppPreferences } = useAppPreferences({
    appLocale,
    desktopNotificationsEnabled,
    keyboardShortcutBindings,
    queryClient,
    summaryOutputLanguage,
    terminalGroupingMode,
    terminalTimeRange,
    themeSkin,
    setAppLocale,
    setDesktopNotificationsEnabled,
    setKeyboardShortcutBindings,
    setSummaryOutputLanguage,
    setTerminalGroupingMode,
    setTerminalTimeRange,
    setThemeSkin,
  });
  const isMobileLayout = useMobileLayout();
  const {
    toggleVirtualKeysVisibility,
    virtualKeysVisible
  } = useTerminalVirtualKeysPreference(isMobileLayout, terminalViewportMode);
  const {
    customQuickKeys,
    handleCustomQuickKeysChange,
    submitCustomQuickKey
  } = useCustomQuickKeys({
    queryClient,
    terminalPaneRef
  });
  const {
    scheduleAgentPreviewFollowupSubmits
  } = useAgentPreviewFollowups({
    terminalPaneRef
  });
  const auxTerminalWindow = useAuxTerminalWindow({
    detailPanelCollapsed,
    detailPanelOpen,
    mobileTerminalActive,
    terminalImmersive,
    workspaceRef
  });

  const {
    mutate: ensureAuxTerminalReady,
    isPending: auxTerminalStarting,
    isError: auxTerminalUnavailable
  } = useMutation({
    mutationFn: ({ clientId, windowId }: { clientId: string; windowId: string }) =>
      ensureAuxTerminal(clientId, windowId),
  });

  const agentRecordModal = useAgentRecordData({
    clientId: selectedClientId,
    windowId: selectedWindowId,
    enabled: agentRecordModalOpen
  });

  useUiInvalidationSocket(queryClient, authEnabled);

  const {
    bootstrapMutation,
    closeAddClientModal,
    openAddClientModal,
    registrationKeyMutation,
    reregisterClientMutation,
    submitBootstrap,
    updateMutation,
  } = useClientLifecycleActions({
    queryClient,
    setAddClientInitialMode,
    setAddClientModalOpen,
    setBootstrapFailed,
    setUpdateFailed,
    setUpdateMessage,
  });

  const focusSelectedTerminal = useCallback(() => {
    requestAnimationFrame(() => {
      terminalPaneRef.current?.refit();
      terminalPaneRef.current?.focus();
    });
  }, []);

  const handleKeyboardShortcutBindingsChange = useCallback((bindings: KeyboardShortcutBindings) => {
    setKeyboardShortcutBindings(bindings);
  }, []);

  const submitMobileShortcutDirection = useCallback((direction: MobileShortcutDirection) => {
    return terminalPaneRef.current?.submitQuickInput(MOBILE_SHORTCUT_DIRECTION_INPUT[direction]) ?? false;
  }, []);

  const closeTerminalSwitcher = useCallback(() => {
    setTerminalSwitcherOpen(false);
    focusSelectedTerminal();
  }, [focusSelectedTerminal]);
  const toggleTerminalSwitcherMode = useCallback(() => {
    setTerminalSwitcherMode((currentMode) => (currentMode === "recent" ? "tree" : "recent"));
  }, []);
  const closeClientSwitcher = useCallback(() => {
    setClientSwitcherOpen(false);
    focusSelectedTerminal();
  }, [focusSelectedTerminal]);
  const queries = useAuthenticatedAppQueries({
    artifactQuickOpenOpen,
    projectTerminalPickerOpen,
    selectedArtifactTerminalId,
    selectedClientId,
    selectedProjectPath,
    selectedWindowId,
    terminalSwitcherOpen,
    terminalTimeRange,
    themeSkin,
  });
  const {
    agentClients,
    artifactMonitorArtifacts,
    artifactTerminalCarrier,
    artifactTerminalMonitorQuery,
    clientsQuery,
    projectPaths,
    projectSummariesQuery,
    projects,
    relatedSwitcherWindows,
    selectedClient,
    selectedClientOffline,
    selectedProject,
    selectedTreeWindow,
    selectedWindow,
    selectedWindowTitle,
    terminalNotificationsQuery,
    terminalProjects,
    terminalProjectsQuery,
    terminalSwitcherActivityQuery,
    terminalSwitcherFolders,
    terminalSwitcherTreeQuery,
    terminalTheme,
    treeFolders,
    treeQuery,
    windowActivityQuery,
  } = queries;
  const terminalNotificationsState = useTerminalNotificationsState({
    desktopNotificationsEnabled,
    queryClient,
    selectedClientId,
    selectedWindowId,
    terminalNotificationsQuery,
  });
  const { terminalNotifications } = terminalNotificationsState;
  const {
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
  } = useAppDomainController({
    agentRecordModal,
    auxTerminalWindow,
    ensureAuxTerminalReady,
    focusSelectedTerminal,
    isMobileLayout,
    queryClient,
    queries,
    scheduleAgentPreviewFollowupSubmits,
    terminalNotificationsState,
    toggleTerminalSwitcherMode,
    ui,
  });

  const {
    clearProjectTodoCreationPendingRequest,
    focusProjectTodo,
    focusProjectTodoCreation,
    openProjectTodoBoard,
    selectWorkspaceMode,
    toggleWorkspaceMode,
  } = useAppWorkspaceActions({
    auxTerminal: drawer,
    selectedClientId,
    selectedProjectPath,
    selectedWindow,
    selectedWindowId,
    setClientsCollapsed,
    setDeferredTreeSelection,
    setDetailPanelCollapsed,
    setDetailContext,
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
  });
  const projectFileTabs = useProjectFileTabController({
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
  });
  const openProjectFileSwitcher = useCallback(() => {
    if (
      selectedClientId === null
      || !projectFileTabsState.tabs.some((tab) => tab.clientId === selectedClientId)
    ) {
      return;
    }
    setTerminalSwitcherOpen(false);
    setClientSwitcherOpen(false);
    setProjectTerminalPickerOpen(false);
    setNotificationCenterOpen(false);
    setTerminalControlsOpen(false);
    setTerminalCreateContext(null);
    setProjectFileSearchOpen(false);
    setProjectFileSwitcherOpen(true);
  }, [
    projectFileTabsState.tabs,
    selectedClientId,
    setClientSwitcherOpen,
    setNotificationCenterOpen,
    setProjectFileSearchOpen,
    setProjectFileSwitcherOpen,
    setProjectTerminalPickerOpen,
    setTerminalControlsOpen,
    setTerminalCreateContext,
    setTerminalSwitcherOpen,
  ]);
  const openProjectFileSearch = useCallback(() => {
    if (selectedClientId === null || selectedProjectPath === null) {
      return;
    }
    setTerminalSwitcherOpen(false);
    setClientSwitcherOpen(false);
    setProjectTerminalPickerOpen(false);
    setNotificationCenterOpen(false);
    setTerminalControlsOpen(false);
    setTerminalCreateContext(null);
    setProjectFileSwitcherOpen(false);
    setProjectFileSearchOpen(true);
  }, [
    selectedClientId,
    selectedProjectPath,
    setClientSwitcherOpen,
    setNotificationCenterOpen,
    setProjectFileSearchOpen,
    setProjectFileSwitcherOpen,
    setProjectTerminalPickerOpen,
    setTerminalControlsOpen,
    setTerminalCreateContext,
    setTerminalSwitcherOpen,
  ]);
  usePageAnnotationHost({
    clearProjectTodoCreationPendingRequest,
    focusProjectTodoCreation,
    focusProjectTodo,
    queryClient,
    selectedClientId,
    selectedProjectPath,
    selectedWindow,
    selectedWindowId,
    selectWorkspaceMode,
    setArtifactQuickOpenOpen,
    setClientSwitcherOpen,
    setProjectTerminalPickerOpen,
    setSelectedProjectBrowseRoot,
    setSelectedProjectPath,
    setTerminalControlsOpen,
    setTerminalQuickInputOpen,
    setTerminalSwitcherOpen,
    themeSkin,
    workspaceMode,
  });
  useAppRuntimeEffects({
    commandActions,
    customQuickKeys,
    drawer,
    focusSelectedTerminal,
    openProjectFileSearch,
    openProjectFileSwitcher,
    openProjectTodoBoard,
    submitCustomQuickKey,
    terminalCreateActions,
    terminalPaneRef,
    treeQuerySuccess: treeQuery.isSuccess,
    toggleVirtualKeysVisibility,
    toggleWorkspaceMode,
    ui,
  });

  const {
    appClassName,
    appOverlayProps,
    appShell,
  } = useAppPresentationController({
    authEnabled,
    agentRecordModal,
    auxTerminalStarting,
    auxTerminalUnavailable,
    auxTerminalWindow,
    closeClientSwitcher,
    closeTerminalSwitcher,
    commandActions,
    creation,
    customQuickKeysState: { customQuickKeys, handleCustomQuickKeysChange, submitCustomQuickKey },
    deletion,
    deleteActions,
    drawer,
    focusSelectedTerminal,
    handleKeyboardShortcutBindingsChange,
    isMobileLayout,
    lifecycle: {
      bootstrapMutation,
      closeAddClientModal,
      openAddClientModal,
      registrationKeyMutation,
      reregisterClientMutation,
      submitBootstrap,
      updateMutation,
    },
    notifications: terminalNotifications,
    notificationActions,
    onboardingActions,
    onLogout,
    onFocusProjectTodo: focusProjectTodo,
    onOpenProjectTodoBoard: openProjectTodoBoard,
    onAppPreferencesSave: saveAppPreferences,
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
    onSelectWorkspaceMode: selectWorkspaceMode,
    appLocale,
    onAppLocaleChange: setAppLocale,
  });

  return (
    <main
      data-debug-id="app-shell"
      data-onboarding-id="app-layout"
      className={appClassName}
    >
      <AppShellMain
        detailPanelProps={appShell.appDetailPanelProps}
        projectFileTabsBarProps={appShell.projectFileTabsBarProps}
        sidebarProps={appShell.appSidebarProps}
        terminalDrawer={{ mounted: drawer.terminalDrawerMounted, props: appShell.terminalDrawerProps }}
        terminalMainPaneProps={appShell.terminalMainPaneProps}
        toolbarProps={appShell.appToolbarProps}
        workspaceMode={workspaceMode}
        workspaceRef={workspaceRef}
      />
      <AppOverlayLayer {...appOverlayProps} />
      {detailPanelOpen && <button type="button" className="detail-backdrop" aria-label={t("toolbar.details")} onClick={() => setDetailPanelOpen(false)} />}
      {terminalImmersive && (
        <button
          type="button"
          className="terminal-immersive-exit"
          onClick={() => setTerminalImmersive(false)}
        >
          {t("toolbar.immersiveMode")}
        </button>
      )}
    </main>
  );
}
