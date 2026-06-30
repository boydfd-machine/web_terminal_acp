import type { OnboardingStep } from "./components/OnboardingTour";
import type { TranslateFn } from "./i18n";

export type OnboardingShortcutLabels = {
  t: TranslateFn;
  settings: string;
  switchTerminal: string;
  newTerminal: string;
  newTerminalProject: string;
  quickInput: string;
};

export function buildOnboardingSteps({ t, ...shortcuts }: OnboardingShortcutLabels): OnboardingStep[] {
  return [
    {
      id: "layout",
      title: t("onboarding.layout.title"),
      body: t("onboarding.layout.body"),
      targetId: "app-layout"
    },
    {
      id: "remote-bootstrap",
      title: t("onboarding.remoteBootstrap.title"),
      body: t("onboarding.remoteBootstrap.body"),
      path: [t("addClient.title"), t("addClient.bootstrap")],
      targetId: "remote-bootstrap-form",
      action: "remote-bootstrap"
    },
    {
      id: "remote-registration-menu",
      title: t("onboarding.remoteRegistrationMenu.title"),
      body: t("onboarding.remoteRegistrationMenu.body"),
      path: [t("addClient.title"), t("addClient.registration")],
      targetId: "add-client-registration-tab",
      action: "remote-registration-menu"
    },
    {
      id: "remote-registration",
      title: t("onboarding.remoteRegistration.title"),
      body: t("onboarding.remoteRegistration.body"),
      path: [t("addClient.title"), t("addClient.registration"), t("onboarding.path.generateRegistration")],
      targetId: "remote-registration-panel",
      action: "remote-registration"
    },
    {
      id: "clients",
      title: t("onboarding.clients.title"),
      body: t("onboarding.clients.body"),
      targetId: "client-list",
      action: "details"
    },
    {
      id: "terminal-tree",
      title: t("onboarding.terminalTree.title"),
      body: t("onboarding.terminalTree.body"),
      targetId: "terminal-tree",
      action: "details"
    },
    {
      id: "new-terminal",
      title: t("onboarding.newTerminal.title"),
      body: t("onboarding.newTerminal.body"),
      path: [t("sidebar.terminal.new")],
      shortcutLabels: [shortcuts.newTerminal, t("onboarding.shortcut.projectCreateSuffix", { shortcut: shortcuts.newTerminalProject })],
      targetId: "new-terminal-button",
      action: "details"
    },
    {
      id: "terminal-pane",
      title: t("onboarding.terminalPane.title"),
      body: t("onboarding.terminalPane.body"),
      path: [t("onboarding.path.selectAnyTerminal")],
      targetId: "terminal-pane",
      action: "details"
    },
    {
      id: "quick-input",
      title: t("onboarding.quickInput.title"),
      body: t("onboarding.quickInput.body"),
      path: [t("onboarding.path.openAnyTerminal"), t("toolbar.quickInput")],
      shortcutLabels: [shortcuts.quickInput, t("onboarding.shortcut.quickInputSend")],
      targetId: "quick-input-panel",
      action: "quick-input"
    },
    {
      id: "switcher",
      title: t("onboarding.switcher.title"),
      body: t("onboarding.switcher.body"),
      path: [t("onboarding.path.anyMainScreen"), t("shortcut.switchTerminal")],
      shortcutLabels: [shortcuts.switchTerminal],
      targetId: "terminal-switcher",
      action: "switch-terminal"
    },
    {
      id: "details",
      title: t("onboarding.details.title"),
      body: t("onboarding.details.body"),
      path: [t("onboarding.path.openAnyTerminal"), t("toolbar.details")],
      targetId: "detail-panel",
      action: "details"
    },
    {
      id: "search",
      title: t("onboarding.search.title"),
      body: t("onboarding.search.body"),
      path: [t("toolbar.details"), t("onboarding.path.agentRecordSearch")],
      targetId: "agent-record-search",
      action: "details"
    },
    {
      id: "notifications",
      title: t("onboarding.notifications.title"),
      body: t("onboarding.notifications.body"),
      path: [t("onboarding.path.topNotificationButton"), t("app.settings"), t("settings.general.desktopNotifications")],
      targetId: "notification-bell",
      action: "details"
    },
    {
      id: "settings",
      title: t("onboarding.settings.title"),
      body: t("onboarding.settings.body"),
      path: [t("app.settings")],
      shortcutLabels: [shortcuts.settings],
      targetId: "settings-modal",
      action: "settings"
    }
  ];
}
