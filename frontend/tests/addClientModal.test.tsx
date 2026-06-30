import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, describe, expect, it, vi } from "vitest";

import { AddClientModal } from "../src/components/AddClientModal";
import { writeClipboardText } from "../src/terminalClipboard";
import type { BootstrapClientInput } from "../src/types";

globalThis.IS_REACT_ACT_ENVIRONMENT = true;

let root: Root | null = null;
let container: HTMLDivElement | null = null;

vi.mock("../src/terminalClipboard", () => ({
  writeClipboardText: vi.fn(() => Promise.resolve())
}));

type RenderAddClientModalOptions = {
  initialMode?: "bootstrap" | "registration";
  registrationKey?: string | null;
  onBootstrapSubmit?: (payload: BootstrapClientInput) => void;
  onGenerateRegistrationKey?: (label?: string | null) => void;
};

function addClientModalElement(options: RenderAddClientModalOptions) {
  return (
    <AddClientModal
      isOpen
      initialMode={options.initialMode}
      bootstrapFailed={false}
      bootstrapPending={false}
      registrationKey={options.registrationKey ?? null}
      registrationKeyPending={false}
      registrationKeyError={null}
      onClose={() => {}}
      onBootstrapSubmit={options.onBootstrapSubmit ?? (() => {})}
      onGenerateRegistrationKey={options.onGenerateRegistrationKey ?? (() => {})}
    />
  );
}

function renderAddClientModal(options: RenderAddClientModalOptions = {}) {
  container = document.createElement("div");
  document.body.appendChild(container);
  root = createRoot(container);
  act(() => {
    root?.render(addClientModalElement(options));
  });
}

async function rerenderAddClientModal(options: RenderAddClientModalOptions = {}) {
  await act(async () => {
    root?.render(addClientModalElement(options));
  });
}

function setInputValue(target: HTMLInputElement | HTMLTextAreaElement, value: string): void {
  const prototype = target instanceof HTMLTextAreaElement ? HTMLTextAreaElement.prototype : HTMLInputElement.prototype;
  const descriptor = Object.getOwnPropertyDescriptor(prototype, "value");
  act(() => {
    descriptor?.set?.call(target, value);
    target.dispatchEvent(new Event("input", { bubbles: true }));
  });
}

afterEach(() => {
  act(() => {
    root?.unmount();
  });
  container?.remove();
  delete (window as Window & { __WEB_TERMINAL_API_BASE?: string }).__WEB_TERMINAL_API_BASE;
  root = null;
  container = null;
  vi.clearAllMocks();
  vi.restoreAllMocks();
});

