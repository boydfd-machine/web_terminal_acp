import { useCallback, type MutableRefObject } from "react";

import { runOnboardingAppAction } from "../appOnboardingActions";
import type { AddClientMode } from "../appTypes";
import type { OnboardingAction } from "../components/OnboardingTour";
import type { TerminalPaneHandle } from "../components/TerminalPane";
import type { TerminalCreateContext } from "../components/TerminalCreateModal";
import type { SettingsView } from "../components/SettingsModal";
import type { TerminalSwitcherMode, TerminalSwitcherRecentScope } from "../components/TerminalSwitcher";

type UseOnboardingActionsArgs = {
  selectedClientId: string | null;
  selectedClientOffline: boolean;
  selectedWindowId: string | null;
  terminalPaneRef: MutableRefObject<TerminalPaneHandle | null>;
  setAddClientInitialMode: (mode: AddClientMode) => void;
  setAddClientModalOpen: (open: boolean) => void;
  setBootstrapFailed: (failed: boolean) => void;
  setDetailPanelOpen: (open: boolean) => void;
  setGitDiffBrowserOpen: (open: boolean) => void;
  setMobileTerminalActive: (active: boolean) => void;
  setNotificationCenterOpen: (open: boolean) => void;
  setProjectTerminalPickerOpen: (open: boolean) => void;
  setSettingsInitialView: (view: SettingsView) => void;
  setSettingsOpen: (open: boolean) => void;
  setTerminalControlsOpen: (open: boolean) => void;
  setTerminalCreateContext: (context: TerminalCreateContext | null) => void;
  setTerminalQuickInputOpen: (open: boolean) => void;
  setTerminalSwitcherMode: (mode: TerminalSwitcherMode) => void;
  setTerminalSwitcherOpen: (open: boolean) => void;
  setTerminalSwitcherRecentScope: (scope: TerminalSwitcherRecentScope) => void;
};

export function useOnboardingActions({
  selectedClientId,
  selectedClientOffline,
  selectedWindowId,
  terminalPaneRef,
  setAddClientInitialMode,
  setAddClientModalOpen,
  setBootstrapFailed,
  setDetailPanelOpen,
  setGitDiffBrowserOpen,
  setMobileTerminalActive,
  setNotificationCenterOpen,
  setProjectTerminalPickerOpen,
  setSettingsInitialView,
  setSettingsOpen,
  setTerminalControlsOpen,
  setTerminalCreateContext,
  setTerminalQuickInputOpen,
  setTerminalSwitcherMode,
  setTerminalSwitcherOpen,
  setTerminalSwitcherRecentScope,
}: UseOnboardingActionsArgs) {
  const startOnboardingFromSettings = useCallback(() => {
    setSettingsOpen(false);
    setSettingsInitialView("general");
    window.requestAnimationFrame(() => {
      window.dispatchEvent(new Event("web-terminal-acp:start-onboarding"));
    });
  }, [setSettingsInitialView, setSettingsOpen]);

  const runOnboardingAction = useCallback((action: OnboardingAction) => {
    runOnboardingAppAction(action, {
      selectedClientId,
      selectedClientOffline,
      selectedWindowId,
      terminalPaneRef,
      setAddClientInitialMode,
      setAddClientModalOpen,
      setBootstrapFailed,
      setDetailPanelOpen,
      setGitDiffBrowserOpen,
      setMobileTerminalActive,
      setNotificationCenterOpen,
      setProjectTerminalPickerOpen,
      setSettingsInitialView,
      setSettingsOpen,
      setTerminalControlsOpen,
      setTerminalCreateContext,
      setTerminalQuickInputOpen,
      setTerminalSwitcherMode,
      setTerminalSwitcherOpen,
      setTerminalSwitcherRecentScope,
    });
  }, [
    selectedClientId,
    selectedClientOffline,
    selectedWindowId,
    terminalPaneRef,
    setAddClientInitialMode,
    setAddClientModalOpen,
    setBootstrapFailed,
    setDetailPanelOpen,
    setGitDiffBrowserOpen,
    setMobileTerminalActive,
    setNotificationCenterOpen,
    setProjectTerminalPickerOpen,
    setSettingsInitialView,
    setSettingsOpen,
    setTerminalControlsOpen,
    setTerminalCreateContext,
    setTerminalQuickInputOpen,
    setTerminalSwitcherMode,
    setTerminalSwitcherOpen,
    setTerminalSwitcherRecentScope,
  ]);

  return {
    runOnboardingAction,
    startOnboardingFromSettings,
  };
}
