import type { MutableRefObject } from "react";

import { AddClientModal } from "./AddClientModal";
import { AgentRecordStateModal } from "./AgentRecordStateModal";
import { ArtifactQuickOpen, ArtifactResultViewer } from "./ArtifactQuickOpen";
import { ClientSwitcher } from "./ClientSwitcher";
import { GitDiffBrowserModal } from "./GitDiffBrowserModal";
import { MobileShortcutFab, type MobileShortcutAction, type MobileShortcutDirection } from "./MobileShortcutFab";
import { NotificationCenter } from "./NotificationCenter";
import { OnboardingTour, type OnboardingAction, type OnboardingStep } from "./OnboardingTour";
import { ProjectTerminalPicker } from "./ProjectTerminalPicker";
import { ProjectFileSearchModal } from "./ProjectFileSearchModal";
import { ProjectFileSwitcher } from "./ProjectFileSwitcher";
import { SettingsModal, type SettingsView } from "./SettingsModal";
import { TerminalCreateModal, type TerminalCreateContext, type TerminalCreateSubmit } from "./TerminalCreateModal";
import { TerminalSwitcher, type TerminalSwitcherMode, type TerminalSwitcherRecentScope } from "./TerminalSwitcher";
import type { AgentRecordDataState } from "../hooks/useAgentRecordData";
import type { KeyboardShortcut, KeyboardShortcutBindings } from "../keyboardShortcuts";
import { effectiveKeyboardShortcut, keyboardShortcutLabel } from "../keyboardShortcuts";
import { terminalStatusLabel } from "../appState";
import { isOnboardingEnabled } from "../onboarding";
import type { AddClientMode } from "../appTypes";
import type { AppLocale } from "../i18n";
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
import type { AppPreferences, SummaryOutputLanguage, TerminalGroupingMode, TerminalTimeRange } from "../userPreferences";
import type { TerminalConnectionStatus, TerminalPaneHandle } from "./TerminalPane";

export type AppOverlayLayerProps = {
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
  onboardingSteps: OnboardingStep[];
  projectPaths: string[];
  projects: Project[];
  projectFileContext?: ProjectFileLinkContext | null;
  projectFileSearchOpen: boolean;
  projectFileSwitcherActiveKey: string | null;
  projectFileSwitcherOpen: boolean;
  projectFileTabsState: ProjectFileTabsState;
  projectPickerLoading: boolean;
  projectSummaries: ProjectSummary[];
  projectTerminalPickerOpen: boolean;
  recentClientIds: string[];
  relatedSwitcherWindows: Parameters<typeof TerminalSwitcher>[0]["relatedWindows"];
  registrationKey: string | null;
  registrationKeyError: string | null;
  registrationKeyPending: boolean;
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
  terminalTimeRange: TerminalTimeRange;
  terminalPaneRef: MutableRefObject<TerminalPaneHandle | null>;
  terminalQuickInputDraft: string;
  terminalSwitcherActivityLoading: boolean;
  terminalSwitcherFolders: TreeFolder[] | undefined;
  terminalSwitcherMode: TerminalSwitcherMode;
  terminalSwitcherOpen: boolean;
  terminalSwitcherRecentScope: TerminalSwitcherRecentScope;
  themeSkin: Parameters<typeof SettingsModal>[0]["themeSkin"];
  notifications: TerminalNotification[];
  notificationCenterOpen: boolean;
  onAddClientClose: () => void;
  onAppLocaleChange: (locale: AppLocale) => void;
  onAppPreferencesSave: (preferences: AppPreferences) => Promise<AppPreferences>;
  onArtifactQuickOpenClose: () => void;
  onArtifactResultClose: () => void;
  onBootstrapSubmit: (payload: BootstrapClientInput) => void;
  onClientSwitcherClose: () => void;
  onClearNotifications: () => void;
  onCreateTerminalAtGroup: Parameters<typeof TerminalSwitcher>[0]["onCreateTerminalAtGroup"];
  onCreateTerminalAtProjectPath: Parameters<typeof ProjectTerminalPicker>[0]["onCreateTerminal"];
  onConfigureTerminalAtProjectPath: Parameters<typeof ProjectTerminalPicker>[0]["onConfigureTerminal"];
  onDeleteNotification: (notification: TerminalNotification) => void;
  onDirectionInput: (direction: MobileShortcutDirection) => boolean;
  onGenerateRegistrationKey: (label?: string | null) => void;
  onGitDiffClose: () => void;
  onLogout: () => void;
  onNotificationCenterClose: () => void;
  onOpenArtifactResult: (artifact: TerminalArtifact) => void;
  onOpenArtifactTerminal: (artifact: TerminalArtifact) => void;
  onProjectFileSearchClose: () => void;
  onProjectFileSwitcherClose: () => void;
  onProjectFileSwitcherSelectTab: (tab: ProjectFileTab) => void;
  onProjectTerminalPickerClose: () => void;
  onQuickInputSubmit: (draft: string) => boolean;
  onRunOnboardingAction: (action: OnboardingAction) => void;
  onSelectClient: (clientId: string) => void;
  onSelectNotification: (notification: TerminalNotification) => void;
  onSelectWindow: (windowId: string) => void;
  onAgentRecordClose: () => void;
  onSettingsClose: () => void;
  onStartOnboarding: () => void;
  onSummaryOutputLanguageChange: (language: SummaryOutputLanguage) => void;
  onTerminalCreateClose: () => void;
  onTerminalCreateSubmit: (payload: TerminalCreateSubmit) => void;
  onTerminalGroupingModeChange: (mode: TerminalGroupingMode) => void;
  onTerminalSwitcherClose: () => void;
  onTerminalSwitcherCreateConfig: Parameters<typeof TerminalSwitcher>[0]["onConfigureTerminalAtGroup"];
  onTerminalSwitcherToggleModeShortcut: (() => void) | undefined;
  onThemeSkinChange: (themeSkin: Parameters<typeof SettingsModal>[0]["themeSkin"]) => void;
  onToggleDesktopNotifications: (enabled: boolean) => void;
};

