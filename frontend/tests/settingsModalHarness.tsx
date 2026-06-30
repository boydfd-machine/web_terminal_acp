import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, vi } from "vitest";

import { AppPromptProvider } from "../src/components/AppPromptProvider";
import { SettingsModal, type SettingsView } from "../src/components/SettingsModal";
import { I18nProvider, type AppLocale } from "../src/i18n";
import type { KeyboardShortcutBindings } from "../src/keyboardShortcuts";
import type { CustomQuickKey } from "../src/terminalQuickKeys";
import type { AppPreferences } from "../src/userPreferences";

globalThis.IS_REACT_ACT_ENVIRONMENT = true;

let root: Root | null = null;
export let container: HTMLDivElement | null = null;
let queryClient: QueryClient | null = null;

export function getSettingsQueryClient(): QueryClient {
  if (queryClient === null) {
    throw new Error("settings query client is not initialized");
  }
  return queryClient;
}

export function renderSettingsModal(options: {
  appLocale?: AppLocale;
  keyboardShortcutBindings?: KeyboardShortcutBindings;
  customQuickKeys?: CustomQuickKey[];
  initialView?: SettingsView;
  onboardingEnabled?: boolean;
  selectedProjectPath?: string | null;
  selectedWindowId?: string | null;
  onClose?: () => void;
  onAppLocaleChange?: (locale: AppLocale) => void;
  onAppPreferencesSave?: (preferences: AppPreferences) => Promise<AppPreferences>;
  onSummaryOutputLanguageChange?: (language: "中文" | "English") => void;
  onKeyboardShortcutBindingsChange?: (bindings: KeyboardShortcutBindings) => void;
  onCustomQuickKeysChange?: (quickKeys: CustomQuickKey[]) => void;
  onStartOnboarding?: () => void;
} = {}) {
  container = document.createElement("div");
  document.body.appendChild(container);
  queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false }
    }
  });
  root = createRoot(container);
  act(() => {
    root?.render(
      <I18nProvider initialLocale={options.appLocale ?? "zh-CN"}>
        <QueryClientProvider client={queryClient as QueryClient}>
          <AppPromptProvider>
            <SettingsModal
              isOpen
              onClose={options.onClose ?? (() => {})}
              appLocale={options.appLocale ?? "zh-CN"}
              summaryOutputLanguage="中文"
              terminalGroupingMode="project-topic"
              terminalTimeRange="7d"
              themeSkin="default"
              desktopNotificationsEnabled
              keyboardShortcutBindings={options.keyboardShortcutBindings ?? {}}
              customQuickKeys={options.customQuickKeys ?? []}
              selectedClientId="client-1"
              selectedProjectPath={options.selectedProjectPath ?? null}
              selectedWindowId={options.selectedWindowId ?? null}
              onAppLocaleChange={options.onAppLocaleChange ?? (() => {})}
              onAppPreferencesSave={options.onAppPreferencesSave ?? (async (preferences) => preferences)}
              onSummaryOutputLanguageChange={options.onSummaryOutputLanguageChange ?? (() => {})}
              onTerminalGroupingModeChange={() => {}}
              onThemeSkinChange={() => {}}
              onDesktopNotificationsEnabledChange={() => {}}
              onKeyboardShortcutBindingsChange={options.onKeyboardShortcutBindingsChange ?? (() => {})}
              onCustomQuickKeysChange={options.onCustomQuickKeysChange ?? (() => {})}
              authEnabled
              initialView={options.initialView}
              onboardingEnabled={options.onboardingEnabled ?? true}
              onStartOnboarding={options.onStartOnboarding ?? (() => {})}
              onLogout={() => {}}
            />
          </AppPromptProvider>
        </QueryClientProvider>
      </I18nProvider>
    );
  });
}

export async function flushQueries() {
  await act(async () => {
    await new Promise((resolve) => window.setTimeout(resolve, 0));
    await new Promise((resolve) => window.setTimeout(resolve, 0));
  });
}

export async function waitFor(assertion: () => void) {
  let lastError: unknown = null;
  for (let index = 0; index < 20; index += 1) {
    try {
      assertion();
      return;
    } catch (error) {
      lastError = error;
      await act(async () => {
        await new Promise((resolve) => setTimeout(resolve, 0));
      });
    }
  }
  throw lastError;
}

export function setValue(target: HTMLInputElement | HTMLTextAreaElement, value: string): void {
  const prototype = target instanceof HTMLTextAreaElement ? HTMLTextAreaElement.prototype : HTMLInputElement.prototype;
  const setter = Object.getOwnPropertyDescriptor(prototype, "value")?.set;
  act(() => {
    setter?.call(target, value);
    target.dispatchEvent(new Event("input", { bubbles: true }));
  });
}

export function buttonByAriaLabel(label: string): HTMLButtonElement | null {
  const button = container?.querySelector(`button[aria-label="${label}"]`);
  return button instanceof HTMLButtonElement ? button : null;
}

export function setInputFiles(element: HTMLInputElement, files: File[]) {
  Object.defineProperty(element, "files", {
    configurable: true,
    value: files
  });
  element.dispatchEvent(new Event("change", { bubbles: true }));
}

export function jsonResponse(body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status: 200,
    headers: { "Content-Type": "application/json" }
  });
}

afterEach(() => {
  act(() => {
    root?.unmount();
  });
  container?.remove();
  root = null;
  container = null;
  queryClient?.clear();
  queryClient = null;
  window.localStorage.clear();
  document.body.replaceChildren();
  vi.useRealTimers();
  vi.restoreAllMocks();
});
