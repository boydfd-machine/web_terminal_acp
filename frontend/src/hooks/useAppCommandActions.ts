import { useCallback, type MutableRefObject } from "react";

import type { TerminalSwitcherRecentScope } from "../components/TerminalSwitcher";
import type { AgentRecordDataState } from "./useAgentRecordData";
import { projectPathForWindow } from "../terminalTree";

type CloneMutation = {
  mutate: (variables: { clientId: string; windowId: string }) => void;
};

type ProjectWindowLike = {
  cwd?: string | null;
  runtime_tags?: string[] | null;
} | null;

type UseAppCommandActionsArgs = {
  agentRecordModal: AgentRecordDataState;
  cloneMutation: CloneMutation;
  selectedClientId: string | null;
  selectedClientOffline: boolean;
  selectedWindow: ProjectWindowLike;
  selectedWindowId: string | null;
  terminalCloneBusy: boolean;
  terminalCreateBusy: boolean;
  terminalSwitcherOpen: boolean;
  terminalSwitcherRecentScope: TerminalSwitcherRecentScope;
  toggleTerminalSwitcherMode: () => void;
  setAgentRecordModalOpen: (open: boolean) => void;
  setClientSwitcherOpen: (open: boolean) => void;
  setDetailPanelOpen: (open: boolean) => void;
  setGitDiffBrowserOpen: (open: boolean) => void;
  setMobileTerminalActive: (active: boolean) => void;
  setNotificationCenterOpen: (open: boolean) => void;
  setProjectTerminalPickerOpen: (open: boolean) => void;
  setSelectedProjectPath: (path: string | null) => void;
  setSettingsInitialView: (view: "general") => void;
  setSettingsOpen: (open: boolean | ((open: boolean) => boolean)) => void;
  setTerminalControlsOpen: (open: boolean) => void;
  setTerminalCreateContext: (context: null) => void;
  setTerminalImmersive: (immersive: boolean) => void;
  setTerminalListLocateSignal: (updater: (signal: number) => number) => void;
  setTerminalSwitcherMode: (mode: "recent" | "tree") => void;
  setTerminalSwitcherOpen: (open: boolean) => void;
  setTerminalSwitcherRecentScope: (scope: TerminalSwitcherRecentScope) => void;
  terminalPaneRef: MutableRefObject<{ openQuickInput: () => void } | null>;
};

