import { KEYBOARD_SHORTCUT_DEFINITIONS, effectiveKeyboardShortcut, keyboardShortcutsEqual, type KeyboardShortcut, type KeyboardShortcutBindings, type KeyboardShortcutId } from "../../keyboardShortcuts";
import type { AppLocale, TranslateFn, TranslationKey } from "../../i18n";
import type { AgentCommandSettings, AgentModelSelectionSettings, AppPreferences, SummaryOutputLanguage, TerminalGroupingMode, TerminalTimeRange, ThemeSkinId } from "../../userPreferences";
import type { CustomQuickKey } from "../../terminalQuickKeys";
import type { AgentModelSelection } from "../../types";

type CoreSettingsView =
  | "general"
  | "theme"
  | "card-types"
  | "system-skills"
  | "system-plugins"
  | "system-mcp"
  | "system-models"
  | "artifacts"
  | "shortcuts"
  | "quick-keys";
export type SettingsTabId = CoreSettingsView | "agents" | "account";
export type SettingsView = SettingsTabId;
export type ShortcutBindingTarget =
  | { type: "builtin"; id: KeyboardShortcutId }
  | { type: "quick-key"; id: string }
  | { type: "quick-key-draft" };

export type SettingsDraft = {
  appLocale: AppLocale;
  apiBase: string;
  summaryOutputLanguage: SummaryOutputLanguage;
  terminalGroupingMode: TerminalGroupingMode;
  artifactTerminalRetentionSeconds: number;
  themeSkin: ThemeSkinId;
  desktopNotificationsEnabled: boolean;
  agentCommandSettings: AgentCommandSettings;
  agentModelSelectionSettings: AgentModelSelectionSettings;
  artifactModelSelectionSettings: AgentModelSelectionSettings;
  keyboardShortcutBindings: KeyboardShortcutBindings;
  customQuickKeys: CustomQuickKey[];
};

export const SETTINGS_TABS: Array<{ id: SettingsTabId; labelKey: TranslationKey }> = [
  { id: "general", labelKey: "settings.tab.general" },
  { id: "theme", labelKey: "settings.tab.theme" },
  { id: "agents", labelKey: "settings.tab.agents" },
  { id: "card-types", labelKey: "settings.tab.cardTypes" },
  { id: "system-skills", labelKey: "settings.tab.systemSkills" },
  { id: "system-plugins", labelKey: "settings.tab.systemPlugins" },
  { id: "system-mcp", labelKey: "settings.tab.systemMcp" },
  { id: "system-models", labelKey: "settings.tab.systemModels" },
  { id: "artifacts", labelKey: "settings.tab.artifacts" },
  { id: "shortcuts", labelKey: "settings.tab.shortcuts" },
  { id: "quick-keys", labelKey: "settings.tab.quickKeys" },
  { id: "account", labelKey: "settings.tab.account" }
];

export type SettingsModalProps = {
  isOpen: boolean;
  onClose: () => void;
  appLocale: AppLocale;
  summaryOutputLanguage: SummaryOutputLanguage;
  terminalGroupingMode: TerminalGroupingMode;
  terminalTimeRange: TerminalTimeRange;
  themeSkin: ThemeSkinId;
  desktopNotificationsEnabled: boolean;
  keyboardShortcutBindings: KeyboardShortcutBindings;
  customQuickKeys: CustomQuickKey[];
  selectedClientId: string | null;
  selectedProjectPath?: string | null;
  selectedWindowId?: string | null;
  onAppLocaleChange: (locale: AppLocale) => void;
  onSummaryOutputLanguageChange: (language: SummaryOutputLanguage) => void;
  onTerminalGroupingModeChange: (mode: TerminalGroupingMode) => void;
  onThemeSkinChange: (themeSkin: ThemeSkinId) => void;
  onDesktopNotificationsEnabledChange: (enabled: boolean) => void;
  onKeyboardShortcutBindingsChange: (bindings: KeyboardShortcutBindings) => void;
  onCustomQuickKeysChange: (quickKeys: CustomQuickKey[]) => void;
  onAppPreferencesSave: (preferences: AppPreferences) => Promise<AppPreferences>;
  authEnabled: boolean;
  initialView?: SettingsView;
  onboardingEnabled: boolean;
  onStartOnboarding: () => void;
  onLogout: () => void;
};

