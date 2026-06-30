import { useEffect, useRef, useState } from "react";

import type { AddClientMode } from "../appTypes";
import {
  readTerminalRouteSelection,
  readTerminalViewportMode,
  readWorkspaceMode,
  type DetailContext,
  type ProjectTodoCreationPendingRequest,
  type ProjectTodoFocusRequest,
  type TerminalRecoveryIntent,
  type TerminalRouteSelection,
  type TerminalViewportMode,
  type WorkspaceMode,
} from "../appState";
import { readInitialSettings, type SettingsView } from "../components/SettingsModal";
import type { TerminalConnectionStatus, TerminalPaneHandle } from "../components/TerminalPane";
import type { TerminalCreateContext } from "../components/TerminalCreateModal";
import {
  readProjectFileTabsState,
  writeProjectFileTabsState,
  type ProjectFileTabsState,
} from "../projectFileTabs";
import { readProjectTodoDateFilter } from "../features/projectTodos/projectTodoDateFilter";
import type { TerminalSwitcherMode, TerminalSwitcherRecentScope } from "../components/TerminalSwitcher";
import {
  readKeyboardShortcutBindings,
  type KeyboardShortcutBindings,
} from "../keyboardShortcuts";
import type { ProjectFileEntry } from "../types";
import {
  readTerminalTimeRange,
  type SummaryOutputLanguage,
  type TerminalGroupingMode,
  type TerminalTimeRange,
  type ThemeSkinId,
} from "../userPreferences";

