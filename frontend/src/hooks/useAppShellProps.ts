import type { MutableRefObject } from "react";

import {
  effectiveKeyboardShortcut,
  keyboardShortcutLabel,
  type KeyboardShortcutBindings,
} from "../keyboardShortcuts";
import type {
  AppDetailPanelProps,
  AppSidebarProps,
  AppToolbarProps,
  ProjectFileTabsBarProps,
  TerminalDrawerProps,
  TerminalMainPaneProps,
  TerminalPaneHandle,
} from "../components/AppShellMain";
import type { TerminalConnectionStatus } from "../components/TerminalPane";
import type { CustomQuickKey } from "../terminalQuickKeys";
import type {
  Client,
  Project,
  ProjectFileEntry,
  ProjectTodoArtifact,
  TerminalArtifact,
  TerminalProject,
  TreeFolder,
  TreeWindow,
} from "../types";
import type {
  SummaryOutputLanguage,
  TerminalGroupingMode,
  TerminalTimeRange,
} from "../userPreferences";
import type {
  ProjectTodoFocusRequest,
  TerminalRecoveryIntent,
  TerminalViewportMode,
  WorkspaceMode,
} from "../appState";
import type { ProjectBrowseRootOption } from "../projectBrowseRoots";
import type { ProjectFileLinkContext } from "../projectFileLinks";
import type { ProjectTodoDateFilter } from "../features/projectTodos/projectTodoDateFilter";

type Ref<T> = MutableRefObject<T>;

type QueryStatus = {
  isError: boolean;
  isFetching?: boolean;
  isLoading?: boolean;
};

type AuxTerminalWindowProps = {
  dragActive: boolean;
  finishDrag: TerminalDrawerProps["onPointerCancel"];
  handlePointerDown: TerminalDrawerProps["onPointerDown"];
  handlePointerMove: TerminalDrawerProps["onPointerMove"];
  style: TerminalDrawerProps["style"];
};