export function shortcutTargetKey(target: ShortcutBindingTarget): string {
  return target.type === "quick-key-draft" ? target.type : `${target.type}:${target.id}`;
}

export function copyKeyboardShortcut(shortcut: KeyboardShortcut | null | undefined): KeyboardShortcut | null | undefined {
  return shortcut === undefined || shortcut === null ? shortcut : { ...shortcut };
}

export function copyKeyboardShortcutBindings(bindings: KeyboardShortcutBindings): KeyboardShortcutBindings {
  const nextBindings: KeyboardShortcutBindings = {};
  for (const definition of KEYBOARD_SHORTCUT_DEFINITIONS) {
    if (Object.prototype.hasOwnProperty.call(bindings, definition.id)) {
      nextBindings[definition.id] = copyKeyboardShortcut(bindings[definition.id]);
    }
  }
  return nextBindings;
}

export function copyCustomQuickKeys(quickKeys: CustomQuickKey[]): CustomQuickKey[] {
  return quickKeys.map((quickKey) => ({
    ...quickKey,
    ...(quickKey.shortcut !== undefined ? { shortcut: copyKeyboardShortcut(quickKey.shortcut) } : {})
  }));
}

export function copyAgentCommandSettings(settings: AgentCommandSettings): AgentCommandSettings {
  return { ...settings };
}

function copyAgentModelSelection(selection: AgentModelSelection | null): AgentModelSelection | null {
  if (selection === null) {
    return null;
  }
  return {
    ...selection,
    ...(selection.claude !== undefined && selection.claude !== null ? { claude: { ...selection.claude } } : {})
  };
}

export function copyAgentModelSelectionSettings(settings: AgentModelSelectionSettings): AgentModelSelectionSettings {
  const copy: AgentModelSelectionSettings = {};
  for (const [agent, selection] of Object.entries(settings)) {
    copy[agent] = copyAgentModelSelection(selection);
  }
  return copy;
}

export function shortcutSignature(shortcut: KeyboardShortcut | null | undefined): string {
  if (shortcut === undefined) {
    return "undefined";
  }
  if (shortcut === null) {
    return "null";
  }
  return [
    shortcut.key,
    shortcut.alt === true ? "1" : "0",
    shortcut.ctrl === true ? "1" : "0",
    shortcut.meta === true ? "1" : "0",
    shortcut.shift === true ? "1" : "0"
  ].join(":");
}

export function keyboardShortcutBindingsEqual(left: KeyboardShortcutBindings, right: KeyboardShortcutBindings): boolean {
  return KEYBOARD_SHORTCUT_DEFINITIONS.every((definition) => {
    const leftHasKey = Object.prototype.hasOwnProperty.call(left, definition.id);
    const rightHasKey = Object.prototype.hasOwnProperty.call(right, definition.id);
    if (leftHasKey !== rightHasKey) {
      return false;
    }
    return shortcutSignature(left[definition.id]) === shortcutSignature(right[definition.id]);
  });
}

export function customQuickKeysEqual(left: CustomQuickKey[], right: CustomQuickKey[]): boolean {
  if (left.length !== right.length) {
    return false;
  }
  return left.every((quickKey, index) => {
    const other = right[index];
    return quickKey.id === other.id
      && quickKey.label === other.label
      && quickKey.input === other.input
      && shortcutSignature(quickKey.shortcut) === shortcutSignature(other.shortcut);
  });
}

export function agentCommandSettingsEqual(left: AgentCommandSettings, right: AgentCommandSettings): boolean {
  const keys = new Set([...Object.keys(left), ...Object.keys(right)]);
  for (const key of keys) {
    if ((left[key] ?? "") !== (right[key] ?? "")) {
      return false;
    }
  }
  return true;
}

function agentModelSelectionSignature(selection: AgentModelSelection | null | undefined): string {
  if (selection === undefined) {
    return "undefined";
  }
  if (selection === null) {
    return "null";
  }
  return JSON.stringify({
    preset_id: selection.preset_id,
    model: selection.model ?? null,
    claude: selection.claude === undefined || selection.claude === null
      ? null
      : {
          mode: selection.claude.mode,
          model: selection.claude.model ?? null,
          opus_model: selection.claude.opus_model ?? null,
          sonnet_model: selection.claude.sonnet_model ?? null,
          haiku_model: selection.claude.haiku_model ?? null
        },
    codex_model_reasoning_effort: selection.codex_model_reasoning_effort ?? null,
    codex_plan_mode_reasoning_effort: selection.codex_plan_mode_reasoning_effort ?? null,
    claude_reasoning_effort: selection.claude_reasoning_effort ?? null
  });
}

