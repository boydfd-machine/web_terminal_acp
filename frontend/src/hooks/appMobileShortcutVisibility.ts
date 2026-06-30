type MobileShortcutUiState = {
  terminalSwitcherOpen: boolean;
  clientSwitcherOpen: boolean;
  projectTerminalPickerOpen: boolean;
  notificationCenterOpen: boolean;
  settingsOpen: boolean;
  addClientModalOpen: boolean;
  terminalQuickInputOpen: boolean;
  gitDiffBrowserOpen: boolean;
  detailPanelOpen: boolean;
};

type MobileShortcutDrawerState = {
  auxTerminalOpen: boolean;
};

export function isMobileShortcutVisible(
  isMobileLayout: boolean,
  ui: MobileShortcutUiState,
  drawer: MobileShortcutDrawerState
): boolean {
  return isMobileLayout
    && !ui.terminalSwitcherOpen
    && !ui.clientSwitcherOpen
    && !ui.projectTerminalPickerOpen
    && !ui.notificationCenterOpen
    && !ui.settingsOpen
    && !ui.addClientModalOpen
    && !ui.terminalQuickInputOpen
    && !ui.gitDiffBrowserOpen
    && !ui.detailPanelOpen
    && !drawer.auxTerminalOpen;
}
