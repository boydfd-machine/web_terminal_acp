import type { MutableRefObject } from "react";

import type { AppOverlayLayerProps } from "../components/AppOverlayLayer";
import type { AgentRecordDataState } from "./useAgentRecordData";
import type { MobileShortcutAction, MobileShortcutDirection } from "../components/MobileShortcutFab";
import type { TerminalConnectionStatus, TerminalPaneHandle } from "../components/TerminalPane";
import type { TerminalCreateContext } from "../components/TerminalCreateModal";
import type { TerminalSwitcherMode, TerminalSwitcherRecentScope } from "../components/TerminalSwitcher";
import type { SettingsView } from "../components/SettingsModal";
import type { AddClientMode } from "../appTypes";
import type { AppLocale } from "../i18n";
import type { KeyboardShortcut, KeyboardShortcutBindings } from "../keyboardShortcuts";
import type { ProjectFileLinkContext } from "../projectFileLinks";
import type { ProjectFileTab, ProjectFileTabsState } from "../projectFileTabs";
import type { CustomQuickKey } from "../terminalQuickKeys";
import type { TerminalNotification } from "../terminalNotifications";
import type {
  AgentClient,
  BootstrapClientInput,
  Client,
  Project,
  ProjectSummary,
  TerminalArtifact,
  TreeFolder,
} from "../types";
import type { AppPreferences, SummaryOutputLanguage, TerminalGroupingMode, ThemeSkinId } from "../userPreferences";

type UseAppOverlayPropsArgs = {
  activeTerminalSwitcherShortcut: KeyboardShortcut | null;
  addClientInitialMode: AddClientMode;
  addClientModalOpen: boolean;
  appLocale: AppLocale;
  agentClients: AgentClient[];
  agentPreviewCanSendQuickInput: boolean;
  agentRecordModal: AgentRecordDataState;
  agentRecordModalOpen: boolean;
  artifactMonitorArtifacts: TerminalArtifact[];
  artifactQuickOpenOpen: boolean;
  artifactResultViewerArtifact: TerminalArtifact | null;
  artifactTerminalMonitorError: boolean;
  artifactTerminalMonitorLoading: boolean;
  authEnabled: boolean;
  bootstrapFailed: boolean;
  bootstrapPending: boolean;
  clientSwitcherOpen: boolean;
  clients: Client[];
  createTerminalDisabled: boolean;
  customQuickKeys: CustomQuickKey[];
  desktopNotificationsEnabled: boolean;
  focusSelectedTerminal: () => void;
  gitDiffBrowserOpen: boolean;
  gitDiffShortcutLabel: string;
  handleCustomQuickKeysChange: (quickKeys: CustomQuickKey[]) => void;
  handleKeyboardShortcutBindingsChange: (bindings: KeyboardShortcutBindings) => void;
  isMobileLayout: boolean;
  keyboardShortcutBindings: KeyboardShortcutBindings;
  mobileShortcutActions: MobileShortcutAction[];
  mobileShortcutVisible: boolean;
  notificationCenterOpen: boolean;
  notifications: TerminalNotification[];
  onboardingSteps: AppOverlayLayerProps["onboardingSteps"];
  projectPaths: string[];
  projects: Project[];
  projectFileContext: ProjectFileLinkContext | null;
  projectFileSearchOpen: boolean;
  projectFileSwitcherActiveKey: string | null;
  projectFileSwitcherOpen: boolean;
  projectFileTabsState: ProjectFileTabsState;
  projectPickerLoading: boolean;
  projectSummaries: ProjectSummary[];
  projectTerminalPickerOpen: boolean;
  recentClientIds: string[];
  registrationKey: string | null;
  registrationKeyError: string | null;
  registrationKeyPending: boolean;
  relatedSwitcherWindows: AppOverlayLayerProps["relatedSwitcherWindows"];
  selectedClientId: string | null;
  selectedProjectPath: string | null;
  selectedWindowId: string | null;
  settingsInitialView: SettingsView;
  settingsOpen: boolean;
  summaryOutputLanguage: SummaryOutputLanguage;
  terminalConnectionStatus: TerminalConnectionStatus;
  terminalCreateBusy: boolean;
  terminalCreateContext: TerminalCreateContext | null;
  terminalGroupingMode: TerminalGroupingMode;
  terminalTimeRange: AppOverlayLayerProps["terminalTimeRange"];
  terminalPaneRef: MutableRefObject<TerminalPaneHandle | null>;
  terminalQuickInputDraft: string;
  terminalSwitcherActivityLoading: boolean;
  terminalSwitcherFolders: TreeFolder[] | undefined;
  terminalSwitcherMode: TerminalSwitcherMode;
  terminalSwitcherOpen: boolean;
  terminalSwitcherRecentScope: TerminalSwitcherRecentScope;
  themeSkin: ThemeSkinId;
  onAddClientClose: () => void;
  onAppLocaleChange: (locale: AppLocale) => void;
  onAppPreferencesSave: (preferences: AppPreferences) => Promise<AppPreferences>;
  onBootstrapSubmit: (payload: BootstrapClientInput) => void;
  onClientSwitcherClose: () => void;
  onClearNotifications: () => void;
  onConfigureTerminalAtProjectPath: AppOverlayLayerProps["onConfigureTerminalAtProjectPath"];
  onCreateTerminalAtGroup: AppOverlayLayerProps["onCreateTerminalAtGroup"];
  onCreateTerminalAtProjectPath: AppOverlayLayerProps["onCreateTerminalAtProjectPath"];
  onDeleteNotification: (notification: TerminalNotification) => void;
  onDirectionInput: (direction: MobileShortcutDirection) => boolean;
  onGenerateRegistrationKey: (label?: string | null) => void;
  onLogout: () => void;
  onOpenArtifactResult: (artifact: TerminalArtifact) => void;
  onOpenArtifactTerminal: (artifact: TerminalArtifact) => void;
  onProjectFileSwitcherSelectTab: (tab: ProjectFileTab) => void;
  onQuickInputSubmit: (draft: string) => boolean;
  onRunOnboardingAction: AppOverlayLayerProps["onRunOnboardingAction"];
  onSelectClient: (clientId: string) => void;
  onSelectNotification: (notification: TerminalNotification) => void;
  onSelectWindow: AppOverlayLayerProps["onSelectWindow"];
  onStartOnboarding: () => void;
  onSummaryOutputLanguageChange: (language: SummaryOutputLanguage) => void;
  onTerminalCreateSubmit: AppOverlayLayerProps["onTerminalCreateSubmit"];
  onTerminalGroupingModeChange: (mode: TerminalGroupingMode) => void;
  onTerminalSwitcherClose: () => void;
  onTerminalSwitcherCreateConfig: AppOverlayLayerProps["onTerminalSwitcherCreateConfig"];
  onTerminalSwitcherToggleModeShortcut: (() => void) | undefined;
  onThemeSkinChange: (themeSkin: ThemeSkinId) => void;
  onToggleDesktopNotifications: (enabled: boolean) => void;
  setAgentRecordModalOpen: (open: boolean) => void;
  setArtifactQuickOpenOpen: (open: boolean) => void;
  setArtifactResultViewerArtifact: (artifact: TerminalArtifact | null) => void;
  setGitDiffBrowserOpen: (open: boolean) => void;
  setNotificationCenterOpen: (open: boolean) => void;
  setProjectFileSearchOpen: (open: boolean) => void;
  setProjectFileSwitcherOpen: (open: boolean) => void;
  setProjectTerminalPickerOpen: (open: boolean) => void;
  setSettingsOpen: (open: boolean) => void;
  setTerminalCreateContext: (context: TerminalCreateContext | null) => void;
};