export function agentModelSelectionSettingsEqual(
  left: AgentModelSelectionSettings,
  right: AgentModelSelectionSettings
): boolean {
  const keys = new Set([...Object.keys(left), ...Object.keys(right)]);
  for (const key of keys) {
    if (agentModelSelectionSignature(left[key]) !== agentModelSelectionSignature(right[key])) {
      return false;
    }
  }
  return true;
}

export function createSettingsDraft(input: {
  appLocale: AppLocale;
  apiBase: string;
  summaryOutputLanguage: SummaryOutputLanguage;
  terminalGroupingMode: TerminalGroupingMode;
  artifactTerminalRetentionSeconds: number;
  themeSkin: ThemeSkinId;
  desktopNotificationsEnabled: boolean;
  agentCommandSettings: AgentCommandSettings;
  agentModelSelectionSettings: AgentModelSelectionSettings;
  artifactModelSelectionSettings: AgentModelSelectionSettings;
  keyboardShortcutBindings: KeyboardShortcutBindings;
  customQuickKeys: CustomQuickKey[];
}): SettingsDraft {
  return {
    appLocale: input.appLocale,
    apiBase: input.apiBase,
    summaryOutputLanguage: input.summaryOutputLanguage,
    terminalGroupingMode: input.terminalGroupingMode,
    artifactTerminalRetentionSeconds: input.artifactTerminalRetentionSeconds,
    themeSkin: input.themeSkin,
    desktopNotificationsEnabled: input.desktopNotificationsEnabled,
    agentCommandSettings: copyAgentCommandSettings(input.agentCommandSettings),
    agentModelSelectionSettings: copyAgentModelSelectionSettings(input.agentModelSelectionSettings),
    artifactModelSelectionSettings: copyAgentModelSelectionSettings(input.artifactModelSelectionSettings),
    keyboardShortcutBindings: copyKeyboardShortcutBindings(input.keyboardShortcutBindings),
    customQuickKeys: copyCustomQuickKeys(input.customQuickKeys)
  };
}

export function settingsDraftsEqual(left: SettingsDraft, right: SettingsDraft): boolean {
  return left.appLocale === right.appLocale
    && left.apiBase === right.apiBase
    && left.summaryOutputLanguage === right.summaryOutputLanguage
    && left.terminalGroupingMode === right.terminalGroupingMode
    && left.artifactTerminalRetentionSeconds === right.artifactTerminalRetentionSeconds
    && left.themeSkin === right.themeSkin
    && left.desktopNotificationsEnabled === right.desktopNotificationsEnabled
    && agentCommandSettingsEqual(left.agentCommandSettings, right.agentCommandSettings)
    && agentModelSelectionSettingsEqual(left.agentModelSelectionSettings, right.agentModelSelectionSettings)
    && agentModelSelectionSettingsEqual(left.artifactModelSelectionSettings, right.artifactModelSelectionSettings)
    && keyboardShortcutBindingsEqual(left.keyboardShortcutBindings, right.keyboardShortcutBindings)
    && customQuickKeysEqual(left.customQuickKeys, right.customQuickKeys);
}

export function shortcutConflictLabel(
  shortcut: KeyboardShortcut | null,
  target: ShortcutBindingTarget,
  keyboardShortcutBindings: KeyboardShortcutBindings,
  customQuickKeys: CustomQuickKey[],
  t?: TranslateFn
): string | null {
  if (shortcut === null) {
    return null;
  }

  const targetKey = shortcutTargetKey(target);
  for (const definition of KEYBOARD_SHORTCUT_DEFINITIONS) {
    if (targetKey === shortcutTargetKey({ type: "builtin", id: definition.id })) {
      continue;
    }
    if (keyboardShortcutsEqual(shortcut, effectiveKeyboardShortcut(definition.id, keyboardShortcutBindings))) {
      return t?.(definition.labelKey) ?? definition.label;
    }
  }

  for (const quickKey of customQuickKeys) {
    if (targetKey === shortcutTargetKey({ type: "quick-key", id: quickKey.id })) {
      continue;
    }
    if (keyboardShortcutsEqual(shortcut, quickKey.shortcut ?? null)) {
      return quickKey.label;
    }
  }

  return null;
}
