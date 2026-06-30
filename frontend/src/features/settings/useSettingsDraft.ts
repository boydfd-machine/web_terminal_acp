import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { normalizeApiBaseInput, readConfiguredApiBase, writeConfiguredApiBase } from "../../apiBase";
import { ensureDesktopNotificationPermission } from "../../desktopNotifications";
import { readAppLocale, translate } from "../../i18n";
import {
  desktopNotificationsSupported,
  readAgentCommandSettings,
  readAgentModelSelectionSettings,
  readArtifactModelSelectionSettings,
  readArtifactTerminalRetentionSeconds,
  readDesktopNotificationsEnabled,
  readSummaryOutputLanguage,
  readTerminalGroupingMode,
  readThemeSkin,
} from "../../userPreferences";
import type { AgentModelSelection } from "../../types";
import {
  copyCustomQuickKeys,
  copyKeyboardShortcutBindings,
  createSettingsDraft,
  settingsDraftsEqual,
  type SettingsDraft,
  type SettingsModalProps
} from "./settingsModalData";

type UseSettingsDraftArgs = Pick<SettingsModalProps,
  | "isOpen"
  | "appLocale"
  | "summaryOutputLanguage"
  | "terminalGroupingMode"
  | "terminalTimeRange"
  | "themeSkin"
  | "desktopNotificationsEnabled"
  | "keyboardShortcutBindings"
  | "customQuickKeys"
  | "onAppLocaleChange"
  | "onSummaryOutputLanguageChange"
  | "onTerminalGroupingModeChange"
  | "onThemeSkinChange"
  | "onDesktopNotificationsEnabledChange"
  | "onKeyboardShortcutBindingsChange"
  | "onCustomQuickKeysChange"
  | "onAppPreferencesSave"
>;

function createPersistedSettingsDraft({
  appLocale,
  summaryOutputLanguage,
  terminalGroupingMode,
  themeSkin,
  desktopNotificationsEnabled,
  keyboardShortcutBindings,
  customQuickKeys
}: Pick<SettingsModalProps,
  | "appLocale"
  | "summaryOutputLanguage"
  | "terminalGroupingMode"
  | "themeSkin"
  | "desktopNotificationsEnabled"
  | "keyboardShortcutBindings"
  | "customQuickKeys"
>): SettingsDraft {
  return createSettingsDraft({
    appLocale,
    apiBase: readConfiguredApiBase(),
    summaryOutputLanguage,
    terminalGroupingMode,
    artifactTerminalRetentionSeconds: readArtifactTerminalRetentionSeconds(),
    themeSkin,
    desktopNotificationsEnabled,
    agentCommandSettings: readAgentCommandSettings(),
    agentModelSelectionSettings: readAgentModelSelectionSettings(),
    artifactModelSelectionSettings: readArtifactModelSelectionSettings(),
    keyboardShortcutBindings,
    customQuickKeys
  });
}

export function readInitialSettings() {
  return {
    appLocale: readAppLocale(),
    summaryOutputLanguage: readSummaryOutputLanguage(),
    terminalGroupingMode: readTerminalGroupingMode(),
    artifactTerminalRetentionSeconds: readArtifactTerminalRetentionSeconds(),
    themeSkin: readThemeSkin(),
    desktopNotificationsEnabled: readDesktopNotificationsEnabled()
  };
}

