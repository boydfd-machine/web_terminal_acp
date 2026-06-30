import { act } from "react";
import type { ReactNode } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it } from "vitest";

import {
  DEFAULT_APP_LOCALE,
  I18nProvider,
  readAppLocale,
  resolveAppLocale,
  translate,
  useI18n,
  writeAppLocale
} from "../src/i18n";

globalThis.IS_REACT_ACT_ENVIRONMENT = true;

let root: Root | null = null;
let container: HTMLDivElement | null = null;

function render(element: ReactNode): void {
  container = document.createElement("div");
  document.body.appendChild(container);
  root = createRoot(container);
  act(() => {
    root?.render(element);
  });
}

function LocaleProbe() {
  const { locale, setLocale, t } = useI18n();
  return (
    <section>
      <span data-testid="locale">{locale}</span>
      <span data-testid="label">{t("app.settings")}</span>
      <button type="button" onClick={() => setLocale("en-US")}>
        Switch
      </button>
    </section>
  );
}

beforeEach(() => {
  window.localStorage.clear();
  document.documentElement.lang = "";
});

afterEach(() => {
  act(() => {
    root?.unmount();
  });
  container?.remove();
  root = null;
  container = null;
  window.localStorage.clear();
  document.documentElement.lang = "";
});

describe("i18n locale preferences", () => {
  it("normalizes supported locale aliases and falls back to Chinese", () => {
    expect(resolveAppLocale("zh")).toBe("zh-CN");
    expect(resolveAppLocale("zh-Hant")).toBe("zh-CN");
    expect(resolveAppLocale("en")).toBe("en-US");
    expect(resolveAppLocale("en-GB")).toBe("en-US");
    expect(resolveAppLocale("fr-FR")).toBe("zh-CN");
    expect(resolveAppLocale(null)).toBe("zh-CN");
  });

  it("persists an explicit app locale", () => {
    expect(readAppLocale(DEFAULT_APP_LOCALE)).toBe("zh-CN");

    writeAppLocale("en-US");

    expect(readAppLocale(DEFAULT_APP_LOCALE)).toBe("en-US");
  });

  it("interpolates translated parameters", () => {
    expect(translate("en-US", "notifications.unread", { count: 3 })).toBe("3 unread");
    expect(translate("zh-CN", "notifications.unread", { count: 3 })).toBe("3 条未读");
  });
});

describe("I18nProvider", () => {
  it("updates rendered text and document language when locale changes", () => {
    render(
      <I18nProvider initialLocale="zh-CN">
        <LocaleProbe />
      </I18nProvider>
    );

    expect(container?.querySelector("[data-testid='locale']")?.textContent).toBe("zh-CN");
    expect(container?.querySelector("[data-testid='label']")?.textContent).toBe("设置");
    expect(document.documentElement.lang).toBe("zh-CN");

    act(() => {
      (container?.querySelector("button") as HTMLButtonElement).click();
    });

    expect(container?.querySelector("[data-testid='locale']")?.textContent).toBe("en-US");
    expect(container?.querySelector("[data-testid='label']")?.textContent).toBe("Settings");
    expect(window.localStorage.getItem("web-terminal-acp:app-locale")).toBeNull();
    expect(document.documentElement.lang).toBe("en");
  });
});
