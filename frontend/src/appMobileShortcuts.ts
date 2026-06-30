import type { MobileShortcutAction } from "./components/MobileShortcutFab";
import type { WorkspaceMode } from "./appState";
import type { TranslateFn } from "./i18n";
import type { KeyboardShortcutBindings } from "./keyboardShortcuts";
import { effectiveKeyboardShortcut, keyboardShortcutLabel } from "./keyboardShortcuts";
import type { CustomQuickKey } from "./terminalQuickKeys";
import { relatedTerminalWindows } from "./terminalTree";
import type { TreeFolder } from "./types";

type BuildMobileShortcutActionsArgs = {
  auxTerminalOpen: boolean;
  auxTerminalShortcutLabel: string;
  cloneTerminalShortcutLabel: string;
  customQuickKeys: CustomQuickKey[];
  keyboardShortcutBindings: KeyboardShortcutBindings;
  relatedTerminalShortcutLabel: string;
  selectedClientId: string | null;
  selectedClientOffline: boolean;
  selectedProjectPath: string | null;
  selectedWindowId: string | null;
  terminalCloneBusy: boolean;
  terminalConnectionStatus: string;
  terminalCreateBusy: boolean;
  terminalSwitcherFolders: TreeFolder[] | undefined;
  t: TranslateFn;
  unreadNotificationCount: number;
  workspaceMode: WorkspaceMode;
  workspaceModeShortcutLabel: string;
  onCloneTerminal: () => void;
  onClientSwitch: () => void;
  onExpandRecord: () => void;
  onGlobalTerminalSwitch: () => void;
  onLocateSelectedTerminal: () => void;
  onNewTerminal: () => void;
  onNewTerminalProject: () => void;
  onOpenArtifacts: () => void;
  onOpenProjectTodoBoard: () => void;
  onQuickInput: () => void;
  onRelatedTerminalSwitch: () => void;
  onSettings: () => void;
  onSubmitCustomQuickKey: (quickKey: CustomQuickKey) => void;
  onSwitchTerminal: () => void;
  onToggleAuxTerminal: () => void;
  onToggleNotificationCenter: () => void;
  onToggleWorkspaceMode: () => void;
  onGitDiff: () => void;
};

