import {
  desktopNotificationsSupported,
  readDesktopNotificationsEnabled as readLegacyDesktopNotificationsEnabled,
} from "./desktopNotifications";
import type { AppLocale } from "./i18n";
import {
  normalizeKeyboardShortcutBindings,
  readKeyboardShortcutBindings,
  type KeyboardShortcut,
  type KeyboardShortcutBindings,
} from "./keyboardShortcuts";
import { DEFAULT_THEME_SKIN, isThemeSkinId, type ThemeSkinId } from "./themeSkins";
import {
  DEFAULT_TERMINAL_TIME_RANGE,
  isTerminalTimeRange,
  type TerminalTimeRange
} from "./terminalTimeRange";
import type { AgentModelSelection } from "./types";

export type { ThemeSkinId } from "./themeSkins";
export type { TerminalTimeRange } from "./terminalTimeRange";
export { desktopNotificationsSupported };

export type SummaryOutputLanguage = "中文" | "English";

export type TerminalGroupingMode = "project-topic" | "topic" | "time-topic" | "project-time-topic";

export type AgentCommandSettings = Record<string, string>;
export type AgentModelSelectionSettings = Record<string, AgentModelSelection | null>;

export type AppPreferences = {
  appLocale: AppLocale;
  summaryOutputLanguage: SummaryOutputLanguage;
  terminalGroupingMode: TerminalGroupingMode;
  terminalTimeRange: TerminalTimeRange;
  artifactTerminalRetentionSeconds: number;
  themeSkin: ThemeSkinId;
  desktopNotificationsEnabled: boolean;
  agentCommandSettings: AgentCommandSettings;
  agentModelSelectionSettings: AgentModelSelectionSettings;
  artifactModelSelectionSettings: AgentModelSelectionSettings;
  keyboardShortcutBindings: KeyboardShortcutBindings;
};

export const DEFAULT_ARTIFACT_TERMINAL_RETENTION_SECONDS = 600;
export const MIN_ARTIFACT_TERMINAL_RETENTION_SECONDS = 0;
export const MAX_ARTIFACT_TERMINAL_RETENTION_SECONDS = 3600;

const SUMMARY_LANGUAGE_KEY = "web-terminal-acp:summary-output-language";
const TERMINAL_GROUPING_KEY = "web-terminal-acp:terminal-grouping-mode";
const TERMINAL_TIME_RANGE_KEY = "web-terminal-acp:terminal-time-range";
const ARTIFACT_TERMINAL_RETENTION_SECONDS_KEY = "web-terminal-acp:artifact-terminal-retention-seconds";
const AGENT_COMMANDS_KEY = "web-terminal-acp:agent-commands";
const AGENT_MODEL_SELECTIONS_KEY = "web-terminal-acp:agent-model-selections";
const ARTIFACT_MODEL_SELECTIONS_KEY = "web-terminal-acp:artifact-model-selections";
const THEME_SKIN_KEY = "web-terminal-acp:theme-skin";
const DEFAULT_AGENT_COMMANDS: AgentCommandSettings = {
  codex: "codex",
  claude: "claude",
  cursor: "agent",
  antigravity: "agy-p"
};

let runtimeAppPreferences: AppPreferences | null = null;

function defaultAgentCommandSettings(): AgentCommandSettings {
  return { ...DEFAULT_AGENT_COMMANDS };
}

function copyKeyboardShortcut(shortcut: KeyboardShortcut | null | undefined): KeyboardShortcut | null | undefined {
  return shortcut === undefined || shortcut === null ? shortcut : { ...shortcut };
}

