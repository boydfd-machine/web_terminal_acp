import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";

import { TRANSLATIONS, zh, type TranslationKey } from "./i18nCatalog";

export type AppLocale = "zh-CN" | "en-US";

export type TranslationParams = Record<string, string | number>;
export type TranslateFn = (key: TranslationKey, params?: TranslationParams) => string;

export const DEFAULT_APP_LOCALE: AppLocale = "zh-CN";

const APP_LOCALE_STORAGE_KEY = "web-terminal-acp:app-locale";

const LOCALE_LABELS: Record<AppLocale, string> = {
  "zh-CN": "简体中文",
  "en-US": "English"
};

const LOCALE_HTML_LANG: Record<AppLocale, string> = {
  "zh-CN": "zh-CN",
  "en-US": "en"
};

function runtimeDefaultAppLocale(): AppLocale {
  return import.meta.env.MODE === "test" ? "en-US" : DEFAULT_APP_LOCALE;
}

export type { TranslationKey };

type I18nContextValue = {
  locale: AppLocale;
  localeLabel: string;
  setLocale: (locale: AppLocale) => void;
  t: TranslateFn;
};

const I18nContext = createContext<I18nContextValue | null>(null);

const DEFAULT_I18N_CONTEXT: I18nContextValue = {
  locale: runtimeDefaultAppLocale(),
  localeLabel: appLocaleLabel(runtimeDefaultAppLocale()),
  setLocale: () => {},
  t: (key, params) => translate(runtimeDefaultAppLocale(), key, params)
};

export function isAppLocale(value: unknown): value is AppLocale {
  return value === "zh-CN" || value === "en-US";
}

export function appLocaleLabel(locale: AppLocale): string {
  return LOCALE_LABELS[locale];
}

export function appLocaleHtmlLang(locale: AppLocale): string {
  return LOCALE_HTML_LANG[locale];
}

export function supportedAppLocales(): AppLocale[] {
  return ["zh-CN", "en-US"];
}

export function resolveAppLocale(value: unknown, fallbackLocale: AppLocale = DEFAULT_APP_LOCALE): AppLocale {
  if (isAppLocale(value)) {
    return value;
  }

  if (typeof value !== "string") {
    return fallbackLocale;
  }

  const normalized = value.toLocaleLowerCase();
  if (normalized === "zh" || normalized.startsWith("zh-")) {
    return "zh-CN";
  }
  if (normalized === "en" || normalized.startsWith("en-")) {
    return "en-US";
  }
  return fallbackLocale;
}

export function readAppLocale(fallbackLocale: AppLocale = runtimeDefaultAppLocale()): AppLocale {
  if (typeof window === "undefined") {
    return fallbackLocale;
  }

  return resolveAppLocale(window.localStorage.getItem(APP_LOCALE_STORAGE_KEY), fallbackLocale);
}

export function writeAppLocale(locale: AppLocale): void {
  if (typeof window === "undefined") {
    return;
  }

  window.localStorage.setItem(APP_LOCALE_STORAGE_KEY, locale);
}

export function translate(locale: AppLocale, key: TranslationKey, params: TranslationParams = {}): string {
  const template = TRANSLATIONS[locale][key] ?? zh[key];
  return template.replace(/\{(\w+)\}/g, (match, name: string) => {
    const value = params[name];
    return value === undefined ? match : String(value);
  });
}

export function I18nProvider({
  children,
  initialLocale
}: {
  children: ReactNode;
  initialLocale?: AppLocale;
}) {
  const [locale, setLocaleState] = useState<AppLocale>(() => initialLocale ?? readAppLocale());

  useEffect(() => {
    document.documentElement.lang = appLocaleHtmlLang(locale);
  }, [locale]);

  const setLocale = useCallback((nextLocale: AppLocale) => {
    setLocaleState(nextLocale);
  }, []);

  const value = useMemo<I18nContextValue>(() => ({
    locale,
    localeLabel: appLocaleLabel(locale),
    setLocale,
    t: (key, params) => translate(locale, key, params)
  }), [locale, setLocale]);

  return (
    <I18nContext.Provider value={value}>
      {children}
    </I18nContext.Provider>
  );
}

export function useI18n(): I18nContextValue {
  const context = useContext(I18nContext);
  return context ?? DEFAULT_I18N_CONTEXT;
}
