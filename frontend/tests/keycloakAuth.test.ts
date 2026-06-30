import { afterEach, describe, expect, it, vi } from "vitest";

import {
  AUTH_REFRESH_TOKEN_STORAGE_KEY,
  AUTH_TOKEN_STORAGE_KEY,
  buildKeycloakLoginUrl,
  consumeKeycloakRedirect,
} from "../src/auth";

afterEach(() => {
  window.localStorage.clear();
  window.sessionStorage.clear();
  vi.restoreAllMocks();
});

describe("Keycloak auth", () => {
  it("builds a public-client PKCE authorization URL", async () => {
    vi.spyOn(window.crypto, "getRandomValues").mockImplementation((array) => {
      const bytes = array as Uint8Array;
      bytes.fill(7);
      return array;
    });
    window.history.replaceState(null, "", "/clients/client-1");

    const loginUrl = await buildKeycloakLoginUrl({
      authorization_endpoint: "https://auth.example.com/realms/home/protocol/openid-connect/auth",
      client_id: "web-terminal",
    });

    const url = new URL(loginUrl);
    expect(url.origin).toBe("https://auth.example.com");
    expect(url.searchParams.get("client_id")).toBe("web-terminal");
    expect(url.searchParams.get("response_type")).toBe("code");
    expect(url.searchParams.get("code_challenge_method")).toBe("S256");
    expect(url.searchParams.get("code_challenge")).toMatch(/^[A-Za-z0-9_-]+$/);
    expect(new URL(url.searchParams.get("redirect_uri") ?? "").pathname).toBe("/clients/client-1");
    expect(url.searchParams.has("client_secret")).toBe(false);
    expect(window.sessionStorage.getItem("web-terminal-acp:keycloak-pkce")).toContain(
      "http://localhost:3000/clients/client-1",
    );
  });

  it("builds the PKCE authorization URL when Web Crypto subtle is unavailable", async () => {
    vi.spyOn(window.crypto, "getRandomValues").mockImplementation((array) => {
      const bytes = array as Uint8Array;
      bytes.fill(11);
      return array;
    });
    vi.stubGlobal("crypto", {
      ...window.crypto,
      getRandomValues: window.crypto.getRandomValues.bind(window.crypto),
      subtle: undefined,
    });
    window.history.replaceState(null, "", "/clients/client-1");

    const loginUrl = await buildKeycloakLoginUrl({
      authorization_endpoint: "https://auth.example.com/realms/home/protocol/openid-connect/auth",
      client_id: "web-terminal",
    });

    const url = new URL(loginUrl);
    expect(url.searchParams.get("code_challenge_method")).toBe("S256");
    expect(url.searchParams.get("code_challenge")).toMatch(/^[A-Za-z0-9_-]+$/);
  });

  it("exchanges the authorization code through the backend callback", async () => {
    window.history.replaceState(null, "", "/clients/client-1?code=auth-code&state=state-1");
    window.sessionStorage.setItem(
      "web-terminal-acp:keycloak-pkce",
      JSON.stringify({
        state: "state-1",
        verifier: "verifier-1",
        redirectUri: "http://localhost:3000/clients/client-1",
      }),
    );
    const fetchMock = vi.fn().mockResolvedValue(new Response(
      JSON.stringify({ token: "access-token", refresh_token: "refresh-token" }),
      { status: 200, headers: { "Content-Type": "application/json" } },
    ));
    vi.stubGlobal("fetch", fetchMock);

    const token = await consumeKeycloakRedirect(window.location.search);

    expect(token).toBe("access-token");
    expect(window.localStorage.getItem(AUTH_TOKEN_STORAGE_KEY)).toBe("access-token");
    expect(window.localStorage.getItem(AUTH_REFRESH_TOKEN_STORAGE_KEY)).toBe("refresh-token");
    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(new URL(url).pathname).toBe("/api/auth/keycloak/callback");
    expect(url).not.toContain("auth.example.com");
    expect(JSON.parse(String(init.body))).toEqual({
      code: "auth-code",
      redirect_uri: "http://localhost:3000/clients/client-1",
      code_verifier: "verifier-1",
    });
  });
});