function copyKeyboardShortcutBindings(bindings: KeyboardShortcutBindings): KeyboardShortcutBindings {
  const copy: KeyboardShortcutBindings = {};
  for (const [id, shortcut] of Object.entries(bindings)) {
    copy[id as keyof KeyboardShortcutBindings] = copyKeyboardShortcut(shortcut) ?? null;
  }
  return normalizeKeyboardShortcutBindings(copy);
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

function copyAgentModelSelectionSettings(settings: AgentModelSelectionSettings): AgentModelSelectionSettings {
  const copy: AgentModelSelectionSettings = {};
  for (const [agent, selection] of Object.entries(settings)) {
    copy[agent] = copyAgentModelSelection(selection);
  }
  return copy;
}

function normalizeAgentCommandSettings(value: unknown): AgentCommandSettings {
  const settings = defaultAgentCommandSettings();
  if (value === null || typeof value !== "object") {
    return settings;
  }

  for (const [agent, command] of Object.entries(value as Record<string, unknown>)) {
    if (typeof command === "string" && command.trim()) {
      settings[agent] = command;
    }
  }
  return settings;
}

function isAgentModelSelection(value: unknown): value is AgentModelSelection {
  if (value === null || typeof value !== "object") {
    return false;
  }
  const candidate = value as Partial<AgentModelSelection>;
  return typeof candidate.preset_id === "string" && candidate.preset_id.trim().length > 0;
}

export function normalizeAgentModelSelectionSettings(value: unknown): AgentModelSelectionSettings {
  if (value === null || typeof value !== "object") {
    return {};
  }

  const settings: AgentModelSelectionSettings = {};
  for (const [agent, selection] of Object.entries(value as Record<string, unknown>)) {
    if (selection === null || isAgentModelSelection(selection)) {
      settings[agent] = selection;
    }
  }
  return settings;
}

export function clampArtifactTerminalRetentionSeconds(value: number): number {
  if (!Number.isFinite(value)) {
    return DEFAULT_ARTIFACT_TERMINAL_RETENTION_SECONDS;
  }

  return Math.min(
    MAX_ARTIFACT_TERMINAL_RETENTION_SECONDS,
    Math.max(MIN_ARTIFACT_TERMINAL_RETENTION_SECONDS, Math.round(value))
  );
}

function copyAppPreferences(preferences: AppPreferences): AppPreferences {
  return {
    appLocale: preferences.appLocale === "en-US" ? "en-US" : "zh-CN",
    summaryOutputLanguage: preferences.summaryOutputLanguage === "English" ? "English" : "中文",
    terminalGroupingMode: normalizeTerminalGroupingMode(preferences.terminalGroupingMode),
    terminalTimeRange: isTerminalTimeRange(preferences.terminalTimeRange)
      ? preferences.terminalTimeRange
      : DEFAULT_TERMINAL_TIME_RANGE,
    artifactTerminalRetentionSeconds: clampArtifactTerminalRetentionSeconds(
      preferences.artifactTerminalRetentionSeconds
    ),
    themeSkin: isThemeSkinId(preferences.themeSkin) ? preferences.themeSkin : DEFAULT_THEME_SKIN,
    desktopNotificationsEnabled: preferences.desktopNotificationsEnabled,
    agentCommandSettings: normalizeAgentCommandSettings(preferences.agentCommandSettings),
    agentModelSelectionSettings: copyAgentModelSelectionSettings(preferences.agentModelSelectionSettings),
    artifactModelSelectionSettings: copyAgentModelSelectionSettings(preferences.artifactModelSelectionSettings),
    keyboardShortcutBindings: copyKeyboardShortcutBindings(preferences.keyboardShortcutBindings),
  };
}

function updateRuntimeAppPreferences(patch: Partial<AppPreferences>): void {
  runtimeAppPreferences = copyAppPreferences({
    ...(runtimeAppPreferences ?? readLegacyAppPreferences("zh-CN")),
    ...patch,
  });
}

export function setRuntimeAppPreferences(preferences: AppPreferences): void {
  runtimeAppPreferences = copyAppPreferences(preferences);
}

export function readRuntimeAppPreferences(): AppPreferences | null {
  return runtimeAppPreferences === null ? null : copyAppPreferences(runtimeAppPreferences);
}

export function clearRuntimeAppPreferencesForTests(): void {
  runtimeAppPreferences = null;
}

export function readLegacyAppPreferences(appLocale: AppLocale): AppPreferences {
  return {
    appLocale,
    summaryOutputLanguage: readLegacySummaryOutputLanguage(),
    terminalGroupingMode: readLegacyTerminalGroupingMode(),
    terminalTimeRange: readLegacyTerminalTimeRange(),
    artifactTerminalRetentionSeconds: readLegacyArtifactTerminalRetentionSeconds(),
    themeSkin: readLegacyThemeSkin(),
    desktopNotificationsEnabled: readLegacyDesktopNotificationsEnabled(),
    agentCommandSettings: readLegacyAgentCommandSettings(),
    agentModelSelectionSettings: readLegacyAgentModelSelectionSettings(),
    artifactModelSelectionSettings: readLegacyArtifactModelSelectionSettings(),
    keyboardShortcutBindings: readKeyboardShortcutBindings(),
  };
}

function normalizeTerminalGroupingMode(value: unknown): TerminalGroupingMode {
  if (value === "topic" || value === "time-topic" || value === "project-time-topic") {
    return value;
  }
  return "project-topic";
}

function readLegacySummaryOutputLanguage(): SummaryOutputLanguage {
  if (typeof window === "undefined") {
    return "中文";
  }

  const stored = window.localStorage.getItem(SUMMARY_LANGUAGE_KEY);
  return stored === "English" ? "English" : "中文";
}

export function readSummaryOutputLanguage(): SummaryOutputLanguage {
  return runtimeAppPreferences?.summaryOutputLanguage ?? readLegacySummaryOutputLanguage();
}

export function writeSummaryOutputLanguage(language: SummaryOutputLanguage): void {
  updateRuntimeAppPreferences({ summaryOutputLanguage: language });
}

function readLegacyTerminalGroupingMode(): TerminalGroupingMode {
  if (typeof window === "undefined") {
    return "project-topic";
  }

  return normalizeTerminalGroupingMode(window.localStorage.getItem(TERMINAL_GROUPING_KEY));
}

export function readTerminalGroupingMode(): TerminalGroupingMode {
  return runtimeAppPreferences?.terminalGroupingMode ?? readLegacyTerminalGroupingMode();
}

export function writeTerminalGroupingMode(mode: TerminalGroupingMode): void {
  updateRuntimeAppPreferences({ terminalGroupingMode: mode });
}

function readLegacyTerminalTimeRange(): TerminalTimeRange {
  if (typeof window === "undefined") {
    return DEFAULT_TERMINAL_TIME_RANGE;
  }

  const stored = window.localStorage.getItem(TERMINAL_TIME_RANGE_KEY);
  return isTerminalTimeRange(stored) ? stored : DEFAULT_TERMINAL_TIME_RANGE;
}

export function readTerminalTimeRange(): TerminalTimeRange {
  return runtimeAppPreferences?.terminalTimeRange ?? readLegacyTerminalTimeRange();
}

export function writeTerminalTimeRange(range: TerminalTimeRange): void {
  updateRuntimeAppPreferences({ terminalTimeRange: range });
}

function readLegacyArtifactTerminalRetentionSeconds(): number {
  if (typeof window === "undefined") {
    return DEFAULT_ARTIFACT_TERMINAL_RETENTION_SECONDS;
  }

  const stored = window.localStorage.getItem(ARTIFACT_TERMINAL_RETENTION_SECONDS_KEY);
  if (stored === null) {
    return DEFAULT_ARTIFACT_TERMINAL_RETENTION_SECONDS;
  }

  return clampArtifactTerminalRetentionSeconds(Number(stored));
}

export function readArtifactTerminalRetentionSeconds(): number {
  return runtimeAppPreferences?.artifactTerminalRetentionSeconds ?? readLegacyArtifactTerminalRetentionSeconds();
}

export function writeArtifactTerminalRetentionSeconds(seconds: number): void {
  updateRuntimeAppPreferences({ artifactTerminalRetentionSeconds: clampArtifactTerminalRetentionSeconds(seconds) });
}

function readLegacyThemeSkin(): ThemeSkinId {
  if (typeof window === "undefined") {
    return DEFAULT_THEME_SKIN;
  }

  const stored = window.localStorage.getItem(THEME_SKIN_KEY);
  return isThemeSkinId(stored) ? stored : DEFAULT_THEME_SKIN;
}

export function readThemeSkin(): ThemeSkinId {
  return runtimeAppPreferences?.themeSkin ?? readLegacyThemeSkin();
}

export function writeThemeSkin(themeSkin: ThemeSkinId): void {
  updateRuntimeAppPreferences({ themeSkin });
}

export function readDesktopNotificationsEnabled(): boolean {
  return runtimeAppPreferences?.desktopNotificationsEnabled ?? readLegacyDesktopNotificationsEnabled();
}

export function writeDesktopNotificationsEnabled(enabled: boolean): void {
  updateRuntimeAppPreferences({ desktopNotificationsEnabled: enabled });
}

function readLegacyAgentCommandSettings(): AgentCommandSettings {
  if (typeof window === "undefined") {
    return defaultAgentCommandSettings();
  }

  try {
    return normalizeAgentCommandSettings(JSON.parse(window.localStorage.getItem(AGENT_COMMANDS_KEY) ?? "{}"));
  } catch {
    return defaultAgentCommandSettings();
  }
}

export function readAgentCommandSettings(): AgentCommandSettings {
  return runtimeAppPreferences === null
    ? readLegacyAgentCommandSettings()
    : { ...runtimeAppPreferences.agentCommandSettings };
}

export function writeAgentCommandSettings(settings: AgentCommandSettings): void {
  updateRuntimeAppPreferences({ agentCommandSettings: normalizeAgentCommandSettings(settings) });
}

function readLegacyAgentModelSelectionSettings(): AgentModelSelectionSettings {
  if (typeof window === "undefined") {
    return {};
  }

  try {
    return normalizeAgentModelSelectionSettings(
      JSON.parse(window.localStorage.getItem(AGENT_MODEL_SELECTIONS_KEY) ?? "{}")
    );
  } catch {
    return {};
  }
}

export function readAgentModelSelectionSettings(): AgentModelSelectionSettings {
  return runtimeAppPreferences === null
    ? readLegacyAgentModelSelectionSettings()
    : copyAgentModelSelectionSettings(runtimeAppPreferences.agentModelSelectionSettings);
}

export function writeAgentModelSelectionSettings(settings: AgentModelSelectionSettings): void {
  updateRuntimeAppPreferences({ agentModelSelectionSettings: normalizeAgentModelSelectionSettings(settings) });
}

function readLegacyArtifactModelSelectionSettings(): AgentModelSelectionSettings {
  if (typeof window === "undefined") {
    return {};
  }

  try {
    return normalizeAgentModelSelectionSettings(
      JSON.parse(window.localStorage.getItem(ARTIFACT_MODEL_SELECTIONS_KEY) ?? "{}")
    );
  } catch {
    return {};
  }
}

export function readArtifactModelSelectionSettings(): AgentModelSelectionSettings {
  return runtimeAppPreferences === null
    ? readLegacyArtifactModelSelectionSettings()
    : copyAgentModelSelectionSettings(runtimeAppPreferences.artifactModelSelectionSettings);
}

export function writeArtifactModelSelectionSettings(settings: AgentModelSelectionSettings): void {
  updateRuntimeAppPreferences({ artifactModelSelectionSettings: normalizeAgentModelSelectionSettings(settings) });
}