export function useAppUiState() {
  const initialRouteSelection = readTerminalRouteSelection();
  const initialWorkspaceMode = readWorkspaceMode();
  const [selectedClientId, setSelectedClientId] = useState<string | null>(null);
  const [selectedWindowId, setSelectedWindowId] = useState<string | null>(null);
  const [selectedProjectPath, setSelectedProjectPath] = useState<string | null>(null);
  const [selectedProjectBrowseRoot, setSelectedProjectBrowseRoot] = useState<string | null>(null);
  const [workspaceMode, setWorkspaceMode] = useState<WorkspaceMode>(initialWorkspaceMode);
  const [detailContext, setDetailContext] = useState<DetailContext>("terminal");
  const [clientsCollapsed, setClientsCollapsed] = useState(false);
  const [projectListCollapsed, setProjectListCollapsed] = useState(() => readWorkspaceMode() === "files");
  const [projectTodoCreationPendingRequest, setProjectTodoCreationPendingRequest] = useState<ProjectTodoCreationPendingRequest | null>(null);
  const [projectTodoFocusRequest, setProjectTodoFocusRequest] = useState<ProjectTodoFocusRequest | null>(null);
  const [projectTodoDateFilter, setProjectTodoDateFilter] = useState(readProjectTodoDateFilter);
  const [selectedProjectFile, setSelectedProjectFile] = useState<ProjectFileEntry | null>(null);
  const [selectedProjectFileLine, setSelectedProjectFileLine] = useState<number | null>(null);
  const [projectFilePreviewMode, setProjectFilePreviewMode] = useState<"edit" | "preview">("preview");
  const [projectFileTabsState, setProjectFileTabsState] = useState<ProjectFileTabsState>(readProjectFileTabsState);
  const [projectFileSearchOpen, setProjectFileSearchOpen] = useState(false);
  const [projectFileSwitcherOpen, setProjectFileSwitcherOpen] = useState(false);
  const [routeSelectionRequest, setRouteSelectionRequest] = useState<TerminalRouteSelection | null>(
    initialRouteSelection
  );
  const [addClientModalOpen, setAddClientModalOpen] = useState(false);
  const [addClientInitialMode, setAddClientInitialMode] = useState<AddClientMode>("bootstrap");
  const [bootstrapFailed, setBootstrapFailed] = useState(false);
  const [updateMessage, setUpdateMessage] = useState<string | null>(null);
  const [updateFailed, setUpdateFailed] = useState(false);
  const [terminalSwitcherOpen, setTerminalSwitcherOpen] = useState(false);
  const [terminalSwitcherMode, setTerminalSwitcherMode] = useState<TerminalSwitcherMode>("recent");
  const [terminalSwitcherRecentScope, setTerminalSwitcherRecentScope] = useState<TerminalSwitcherRecentScope>("client");
  const [clientSwitcherOpen, setClientSwitcherOpen] = useState(false);
  const [projectTerminalPickerOpen, setProjectTerminalPickerOpen] = useState(false);
  const [terminalCreateContext, setTerminalCreateContext] = useState<TerminalCreateContext | null>(null);
  const [mobileTerminalActive, setMobileTerminalActive] = useState(false);
  const [detailPanelOpen, setDetailPanelOpen] = useState(false);
  const [detailPanelCollapsed, setDetailPanelCollapsed] = useState(false);
  const [terminalViewportMode, setTerminalViewportMode] = useState<TerminalViewportMode>(readTerminalViewportMode);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [settingsInitialView, setSettingsInitialView] = useState<SettingsView>("general");
  const [summaryOutputLanguage, setSummaryOutputLanguage] = useState<SummaryOutputLanguage>(
    () => readInitialSettings().summaryOutputLanguage
  );
  const [terminalGroupingMode, setTerminalGroupingMode] = useState<TerminalGroupingMode>(
    () => readInitialSettings().terminalGroupingMode
  );
  const [terminalTimeRange, setTerminalTimeRange] = useState<TerminalTimeRange>(() => readTerminalTimeRange());
  const [themeSkin, setThemeSkin] = useState<ThemeSkinId>(() => readInitialSettings().themeSkin);
  const [desktopNotificationsEnabled, setDesktopNotificationsEnabled] = useState(
    () => readInitialSettings().desktopNotificationsEnabled
  );
  const [keyboardShortcutBindings, setKeyboardShortcutBindings] = useState<KeyboardShortcutBindings>(
    () => readKeyboardShortcutBindings()
  );
  const [terminalControlsOpen, setTerminalControlsOpen] = useState(false);
  const [terminalQuickInputOpen, setTerminalQuickInputOpen] = useState(false);
  const [terminalQuickInputDraft, setTerminalQuickInputDraft] = useState("");
  const [terminalConnectionStatus, setTerminalConnectionStatus] = useState<TerminalConnectionStatus>("connecting");
  const [terminalImmersive, setTerminalImmersive] = useState(false);
  const [terminalRecoveryIntent, setTerminalRecoveryIntent] = useState<TerminalRecoveryIntent | null>(() => (
    initialWorkspaceMode === "terminal"
    && initialRouteSelection.clientId !== null
    && initialRouteSelection.windowId !== null
      ? {
          clientId: initialRouteSelection.clientId,
          windowId: initialRouteSelection.windowId,
          nonce: Date.now(),
        }
      : null
  ));
  const [selectedArtifactTerminalId, setSelectedArtifactTerminalId] = useState<string | null>(null);
  const [artifactQuickOpenOpen, setArtifactQuickOpenOpen] = useState(false);
  const [notificationCenterOpen, setNotificationCenterOpen] = useState(false);
  const [gitDiffBrowserOpen, setGitDiffBrowserOpen] = useState(false);
  const [agentRecordModalOpen, setAgentRecordModalOpen] = useState(false);
  const [deferredTreeSelection, setDeferredTreeSelection] = useState<TerminalRouteSelection | null>(null);
  const [terminalListLocateSignal, setTerminalListLocateSignal] = useState(0);
  const terminalControlsRef = useRef<HTMLDivElement | null>(null);
  const workspaceRef = useRef<HTMLElement | null>(null);
  const terminalPaneRef = useRef<TerminalPaneHandle | null>(null);
  const auxTerminalPaneRef = useRef<TerminalPaneHandle | null>(null);

  useEffect(() => {
    writeProjectFileTabsState(projectFileTabsState);
  }, [projectFileTabsState]);

  return {
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
    projectFilePreviewMode, setProjectFilePreviewMode,
    projectFileSearchOpen, setProjectFileSearchOpen,
    projectFileSwitcherOpen, setProjectFileSwitcherOpen,
    projectFileTabsState, setProjectFileTabsState,
    projectTodoCreationPendingRequest, setProjectTodoCreationPendingRequest,
    projectTodoDateFilter, setProjectTodoDateFilter,
    projectTodoFocusRequest, setProjectTodoFocusRequest,
    projectTerminalPickerOpen, setProjectTerminalPickerOpen,
    routeSelectionRequest, setRouteSelectionRequest,
    selectedArtifactTerminalId, setSelectedArtifactTerminalId,
    selectedClientId, setSelectedClientId,
    selectedProjectBrowseRoot, setSelectedProjectBrowseRoot,
    selectedProjectFile, setSelectedProjectFile,
    selectedProjectFileLine, setSelectedProjectFileLine,
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
    terminalRecoveryIntent, setTerminalRecoveryIntent,
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
  };
}
