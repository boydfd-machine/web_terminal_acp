import { request } from "./apiCore";
import { normalizeKeyboardShortcutBindings } from "./keyboardShortcuts";
import { DEFAULT_THEME_SKIN, isThemeSkinId } from "./themeSkins";
import { DEFAULT_TERMINAL_TIME_RANGE, isTerminalTimeRange } from "./terminalTimeRange";
import {
  clampArtifactTerminalRetentionSeconds,
  normalizeAgentModelSelectionSettings,
  type AppPreferences,
  type AgentCommandSettings,
  type AgentModelSelectionSettings,
  type SummaryOutputLanguage,
  type TerminalGroupingMode,
  type ThemeSkinId,
} from "./userPreferences";
import type { AppLocale } from "./i18n";
import type { KeyboardShortcutBindings } from "./keyboardShortcuts";

export type AppPreferencesResponse = {
  configured: boolean;
  app_locale: AppLocale;
  summary_output_language: SummaryOutputLanguage;
  terminal_grouping_mode: TerminalGroupingMode;
  terminal_time_range: string;
  artifact_terminal_retention_seconds: number;
  theme_skin: ThemeSkinId;
  desktop_notifications_enabled: boolean;
  agent_command_settings: AgentCommandSettings;
  agent_model_selection_settings: AgentModelSelectionSettings;
  artifact_model_selection_settings: AgentModelSelectionSettings;
  keyboard_shortcut_bindings: KeyboardShortcutBindings;
};

export type AppPreferencesPayload = Omit<AppPreferencesResponse, "configured">;

function normalizeAppLocale(value: unknown): AppLocale {
  return value === "en-US" ? "en-US" : "zh-CN";
}

function normalizeSummaryOutputLanguage(value: unknown): SummaryOutputLanguage {
  return value === "English" ? "English" : "中文";
}

function normalizeTerminalGroupingMode(value: unknown): TerminalGroupingMode {
  if (value === "topic" || value === "time-topic" || value === "project-time-topic") {
    return value;
  }
  return "project-topic";
}

export function appPreferencesFromResponse(response: AppPreferencesResponse): AppPreferences {
  return {
    appLocale: normalizeAppLocale(response.app_locale),
    summaryOutputLanguage: normalizeSummaryOutputLanguage(response.summary_output_language),
    terminalGroupingMode: normalizeTerminalGroupingMode(response.terminal_grouping_mode),
    terminalTimeRange: isTerminalTimeRange(response.terminal_time_range)
      ? response.terminal_time_range
      : DEFAULT_TERMINAL_TIME_RANGE,
    artifactTerminalRetentionSeconds: clampArtifactTerminalRetentionSeconds(
      response.artifact_terminal_retention_seconds
    ),
    themeSkin: isThemeSkinId(response.theme_skin) ? response.theme_skin : DEFAULT_THEME_SKIN,
    desktopNotificationsEnabled: response.desktop_notifications_enabled === true,
    agentCommandSettings: response.agent_command_settings,
    agentModelSelectionSettings: normalizeAgentModelSelectionSettings(
      response.agent_model_selection_settings
    ),
    artifactModelSelectionSettings: normalizeAgentModelSelectionSettings(
      response.artifact_model_selection_settings
    ),
    keyboardShortcutBindings: normalizeKeyboardShortcutBindings(response.keyboard_shortcut_bindings),
  };
}

export function appPreferencesPayload(preferences: AppPreferences): AppPreferencesPayload {
  return {
    app_locale: preferences.appLocale,
    summary_output_language: preferences.summaryOutputLanguage,
    terminal_grouping_mode: preferences.terminalGroupingMode,
    terminal_time_range: preferences.terminalTimeRange,
    artifact_terminal_retention_seconds: clampArtifactTerminalRetentionSeconds(
      preferences.artifactTerminalRetentionSeconds
    ),
    theme_skin: preferences.themeSkin,
    desktop_notifications_enabled: preferences.desktopNotificationsEnabled,
    agent_command_settings: preferences.agentCommandSettings,
    agent_model_selection_settings: preferences.agentModelSelectionSettings,
    artifact_model_selection_settings: preferences.artifactModelSelectionSettings,
    keyboard_shortcut_bindings: preferences.keyboardShortcutBindings,
  };
}

export function fetchAppPreferences(): Promise<AppPreferencesResponse> {
  return request<AppPreferencesResponse>("/api/ui-settings/app-preferences");
}

export function updateAppPreferences(preferences: AppPreferences): Promise<AppPreferencesResponse> {
  return request<AppPreferencesResponse>("/api/ui-settings/app-preferences", {
    method: "PUT",
    body: JSON.stringify(appPreferencesPayload(preferences)),
  });
}
