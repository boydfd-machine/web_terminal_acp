import { useCallback, useEffect } from "react";

import type { KeyboardShortcutBindings, KeyboardShortcutId } from "../keyboardShortcuts";
import {
  effectiveKeyboardShortcut,
  keyboardShortcutMatches,
} from "../keyboardShortcuts";
import {
  isBlockingTextInput,
  isGlobalShortcutTextTarget,
  isXtermInput,
} from "../keyboardTargets";
import type { CustomQuickKey } from "../terminalQuickKeys";
import type { WorkspaceMode } from "../appState";

type ShortcutActions = {
  expandRecord: () => void;
  gitDiff: () => void;
  locateTerminal: () => void;
  newTerminal: () => void;
  newTerminalProject: () => void;
  openArtifacts: () => void;
  openProjectTodoBoard: () => void;
  projectFileSearch: () => void;
  quickInput: () => void;
  refitTerminal: () => void;
  settings: () => void;
  switchClient: () => void;
  switchProjectFile: () => void;
  switchRelatedTerminal: () => void;
  switchTerminal: () => void;
  switchTerminalGlobal: () => void;
  switchAuxTerminalTab: (direction: "previous" | "next") => void;
  switchWorkspaceMode: () => void;
  cloneTerminal: () => void;
  toggleAuxTerminal: () => void;
};

type UseAppKeyboardShortcutsArgs = {
  addClientModalOpen: boolean;
  agentRecordModalOpen: boolean;
  artifactQuickOpenOpen: boolean;
  artifactResultViewerOpen: boolean;
  auxTerminalOpen: boolean;
  auxTerminalTabsVisible: boolean;
  clientSwitcherOpen: boolean;
  customQuickKeys: CustomQuickKey[];
  focusSelectedTerminal: () => void;
  gitDiffBrowserOpen: boolean;
  keyboardShortcutBindings: KeyboardShortcutBindings;
  notificationCenterOpen: boolean;
  projectFileSearchOpen: boolean;
  projectFileSwitcherOpen: boolean;
  projectTerminalPickerOpen: boolean;
  selectedClientId: string | null;
  selectedWindowId: string | null;
  settingsOpen: boolean;
  submitCustomQuickKey: (quickKey: CustomQuickKey) => boolean;
  terminalControlsOpen: boolean;
  terminalCreateContextOpen: boolean;
  terminalSwitcherOpen: boolean;
  workspaceMode: WorkspaceMode;
  actions: ShortcutActions;
};

const SHORTCUT_ORDER: KeyboardShortcutId[] = [
  "new-terminal-project",
  "switch-terminal-global",
  "switch-client",
  "switch-related-terminal",
  "switch-terminal",
  "switch-workspace-mode",
  "new-terminal",
  "clone-terminal",
  "open-artifacts",
  "open-project-todo-board",
  "project-file-search",
  "toggle-aux-terminal",
  "quick-input",
  "expand-record",
  "locate-terminal",
  "git-diff",
  "refit-terminal",
  "settings",
];

