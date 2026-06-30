import type { AppLocale } from "./i18n";
import { en as coreEn, zh as coreZh } from "./i18nCoreCatalog";
import { enDetail, zhDetail } from "./i18nDetailCatalog";
import { enProject, zhProject } from "./i18nProjectCatalog";
import { enShared, zhShared } from "./i18nSharedCatalog";
import { enSettings, zhSettings } from "./i18nSettingsCatalog";
import { enTerminal, zhTerminal } from "./i18nTerminalCatalog";
import { enWindow, zhWindow } from "./i18nWindowCatalog";

export const zh = {
  ...coreZh,
  ...zhShared,
  ...zhDetail,
  ...zhSettings,
  ...zhProject,
  ...zhTerminal,
  ...zhWindow
} as const;

export type TranslationKey = keyof typeof zh;

export const en: Record<TranslationKey, string> = {
  ...coreEn,
  ...enShared,
  ...enDetail,
  ...enSettings,
  ...enProject,
  ...enTerminal,
  ...enWindow
};

export const TRANSLATIONS: Record<AppLocale, Record<TranslationKey, string>> = {
  "zh-CN": zh,
  "en-US": en
};
