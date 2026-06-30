import { useCallback, useEffect, useRef } from "react";
import { useMutation, useQuery, type QueryClient } from "@tanstack/react-query";

import {
  appPreferencesFromResponse,
  fetchAppPreferences,
  updateAppPreferences,
} from "../api";
import type { AppLocale } from "../i18n";
import type { KeyboardShortcutBindings } from "../keyboardShortcuts";
import {
  readLegacyAppPreferences,
  readRuntimeAppPreferences,
  setRuntimeAppPreferences,
  type AppPreferences,
  type SummaryOutputLanguage,
  type TerminalGroupingMode,
  type TerminalTimeRange,
  type ThemeSkinId,
} from "../userPreferences";

type UseAppPreferencesArgs = {
  appLocale: AppLocale;
  desktopNotificationsEnabled: boolean;
  keyboardShortcutBindings: KeyboardShortcutBindings;
  queryClient: QueryClient;
  summaryOutputLanguage: SummaryOutputLanguage;
  terminalGroupingMode: TerminalGroupingMode;
  terminalTimeRange: TerminalTimeRange;
  themeSkin: ThemeSkinId;
  setAppLocale: (locale: AppLocale) => void;
  setDesktopNotificationsEnabled: (enabled: boolean) => void;
  setKeyboardShortcutBindings: (bindings: KeyboardShortcutBindings) => void;
  setSummaryOutputLanguage: (language: SummaryOutputLanguage) => void;
  setTerminalGroupingMode: (mode: TerminalGroupingMode) => void;
  setTerminalTimeRange: (range: TerminalTimeRange) => void;
  setThemeSkin: (themeSkin: ThemeSkinId) => void;
};

function statePreferences(args: UseAppPreferencesArgs): AppPreferences {
  const runtime = readRuntimeAppPreferences();
  return {
    ...(runtime ?? readLegacyAppPreferences(args.appLocale)),
    appLocale: args.appLocale,
    summaryOutputLanguage: args.summaryOutputLanguage,
    terminalGroupingMode: args.terminalGroupingMode,
    terminalTimeRange: args.terminalTimeRange,
    themeSkin: args.themeSkin,
    desktopNotificationsEnabled: args.desktopNotificationsEnabled,
    keyboardShortcutBindings: args.keyboardShortcutBindings,
  };
}

export function useAppPreferences(args: UseAppPreferencesArgs) {
  const {
    appLocale,
    desktopNotificationsEnabled,
    keyboardShortcutBindings,
    queryClient,
    summaryOutputLanguage,
    terminalGroupingMode,
    terminalTimeRange,
    themeSkin,
    setAppLocale,
    setDesktopNotificationsEnabled,
    setKeyboardShortcutBindings,
    setSummaryOutputLanguage,
    setTerminalGroupingMode,
    setTerminalTimeRange,
    setThemeSkin,
  } = args;
  const hydratedRef = useRef(false);
  const terminalTimeRangeSaveRef = useRef(terminalTimeRange);
  const { mutate: mutateAppPreferences, mutateAsync: mutateAppPreferencesAsync } = useMutation({
    mutationFn: updateAppPreferences,
    onSuccess: (response) => {
      queryClient.setQueryData(["app-preferences"], response);
      setRuntimeAppPreferences(appPreferencesFromResponse(response));
    },
  });
  const appPreferencesQuery = useQuery({
    queryKey: ["app-preferences"],
    queryFn: fetchAppPreferences,
  });

  const applyPreferences = useCallback((preferences: AppPreferences) => {
    setRuntimeAppPreferences(preferences);
    terminalTimeRangeSaveRef.current = preferences.terminalTimeRange;
    setAppLocale(preferences.appLocale);
    setSummaryOutputLanguage(preferences.summaryOutputLanguage);
    setTerminalGroupingMode(preferences.terminalGroupingMode);
    setTerminalTimeRange(preferences.terminalTimeRange);
    setThemeSkin(preferences.themeSkin);
    setDesktopNotificationsEnabled(preferences.desktopNotificationsEnabled);
    setKeyboardShortcutBindings(preferences.keyboardShortcutBindings);
  }, [
    setAppLocale,
    setDesktopNotificationsEnabled,
    setKeyboardShortcutBindings,
    setSummaryOutputLanguage,
    setTerminalGroupingMode,
    setTerminalTimeRange,
    setThemeSkin,
  ]);

  useEffect(() => {
    if (!appPreferencesQuery.isSuccess) {
      return;
    }

    if (!appPreferencesQuery.data.configured) {
      const legacyPreferences = readLegacyAppPreferences(appLocale);
      applyPreferences(legacyPreferences);
      hydratedRef.current = true;
      mutateAppPreferences(legacyPreferences);
      return;
    }

    applyPreferences(appPreferencesFromResponse(appPreferencesQuery.data));
    hydratedRef.current = true;
  }, [
    appPreferencesQuery.data,
    appPreferencesQuery.isSuccess,
    applyPreferences,
    appLocale,
    mutateAppPreferences,
  ]);

  useEffect(() => {
    if (!hydratedRef.current || terminalTimeRangeSaveRef.current === terminalTimeRange) {
      return;
    }

    const nextPreferences = {
      ...statePreferences({
        appLocale,
        desktopNotificationsEnabled,
        keyboardShortcutBindings,
        queryClient,
        summaryOutputLanguage,
        terminalGroupingMode,
        terminalTimeRange,
        themeSkin,
        setAppLocale,
        setDesktopNotificationsEnabled,
        setKeyboardShortcutBindings,
        setSummaryOutputLanguage,
        setTerminalGroupingMode,
        setTerminalTimeRange,
        setThemeSkin,
      }),
      terminalTimeRange,
    };
    terminalTimeRangeSaveRef.current = terminalTimeRange;
    setRuntimeAppPreferences(nextPreferences);
    mutateAppPreferences(nextPreferences);
  }, [
    appLocale,
    desktopNotificationsEnabled,
    keyboardShortcutBindings,
    mutateAppPreferences,
    queryClient,
    summaryOutputLanguage,
    terminalGroupingMode,
    terminalTimeRange,
    themeSkin,
    setAppLocale,
    setDesktopNotificationsEnabled,
    setKeyboardShortcutBindings,
    setSummaryOutputLanguage,
    setTerminalGroupingMode,
    setTerminalTimeRange,
    setThemeSkin,
  ]);

  const saveAppPreferences = useCallback(async (preferences: AppPreferences) => {
    const response = await mutateAppPreferencesAsync(preferences);
    const savedPreferences = appPreferencesFromResponse(response);
    terminalTimeRangeSaveRef.current = savedPreferences.terminalTimeRange;
    setRuntimeAppPreferences(savedPreferences);
    return savedPreferences;
  }, [mutateAppPreferencesAsync]);

  return {
    appPreferencesReady: hydratedRef.current,
    saveAppPreferences,
  };
}