export function useAppKeyboardShortcuts({
  addClientModalOpen,
  agentRecordModalOpen,
  artifactQuickOpenOpen,
  artifactResultViewerOpen,
  auxTerminalOpen,
  auxTerminalTabsVisible,
  clientSwitcherOpen,
  customQuickKeys,
  focusSelectedTerminal,
  gitDiffBrowserOpen,
  keyboardShortcutBindings,
  notificationCenterOpen,
  projectFileSearchOpen,
  projectFileSwitcherOpen,
  projectTerminalPickerOpen,
  selectedClientId,
  selectedWindowId,
  settingsOpen,
  submitCustomQuickKey,
  terminalControlsOpen,
  terminalCreateContextOpen,
  terminalSwitcherOpen,
  workspaceMode,
  actions,
}: UseAppKeyboardShortcutsArgs): void {
  const { switchAuxTerminalTab } = actions;
  const runKeyboardShortcutAction = useCallback((id: KeyboardShortcutId) => {
    switch (id) {
      case "switch-terminal":
        if (workspaceMode === "files") {
          actions.switchProjectFile();
          return true;
        }
        actions.switchTerminal();
        return true;
      case "switch-related-terminal":
        actions.switchRelatedTerminal();
        return true;
      case "switch-terminal-global":
        actions.switchTerminalGlobal();
        return true;
      case "switch-client":
        actions.switchClient();
        return true;
      case "new-terminal":
        actions.newTerminal();
        return true;
      case "new-terminal-project":
        actions.newTerminalProject();
        return true;
      case "switch-workspace-mode":
        actions.switchWorkspaceMode();
        return true;
      case "clone-terminal":
        actions.cloneTerminal();
        return true;
      case "open-artifacts":
        actions.openArtifacts();
        return true;
      case "open-project-todo-board":
        actions.openProjectTodoBoard();
        return true;
      case "project-file-search":
        if (workspaceMode !== "files") {
          return false;
        }
        actions.projectFileSearch();
        return true;
      case "toggle-aux-terminal":
        actions.toggleAuxTerminal();
        return true;
      case "quick-input":
        actions.quickInput();
        return true;
      case "expand-record":
        actions.expandRecord();
        return true;
      case "locate-terminal":
        actions.locateTerminal();
        return true;
      case "git-diff":
        actions.gitDiff();
        return true;
      case "refit-terminal":
        actions.refitTerminal();
        return true;
      case "settings":
        actions.settings();
        return true;
    }
  }, [actions, workspaceMode]);

  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      if (settingsOpen || isGlobalShortcutTextTarget(event.target)) {
        return;
      }

      if (auxTerminalTabsVisible && event.altKey && !event.ctrlKey && !event.metaKey && !event.shiftKey) {
        const direction = auxTerminalTabShortcutDirection(event);
        if (direction !== null) {
          event.preventDefault();
          event.stopPropagation();
          switchAuxTerminalTab(direction);
          return;
        }
      }

      for (const definition of SHORTCUT_ORDER) {
        const shortcut = effectiveKeyboardShortcut(definition, keyboardShortcutBindings);
        if (!keyboardShortcutMatches(event, shortcut)) {
          continue;
        }
        if (definition === "project-file-search" && workspaceMode !== "files") {
          continue;
        }

        event.preventDefault();
        event.stopPropagation();
        if (event.repeat && definition === "locate-terminal") {
          return;
        }
        runKeyboardShortcutAction(definition);
        return;
      }

      for (const quickKey of customQuickKeys) {
        if (!keyboardShortcutMatches(event, quickKey.shortcut ?? null)) {
          continue;
        }

        event.preventDefault();
        event.stopPropagation();
        submitCustomQuickKey(quickKey);
        return;
      }
    };

    window.addEventListener("keydown", handleKeyDown, { capture: true });
    return () => window.removeEventListener("keydown", handleKeyDown, { capture: true });
  }, [
    auxTerminalTabsVisible,
    customQuickKeys,
    keyboardShortcutBindings,
    runKeyboardShortcutAction,
    settingsOpen,
    submitCustomQuickKey,
    switchAuxTerminalTab,
  ]);

  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key !== "Escape" || event.defaultPrevented) {
        return;
      }

      if (
        terminalSwitcherOpen
        || clientSwitcherOpen
        || projectFileSearchOpen
        || projectFileSwitcherOpen
        || projectTerminalPickerOpen
        || terminalCreateContextOpen
        || notificationCenterOpen
        || settingsOpen
        || addClientModalOpen
        || terminalControlsOpen
        || gitDiffBrowserOpen
        || agentRecordModalOpen
        || artifactQuickOpenOpen
        || artifactResultViewerOpen
        || auxTerminalOpen
      ) {
        return;
      }

      const target = event.target;
      const activeElement = document.activeElement;
      if (isXtermInput(target) || isXtermInput(activeElement)) {
        return;
      }

      if (isBlockingTextInput(target) || isBlockingTextInput(activeElement)) {
        return;
      }

      if (selectedClientId !== null && selectedWindowId !== null) {
        event.preventDefault();
        focusSelectedTerminal();
      }
    };

    window.addEventListener("keydown", handleKeyDown, { capture: true });
    return () => window.removeEventListener("keydown", handleKeyDown, { capture: true });
  }, [
    addClientModalOpen,
    agentRecordModalOpen,
    artifactQuickOpenOpen,
    artifactResultViewerOpen,
    auxTerminalOpen,
    clientSwitcherOpen,
    focusSelectedTerminal,
    gitDiffBrowserOpen,
    notificationCenterOpen,
    projectFileSearchOpen,
    projectFileSwitcherOpen,
    projectTerminalPickerOpen,
    selectedClientId,
    selectedWindowId,
    settingsOpen,
    terminalControlsOpen,
    terminalCreateContextOpen,
    terminalSwitcherOpen,
  ]);
}

function auxTerminalTabShortcutDirection(event: KeyboardEvent): "previous" | "next" | null {
  if (event.key === "[" || event.code === "BracketLeft") {
    return "previous";
  }
  if (event.key === "]" || event.code === "BracketRight") {
    return "next";
  }
  return null;
}