type UseAppShellPropsArgs = {
  agentPreviewCanSendQuickInput: boolean;
  addClientPending: boolean;
  activeAuxTerminalTab: TerminalDrawerProps["activeAuxTerminalTab"];
  artifactTerminalStatus: string;
  artifactTerminalTitle: string;
  artifactTerminalWindowId: string | null;
  auxTerminalOpen: boolean;
  auxTerminalPaneLayoutVersion: string;
  auxTerminalPaneRef: TerminalDrawerProps["auxTerminalPaneRef"];
  auxTerminalStarting: boolean;
  auxTerminalUnavailable: boolean;
  auxTerminalWindow: AuxTerminalWindowProps;
  auxTerminalShortcutLabel: string;
  cloneErrorMessage: string;
  cloneTerminalShortcutLabel: string;
  cloneTerminalStatus: "idle" | "success";
  clients: Client[] | undefined;
  clientsCollapsed: boolean;
  clientsQuery: QueryStatus;
  createErrorMessage: string;
  customQuickKeys: CustomQuickKey[];
  deleteClientErrorMessage: string;
  deleteClientId: string | null;
  deleteErrorMessage: string;
  deletingWindowId: string | null;
  detailContext: AppDetailPanelProps["detailContext"];
  detailPanelCollapsed: boolean;
  detailPanelOpen: boolean;
  generateTraceErrorMessage: string;
  gitDiffShortcutLabel: string;
  hasUnreadNotification: (windowId: string) => boolean;
  keyboardShortcutBindings: KeyboardShortcutBindings;
  loadingSelectedProject: boolean;
  mobileTerminalActive: boolean;
  newTerminalShortcutLabel: string;
  notificationCenterOpen: boolean;
  pendingTerminalCreate: TerminalMainPaneProps["pendingTerminalCreate"];
  projectFileContext: ProjectFileLinkContext | null;
  projectFileTabsBarProps: ProjectFileTabsBarProps;
  projectListCollapsed: boolean;
  projectFilePreviewMode: "edit" | "preview";
  projectTodoCreationPendingRequest: TerminalMainPaneProps["projectTodoCreationPendingRequest"];
  projectTodoDateFilter: ProjectTodoDateFilter;
  projectTodoFocusRequest: ProjectTodoFocusRequest | null;
  projectBrowseRootOptions: ProjectBrowseRootOption[];
  projects: Project[];
  quickInputShortcutLabel: string;
  relatedTerminalShortcutLabel: string;
  selectedClientId: string | null;
  selectedClientOffline: boolean;
  selectedProject: Project | null;
  selectedProjectFile: ProjectFileEntry | null;
  selectedProjectFileLine: number | null;
  selectedProjectBrowseRoot: string | null;
  selectedProjectPath: string | null;
  selectedTreeWindow: TreeWindow | null | undefined;
  selectedWindowId: string | null;
  selectedWindowTitle: string | null;
  settingsShortcutLabel: string;
  summaryOutputLanguage: SummaryOutputLanguage;
  terminalCloneBusy: boolean;
  terminalConnectionStatus: TerminalConnectionStatus;
  terminalControlsOpen: boolean;
  terminalControlsRef: Ref<HTMLDivElement | null>;
  terminalCreateBusy: boolean;
  terminalDrawerMode: TerminalDrawerProps["mode"];
  terminalDrawerOpen: boolean;
  auxTerminalTabsVisible: boolean;
  terminalWindowClientId: string | null;
  terminalWindowId: string | null;
  terminalWindowPaneRef: TerminalDrawerProps["terminalWindowPaneRef"];
  terminalWindowProjectPath: string | null;
  terminalWindowTitle: string | null;
  terminalGroupingMode: TerminalGroupingMode;
  terminalImmersive: boolean;
  terminalListLocateSignal: number;
  terminalPaneRef: Ref<TerminalPaneHandle | null>;
  terminalProjects: TerminalProject[];
  terminalProjectsQuery: QueryStatus;
  terminalQuickInputDraft: string;
  terminalQuickInputOpen: boolean;
  terminalRecoveryIntent: TerminalRecoveryIntent | null;
  terminalTheme: TerminalMainPaneProps["terminalTheme"];
  terminalTimeRange: TerminalTimeRange;
  terminalViewportMode: TerminalViewportMode;
  toolbarSubtitle: string;
  toolbarTitle: string;
  treeFolders: TreeFolder[] | undefined;
  treeQuery: QueryStatus;
  unreadNotificationCount: number;
  updateFailed: boolean;
  updateMessage: string | null;
  updatingClientId: string | null;
  reregisteringClientId: string | null;
  virtualKeysVisible: boolean;
  workspaceMode: WorkspaceMode;
  workspaceModeShortcutLabel: string;
  cloneMutationError: boolean;
  createMutationError: boolean;
  deleteClientMutationError: boolean;
  deleteMutationError: boolean;
  generateTraceMutationError: boolean;
  deletePending: boolean;
  generateTracePending: boolean;
  onCloseDetails: () => void;
  onConfirmDeleteTerminal: () => void;
  onConfigureTerminalAtGroup: AppSidebarProps["onConfigureTerminalAtGroup"];
  onCreateTerminalAtGroup: AppSidebarProps["onCreateTerminalAtGroup"];
  onCustomQuickKeySubmit: TerminalMainPaneProps["onCustomQuickKeySubmit"];
  onDeleteClient: AppSidebarProps["onDeleteClient"];
  onDeleteWindow: AppSidebarProps["onDeleteWindow"];
  onEnterTerminal: () => void;
  onGenerateTrace: () => void;
  onOpenAddClient: AppSidebarProps["onOpenAddClient"];
  onOpenArtifactTerminal: (artifact: TerminalArtifact) => void;
  onOpenProjectTodoArtifact: (artifact: ProjectTodoArtifact, projectPath?: string | null) => void;
  onOpenProjectTodoTerminalWindow: TerminalMainPaneProps["onOpenProjectTodoTerminalWindow"];
  onFocusProjectTodo: (projectPath: string, todoId: string) => void;
  onSelectGlobalSearchWindow: AppToolbarProps["onSelectGlobalSearchWindow"];
  onOpenProjectTodoBoard: AppToolbarProps["onOpenProjectTodoBoard"];
  onOpenProjectDetail: AppSidebarProps["onOpenProjectDetail"];
  onOpenSettings: (open: boolean) => void;
  onQuickInputDraftChange: TerminalMainPaneProps["onQuickInputDraftChange"];
  onQuickInputOpenChange: TerminalMainPaneProps["onQuickInputOpenChange"];
  onQuickInputSubmit: AppDetailPanelProps["onQuickInputSubmit"];
  onSelectClient: AppSidebarProps["onSelectClient"];
  onSelectProjectBrowseRoot: AppToolbarProps["onSelectProjectBrowseRoot"];
  onSelectProject: AppSidebarProps["onSelectProject"];
  onSelectProjectFile: AppSidebarProps["onSelectProjectFile"];
  onSelectProjectWindow: (windowId: string, projectPath: string) => void;
  onSelectWorkspaceMode: AppToolbarProps["onSelectWorkspaceMode"];
  onSelectWindow: AppSidebarProps["onSelectWindow"];
  onSetClientsCollapsed: AppSidebarProps["onSetClientsCollapsed"];
  onSetDetailPanelCollapsed: (collapsed: boolean) => void;
  onSetDetailPanelOpen: (open: boolean) => void;
  onSetMobileTerminalActive: (active: boolean) => void;
  onSetProjectListCollapsed: AppSidebarProps["onSetProjectListCollapsed"];
  onSetProjectFilePreviewMode: (mode: "edit" | "preview") => void;
  onSetProjectTodoDateFilter: (filter: ProjectTodoDateFilter) => void;
  onSetTerminalControlsOpen: AppToolbarProps["onSetTerminalControlsOpen"];
  onSetTerminalImmersive: (immersive: boolean) => void;
  onSetTerminalSwitcherOpen: (open: boolean) => void;
  onSetTerminalTimeRange: AppSidebarProps["onSetTerminalTimeRange"];
  onSetTerminalViewportMode: (mode: TerminalViewportMode) => void;
  onTerminalConnectionStatusChange: TerminalMainPaneProps["onTerminalConnectionStatusChange"];
  onTerminalDrawerClose: TerminalDrawerProps["onClose"];
  onTerminalDrawerOpenTerminalTab: TerminalDrawerProps["onOpenTerminalTab"];
  onTerminalDrawerSelectAuxTerminalTab: TerminalDrawerProps["onSelectAuxTerminalTab"];
  onTerminalSelection: TerminalMainPaneProps["onTerminalSelection"];
  onToggleAuxTerminal: () => void;
  onToggleNotificationCenter: () => void;
  onToggleVirtualKeysVisibility: () => void;
  onToggleWorkspaceMode: () => void;
  onTriggerAgentRecordExpand: () => void;
  onTriggerCloneTerminal: () => void;
  onTriggerGitDiffBrowser: () => void;
  onTriggerNewTerminal: () => void;
  onTriggerQuickInput: () => void;
  onTriggerRelatedTerminalSwitch: () => void;
  onUpdateClient: AppSidebarProps["onUpdateClient"];
  onReregisterClient: AppSidebarProps["onReregisterClient"];
};

