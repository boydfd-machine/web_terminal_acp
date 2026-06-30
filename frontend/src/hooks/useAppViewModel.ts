import { useMemo } from "react";

import { buildMobileShortcutActions } from "../appMobileShortcuts";
import { buildOnboardingSteps } from "../appOnboarding";
import { terminalStatusLabel, type WorkspaceMode } from "../appState";
import { useI18n } from "../i18n";
import {
  effectiveKeyboardShortcut,
  keyboardShortcutLabel,
  type KeyboardShortcut,
  type KeyboardShortcutBindings,
} from "../keyboardShortcuts";
import type { CustomQuickKey } from "../terminalQuickKeys";
import type { TerminalNotification } from "../terminalNotifications";
import type { MobileShortcutAction } from "../components/MobileShortcutFab";
import type { TerminalConnectionStatus } from "../components/TerminalPane";
import type { Project, ProjectFileEntry, TreeFolder } from "../types";
import type { TerminalGroupingMode } from "../userPreferences";

type AppViewModelArgs = {
  auxTerminalOpen: boolean;
  cloneMutationError: unknown;
  cloneMutationVariables: { windowId: string } | undefined;
  cloneTerminalStatus: "idle" | "success";
  customQuickKeys: CustomQuickKey[];
  deleteClientMutationError: unknown;
  deleteClientMutationVariables: { clientId: string } | undefined;
  deleteMutationError: unknown;
  deleteMutationVariables: { windowId: string } | undefined;
  generateTraceMutationError: unknown;
  keyboardShortcutBindings: KeyboardShortcutBindings;
  selectedClientId: string | null;
  selectedClientOffline: boolean;
  selectedProject: Project | null;
  selectedProjectFile: ProjectFileEntry | null;
  selectedProjectPath: string | null;
  selectedWindowId: string | null;
  selectedWindowTitle: string | null;
  terminalCloneBusy: boolean;
  terminalConnectionStatus: TerminalConnectionStatus;
  terminalCreateBusy: boolean;
  terminalGroupingMode: TerminalGroupingMode;
  terminalNotifications: TerminalNotification[];
  terminalSwitcherFolders: TreeFolder[] | undefined;
  terminalSwitcherRecentScope: "client" | "global" | "related";
  treeFolders: TreeFolder[] | undefined;
  workspaceMode: WorkspaceMode;
  createMutationError: unknown;
  onCloneTerminal: () => void;
  onClientSwitch: () => void;
  onExpandRecord: () => void;
  onGitDiff: () => void;
  onGlobalTerminalSwitch: () => void;
  onLocateSelectedTerminal: () => void;
  onNewTerminal: () => void;
  onNewTerminalProject: () => void;
  onOpenArtifacts: () => void;
  onOpenProjectTodoBoard: () => void;
  onQuickInput: () => void;
  onRelatedTerminalSwitch: () => void;
  onSettings: () => void;
  onSubmitCustomQuickKey: (quickKey: CustomQuickKey) => boolean;
  onSwitchTerminal: () => void;
  onToggleAuxTerminal: () => void;
  onToggleNotificationCenter: () => void;
  onToggleWorkspaceMode: () => void;
};

function errorMessage(error: unknown, fallback: string): string {
  return error instanceof Error ? error.message : fallback;
}

