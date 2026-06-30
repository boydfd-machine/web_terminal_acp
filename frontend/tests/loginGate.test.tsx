import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import type { ReactElement } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { BackendConnectionGate, LoginGate } from "../src/components/LoginGate";

globalThis.IS_REACT_ACT_ENVIRONMENT = true;

let root: Root | null = null;
let container: HTMLDivElement | null = null;

function render(element: ReactElement): void {
  container = document.createElement("div");
  document.body.appendChild(container);
  root = createRoot(container);
  act(() => {
    root?.render(element);
  });
}

function changeInputValue(target: HTMLInputElement, value: string): void {
  const descriptor = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value");
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
  root = null;
  container = null;
  vi.restoreAllMocks();
});

describe("LoginGate", () => {
  it("lets users save a backend address before logging in", () => {
    const onSaveBackendAddress = vi.fn();
    render(
      <LoginGate
        backendAddress="http://127.0.0.1:8001"
        backendAddressError={null}
        captchaImageBase64={null}
        error={null}
        isCheckingBackend={false}
        isSubmitting={false}
        onSaveBackendAddress={onSaveBackendAddress}
        onSubmit={async () => {}}
      />
    );

    const backendInput = Array.from(container?.querySelectorAll("input") ?? [])
      .find((input) => input.previousElementSibling?.textContent === "Backend address");
    expect(backendInput).toBeInstanceOf(HTMLInputElement);
    changeInputValue(backendInput as HTMLInputElement, "http://control.example.com:8001");

    const saveButton = Array.from(container?.querySelectorAll("button") ?? [])
      .find((button) => button.textContent === "Save backend address");
    act(() => {
      saveButton?.click();
    });

    expect(onSaveBackendAddress).toHaveBeenCalledWith("http://control.example.com:8001");
  });

  it("submits the captcha answer when the login challenge is visible", () => {
    const onSubmit = vi.fn(async () => {});
    render(
      <LoginGate
        backendAddress="http://127.0.0.1:8001"
        backendAddressError={null}
        captchaImageBase64="iVBORw0KGgo="
        error="Enter the CAPTCHA and try again"
        isCheckingBackend={false}
        isSubmitting={false}
        onSaveBackendAddress={() => {}}
        onSubmit={onSubmit}
      />
    );

    const inputs = Array.from(container?.querySelectorAll("input") ?? []);
    const secretInput = inputs.find((input) => input.type === "password");
    const captchaInput = inputs.find((input) => input.previousElementSibling?.textContent === "CAPTCHA");
    expect(secretInput).toBeInstanceOf(HTMLInputElement);
    expect(captchaInput).toBeInstanceOf(HTMLInputElement);
    changeInputValue(secretInput as HTMLInputElement, "login-secret");
    changeInputValue(captchaInput as HTMLInputElement, "ABCDE");

    const submitButton = Array.from(container?.querySelectorAll("button") ?? [])
      .find((button) => button.textContent === "Log in");
    act(() => {
      submitButton?.click();
    });

    expect(onSubmit).toHaveBeenCalledWith("login-secret", "ABCDE");
    expect(container?.querySelector("img")?.getAttribute("src")).toBe("data:image/png;base64,iVBORw0KGgo=");
  });

  it("shows backend configuration when the app cannot connect", () => {
    const onSaveBackendAddress = vi.fn();
    render(
      <BackendConnectionGate
        backendAddress="http://127.0.0.1:8001"
        backendAddressError="请输入有效的 HTTP/HTTPS 后端地址"
        connectionError="404 File not found"
        isCheckingBackend={false}
        onSaveBackendAddress={onSaveBackendAddress}
      />
    );

    expect(container?.textContent).toContain("Cannot connect to backend: 404 File not found");
    expect(container?.textContent).toContain("请输入有效的 HTTP/HTTPS 后端地址");

    const resetButton = Array.from(container?.querySelectorAll("button") ?? [])
      .find((button) => button.textContent === "Restore default");
    act(() => {
      resetButton?.click();
    });

    expect(onSaveBackendAddress).toHaveBeenCalledWith("");
  });

  it("uses a Keycloak login action without showing the shared secret field", () => {
    const onKeycloakLogin = vi.fn();
    render(
      <LoginGate
        backendAddress="http://127.0.0.1:8001"
        backendAddressError={null}
        error={null}
        isCheckingBackend={false}
        isSubmitting={false}
        mode="keycloak"
        onKeycloakLogin={onKeycloakLogin}
        onSaveBackendAddress={() => {}}
        onSubmit={async () => {}}
      />
    );

    expect(container?.textContent).toContain("Log in with Keycloak");
    expect(container?.textContent).not.toContain("Login secret");

    const loginButton = Array.from(container?.querySelectorAll("button") ?? [])
      .find((button) => button.textContent === "Log in with Keycloak");
    act(() => {
      loginButton?.click();
    });

    expect(onKeycloakLogin).toHaveBeenCalledTimes(1);
  });
});