export function useAppShellProps(args: UseAppShellPropsArgs) {
  const appSidebarProps: AppSidebarProps = {
    addClientPending: args.addClientPending,
    clients: args.clients,
    clientsCollapsed: args.clientsCollapsed,
    clientsError: args.clientsQuery.isError,
    clientsLoading: Boolean(args.clientsQuery.isLoading),
    cloneError: args.cloneMutationError,
    cloneErrorMessage: args.cloneErrorMessage,
    createError: args.createMutationError,
    createErrorMessage: args.createErrorMessage,
    createTerminalBusy: args.terminalCreateBusy,
    deleteClientError: args.deleteClientMutationError,
    deleteClientErrorMessage: args.deleteClientErrorMessage,
    deleteClientId: args.deleteClientId,
    deleteError: args.deleteMutationError,
    deleteErrorMessage: args.deleteErrorMessage,
    deletingWindowId: args.deletingWindowId,
    generateTraceError: args.generateTraceMutationError,
    generateTraceErrorMessage: args.generateTraceErrorMessage,
    hasUnreadNotification: args.hasUnreadNotification,
    loadingSelectedProject: args.loadingSelectedProject,
    loadingTerminalProjects: Boolean(args.terminalProjectsQuery.isFetching),
    newTerminalShortcutLabel: args.newTerminalShortcutLabel,
    notificationCenterOpen: args.notificationCenterOpen,
    projectListCollapsed: args.projectListCollapsed,
    projectTodoDateFilter: args.projectTodoDateFilter,
    projects: args.projects,
    selectedClientId: args.selectedClientId,
    selectedClientOffline: args.selectedClientOffline,
    selectedProjectFile: args.selectedProjectFile,
    selectedProjectBrowseRoot: args.selectedProjectBrowseRoot,
    selectedProjectPath: args.selectedProjectPath,
    selectedWindowId: args.selectedWindowId,
    summaryOutputLanguage: args.summaryOutputLanguage,
    terminalGroupingMode: args.terminalGroupingMode,
    terminalListLocateSignal: args.terminalListLocateSignal,
    terminalProjects: args.terminalProjects,
    terminalProjectsError: args.terminalProjectsQuery.isError,
    terminalTimeRange: args.terminalTimeRange,
    treeError: args.treeQuery.isError,
    treeFolders: args.treeFolders,
    unreadNotificationCount: args.unreadNotificationCount,
    updateFailed: args.updateFailed,
    updateMessage: args.updateMessage,
    updatingClientId: args.updatingClientId,
    reregisteringClientId: args.reregisteringClientId,
    workspaceMode: args.workspaceMode,
    onCreateTerminalAtGroup: args.onCreateTerminalAtGroup,
    onConfigureTerminalAtGroup: args.onConfigureTerminalAtGroup,
    onDeleteClient: args.onDeleteClient,
    onDeleteWindow: args.onDeleteWindow,
    onEnterTerminal: args.onEnterTerminal,
    onOpenAddClient: args.onOpenAddClient,
    onOpenProjectDetail: args.onOpenProjectDetail,
    onSelectClient: args.onSelectClient,
    onSelectProject: args.onSelectProject,
    onSelectProjectFile: args.onSelectProjectFile,
    onSelectWindow: args.onSelectWindow,
    onSetClientsCollapsed: args.onSetClientsCollapsed,
    onSetProjectListCollapsed: args.onSetProjectListCollapsed,
    onSetProjectTodoDateFilter: args.onSetProjectTodoDateFilter,
    onSetTerminalTimeRange: args.onSetTerminalTimeRange,
    onToggleNotificationCenter: args.onToggleNotificationCenter,
    onTriggerNewTerminal: args.onTriggerNewTerminal,
    onUpdateClient: args.onUpdateClient,
    onReregisterClient: args.onReregisterClient,
  };

  const appToolbarProps: AppToolbarProps = {
    auxTerminalOpen: args.auxTerminalOpen,
    auxTerminalShortcutLabel: args.auxTerminalShortcutLabel,
    cloneTerminalShortcutLabel: args.cloneTerminalShortcutLabel,
    deletePending: args.deletePending,
    detailPanelCollapsed: args.detailPanelCollapsed,
    generateTracePending: args.generateTracePending,
    gitDiffShortcutLabel: args.gitDiffShortcutLabel,
    keyboardShortcutBindings: args.keyboardShortcutBindings,
    quickInputShortcutLabel: args.quickInputShortcutLabel,
    projectBrowseRootOptions: args.projectBrowseRootOptions,
    projectFilePreviewMode: args.projectFilePreviewMode,
    relatedTerminalShortcutLabel: args.relatedTerminalShortcutLabel,
    selectedClientId: args.selectedClientId,
    selectedClientOffline: args.selectedClientOffline,
    selectedProjectBrowseRoot: args.selectedProjectBrowseRoot,
    selectedProjectFile: args.selectedProjectFile,
    selectedProjectPath: args.selectedProjectPath,
    selectedWindowId: args.selectedWindowId,
    settingsShortcutLabel: args.settingsShortcutLabel,
    terminalCloneBusy: args.terminalCloneBusy,
    terminalControlsOpen: args.terminalControlsOpen,
    terminalControlsRef: args.terminalControlsRef,
    terminalCreateBusy: args.terminalCreateBusy,
    terminalQuickInputOpen: args.terminalQuickInputOpen,
    terminalViewportMode: args.terminalViewportMode,
    toolbarSubtitle: args.toolbarSubtitle,
    toolbarTitle: args.toolbarTitle,
    virtualKeysVisible: args.virtualKeysVisible,
    workspaceMode: args.workspaceMode,
    workspaceModeShortcutLabel: args.workspaceModeShortcutLabel,
    onConfirmDeleteTerminal: args.onConfirmDeleteTerminal,
    onGenerateTrace: args.onGenerateTrace,
    onSetDetailPanelCollapsed: args.onSetDetailPanelCollapsed,
    onSetDetailPanelOpen: args.onSetDetailPanelOpen,
    onSetMobileTerminalActive: args.onSetMobileTerminalActive,
    onSetSettingsOpen: args.onOpenSettings,
    onSetTerminalControlsOpen: args.onSetTerminalControlsOpen,
    onSetTerminalImmersive: args.onSetTerminalImmersive,
    onSetTerminalSwitcherOpen: args.onSetTerminalSwitcherOpen,
    onSetTerminalViewportMode: args.onSetTerminalViewportMode,
    onSelectProjectBrowseRoot: args.onSelectProjectBrowseRoot,
    onSelectWorkspaceMode: args.onSelectWorkspaceMode,
    onSetProjectFilePreviewMode: args.onSetProjectFilePreviewMode,
    onFocusProjectTodo: args.onFocusProjectTodo,
    onOpenProjectTodoBoard: args.onOpenProjectTodoBoard,
    onSelectGlobalSearchWindow: args.onSelectGlobalSearchWindow,
    onToggleAuxTerminal: args.onToggleAuxTerminal,
    onToggleVirtualKeysVisibility: args.onToggleVirtualKeysVisibility,
    onToggleWorkspaceMode: args.onToggleWorkspaceMode,
    onTriggerAgentRecordExpand: args.onTriggerAgentRecordExpand,
    onTriggerCloneTerminal: args.onTriggerCloneTerminal,
    onTriggerGitDiffBrowser: args.onTriggerGitDiffBrowser,
    onTriggerQuickInput: args.onTriggerQuickInput,
    onTriggerRelatedTerminalSwitch: args.onTriggerRelatedTerminalSwitch,
  };

  const terminalMainPaneProps: TerminalMainPaneProps = {
    cloneTerminalStatus: args.cloneTerminalStatus,
    customQuickKeys: args.customQuickKeys,
    detailPanelCollapsed: args.detailPanelCollapsed,
    detailPanelOpen: args.detailPanelOpen,
    mobileTerminalActive: args.mobileTerminalActive,
    pendingTerminalCreate: args.pendingTerminalCreate,
    projects: args.projects,
    projectPath: args.selectedProjectPath,
    projectFilePreviewMode: args.projectFilePreviewMode,
    projectTodoCreationPendingRequest: args.projectTodoCreationPendingRequest,
    projectTodoDateFilter: args.projectTodoDateFilter,
    projectTodoFocusRequest: args.projectTodoFocusRequest,
    selectedClientId: args.selectedClientId,
    selectedProjectBrowseRoot: args.selectedProjectBrowseRoot,
    selectedProjectFile: args.selectedProjectFile,
    selectedProjectFileLine: args.selectedProjectFileLine,
    selectedWindowId: args.selectedWindowId,
    allowMissingWindowRecreate: (
      args.terminalRecoveryIntent?.clientId === args.selectedClientId
      && args.terminalRecoveryIntent.windowId === args.selectedWindowId
    ),
    terminalCloneBusy: args.terminalCloneBusy,
    terminalImmersive: args.terminalImmersive,
    terminalPaneRef: args.terminalPaneRef,
    terminalTheme: args.terminalTheme,
    terminalViewportMode: args.terminalViewportMode,
    virtualKeysVisible: args.virtualKeysVisible,
    workspaceMode: args.workspaceMode,
    onCustomQuickKeySubmit: args.onCustomQuickKeySubmit,
    onQuickInputDraftChange: args.onQuickInputDraftChange,
    onQuickInputOpenChange: args.onQuickInputOpenChange,
    onSetProjectFilePreviewMode: args.onSetProjectFilePreviewMode,
    onOpenProjectTodoArtifact: args.onOpenProjectTodoArtifact,
    onOpenProjectTodoTerminalWindow: args.onOpenProjectTodoTerminalWindow,
    onSelectProjectWindow: args.onSelectProjectWindow,
    onTerminalConnectionStatusChange: args.onTerminalConnectionStatusChange,
    onTerminalSelection: args.onTerminalSelection,
  };

  const terminalDrawerClientId = args.terminalDrawerMode === "terminal" ? args.terminalWindowClientId : args.selectedClientId;
  const terminalDrawerSelectedWindowId = args.selectedWindowId ?? args.terminalWindowId;
  const terminalDrawerProps: TerminalDrawerProps | null = terminalDrawerClientId !== null && terminalDrawerSelectedWindowId !== null
    ? {
        activeAuxTerminalTab: args.activeAuxTerminalTab,
        artifactTerminalStatus: args.artifactTerminalStatus,
        artifactTerminalTitle: args.artifactTerminalTitle,
        artifactTerminalWindowId: args.artifactTerminalWindowId,
        autoFocusAuxTerminal: args.auxTerminalOpen,
        auxTerminalPaneRef: args.auxTerminalPaneRef,
        auxTerminalStarting: args.auxTerminalStarting,
        auxTerminalUnavailable: args.auxTerminalUnavailable,
        clientId: terminalDrawerClientId,
        dragActive: args.auxTerminalWindow.dragActive,
        layoutVersion: args.auxTerminalPaneLayoutVersion,
        mode: args.terminalDrawerMode,
        open: args.terminalDrawerOpen,
        showAuxTerminalTabs: args.auxTerminalTabsVisible,
        selectedWindowId: terminalDrawerSelectedWindowId,
        selectedWindowTitle: args.selectedWindowTitle,
        style: args.auxTerminalWindow.style,
        terminalWindowClientId: args.terminalWindowClientId,
        terminalWindowId: args.terminalWindowId,
        terminalWindowPaneRef: args.terminalWindowPaneRef,
        terminalWindowProjectPath: args.terminalWindowProjectPath,
        terminalWindowTitle: args.terminalWindowTitle,
        terminalTheme: args.terminalTheme,
        onClose: args.onTerminalDrawerClose,
        onOpenTerminalTab: args.onTerminalDrawerOpenTerminalTab,
        onSelectAuxTerminalTab: args.onTerminalDrawerSelectAuxTerminalTab,
        onPointerCancel: args.auxTerminalWindow.finishDrag,
        onPointerDown: args.auxTerminalWindow.handlePointerDown,
        onPointerMove: args.auxTerminalWindow.handlePointerMove,
        onPointerUp: args.auxTerminalWindow.finishDrag,
      }
    : null;

  const appDetailPanelProps: AppDetailPanelProps = {
    agentPreviewCanSendQuickInput: args.agentPreviewCanSendQuickInput,
    agentRecordShortcutLabel: keyboardShortcutLabel(effectiveKeyboardShortcut("expand-record", args.keyboardShortcutBindings)),
    detailContext: args.detailContext,
    project: args.selectedProject,
    projects: args.projects,
    projectFileContext: args.projectFileContext,
    projectPath: args.selectedProjectPath,
    projectTodoFocusRequest: args.projectTodoFocusRequest,
    quickInputDraft: args.terminalQuickInputDraft,
    selectedClientId: args.selectedClientId,
    selectedProjectPath: args.selectedProjectPath,
    selectedTreeWindow: args.selectedTreeWindow ?? null,
    selectedWindowId: args.selectedWindowId,
    terminalConnectionStatus: args.terminalConnectionStatus,
    terminalPaneRef: args.terminalPaneRef,
    terminalTimeRange: args.terminalTimeRange,
    workspaceMode: args.workspaceMode,
    onCollapseDetails: () => args.onSetDetailPanelCollapsed(true),
    onCloseDetails: args.onCloseDetails,
    onFocusProjectTodo: args.onFocusProjectTodo,
    onOpenArtifactTerminal: args.onOpenArtifactTerminal,
    onOpenProjectTodoArtifact: args.onOpenProjectTodoArtifact,
    onQuickInputSubmit: args.onQuickInputSubmit,
    onSelectProjectWindow: args.onSelectProjectWindow,
    onSelectWindow: args.onSelectWindow,
  };

  return {
    appDetailPanelProps,
    appSidebarProps,
    projectFileTabsBarProps: args.projectFileTabsBarProps,
    appToolbarProps,
    terminalDrawerProps,
    terminalMainPaneProps,
  };
}
