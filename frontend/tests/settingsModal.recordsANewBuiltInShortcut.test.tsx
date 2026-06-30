import { act } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import {
  container,
  flushQueries,
  jsonResponse,
  renderSettingsModal,
  setValue,
  waitFor
} from "./settingsModalHarness";

beforeEach(() => {
  vi.useFakeTimers();
});

function buttonByAriaLabel(label: string): HTMLButtonElement | null {
  const button = container?.querySelector(`button[aria-label="${label}"]`);
  return button instanceof HTMLButtonElement ? button : null;
}

function buttonByAriaLabelPrefix(prefix: string): HTMLButtonElement | null {
  return Array.from(container?.querySelectorAll("button[aria-label]") ?? [])
    .find((button): button is HTMLButtonElement =>
      button instanceof HTMLButtonElement && button.getAttribute("aria-label")?.startsWith(prefix) === true
    ) ?? null;
}

function promptButtonByText(label: string): HTMLButtonElement | null {
  const dialog = document.body.querySelector('[role="alertdialog"]');
  return Array.from(dialog?.querySelectorAll("button") ?? [])
    .find((button): button is HTMLButtonElement => button instanceof HTMLButtonElement && button.textContent === label)
    ?? null;
}

describe("SettingsModal", () => {
  it("records a new built-in shortcut binding after save", async () => {
    const onKeyboardShortcutBindingsChange = vi.fn();
    renderSettingsModal({ onKeyboardShortcutBindingsChange });

    const shortcutRow = Array.from(container?.querySelectorAll(".settings-tabs button") ?? [])
      .find((row) => row.textContent?.includes("快捷键"));
    act(() => {
      (shortcutRow as HTMLButtonElement).click();
    });

    const settingsBindButton = Array.from(container?.querySelectorAll(".shortcut-binding-item") ?? [])
      .find((item) => item.textContent?.includes("设置"))
      ?.querySelector(".shortcut-recorder-button");
    expect(settingsBindButton).toBeInstanceOf(HTMLButtonElement);

    act(() => {
      (settingsBindButton as HTMLButtonElement).click();
    });
    act(() => {
      (settingsBindButton as HTMLButtonElement).dispatchEvent(new KeyboardEvent("keydown", {
        bubbles: true,
        cancelable: true,
        key: "s",
        ctrlKey: true
      }));
    });

    expect(onKeyboardShortcutBindingsChange).not.toHaveBeenCalled();
    expect(container?.textContent).toContain("有未保存的修改");

    const saveButton = buttonByAriaLabel("保存");
    expect(saveButton).toBeInstanceOf(HTMLButtonElement);

    await act(async () => {
      (saveButton as HTMLButtonElement).click();
    });

    expect(onKeyboardShortcutBindingsChange).toHaveBeenCalledWith({
      settings: { key: "s", alt: false, ctrl: true, meta: false, shift: false }
    });
  });

  it("cancels shortcut recording with Escape without closing the settings modal", () => {
    const onClose = vi.fn();
    renderSettingsModal({ onClose });

    const shortcutRow = Array.from(container?.querySelectorAll(".settings-tabs button") ?? [])
      .find((row) => row.textContent?.includes("快捷键"));
    act(() => {
      (shortcutRow as HTMLButtonElement).click();
    });

    const settingsBindButton = Array.from(container?.querySelectorAll(".shortcut-binding-item") ?? [])
      .find((item) => item.textContent?.includes("设置"))
      ?.querySelector(".shortcut-recorder-button");
    expect(settingsBindButton).toBeInstanceOf(HTMLButtonElement);

    act(() => {
      (settingsBindButton as HTMLButtonElement).click();
    });
    expect(settingsBindButton?.textContent).toContain("按下快捷键");

    act(() => {
      window.dispatchEvent(new KeyboardEvent("keydown", {
        bubbles: true,
        cancelable: true,
        key: "Escape"
      }));
    });

    expect(onClose).not.toHaveBeenCalled();
    expect(settingsBindButton?.textContent).toContain("Alt+,");
  });

  it("starts onboarding from settings", () => {
    const onStartOnboarding = vi.fn();
    renderSettingsModal({ onStartOnboarding });

    const accountTab = Array.from(container?.querySelectorAll(".settings-tabs button") ?? [])
      .find((button) => button.textContent?.includes("账号"));
    expect(accountTab).toBeInstanceOf(HTMLButtonElement);

    act(() => {
      (accountTab as HTMLButtonElement).click();
    });

    const onboardingRow = Array.from(container?.querySelectorAll(".settings-nav-row") ?? [])
      .find((row) => row.textContent?.includes("新手引导"));
    expect(onboardingRow).toBeInstanceOf(HTMLButtonElement);

    act(() => {
      (onboardingRow as HTMLButtonElement).click();
    });

    expect(onStartOnboarding).toHaveBeenCalledTimes(1);
  });

  it("hides onboarding entry when onboarding is disabled", () => {
    renderSettingsModal({ onboardingEnabled: false });

    expect(container?.textContent).not.toContain("新手引导");
  });

  it("records shortcut bindings for custom quick keys after save", async () => {
    const onCustomQuickKeysChange = vi.fn();
    renderSettingsModal({
      customQuickKeys: [{ id: "interrupt", label: "Interrupt", input: "{Ctrl-C}" }],
      onCustomQuickKeysChange
    });

    const shortcutRow = Array.from(container?.querySelectorAll(".settings-tabs button") ?? [])
      .find((row) => row.textContent?.includes("快捷键"));
    act(() => {
      (shortcutRow as HTMLButtonElement).click();
    });

    const quickKeyBindButton = Array.from(container?.querySelectorAll(".shortcut-binding-item") ?? [])
      .find((item) => item.textContent?.includes("快捷按键：Interrupt"))
      ?.querySelector(".shortcut-recorder-button");
    expect(quickKeyBindButton).toBeInstanceOf(HTMLButtonElement);

    act(() => {
      (quickKeyBindButton as HTMLButtonElement).click();
    });
    act(() => {
      (quickKeyBindButton as HTMLButtonElement).dispatchEvent(new KeyboardEvent("keydown", {
        bubbles: true,
        cancelable: true,
        key: "c",
        altKey: true
      }));
    });

    expect(onCustomQuickKeysChange).not.toHaveBeenCalled();

    const saveButton = buttonByAriaLabel("保存");
    expect(saveButton).toBeInstanceOf(HTMLButtonElement);

    await act(async () => {
      (saveButton as HTMLButtonElement).click();
    });

    expect(onCustomQuickKeysChange).toHaveBeenCalledWith([
      {
        id: "interrupt",
        label: "Interrupt",
        input: "{Ctrl-C}",
        shortcut: { key: "c", alt: true, ctrl: false, meta: false, shift: false }
      }
    ]);
  });

  it("confirms before closing with unsaved changes", async () => {
    const onClose = vi.fn();
    renderSettingsModal({ onClose });

    const languageSelect = Array.from(container?.querySelectorAll("select") ?? [])
      .find((select) => select.textContent?.includes("English"));
    expect(languageSelect).toBeInstanceOf(HTMLSelectElement);

    act(() => {
      (languageSelect as HTMLSelectElement).value = "English";
      (languageSelect as HTMLSelectElement).dispatchEvent(new Event("change", { bubbles: true }));
    });

    act(() => {
      window.dispatchEvent(new KeyboardEvent("keydown", {
        bubbles: true,
        cancelable: true,
        key: "Escape"
      }));
    });

    expect(document.body.querySelector('[role="alertdialog"]')?.textContent).toContain("设置有未保存的修改");
    expect(onClose).not.toHaveBeenCalled();

    const cancelButton = promptButtonByText("取消");
    expect(cancelButton).toBeInstanceOf(HTMLButtonElement);
    await act(async () => {
      (cancelButton as HTMLButtonElement).click();
      await Promise.resolve();
    });
    expect(onClose).not.toHaveBeenCalled();

    act(() => {
      window.dispatchEvent(new KeyboardEvent("keydown", {
        bubbles: true,
        cancelable: true,
        key: "Escape"
      }));
    });
    const discardButton = promptButtonByText("放弃修改");
    expect(discardButton).toBeInstanceOf(HTMLButtonElement);
    await act(async () => {
      (discardButton as HTMLButtonElement).click();
      await Promise.resolve();
    });

    expect(onClose).toHaveBeenCalledTimes(1);
  });
});