export function useSettingsDraft(args: UseSettingsDraftArgs) {
  const currentPersistedDraft = useMemo(() => createPersistedSettingsDraft(args), [
    args.appLocale,
    args.summaryOutputLanguage,
    args.terminalGroupingMode,
    args.themeSkin,
    args.desktopNotificationsEnabled,
    args.keyboardShortcutBindings,
    args.customQuickKeys
  ]);
  const [draft, setDraft] = useState<SettingsDraft>(currentPersistedDraft);
  const [savedDraft, setSavedDraft] = useState<SettingsDraft>(currentPersistedDraft);
  const [apiBaseError, setApiBaseError] = useState<string | null>(null);
  const [saveStatus, setSaveStatus] = useState<string | null>(null);
  const wasOpenRef = useRef(false);
  const hasUnsavedChanges = !settingsDraftsEqual(draft, savedDraft);

  useEffect(() => {
    if (!args.isOpen) {
      wasOpenRef.current = false;
      return;
    }
    if (wasOpenRef.current) {
      return;
    }

    wasOpenRef.current = true;
    const nextDraft = createPersistedSettingsDraft(args);
    setDraft(nextDraft);
    setSavedDraft(nextDraft);
    setApiBaseError(null);
    setSaveStatus(null);
  }, [
    args.appLocale,
    args.customQuickKeys,
    args.desktopNotificationsEnabled,
    args.isOpen,
    args.keyboardShortcutBindings,
    args.summaryOutputLanguage,
    args.terminalGroupingMode,
    args.themeSkin
  ]);

  const changeDraft = useCallback((patch: Partial<SettingsDraft>) => {
    setDraft((current) => ({ ...current, ...patch }));
    setSaveStatus(null);
  }, []);

  const saveSettings = useCallback(async () => {
    try {
      const normalizedApiBase = normalizeApiBaseInput(draft.apiBase);
      const previousApiBase = savedDraft.apiBase;
      if (
        draft.desktopNotificationsEnabled
        && !savedDraft.desktopNotificationsEnabled
        && desktopNotificationsSupported()
      ) {
        const permission = await ensureDesktopNotificationPermission();
        if (permission !== "granted") {
          setDraft((current) => ({ ...current, desktopNotificationsEnabled: false }));
          setApiBaseError(null);
          setSaveStatus(translate(args.appLocale, "app.settings.save.notificationPermissionDenied"));
          return;
        }
      }

      writeConfiguredApiBase(normalizedApiBase);

      const savedPreferences = await args.onAppPreferencesSave({
        appLocale: draft.appLocale,
        summaryOutputLanguage: draft.summaryOutputLanguage,
        terminalGroupingMode: draft.terminalGroupingMode,
        terminalTimeRange: args.terminalTimeRange,
        artifactTerminalRetentionSeconds: draft.artifactTerminalRetentionSeconds,
        themeSkin: draft.themeSkin,
        desktopNotificationsEnabled: draft.desktopNotificationsEnabled,
        agentCommandSettings: draft.agentCommandSettings,
        agentModelSelectionSettings: draft.agentModelSelectionSettings,
        artifactModelSelectionSettings: draft.artifactModelSelectionSettings,
        keyboardShortcutBindings: copyKeyboardShortcutBindings(draft.keyboardShortcutBindings),
      });

      args.onAppLocaleChange(savedPreferences.appLocale);
      args.onSummaryOutputLanguageChange(savedPreferences.summaryOutputLanguage);
      args.onTerminalGroupingModeChange(savedPreferences.terminalGroupingMode);
      args.onThemeSkinChange(savedPreferences.themeSkin);
      args.onDesktopNotificationsEnabledChange(savedPreferences.desktopNotificationsEnabled);
      args.onKeyboardShortcutBindingsChange(copyKeyboardShortcutBindings(savedPreferences.keyboardShortcutBindings));
      args.onCustomQuickKeysChange(copyCustomQuickKeys(draft.customQuickKeys));

      const nextSavedDraft = createSettingsDraft({
        ...draft,
        apiBase: normalizedApiBase,
        appLocale: savedPreferences.appLocale,
        summaryOutputLanguage: savedPreferences.summaryOutputLanguage,
        terminalGroupingMode: savedPreferences.terminalGroupingMode,
        artifactTerminalRetentionSeconds: savedPreferences.artifactTerminalRetentionSeconds,
        themeSkin: savedPreferences.themeSkin,
        desktopNotificationsEnabled: savedPreferences.desktopNotificationsEnabled,
        agentCommandSettings: savedPreferences.agentCommandSettings,
        agentModelSelectionSettings: savedPreferences.agentModelSelectionSettings,
        artifactModelSelectionSettings: savedPreferences.artifactModelSelectionSettings,
        keyboardShortcutBindings: savedPreferences.keyboardShortcutBindings,
      });
      setDraft(nextSavedDraft);
      setSavedDraft(nextSavedDraft);
      setApiBaseError(null);
      setSaveStatus(translate(draft.appLocale, "app.settings.save.done"));

      if (normalizedApiBase !== previousApiBase) {
        window.location.reload();
      }
    } catch {
      setApiBaseError(translate(args.appLocale, "app.settings.error.invalidBackend"));
      setSaveStatus(null);
    }
  }, [args, draft, savedDraft]);

  const updateAgentCommand = useCallback((agent: string, value: string) => {
    changeDraft({
      agentCommandSettings: { ...draft.agentCommandSettings, [agent]: value }
    });
  }, [changeDraft, draft.agentCommandSettings]);

  const updateAgentModelSelection = useCallback((agent: string, value: AgentModelSelection | null) => {
    changeDraft({
      agentModelSelectionSettings: { ...draft.agentModelSelectionSettings, [agent]: value }
    });
  }, [changeDraft, draft.agentModelSelectionSettings]);

  const updateArtifactModelSelection = useCallback((agent: string, value: AgentModelSelection | null) => {
    changeDraft({
      artifactModelSelectionSettings: { ...draft.artifactModelSelectionSettings, [agent]: value }
    });
  }, [changeDraft, draft.artifactModelSelectionSettings]);

  return {
    apiBaseError,
    changeDraft,
    draft,
    hasUnsavedChanges,
    saveSettings,
    saveStatus,
    setApiBaseError,
    updateAgentCommand,
    updateAgentModelSelection,
    updateArtifactModelSelection
  };
}
