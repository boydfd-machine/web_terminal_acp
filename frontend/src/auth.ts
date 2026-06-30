import { readApiBase } from "./apiBase";

export const AUTH_TOKEN_STORAGE_KEY = "web-terminal-acp:auth-token";
export const AUTH_REFRESH_TOKEN_STORAGE_KEY = "web-terminal-acp:auth-refresh-token";
export const WEBSOCKET_AUTH_PROTOCOL_PREFIX = "web-terminal-auth.";
const AUTH_CHANGED_EVENT = "web-terminal-auth-changed";
const KEYCLOAK_PKCE_STORAGE_KEY = "web-terminal-acp:keycloak-pkce";

export type KeycloakAuthConfig = {
  authorization_endpoint: string;
  end_session_endpoint?: string;
  client_id: string;
};

type KeycloakPkceState = {
  state: string;
  verifier: string;
  redirectUri: string;
};

export function readAuthToken(): string | null {
  return readStoredToken(AUTH_TOKEN_STORAGE_KEY);
}

export function readAuthRefreshToken(): string | null {
  return readStoredToken(AUTH_REFRESH_TOKEN_STORAGE_KEY);
}

function readStoredToken(key: string): string | null {
  if (typeof window === "undefined") {
    return null;
  }
  const token = window.localStorage.getItem(key);
  return token && token.trim() !== "" ? token : null;
}

export function writeAuthToken(token: string): void {
  writeAuthTokens(token, null);
}

export function writeAuthTokens(token: string, refreshToken: string | null = null): void {
  if (typeof window === "undefined") {
    return;
  }
  window.localStorage.setItem(AUTH_TOKEN_STORAGE_KEY, token);
  if (refreshToken !== null && refreshToken.trim() !== "") {
    window.localStorage.setItem(AUTH_REFRESH_TOKEN_STORAGE_KEY, refreshToken);
  } else {
    window.localStorage.removeItem(AUTH_REFRESH_TOKEN_STORAGE_KEY);
  }
  dispatchAuthChanged();
}

export function clearAuthToken(): void {
  clearAuthTokens();
}

export function clearAuthTokens(): void {
  if (typeof window === "undefined") {
    return;
  }
  window.localStorage.removeItem(AUTH_TOKEN_STORAGE_KEY);
  window.localStorage.removeItem(AUTH_REFRESH_TOKEN_STORAGE_KEY);
  dispatchAuthChanged();
}

function dispatchAuthChanged(): void {
  window.dispatchEvent(new Event(AUTH_CHANGED_EVENT));
}

export function authChangedEventName(): string {
  return AUTH_CHANGED_EVENT;
}

export function appendAuthToken(url: URL): URL {
  const token = readAuthToken();
  if (token !== null) {
    url.searchParams.set("auth_token", token);
  }
  return url;
}

export function webSocketAuthProtocols(): string[] {
  const token = readAuthToken();
  return token === null ? [] : [`${WEBSOCKET_AUTH_PROTOCOL_PREFIX}${token}`];
}

export async function buildKeycloakLoginUrl(config: KeycloakAuthConfig): Promise<string> {
  const redirectUri = keycloakRedirectUri();
  const state = randomBase64Url(24);
  const verifier = randomBase64Url(64);
  const challenge = await sha256Base64Url(verifier);
  const payload: KeycloakPkceState = {
    state,
    verifier,
    redirectUri,
  };
  window.sessionStorage.setItem(KEYCLOAK_PKCE_STORAGE_KEY, JSON.stringify(payload));

  const url = new URL(config.authorization_endpoint);
  url.searchParams.set("client_id", config.client_id);
  url.searchParams.set("response_type", "code");
  url.searchParams.set("scope", "openid profile email");
  url.searchParams.set("redirect_uri", redirectUri);
  url.searchParams.set("state", state);
  url.searchParams.set("code_challenge", challenge);
  url.searchParams.set("code_challenge_method", "S256");
  return url.toString();
}

export async function consumeKeycloakRedirect(search: string): Promise<string | null> {
  if (typeof window === "undefined") {
    return null;
  }
  const params = new URLSearchParams(search);
  const code = params.get("code");
  const state = params.get("state");
  if (!code || !state) {
    return null;
  }
  const stored = readKeycloakPkceState();
  if (stored === null || stored.state !== state) {
    throw new Error("Invalid Keycloak login state.");
  }
  window.sessionStorage.removeItem(KEYCLOAK_PKCE_STORAGE_KEY);

  const response = await fetch(keycloakCallbackUrl(), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      code,
      redirect_uri: stored.redirectUri,
      code_verifier: stored.verifier,
    }),
  });
  if (!response.ok) {
    throw new Error("Keycloak callback failed.");
  }
  const tokenResponse = await response.json() as { token?: unknown; refresh_token?: unknown };
  if (typeof tokenResponse.token !== "string" || tokenResponse.token.trim() === "") {
    throw new Error("Keycloak access token missing.");
  }
  if (typeof tokenResponse.refresh_token !== "string" || tokenResponse.refresh_token.trim() === "") {
    throw new Error("Keycloak refresh token missing.");
  }
  writeAuthTokens(tokenResponse.token, tokenResponse.refresh_token);
  clearKeycloakCodeFromLocation();
  return tokenResponse.token;
}

function readKeycloakPkceState(): KeycloakPkceState | null {
  const raw = window.sessionStorage.getItem(KEYCLOAK_PKCE_STORAGE_KEY);
  if (!raw) {
    return null;
  }
  try {
    return JSON.parse(raw) as KeycloakPkceState;
  } catch {
    return null;
  }
}

function keycloakRedirectUri(): string {
  const url = new URL(window.location.href);
  url.search = "";
  url.hash = "";
  return url.toString();
}