export function buildMobileShortcutActions({
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
  terminalSwitcherFolders,
  t,
  unreadNotificationCount,
  workspaceMode,
  workspaceModeShortcutLabel,
  onCloneTerminal,
  onClientSwitch,
  onExpandRecord,
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
  onGitDiff,
}: BuildMobileShortcutActionsArgs): MobileShortcutAction[] {
  return [
    {
      id: "switch-terminal",
      label: t("shortcut.switchTerminal"),
      hint: keyboardShortcutLabel(effectiveKeyboardShortcut("switch-terminal", keyboardShortcutBindings)),
      onPress: onSwitchTerminal,
    },
    {
      id: "switch-related-terminal",
      label: t("mobileShortcut.relatedTerminal"),
      hint: relatedTerminalShortcutLabel,
      disabled: relatedTerminalWindows(terminalSwitcherFolders, selectedWindowId).length < 2,
      onPress: onRelatedTerminalSwitch,
    },
    {
      id: "switch-terminal-global",
      label: t("shortcut.switchTerminalGlobal"),
      hint: keyboardShortcutLabel(effectiveKeyboardShortcut("switch-terminal-global", keyboardShortcutBindings)),
      onPress: onGlobalTerminalSwitch,
    },
    {
      id: "switch-client",
      label: t("shortcut.switchClient"),
      hint: keyboardShortcutLabel(effectiveKeyboardShortcut("switch-client", keyboardShortcutBindings)),
      onPress: onClientSwitch,
    },
    {
      id: "new-terminal",
      label: t("shortcut.newTerminal"),
      hint: keyboardShortcutLabel(effectiveKeyboardShortcut("new-terminal", keyboardShortcutBindings)),
      disabled: selectedClientId === null || terminalCreateBusy || selectedClientOffline,
      onPress: onNewTerminal,
    },
    {
      id: "new-terminal-project",
      label: t("shortcut.newTerminalProject"),
      hint: keyboardShortcutLabel(effectiveKeyboardShortcut("new-terminal-project", keyboardShortcutBindings)),
      disabled: selectedClientId === null || terminalCreateBusy || selectedClientOffline,
      onPress: onNewTerminalProject,
    },
    {
      id: "switch-workspace-mode",
      label: workspaceMode === "terminal" ? t("mobileShortcut.fileMode") : t("mobileShortcut.terminalMode"),
      hint: workspaceModeShortcutLabel,
      disabled: selectedClientId === null || (workspaceMode === "terminal" && selectedProjectPath === null),
      onPress: onToggleWorkspaceMode,
    },
    {
      id: "clone-terminal",
      label: t("shortcut.cloneTerminal"),
      hint: cloneTerminalShortcutLabel,
      disabled: selectedClientId === null || selectedWindowId === null || terminalCreateBusy || terminalCloneBusy || selectedClientOffline,
      onPress: onCloneTerminal,
    },
    {
      id: "quick-input",
      label: t("shortcut.quickInput"),
      hint: keyboardShortcutLabel(effectiveKeyboardShortcut("quick-input", keyboardShortcutBindings)),
      disabled: selectedClientId === null || selectedWindowId === null,
      onPress: onQuickInput,
    },
    {
      id: "open-artifacts",
      label: t("shortcut.openArtifacts"),
      hint: keyboardShortcutLabel(effectiveKeyboardShortcut("open-artifacts", keyboardShortcutBindings)),
      disabled: selectedClientId === null || selectedWindowId === null,
      onPress: onOpenArtifacts,
    },
    {
      id: "open-project-todo-board",
      label: t("shortcut.openProjectTodoBoard"),
      hint: keyboardShortcutLabel(effectiveKeyboardShortcut("open-project-todo-board", keyboardShortcutBindings)),
      disabled: selectedClientId === null || (selectedProjectPath === null && selectedWindowId === null),
      onPress: onOpenProjectTodoBoard,
    },
    {
      id: "toggle-aux-terminal",
      label: t("shortcut.toggleAuxTerminal"),
      hint: auxTerminalShortcutLabel,
      disabled: selectedClientId === null || selectedWindowId === null,
      onPress: onToggleAuxTerminal,
    },
    {
      id: "locate-terminal",
      label: t("shortcut.locateTerminal"),
      hint: keyboardShortcutLabel(effectiveKeyboardShortcut("locate-terminal", keyboardShortcutBindings)),
      disabled: selectedClientId === null || selectedWindowId === null,
      onPress: onLocateSelectedTerminal,
    },
    {
      id: "expand-record",
      label: t("toolbar.agentPreview"),
      hint: keyboardShortcutLabel(effectiveKeyboardShortcut("expand-record", keyboardShortcutBindings)),
      disabled: selectedClientId === null || selectedWindowId === null,
      onPress: onExpandRecord,
    },
    {
      id: "git-diff",
      label: t("shortcut.gitDiff"),
      hint: keyboardShortcutLabel(effectiveKeyboardShortcut("git-diff", keyboardShortcutBindings)),
      disabled: selectedClientId === null || selectedWindowId === null,
      onPress: onGitDiff,
    },
    {
      id: "notifications",
      label: t("mobileShortcut.notifications"),
      badge: unreadNotificationCount,
      onPress: onToggleNotificationCenter,
    },
    ...customQuickKeys.map((quickKey) => ({
      id: `quick-key-${quickKey.id}`,
      label: quickKey.label,
      hint: quickKey.shortcut ? keyboardShortcutLabel(quickKey.shortcut) : t("mobileShortcut.quickKeyHint"),
      disabled: selectedClientId === null || selectedWindowId === null || terminalConnectionStatus !== "connected",
      onPress: () => onSubmitCustomQuickKey(quickKey),
    })),
    {
      id: "settings",
      label: t("shortcut.settings"),
      hint: keyboardShortcutLabel(effectiveKeyboardShortcut("settings", keyboardShortcutBindings)),
      onPress: onSettings,
    },
  ];
}