describe("AddClientModal", () => {
  it("opens on SSH bootstrap and submits bootstrap details", () => {
    const onBootstrapSubmit = vi.fn();
    renderAddClientModal({ onBootstrapSubmit });

    expect(container?.textContent).toContain("SSH bootstrap");
    setInputValue(container?.querySelector("#bootstrap-client-name") as HTMLInputElement, "Production host");
    setInputValue(container?.querySelector("#bootstrap-client-host") as HTMLInputElement, "example.com");
    setInputValue(container?.querySelector("#bootstrap-client-port") as HTMLInputElement, "2222");
    setInputValue(container?.querySelector("#bootstrap-client-username") as HTMLInputElement, "deploy");
    setInputValue(container?.querySelector("#bootstrap-client-private-key") as HTMLTextAreaElement, "private-key");
    setInputValue(container?.querySelector("#bootstrap-client-passphrase") as HTMLInputElement, "secret");
    setInputValue(container?.querySelector("#bootstrap-client-server-url") as HTMLInputElement, "http://control.example.com:5173");

    act(() => {
      container?.querySelector("form")?.dispatchEvent(new Event("submit", { bubbles: true, cancelable: true }));
    });

    expect(onBootstrapSubmit).toHaveBeenCalledWith({
      name: "Production host",
      host: "example.com",
      port: 2222,
      username: "deploy",
      private_key: "private-key",
      passphrase: "secret",
      server_url: "http://control.example.com:5173"
    });
  });

  it("switches to registration key mode and requests a one-time key", () => {
    const onGenerateRegistrationKey = vi.fn();
    (window as Window & { __WEB_TERMINAL_API_BASE?: string }).__WEB_TERMINAL_API_BASE = "http://control.example.com:5173";
    renderAddClientModal({
      registrationKey: "wtr_test_key",
      onGenerateRegistrationKey
    });

    const registrationTab = Array.from(container?.querySelectorAll("[role='tab']") ?? [])
      .find((button) => button.textContent?.includes("Registration Key"));
    expect(registrationTab).toBeInstanceOf(HTMLButtonElement);

    act(() => {
      (registrationTab as HTMLButtonElement).click();
    });

    expect(container?.querySelector("[data-onboarding-id='remote-registration-panel']")).not.toBeNull();
    expect(container?.textContent).toContain("One-time registration key");
    expect(container?.textContent).toContain("wtr_test_key");
    const clientNameInput = Array.from(container?.querySelectorAll("input") ?? [])
      .find((input) => input.placeholder === "Example: office-mac-mini");
    expect(clientNameInput).toBeInstanceOf(HTMLInputElement);
    setInputValue(clientNameInput as HTMLInputElement, "office-mac-mini");
    const scriptTextarea = Array.from(container?.querySelectorAll("textarea") ?? [])
      .find((textarea) => textarea.value.includes("register-client-direct.sh"));
    expect(scriptTextarea?.value).toContain("http://control.example.com:5173/api/clients/register-script");
    expect(scriptTextarea?.value).toContain("WEB_TERMINAL_SERVER_URL='http://control.example.com:5173'");
    expect(scriptTextarea?.value).toContain("WEB_TERMINAL_REGISTRATION_KEY='wtr_test_key'");
    expect(scriptTextarea?.value).toContain("WEB_TERMINAL_CLIENT_NAME='office-mac-mini'");
    expect(scriptTextarea?.value).not.toContain("raw.githubusercontent.com");
    const generateButton = Array.from(container?.querySelectorAll("button") ?? [])
      .find((button) => button.textContent?.includes("Generate one-time registration key"));
    act(() => {
      generateButton?.click();
    });
    expect(onGenerateRegistrationKey).toHaveBeenCalledWith("office-mac-mini");
  });

  it("can open directly to registration key mode", () => {
    renderAddClientModal({ initialMode: "registration", registrationKey: "wtr_direct_key" });

    expect(container?.textContent).toContain("Registration key");
    expect(container?.textContent).toContain("wtr_direct_key");
    expect(container?.querySelector("[data-onboarding-id='remote-registration-panel']")).not.toBeNull();
  });

  it("copies the registration script from the script header and after key generation", async () => {
    const onGenerateRegistrationKey = vi.fn();
    const writeClipboardTextMock = vi.mocked(writeClipboardText);
    (window as Window & { __WEB_TERMINAL_API_BASE?: string }).__WEB_TERMINAL_API_BASE = "http://control.example.com:5173";
    renderAddClientModal({
      initialMode: "registration",
      registrationKey: "wtr_existing_key",
      onGenerateRegistrationKey
    });

    const clientNameInput = Array.from(container?.querySelectorAll("input") ?? [])
      .find((input) => input.placeholder === "Example: office-mac-mini");
    setInputValue(clientNameInput as HTMLInputElement, "office-mac-mini");

    const copyScriptButton = container?.querySelector('button[aria-label="Copy registration script"]');
    expect(copyScriptButton).toBeInstanceOf(HTMLButtonElement);
    expect(copyScriptButton?.querySelector("svg")).not.toBeNull();
    expect(copyScriptButton?.textContent?.trim()).toBe("");

    await act(async () => {
      (copyScriptButton as HTMLButtonElement).click();
    });

    expect(writeClipboardTextMock).toHaveBeenCalledTimes(1);
    expect(writeClipboardTextMock.mock.calls[0]?.[0]).toContain("WEB_TERMINAL_REGISTRATION_KEY='wtr_existing_key'");
    expect(writeClipboardTextMock.mock.calls[0]?.[0]).toContain("WEB_TERMINAL_CLIENT_NAME='office-mac-mini'");
    expect(writeClipboardTextMock.mock.calls[0]?.[1]).toBe(true);

    writeClipboardTextMock.mockClear();
    const generateAndCopyButton = Array.from(container?.querySelectorAll("button") ?? [])
      .find((button) => button.textContent?.includes("Generate and copy registration script"));
    expect(generateAndCopyButton).toBeInstanceOf(HTMLButtonElement);

    await act(async () => {
      (generateAndCopyButton as HTMLButtonElement).click();
    });

    expect(onGenerateRegistrationKey).toHaveBeenCalledWith("office-mac-mini");
    expect(writeClipboardTextMock).not.toHaveBeenCalled();

    await rerenderAddClientModal({
      initialMode: "registration",
      registrationKey: "wtr_new_key",
      onGenerateRegistrationKey
    });

    expect(writeClipboardTextMock).toHaveBeenCalledTimes(1);
    expect(writeClipboardTextMock.mock.calls[0]?.[0]).toContain("WEB_TERMINAL_REGISTRATION_KEY='wtr_new_key'");
    expect(writeClipboardTextMock.mock.calls[0]?.[0]).toContain("WEB_TERMINAL_CLIENT_NAME='office-mac-mini'");
    expect(writeClipboardTextMock.mock.calls[0]?.[1]).toBe(true);
  });
});