export function AppOverlayLayer({
  activeTerminalSwitcherShortcut,
  addClientInitialMode,
  addClientModalOpen,
  appLocale,
  agentClients,
  agentPreviewCanSendQuickInput,
  agentRecordModal,
  agentRecordModalOpen,
  artifactMonitorArtifacts,
  artifactQuickOpenOpen,
  artifactResultViewerArtifact,
  artifactTerminalMonitorError,
  artifactTerminalMonitorLoading,
  authEnabled,
  bootstrapFailed,
  bootstrapPending,
  clientSwitcherOpen,
  clients,
  createTerminalDisabled,
  customQuickKeys,
  desktopNotificationsEnabled,
  focusSelectedTerminal,
  gitDiffBrowserOpen,
  gitDiffShortcutLabel,
  handleCustomQuickKeysChange,
  handleKeyboardShortcutBindingsChange,
  isMobileLayout,
  keyboardShortcutBindings,
  mobileShortcutActions,
  mobileShortcutVisible,
  onboardingSteps,
  projectPaths,
  projects,
  projectFileContext = null,
  projectFileSearchOpen,
  projectFileSwitcherActiveKey,
  projectFileSwitcherOpen,
  projectFileTabsState,
  projectPickerLoading,
  projectSummaries,
  projectTerminalPickerOpen,
  recentClientIds,
  relatedSwitcherWindows,
  registrationKey,
  registrationKeyError,
  registrationKeyPending,
  selectedClientId,
  selectedProjectPath,
  selectedWindowId,
  settingsInitialView,
  settingsOpen,
  summaryOutputLanguage,
  terminalConnectionStatus,
  terminalCreateBusy,
  terminalCreateContext,
  terminalGroupingMode,
  terminalTimeRange,
  terminalPaneRef,
  terminalQuickInputDraft,
  terminalSwitcherActivityLoading,
  terminalSwitcherFolders,
  terminalSwitcherMode,
  terminalSwitcherOpen,
  terminalSwitcherRecentScope,
  themeSkin,
  notifications,
  notificationCenterOpen,
  onAddClientClose,
  onAppLocaleChange,
  onAppPreferencesSave,
  onArtifactQuickOpenClose,
  onArtifactResultClose,
  onBootstrapSubmit,
  onClientSwitcherClose,
  onClearNotifications,
  onCreateTerminalAtGroup,
  onCreateTerminalAtProjectPath,
  onConfigureTerminalAtProjectPath,
  onDeleteNotification,
  onDirectionInput,
  onGenerateRegistrationKey,
  onGitDiffClose,
  onLogout,
  onNotificationCenterClose,
  onOpenArtifactResult,
  onOpenArtifactTerminal,
  onProjectFileSearchClose,
  onProjectFileSwitcherClose,
  onProjectFileSwitcherSelectTab,
  onProjectTerminalPickerClose,
  onQuickInputSubmit,
  onRunOnboardingAction,
  onSelectClient,
  onSelectNotification,
  onSelectWindow,
  onAgentRecordClose,
  onSettingsClose,
  onStartOnboarding,
  onSummaryOutputLanguageChange,
  onTerminalCreateClose,
  onTerminalCreateSubmit,
  onTerminalGroupingModeChange,
  onTerminalSwitcherClose,
  onTerminalSwitcherCreateConfig,
  onTerminalSwitcherToggleModeShortcut,
  onThemeSkinChange,
  onToggleDesktopNotifications,
}: AppOverlayLayerProps) {
  return (
    <>
      <AgentRecordStateModal
        agentRecord={agentRecordModal}
        open={agentRecordModalOpen}
        projectFileContext={projectFileContext}
        terminalStatusLabel={terminalStatusLabel(terminalConnectionStatus)}
        terminalStatusTone={terminalConnectionStatus}
        quickInputDraft={terminalQuickInputDraft}
        canSendQuickInput={agentPreviewCanSendQuickInput}
        onQuickInputDraftChange={(draft) => terminalPaneRef.current?.setQuickInputDraft(draft)}
        onQuickInputSubmit={onQuickInputSubmit}
        onClose={onAgentRecordClose}
      />
      <ArtifactQuickOpen
        isOpen={artifactQuickOpenOpen}
        artifacts={artifactMonitorArtifacts}
        isLoading={artifactTerminalMonitorLoading}
        isError={artifactTerminalMonitorError}
        onClose={onArtifactQuickOpenClose}
        onOpenTerminal={onOpenArtifactTerminal}
        onOpenResult={onOpenArtifactResult}
      />
      {artifactResultViewerArtifact !== null && (
        <ArtifactResultViewer
          clientId={artifactResultViewerArtifact.client_id}
          windowId={artifactResultViewerArtifact.virtual_window_id}
          artifact={artifactResultViewerArtifact}
          projectPath={selectedProjectPath}
          onClose={onArtifactResultClose}
        />
      )}
      <TerminalSwitcher
        clientId={selectedClientId}
        folders={terminalSwitcherFolders}
        relatedWindows={relatedSwitcherWindows}
        relatedLoading={terminalSwitcherActivityLoading}
        mode={terminalSwitcherMode}
        recentScope={terminalSwitcherRecentScope}
        terminalGroupingMode={terminalGroupingMode}
        summaryOutputLanguage={summaryOutputLanguage}
        isOpen={terminalSwitcherOpen}
        selectedWindowId={selectedWindowId}
        hasUnreadNotification={(windowId) => notifications.some((notification) => (
          notification.windowId === windowId && !notification.read
        ))}
        onClose={onTerminalSwitcherClose}
        onSelectWindow={onSelectWindow}
        onToggleModeShortcut={onTerminalSwitcherToggleModeShortcut}
        onCreateTerminalAtGroup={onCreateTerminalAtGroup}
        onConfigureTerminalAtGroup={onTerminalSwitcherCreateConfig}
        creatingTerminal={terminalCreateBusy}
        createTerminalDisabled={createTerminalDisabled}
        switchShortcut={activeTerminalSwitcherShortcut}
        switchShortcutLabel={keyboardShortcutLabel(activeTerminalSwitcherShortcut)}
      />
      <ClientSwitcher
        clients={clients}
        selectedClientId={selectedClientId}
        recentClientIds={recentClientIds}
        isOpen={clientSwitcherOpen}
        onClose={onClientSwitcherClose}
        onSelectClient={onSelectClient}
      />
      <ProjectFileSwitcher
        activeKey={projectFileSwitcherActiveKey}
        clientId={selectedClientId}
        isOpen={projectFileSwitcherOpen}
        tabsState={projectFileTabsState}
        onClose={onProjectFileSwitcherClose}
        onSelectTab={onProjectFileSwitcherSelectTab}
      />
      <ProjectFileSearchModal
        clientId={selectedClientId}
        isOpen={projectFileSearchOpen}
        projectPath={selectedProjectPath}
        selectedWindowId={selectedWindowId}
        onClose={onProjectFileSearchClose}
      />
      <ProjectTerminalPicker
        isOpen={projectTerminalPickerOpen}
        projectPaths={projectPaths}
        projects={projects}
        projectSummaries={projectSummaries}
        agentClients={agentClients}
        loadingProjects={projectPickerLoading}
        creatingTerminal={terminalCreateBusy}
        createTerminalDisabled={createTerminalDisabled}
        onClose={onProjectTerminalPickerClose}
        onCreateTerminal={onCreateTerminalAtProjectPath}
        onConfigureTerminal={onConfigureTerminalAtProjectPath}
      />
      <TerminalCreateModal
        isOpen={terminalCreateContext !== null}
        clientId={selectedClientId}
        context={terminalCreateContext}
        creatingTerminal={terminalCreateBusy}
        createTerminalDisabled={createTerminalDisabled}
        onClose={onTerminalCreateClose}
        onSubmit={onTerminalCreateSubmit}
      />
      <SettingsModal
        isOpen={settingsOpen}
        onClose={onSettingsClose}
        initialView={settingsInitialView}
        appLocale={appLocale}
        summaryOutputLanguage={summaryOutputLanguage}
        terminalGroupingMode={terminalGroupingMode}
        terminalTimeRange={terminalTimeRange}
        themeSkin={themeSkin}
        desktopNotificationsEnabled={desktopNotificationsEnabled}
        keyboardShortcutBindings={keyboardShortcutBindings}
        customQuickKeys={customQuickKeys}
        selectedClientId={selectedClientId}
        selectedProjectPath={selectedProjectPath}
        selectedWindowId={selectedWindowId}
        onAppLocaleChange={onAppLocaleChange}
        onAppPreferencesSave={onAppPreferencesSave}
        onSummaryOutputLanguageChange={onSummaryOutputLanguageChange}
        onTerminalGroupingModeChange={onTerminalGroupingModeChange}
        onThemeSkinChange={onThemeSkinChange}
        onDesktopNotificationsEnabledChange={onToggleDesktopNotifications}
        onKeyboardShortcutBindingsChange={handleKeyboardShortcutBindingsChange}
        onCustomQuickKeysChange={handleCustomQuickKeysChange}
        authEnabled={authEnabled}
        onboardingEnabled={isOnboardingEnabled()}
        onStartOnboarding={onStartOnboarding}
        onLogout={onLogout}
      />
      <AddClientModal
        isOpen={addClientModalOpen}
        initialMode={addClientInitialMode}
        bootstrapFailed={bootstrapFailed}
        bootstrapPending={bootstrapPending}
        registrationKey={registrationKey}
        registrationKeyPending={registrationKeyPending}
        registrationKeyError={registrationKeyError}
        onClose={onAddClientClose}
        onBootstrapSubmit={onBootstrapSubmit}
        onGenerateRegistrationKey={onGenerateRegistrationKey}
      />
      <NotificationCenter
        isOpen={notificationCenterOpen}
        notifications={notifications}
        onClose={onNotificationCenterClose}
        onSelectNotification={onSelectNotification}
        onDeleteNotification={onDeleteNotification}
        onClearNotifications={onClearNotifications}
      />
      {gitDiffBrowserOpen && selectedClientId !== null && selectedWindowId !== null && (
        <GitDiffBrowserModal
          clientId={selectedClientId}
          windowId={selectedWindowId}
          isMobileLayout={isMobileLayout}
          shortcutLabel={gitDiffShortcutLabel}
          onClose={onGitDiffClose}
        />
      )}
      <MobileShortcutFab
        visible={mobileShortcutVisible}
        actions={mobileShortcutActions}
        onDirectionInput={onDirectionInput}
      />
      <OnboardingTour steps={onboardingSteps} onStepAction={onRunOnboardingAction} />
    </>
  );
}