export function useAppViewModel({
  auxTerminalOpen,
  cloneMutationError,
  customQuickKeys,
  deleteClientMutationError,
  deleteClientMutationVariables,
  deleteMutationError,
  deleteMutationVariables,
  generateTraceMutationError,
  keyboardShortcutBindings,
  selectedClientId,
  selectedClientOffline,
  selectedProject,
  selectedProjectFile,
  selectedProjectPath,
  selectedWindowId,
  selectedWindowTitle,
  terminalCloneBusy,
  terminalConnectionStatus,
  terminalCreateBusy,
  terminalNotifications,
  terminalSwitcherFolders,
  terminalSwitcherRecentScope,
  treeFolders,
  workspaceMode,
  createMutationError,
  onCloneTerminal,
  onClientSwitch,
  onExpandRecord,
  onGitDiff,
  onGlobalTerminalSwitch,
  onLocateSelectedTerminal,
  onNewTerminal,
  onNewTerminalProject,
  onOpenArtifacts,
  onOpenProjectTodoBoard,
  onQuickInput,
  onRelatedTerminalSwitch,
  onSettings,
  onSubmitCustomQuickKey,
  onSwitchTerminal,
  onToggleAuxTerminal,
  onToggleNotificationCenter,
  onToggleWorkspaceMode,
}: AppViewModelArgs) {
  const { t } = useI18n();
  const switchTerminalShortcut = effectiveKeyboardShortcut("switch-terminal", keyboardShortcutBindings);
  const switchGlobalTerminalShortcut = effectiveKeyboardShortcut("switch-terminal-global", keyboardShortcutBindings);
  const switchRelatedTerminalShortcut = effectiveKeyboardShortcut("switch-related-terminal", keyboardShortcutBindings);
  const activeTerminalSwitcherShortcut: KeyboardShortcut | null = terminalSwitcherRecentScope === "related"
    ? switchRelatedTerminalShortcut
    : terminalSwitcherRecentScope === "global"
      ? switchGlobalTerminalShortcut
      : switchTerminalShortcut;
  const newTerminalShortcutLabel = keyboardShortcutLabel(effectiveKeyboardShortcut("new-terminal", keyboardShortcutBindings));
  const quickInputShortcutLabel = keyboardShortcutLabel(effectiveKeyboardShortcut("quick-input", keyboardShortcutBindings));
  const auxTerminalShortcutLabel = keyboardShortcutLabel(effectiveKeyboardShortcut("toggle-aux-terminal", keyboardShortcutBindings));
  const relatedTerminalShortcutLabel = keyboardShortcutLabel(switchRelatedTerminalShortcut);
  const cloneTerminalShortcutLabel = keyboardShortcutLabel(effectiveKeyboardShortcut("clone-terminal", keyboardShortcutBindings));
  const gitDiffShortcutLabel = keyboardShortcutLabel(effectiveKeyboardShortcut("git-diff", keyboardShortcutBindings));
  const settingsShortcutLabel = keyboardShortcutLabel(effectiveKeyboardShortcut("settings", keyboardShortcutBindings));
  const workspaceModeShortcutLabel = keyboardShortcutLabel(effectiveKeyboardShortcut("switch-workspace-mode", keyboardShortcutBindings));

  const onboardingSteps = useMemo(
    () => buildOnboardingSteps({
      t,
      settings: settingsShortcutLabel,
      switchTerminal: keyboardShortcutLabel(effectiveKeyboardShortcut("switch-terminal", keyboardShortcutBindings)),
      newTerminal: newTerminalShortcutLabel,
      newTerminalProject: keyboardShortcutLabel(effectiveKeyboardShortcut("new-terminal-project", keyboardShortcutBindings)),
      quickInput: quickInputShortcutLabel,
    }),
    [keyboardShortcutBindings, newTerminalShortcutLabel, quickInputShortcutLabel, settingsShortcutLabel, t],
  );

  const unreadNotificationCount = terminalNotifications.filter((notification) => !notification.read).length;
  const toolbarTerminalTitle = selectedWindowTitle ?? (selectedWindowId === null ? t("terminal.noSelected") : t("terminal.titleFallback"));
  const toolbarTitle = workspaceMode === "files"
    ? selectedProjectFile?.name ?? selectedProject?.display_name ?? selectedProjectPath ?? t("workspace.files")
    : workspaceMode === "kanban"
      ? selectedProject?.display_name ?? selectedProjectPath ?? t("workspace.kanban")
    : toolbarTerminalTitle;
  const toolbarSubtitle = workspaceMode === "files"
    ? selectedProjectFile?.path ?? selectedProjectPath ?? t("workspace.projectFiles")
    : workspaceMode === "kanban"
      ? selectedProjectPath ?? t("workspace.projectKanban")
    : terminalStatusLabel(terminalConnectionStatus, t);

  const mobileShortcutActions: MobileShortcutAction[] = useMemo(
    () => buildMobileShortcutActions({
      auxTerminalOpen,
      auxTerminalShortcutLabel,
      cloneTerminalShortcutLabel,
      customQuickKeys,
      keyboardShortcutBindings,
      relatedTerminalShortcutLabel,
      selectedClientId,
      selectedClientOffline,
      selectedProjectPath,
      selectedWindowId,
      terminalCloneBusy,
      terminalConnectionStatus,
      terminalCreateBusy,
      terminalSwitcherFolders: terminalSwitcherFolders ?? treeFolders,
      t,
      unreadNotificationCount,
      workspaceMode,
      workspaceModeShortcutLabel,
      onCloneTerminal,
      onClientSwitch,
      onExpandRecord,
      onGitDiff,
      onGlobalTerminalSwitch,
      onLocateSelectedTerminal,
      onNewTerminal,
      onNewTerminalProject,
      onOpenArtifacts,
      onOpenProjectTodoBoard,
      onQuickInput,
      onRelatedTerminalSwitch,
      onSettings,
      onSubmitCustomQuickKey,
      onSwitchTerminal,
      onToggleAuxTerminal,
      onToggleNotificationCenter,
      onToggleWorkspaceMode,
    }),
    [
      auxTerminalOpen,
      auxTerminalShortcutLabel,
      cloneTerminalShortcutLabel,
      customQuickKeys,
      keyboardShortcutBindings,
      onCloneTerminal,
      onClientSwitch,
      onExpandRecord,
      onGitDiff,
      onGlobalTerminalSwitch,
      onLocateSelectedTerminal,
      onNewTerminal,
      onNewTerminalProject,
      onOpenArtifacts,
      onOpenProjectTodoBoard,
      onQuickInput,
      onRelatedTerminalSwitch,
      onSettings,
      onSubmitCustomQuickKey,
      onSwitchTerminal,
      onToggleAuxTerminal,
      onToggleNotificationCenter,
      onToggleWorkspaceMode,
      relatedTerminalShortcutLabel,
      selectedClientId,
      selectedClientOffline,
      selectedProjectPath,
      selectedWindowId,
      terminalCloneBusy,
      terminalConnectionStatus,
      terminalCreateBusy,
      terminalSwitcherFolders,
      t,
      treeFolders,
      unreadNotificationCount,
      workspaceMode,
      workspaceModeShortcutLabel,
    ],
  );

  return {
    activeTerminalSwitcherShortcut,
    agentPreviewCanSendQuickInput: terminalConnectionStatus === "connected",
    auxTerminalShortcutLabel,
    cloneErrorMessage: errorMessage(cloneMutationError, "Failed to clone terminal."),
    cloneTerminalShortcutLabel,
    createErrorMessage: errorMessage(createMutationError, "Failed to create terminal."),
    deleteClientErrorMessage: errorMessage(deleteClientMutationError, "Failed to delete client."),
    deleteClientId: deleteClientMutationVariables?.clientId ?? null,
    deleteErrorMessage: errorMessage(deleteMutationError, "Failed to delete terminal."),
    deletingWindowId: deleteMutationVariables?.windowId ?? null,
    generateTraceErrorMessage: errorMessage(generateTraceMutationError, "Failed to generate trace."),
    gitDiffShortcutLabel,
    mobileShortcutActions,
    newTerminalShortcutLabel,
    onboardingSteps,
    quickInputShortcutLabel,
    relatedTerminalShortcutLabel,
    settingsShortcutLabel,
    toolbarSubtitle,
    toolbarTitle,
    unreadNotificationCount,
    workspaceModeShortcutLabel,
  };
}