export function useAppCommandActions({
  agentRecordModal,
  cloneMutation,
  selectedClientId,
  selectedClientOffline,
  selectedWindow,
  selectedWindowId,
  terminalCloneBusy,
  terminalCreateBusy,
  terminalSwitcherOpen,
  terminalSwitcherRecentScope,
  toggleTerminalSwitcherMode,
  setAgentRecordModalOpen,
  setClientSwitcherOpen,
  setDetailPanelOpen,
  setGitDiffBrowserOpen,
  setMobileTerminalActive,
  setNotificationCenterOpen,
  setProjectTerminalPickerOpen,
  setSelectedProjectPath,
  setSettingsInitialView,
  setSettingsOpen,
  setTerminalControlsOpen,
  setTerminalCreateContext,
  setTerminalImmersive,
  setTerminalListLocateSignal,
  setTerminalSwitcherMode,
  setTerminalSwitcherOpen,
  setTerminalSwitcherRecentScope,
  terminalPaneRef,
}: UseAppCommandActionsArgs) {
  const triggerTerminalSwitcherShortcut = useCallback((scope: TerminalSwitcherRecentScope = "client") => {
    if (terminalSwitcherOpen) {
      setTerminalSwitcherRecentScope(scope);
      if (terminalSwitcherRecentScope !== scope) {
        setTerminalSwitcherMode("recent");
      } else {
        toggleTerminalSwitcherMode();
      }
      return;
    }

    setTerminalSwitcherMode("recent");
    setTerminalSwitcherRecentScope(scope);
    setTerminalSwitcherOpen(true);
  }, [
    setTerminalSwitcherMode,
    setTerminalSwitcherOpen,
    setTerminalSwitcherRecentScope,
    terminalSwitcherOpen,
    terminalSwitcherRecentScope,
    toggleTerminalSwitcherMode,
  ]);

  const triggerGlobalTerminalSwitcherShortcut = useCallback(() => {
    triggerTerminalSwitcherShortcut("global");
  }, [triggerTerminalSwitcherShortcut]);

  const triggerClientScopedTerminalSwitcherShortcut = useCallback(() => {
    triggerTerminalSwitcherShortcut("client");
  }, [triggerTerminalSwitcherShortcut]);

  const triggerClientSwitcherShortcut = useCallback(() => {
    setTerminalSwitcherOpen(false);
    setProjectTerminalPickerOpen(false);
    setNotificationCenterOpen(false);
    setGitDiffBrowserOpen(false);
    setTerminalControlsOpen(false);
    setTerminalCreateContext(null);
    setClientSwitcherOpen(true);
  }, [
    setClientSwitcherOpen,
    setGitDiffBrowserOpen,
    setNotificationCenterOpen,
    setProjectTerminalPickerOpen,
    setTerminalControlsOpen,
    setTerminalCreateContext,
    setTerminalSwitcherOpen,
  ]);

  const triggerAgentRecordExpand = useCallback(() => {
    if (selectedClientId === null || selectedWindowId === null) {
      return;
    }

    setTerminalImmersive(false);
    setTerminalControlsOpen(false);
    setTerminalSwitcherOpen(false);
    setNotificationCenterOpen(false);
    agentRecordModal.setJumpRequest(null);
    agentRecordModal.setExpanded(true);
    setAgentRecordModalOpen(true);
  }, [
    agentRecordModal,
    selectedClientId,
    selectedWindowId,
    setAgentRecordModalOpen,
    setNotificationCenterOpen,
    setTerminalControlsOpen,
    setTerminalImmersive,
    setTerminalSwitcherOpen,
  ]);

  const triggerLocateSelectedTerminal = useCallback(() => {
    if (selectedClientId === null || selectedWindowId === null) {
      return;
    }

    const selectedWindowProjectPath = projectPathForWindow(selectedWindow);
    if (selectedWindowProjectPath !== null) {
      setSelectedProjectPath(selectedWindowProjectPath);
    }
    setMobileTerminalActive(false);
    setTerminalImmersive(false);
    setTerminalControlsOpen(false);
    setTerminalListLocateSignal((signal) => signal + 1);
  }, [
    selectedClientId,
    selectedWindow,
    selectedWindowId,
    setMobileTerminalActive,
    setSelectedProjectPath,
    setTerminalControlsOpen,
    setTerminalImmersive,
    setTerminalListLocateSignal,
  ]);

  const triggerGitDiffBrowser = useCallback(() => {
    if (selectedClientId === null || selectedWindowId === null) {
      return;
    }

    setTerminalImmersive(false);
    setTerminalControlsOpen(false);
    setTerminalSwitcherOpen(false);
    setProjectTerminalPickerOpen(false);
    setNotificationCenterOpen(false);
    setAgentRecordModalOpen(false);
    setDetailPanelOpen(false);
    setGitDiffBrowserOpen(true);
  }, [
    selectedClientId,
    selectedWindowId,
    setAgentRecordModalOpen,
    setDetailPanelOpen,
    setGitDiffBrowserOpen,
    setNotificationCenterOpen,
    setProjectTerminalPickerOpen,
    setTerminalControlsOpen,
    setTerminalImmersive,
    setTerminalSwitcherOpen,
  ]);

  const triggerQuickInput = useCallback(() => {
    if (selectedClientId === null || selectedWindowId === null) {
      return;
    }

    setMobileTerminalActive(true);
    requestAnimationFrame(() => {
      terminalPaneRef.current?.openQuickInput();
    });
  }, [selectedClientId, selectedWindowId, setMobileTerminalActive, terminalPaneRef]);

  const toggleSettings = useCallback(() => {
    setSettingsInitialView("general");
    setSettingsOpen((open) => !open);
  }, [setSettingsInitialView, setSettingsOpen]);

  const triggerCloneTerminal = useCallback(() => {
    if (
      selectedClientId === null
      || selectedWindowId === null
      || terminalCreateBusy
      || terminalCloneBusy
      || selectedClientOffline
    ) {
      return;
    }
    cloneMutation.mutate({ clientId: selectedClientId, windowId: selectedWindowId });
  }, [
    cloneMutation,
    selectedClientId,
    selectedClientOffline,
    selectedWindowId,
    terminalCloneBusy,
    terminalCreateBusy,
  ]);

  const triggerRelatedTerminalSwitch = useCallback(() => {
    if (
      selectedClientId === null
      || selectedWindowId === null
    ) {
      return;
    }
    setTerminalSwitcherMode("recent");
    setTerminalSwitcherRecentScope("related");
    setTerminalSwitcherOpen(true);
  }, [
    selectedClientId,
    selectedWindowId,
    setTerminalSwitcherMode,
    setTerminalSwitcherOpen,
    setTerminalSwitcherRecentScope,
  ]);

  return {
    toggleSettings,
    triggerAgentRecordExpand,
    triggerClientScopedTerminalSwitcherShortcut,
    triggerClientSwitcherShortcut,
    triggerCloneTerminal,
    triggerGitDiffBrowser,
    triggerGlobalTerminalSwitcherShortcut,
    triggerLocateSelectedTerminal,
    triggerQuickInput,
    triggerRelatedTerminalSwitch,
    triggerTerminalSwitcherShortcut,
  };
}