function keycloakCallbackUrl(): string {
  const base = new URL(readApiBase());
  if (!base.pathname.endsWith("/")) {
    base.pathname = `${base.pathname}/`;
  }
  return new URL("api/auth/keycloak/callback", base).toString();
}

function clearKeycloakCodeFromLocation(): void {
  const url = new URL(window.location.href);
  url.searchParams.delete("code");
  url.searchParams.delete("state");
  url.searchParams.delete("session_state");
  window.history.replaceState(null, "", `${url.pathname}${url.search}${url.hash}`);
}

function randomBase64Url(byteLength: number): string {
  const bytes = new Uint8Array(byteLength);
  window.crypto.getRandomValues(bytes);
  return bytesToBase64Url(bytes);
}

async function sha256Base64Url(value: string): Promise<string> {
  const bytes = new TextEncoder().encode(value);
  const subtle = window.crypto.subtle;
  if (!subtle) {
    return bytesToBase64Url(sha256(bytes));
  }
  const digest = await subtle.digest("SHA-256", bytes);
  return bytesToBase64Url(new Uint8Array(digest));
}

function sha256(message: Uint8Array): Uint8Array {
  const constants = [
    0x428a2f98, 0x71374491, 0xb5c0fbcf, 0xe9b5dba5, 0x3956c25b, 0x59f111f1, 0x923f82a4,
    0xab1c5ed5, 0xd807aa98, 0x12835b01, 0x243185be, 0x550c7dc3, 0x72be5d74, 0x80deb1fe,
    0x9bdc06a7, 0xc19bf174, 0xe49b69c1, 0xefbe4786, 0x0fc19dc6, 0x240ca1cc, 0x2de92c6f,
    0x4a7484aa, 0x5cb0a9dc, 0x76f988da, 0x983e5152, 0xa831c66d, 0xb00327c8, 0xbf597fc7,
    0xc6e00bf3, 0xd5a79147, 0x06ca6351, 0x14292967, 0x27b70a85, 0x2e1b2138, 0x4d2c6dfc,
    0x53380d13, 0x650a7354, 0x766a0abb, 0x81c2c92e, 0x92722c85, 0xa2bfe8a1, 0xa81a664b,
    0xc24b8b70, 0xc76c51a3, 0xd192e819, 0xd6990624, 0xf40e3585, 0x106aa070, 0x19a4c116,
    0x1e376c08, 0x2748774c, 0x34b0bcb5, 0x391c0cb3, 0x4ed8aa4a, 0x5b9cca4f, 0x682e6ff3,
    0x748f82ee, 0x78a5636f, 0x84c87814, 0x8cc70208, 0x90befffa, 0xa4506ceb, 0xbef9a3f7,
    0xc67178f2,
  ];
  const state = [
    0x6a09e667, 0xbb67ae85, 0x3c6ef372, 0xa54ff53a, 0x510e527f, 0x9b05688c, 0x1f83d9ab,
    0x5be0cd19,
  ];
  const bitLength = message.length * 8;
  const paddedLength = (((message.length + 9 + 63) >> 6) << 6);
  const padded = new Uint8Array(paddedLength);
  padded.set(message);
  padded[message.length] = 0x80;
  const view = new DataView(padded.buffer);
  view.setUint32(paddedLength - 4, bitLength, false);

  const words = new Uint32Array(64);
  for (let offset = 0; offset < padded.length; offset += 64) {
    for (let index = 0; index < 16; index += 1) {
      words[index] = view.getUint32(offset + index * 4, false);
    }
    for (let index = 16; index < 64; index += 1) {
      const s0 = rotateRight(words[index - 15], 7)
        ^ rotateRight(words[index - 15], 18)
        ^ (words[index - 15] >>> 3);
      const s1 = rotateRight(words[index - 2], 17)
        ^ rotateRight(words[index - 2], 19)
        ^ (words[index - 2] >>> 10);
      words[index] = (words[index - 16] + s0 + words[index - 7] + s1) >>> 0;
    }

    let [a, b, c, d, e, f, g, h] = state;
    for (let index = 0; index < 64; index += 1) {
      const s1 = rotateRight(e, 6) ^ rotateRight(e, 11) ^ rotateRight(e, 25);
      const choice = (e & f) ^ (~e & g);
      const temp1 = (h + s1 + choice + constants[index] + words[index]) >>> 0;
      const s0 = rotateRight(a, 2) ^ rotateRight(a, 13) ^ rotateRight(a, 22);
      const majority = (a & b) ^ (a & c) ^ (b & c);
      const temp2 = (s0 + majority) >>> 0;
      h = g;
      g = f;
      f = e;
      e = (d + temp1) >>> 0;
      d = c;
      c = b;
      b = a;
      a = (temp1 + temp2) >>> 0;
    }

    state[0] = (state[0] + a) >>> 0;
    state[1] = (state[1] + b) >>> 0;
    state[2] = (state[2] + c) >>> 0;
    state[3] = (state[3] + d) >>> 0;
    state[4] = (state[4] + e) >>> 0;
    state[5] = (state[5] + f) >>> 0;
    state[6] = (state[6] + g) >>> 0;
    state[7] = (state[7] + h) >>> 0;
  }

  const digest = new Uint8Array(32);
  const digestView = new DataView(digest.buffer);
  state.forEach((word, index) => digestView.setUint32(index * 4, word, false));
  return digest;
}

function rotateRight(value: number, shift: number): number {
  return (value >>> shift) | (value << (32 - shift));
}

function bytesToBase64Url(bytes: Uint8Array): string {
  let binary = "";
  for (const byte of bytes) {
    binary += String.fromCharCode(byte);
  }
  return window.btoa(binary)
    .replace(/\+/g, "-")
    .replace(/\//g, "_")
    .replace(/=+$/g, "");
}
