import type { AuthCaptcha, AuthStatus, BootstrapClientInput, BootstrapClientResult, Client, ClientRegistrationKeyResult, ClientUpdateResult, LoginResult } from "./types";
import { asWebSocketUrl, pathSegment, request, requestVoid } from "./apiCore";
import { customQuickKeyForStorage, type CustomQuickKey } from "./terminalQuickKeys";

export type CustomQuickKeysResponse = { quick_keys: CustomQuickKey[] };
export type AuxTerminalEnsureResult = { status: string; cwd: string | null };

export function fetchAuthStatus(): Promise<AuthStatus> {
  return request<AuthStatus>("/api/auth/status");
}

export type LoginInput = {
  secret: string;
  captchaId?: string | null;
  captchaAnswer?: string | null;
};

export function login(payload: LoginInput): Promise<LoginResult> {
  return request<LoginResult>("/api/auth/login", {
    method: "POST",
    body: JSON.stringify({
      secret: payload.secret,
      captcha_id: payload.captchaId ?? null,
      captcha_answer: payload.captchaAnswer ?? null
    })
  });
}

export function createAuthCaptcha(): Promise<AuthCaptcha> {
  return request<AuthCaptcha>("/api/auth/captcha", {
    method: "POST"
  });
}

export function terminalWebSocketUrl(
  clientId: string,
  windowId: string,
  viewId?: string,
  options?: { allowMissingWindowRecreate?: boolean },
): string {
  const url = new URL(asWebSocketUrl(
    `/api/clients/${pathSegment(clientId)}/terminal/${pathSegment(windowId)}`,
    viewId,
  ));
  if (options?.allowMissingWindowRecreate === true) {
    url.searchParams.set("allow_missing_window_recreate", "1");
  }
  return url.toString();
}

export function ensureAuxTerminal(clientId: string, windowId: string): Promise<AuxTerminalEnsureResult> {
  return request<AuxTerminalEnsureResult>(
    `/api/clients/${pathSegment(clientId)}/windows/${pathSegment(windowId)}/aux-terminal/ensure`,
    { method: "POST" }
  );
}

export function auxTerminalWebSocketUrl(clientId: string, windowId: string, viewId?: string): string {
  return asWebSocketUrl(
    `/api/clients/${pathSegment(clientId)}/windows/${pathSegment(windowId)}/aux-terminal`,
    viewId
  );
}

export function terminalSelectionWebSocketUrl(clientId: string): string {
  return asWebSocketUrl(`/api/clients/${pathSegment(clientId)}/terminal-selection`);
}

export function uiEventsWebSocketUrl(): string {
  return asWebSocketUrl("/api/ui-events");
}

export function fetchClients(): Promise<Client[]> {
  return request<Client[]>("/api/clients");
}

export function fetchCustomQuickKeys(): Promise<CustomQuickKeysResponse> {
  return request<CustomQuickKeysResponse>("/api/ui-settings/custom-quick-keys");
}

export function updateCustomQuickKeys(quickKeys: CustomQuickKey[]): Promise<CustomQuickKeysResponse> {
  return request<CustomQuickKeysResponse>("/api/ui-settings/custom-quick-keys", {
    method: "PUT",
    body: JSON.stringify({ quick_keys: quickKeys.map(customQuickKeyForStorage) })
  });
}

export function bootstrapClient(payload: BootstrapClientInput): Promise<BootstrapClientResult> {
  return request<BootstrapClientResult>("/api/clients/bootstrap", {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

export function createClientRegistrationKey(label?: string | null): Promise<ClientRegistrationKeyResult> {
  return request<ClientRegistrationKeyResult>("/api/clients/registration-keys", {
    method: "POST",
    body: JSON.stringify({ label: label ?? null })
  });
}

export function updateClient(clientId: string): Promise<ClientUpdateResult> {
  return request<ClientUpdateResult>(`/api/clients/${pathSegment(clientId)}/update`, {
    method: "POST"
  });
}

export async function deleteClient(clientId: string): Promise<void> {
  await requestVoid(`/api/clients/${pathSegment(clientId)}`, { method: "DELETE" });
}
