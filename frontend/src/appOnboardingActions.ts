import type { RefObject } from "react";

import type { OnboardingAction } from "./components/OnboardingTour";
import type { AddClientMode } from "./appTypes";
import type { TerminalCreateContext } from "./components/TerminalCreateModal";
import type { TerminalPaneHandle } from "./components/TerminalPane";
import type { TerminalSwitcherMode, TerminalSwitcherRecentScope } from "./components/TerminalSwitcher";
import type { SettingsView } from "./components/SettingsModal";

type OnboardingActionHandlers = {
  selectedClientId: string | null;
  selectedClientOffline: boolean;
  selectedWindowId: string | null;
  terminalPaneRef: RefObject<TerminalPaneHandle | null>;
  setAddClientInitialMode: (mode: AddClientMode) => void;
  setAddClientModalOpen: (open: boolean) => void;
  setBootstrapFailed: (failed: boolean) => void;
  setDetailPanelOpen: (open: boolean) => void;
  setGitDiffBrowserOpen: (open: boolean) => void;
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
  setMobileTerminalActive: (active: boolean) => void;
};

function closeCommonSurfaces({
  setTerminalCreateContext,
  setTerminalSwitcherOpen,
  setProjectTerminalPickerOpen,
  setNotificationCenterOpen,
  setGitDiffBrowserOpen,
  setTerminalControlsOpen,
  setTerminalQuickInputOpen,
}: Pick<
  OnboardingActionHandlers,
  | "setTerminalCreateContext"
  | "setTerminalSwitcherOpen"
  | "setProjectTerminalPickerOpen"
  | "setNotificationCenterOpen"
  | "setGitDiffBrowserOpen"
  | "setTerminalControlsOpen"
  | "setTerminalQuickInputOpen"
>) {
  setTerminalCreateContext(null);
  setTerminalSwitcherOpen(false);
  setProjectTerminalPickerOpen(false);
  setNotificationCenterOpen(false);
  setGitDiffBrowserOpen(false);
  setTerminalControlsOpen(false);
  setTerminalQuickInputOpen(false);
}

export function runOnboardingAppAction(action: OnboardingAction, handlers: OnboardingActionHandlers): void {
  switch (action) {
    case "remote-bootstrap":
      handlers.setSettingsOpen(false);
      handlers.setSettingsInitialView("general");
      closeCommonSurfaces(handlers);
      handlers.setDetailPanelOpen(false);
      handlers.setBootstrapFailed(false);
      handlers.setAddClientInitialMode("bootstrap");
      handlers.setAddClientModalOpen(true);
      return;
    case "remote-registration-menu":
    case "remote-registration":
      closeCommonSurfaces(handlers);
      handlers.setSettingsInitialView("general");
      handlers.setSettingsOpen(false);
      handlers.setAddClientInitialMode("registration");
      handlers.setAddClientModalOpen(true);
      return;
    case "new-terminal":
      handlers.setAddClientModalOpen(false);
      handlers.setSettingsOpen(false);
      handlers.setSettingsInitialView("general");
      closeCommonSurfaces(handlers);
      return;
    case "quick-input":
      handlers.setAddClientModalOpen(false);
      handlers.setSettingsOpen(false);
      handlers.setSettingsInitialView("general");
      closeCommonSurfaces(handlers);
      if (handlers.selectedClientId !== null && handlers.selectedWindowId !== null) {
        handlers.setMobileTerminalActive(true);
        requestAnimationFrame(() => handlers.terminalPaneRef.current?.openQuickInput());
      }
      return;
    case "switch-terminal":
      handlers.setAddClientModalOpen(false);
      handlers.setSettingsOpen(false);
      handlers.setSettingsInitialView("general");
      handlers.setTerminalCreateContext(null);
      handlers.setProjectTerminalPickerOpen(false);
      handlers.setNotificationCenterOpen(false);
      handlers.setGitDiffBrowserOpen(false);
      handlers.setTerminalControlsOpen(false);
      handlers.setTerminalQuickInputOpen(false);
      handlers.setTerminalSwitcherMode("recent");
      handlers.setTerminalSwitcherRecentScope("client");
      handlers.setTerminalSwitcherOpen(true);
      return;
    case "settings":
      handlers.setAddClientModalOpen(false);
      closeCommonSurfaces(handlers);
      handlers.setSettingsInitialView("general");
      handlers.setSettingsOpen(true);
      return;
    case "details":
      handlers.setAddClientModalOpen(false);
      handlers.setSettingsOpen(false);
      handlers.setSettingsInitialView("general");
      closeCommonSurfaces(handlers);
      return;
  }
}