export function useAppOverlayProps(args: UseAppOverlayPropsArgs): AppOverlayLayerProps {
  return {
    activeTerminalSwitcherShortcut: args.activeTerminalSwitcherShortcut,
    addClientInitialMode: args.addClientInitialMode,
    addClientModalOpen: args.addClientModalOpen,
    appLocale: args.appLocale,
    agentClients: args.agentClients,
    agentPreviewCanSendQuickInput: args.agentPreviewCanSendQuickInput,
    agentRecordModal: args.agentRecordModal,
    agentRecordModalOpen: args.agentRecordModalOpen,
    artifactMonitorArtifacts: args.artifactMonitorArtifacts,
    artifactQuickOpenOpen: args.artifactQuickOpenOpen,
    artifactResultViewerArtifact: args.artifactResultViewerArtifact,
    artifactTerminalMonitorError: args.artifactTerminalMonitorError,
    artifactTerminalMonitorLoading: args.artifactTerminalMonitorLoading,
    authEnabled: args.authEnabled,
    bootstrapFailed: args.bootstrapFailed,
    bootstrapPending: args.bootstrapPending,
    clientSwitcherOpen: args.clientSwitcherOpen,
    clients: args.clients,
    createTerminalDisabled: args.createTerminalDisabled,
    customQuickKeys: args.customQuickKeys,
    desktopNotificationsEnabled: args.desktopNotificationsEnabled,
    focusSelectedTerminal: args.focusSelectedTerminal,
    gitDiffBrowserOpen: args.gitDiffBrowserOpen,
    gitDiffShortcutLabel: args.gitDiffShortcutLabel,
    handleCustomQuickKeysChange: args.handleCustomQuickKeysChange,
    handleKeyboardShortcutBindingsChange: args.handleKeyboardShortcutBindingsChange,
    isMobileLayout: args.isMobileLayout,
    keyboardShortcutBindings: args.keyboardShortcutBindings,
    mobileShortcutActions: args.mobileShortcutActions,
    mobileShortcutVisible: args.mobileShortcutVisible,
    notificationCenterOpen: args.notificationCenterOpen,
    notifications: args.notifications,
    onboardingSteps: args.onboardingSteps,
    projectPaths: args.projectPaths,
    projects: args.projects,
    projectFileContext: args.projectFileContext,
    projectFileSearchOpen: args.projectFileSearchOpen,
    projectFileSwitcherActiveKey: args.projectFileSwitcherActiveKey,
    projectFileSwitcherOpen: args.projectFileSwitcherOpen,
    projectFileTabsState: args.projectFileTabsState,
    projectPickerLoading: args.projectPickerLoading,
    projectSummaries: args.projectSummaries,
    projectTerminalPickerOpen: args.projectTerminalPickerOpen,
    recentClientIds: args.recentClientIds,
    registrationKey: args.registrationKey,
    registrationKeyError: args.registrationKeyError,
    registrationKeyPending: args.registrationKeyPending,
    relatedSwitcherWindows: args.relatedSwitcherWindows,
    selectedClientId: args.selectedClientId,
    selectedProjectPath: args.selectedProjectPath,
    selectedWindowId: args.selectedWindowId,
    settingsInitialView: args.settingsInitialView,
    settingsOpen: args.settingsOpen,
    summaryOutputLanguage: args.summaryOutputLanguage,
    terminalConnectionStatus: args.terminalConnectionStatus,
    terminalCreateBusy: args.terminalCreateBusy,
    terminalCreateContext: args.terminalCreateContext,
    terminalGroupingMode: args.terminalGroupingMode,
    terminalTimeRange: args.terminalTimeRange,
    terminalPaneRef: args.terminalPaneRef,
    terminalQuickInputDraft: args.terminalQuickInputDraft,
    terminalSwitcherActivityLoading: args.terminalSwitcherActivityLoading,
    terminalSwitcherFolders: args.terminalSwitcherFolders,
    terminalSwitcherMode: args.terminalSwitcherMode,
    terminalSwitcherOpen: args.terminalSwitcherOpen,
    terminalSwitcherRecentScope: args.terminalSwitcherRecentScope,
    themeSkin: args.themeSkin,
    onAddClientClose: args.onAddClientClose,
    onAppLocaleChange: args.onAppLocaleChange,
    onAppPreferencesSave: args.onAppPreferencesSave,
    onAgentRecordClose: () => args.setAgentRecordModalOpen(false),
    onArtifactQuickOpenClose: () => {
      args.setArtifactQuickOpenOpen(false);
      args.focusSelectedTerminal();
    },
    onArtifactResultClose: () => {
      args.setArtifactResultViewerArtifact(null);
      args.focusSelectedTerminal();
    },
    onBootstrapSubmit: args.onBootstrapSubmit,
    onClientSwitcherClose: args.onClientSwitcherClose,
    onClearNotifications: args.onClearNotifications,
    onConfigureTerminalAtProjectPath: args.onConfigureTerminalAtProjectPath,
    onCreateTerminalAtGroup: args.onCreateTerminalAtGroup,
    onCreateTerminalAtProjectPath: args.onCreateTerminalAtProjectPath,
    onDeleteNotification: args.onDeleteNotification,
    onDirectionInput: args.onDirectionInput,
    onGenerateRegistrationKey: args.onGenerateRegistrationKey,
    onGitDiffClose: () => {
      args.setGitDiffBrowserOpen(false);
      args.focusSelectedTerminal();
    },
    onLogout: args.onLogout,
    onNotificationCenterClose: () => args.setNotificationCenterOpen(false),
    onOpenArtifactResult: args.onOpenArtifactResult,
    onOpenArtifactTerminal: args.onOpenArtifactTerminal,
    onProjectFileSearchClose: () => args.setProjectFileSearchOpen(false),
    onProjectFileSwitcherClose: () => args.setProjectFileSwitcherOpen(false),
    onProjectFileSwitcherSelectTab: args.onProjectFileSwitcherSelectTab,
    onProjectTerminalPickerClose: () => {
      args.setProjectTerminalPickerOpen(false);
      args.focusSelectedTerminal();
    },
    onQuickInputSubmit: args.onQuickInputSubmit,
    onRunOnboardingAction: args.onRunOnboardingAction,
    onSelectClient: args.onSelectClient,
    onSelectNotification: args.onSelectNotification,
    onSelectWindow: args.onSelectWindow,
    onSettingsClose: () => {
      args.setSettingsOpen(false);
      args.focusSelectedTerminal();
    },
    onStartOnboarding: args.onStartOnboarding,
    onSummaryOutputLanguageChange: args.onSummaryOutputLanguageChange,
    onTerminalCreateClose: () => {
      args.setTerminalCreateContext(null);
      args.focusSelectedTerminal();
    },
    onTerminalCreateSubmit: args.onTerminalCreateSubmit,
    onTerminalGroupingModeChange: args.onTerminalGroupingModeChange,
    onTerminalSwitcherClose: args.onTerminalSwitcherClose,
    onTerminalSwitcherCreateConfig: args.onTerminalSwitcherCreateConfig,
    onTerminalSwitcherToggleModeShortcut: args.onTerminalSwitcherToggleModeShortcut,
    onThemeSkinChange: args.onThemeSkinChange,
    onToggleDesktopNotifications: args.onToggleDesktopNotifications,
  };
}
