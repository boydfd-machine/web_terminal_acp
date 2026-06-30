import type { MutableRefObject } from "react";

import { useAppKeyboardShortcuts } from "./useAppKeyboardShortcuts";
import { useAppLifecycleEffects } from "./useAppLifecycleEffects";
import type { useAppCommandActions } from "./useAppCommandActions";
import type { useAppUiState } from "./useAppUiState";
import type { useTerminalArtifactDrawer } from "./useTerminalArtifactDrawer";
import type { useTerminalCreateActions } from "./useTerminalCreateActions";
import type { CustomQuickKey } from "../terminalQuickKeys";
import type { TerminalPaneHandle } from "../components/TerminalPane";

type UseAppRuntimeEffectsArgs = {
  commandActions: ReturnType<typeof useAppCommandActions>;
  customQuickKeys: CustomQuickKey[];
  drawer: ReturnType<typeof useTerminalArtifactDrawer>;
  focusSelectedTerminal: () => void;
  openProjectTodoBoard: () => void;
  openProjectFileSearch: () => void;
  openProjectFileSwitcher: () => void;
  submitCustomQuickKey: (quickKey: CustomQuickKey) => boolean;
  terminalCreateActions: ReturnType<typeof useTerminalCreateActions>;
  terminalPaneRef: MutableRefObject<TerminalPaneHandle | null>;
  treeQuerySuccess: boolean;
  toggleVirtualKeysVisibility: () => void;
  toggleWorkspaceMode: () => void;
  ui: ReturnType<typeof useAppUiState>;
};

export function useAppRuntimeEffects({
  commandActions,
  customQuickKeys,
  drawer,
  focusSelectedTerminal,
  openProjectTodoBoard,
  openProjectFileSearch,
  openProjectFileSwitcher,
  submitCustomQuickKey,
  terminalCreateActions,
  terminalPaneRef,
  treeQuerySuccess,
  toggleWorkspaceMode,
  ui,
}: UseAppRuntimeEffectsArgs) {
  useAppKeyboardShortcuts({
    addClientModalOpen: ui.addClientModalOpen,
    agentRecordModalOpen: ui.agentRecordModalOpen,
    artifactQuickOpenOpen: ui.artifactQuickOpenOpen,
    artifactResultViewerOpen: drawer.artifactResultViewerArtifact !== null,
    auxTerminalOpen: drawer.auxTerminalOpen,
    auxTerminalTabsVisible: drawer.auxTerminalTabsVisible,
    clientSwitcherOpen: ui.clientSwitcherOpen,
    customQuickKeys,
    focusSelectedTerminal,
    gitDiffBrowserOpen: ui.gitDiffBrowserOpen,
    keyboardShortcutBindings: ui.keyboardShortcutBindings,
    notificationCenterOpen: ui.notificationCenterOpen,
    projectFileSearchOpen: ui.projectFileSearchOpen,
    projectFileSwitcherOpen: ui.projectFileSwitcherOpen,
    projectTerminalPickerOpen: ui.projectTerminalPickerOpen,
    selectedClientId: ui.selectedClientId,
    selectedWindowId: ui.selectedWindowId,
    settingsOpen: ui.settingsOpen,
    submitCustomQuickKey,
    terminalControlsOpen: ui.terminalControlsOpen,
    terminalCreateContextOpen: ui.terminalCreateContext !== null,
    terminalSwitcherOpen: ui.terminalSwitcherOpen,
    workspaceMode: ui.workspaceMode,
    actions: {
      cloneTerminal: commandActions.triggerCloneTerminal,
      expandRecord: commandActions.triggerAgentRecordExpand,
      gitDiff: commandActions.triggerGitDiffBrowser,
      locateTerminal: commandActions.triggerLocateSelectedTerminal,
      newTerminal: terminalCreateActions.triggerNewTerminalShortcut,
      newTerminalProject: terminalCreateActions.triggerNewTerminalByProjectShortcut,
      openArtifacts: drawer.triggerArtifactQuickOpen,
      openProjectTodoBoard,
      projectFileSearch: openProjectFileSearch,
      quickInput: commandActions.triggerQuickInput,
      refitTerminal: () => {
        terminalPaneRef.current?.refit();
      },
      settings: commandActions.toggleSettings,
      switchClient: commandActions.triggerClientSwitcherShortcut,
      switchProjectFile: openProjectFileSwitcher,
      switchRelatedTerminal: commandActions.triggerRelatedTerminalSwitch,
      switchTerminal: commandActions.triggerClientScopedTerminalSwitcherShortcut,
      switchTerminalGlobal: commandActions.triggerGlobalTerminalSwitcherShortcut,
      switchWorkspaceMode: toggleWorkspaceMode,
      switchAuxTerminalTab: drawer.switchAuxTerminalTab,
      toggleAuxTerminal: drawer.toggleAuxTerminal,
    },
  });

  useAppLifecycleEffects({
    focusSelectedTerminal,
    projectTodoDateFilter: ui.projectTodoDateFilter,
    selectedClientId: ui.selectedClientId,
    selectedWindowId: ui.selectedWindowId,
    terminalControlsOpen: ui.terminalControlsOpen,
    terminalControlsRef: ui.terminalControlsRef,
    terminalPaneRef,
    terminalTimeRange: ui.terminalTimeRange,
    terminalViewportMode: ui.terminalViewportMode,
    treeQuerySuccess,
    workspaceMode: ui.workspaceMode,
    setAgentRecordModalOpen: ui.setAgentRecordModalOpen,
    setArtifactQuickOpenOpen: ui.setArtifactQuickOpenOpen,
    setArtifactResultViewerArtifact: drawer.setArtifactResultViewerArtifact,
    setClientSwitcherOpen: ui.setClientSwitcherOpen,
    setGitDiffBrowserOpen: ui.setGitDiffBrowserOpen,
    setNotificationCenterOpen: ui.setNotificationCenterOpen,
    setProjectTerminalPickerOpen: ui.setProjectTerminalPickerOpen,
    setTerminalControlsOpen: ui.setTerminalControlsOpen,
    setTerminalCreateContext: ui.setTerminalCreateContext,
    setTerminalImmersive: ui.setTerminalImmersive,
    setTerminalSwitcherOpen: ui.setTerminalSwitcherOpen,
  });
}
