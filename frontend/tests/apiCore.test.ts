import { afterEach, describe, expect, it, vi } from "vitest";

import { ApiError, ApiNetworkError, fetchApi, request, requestVoid } from "../src/apiCore";
import { AUTH_REFRESH_TOKEN_STORAGE_KEY, AUTH_TOKEN_STORAGE_KEY } from "../src/auth";

afterEach(() => {
  vi.restoreAllMocks();
  window.localStorage.clear();
});

describe("apiCore failures", () => {
  it("throws ApiError with parsed detail for JSON API failures", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(JSON.stringify({ detail: "bad input" }), {
      status: 422,
      statusText: "Unprocessable Entity",
      headers: { "Content-Type": "application/json" }
    }));

    await expect(request("/api/demo")).rejects.toMatchObject({
      name: "ApiError",
      status: 422,
      detail: "bad input",
      message: "422 bad input"
    });
  });

  it("throws ApiError for void API failures", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(JSON.stringify({ detail: "missing" }), {
      status: 404,
      statusText: "Not Found",
      headers: { "Content-Type": "application/json" }
    }));

    await expect(requestVoid("/api/demo", { method: "DELETE" })).rejects.toBeInstanceOf(ApiError);
  });

  it("wraps fetch transport failures as ApiNetworkError", async () => {
    vi.spyOn(globalThis, "fetch").mockRejectedValue(new TypeError("Failed to fetch"));

    await expect(fetchApi("/api/demo")).rejects.toBeInstanceOf(ApiNetworkError);
  });

  it("refreshes an expired access token and retries the protected request once", async () => {
    window.localStorage.setItem(AUTH_TOKEN_STORAGE_KEY, "access-1");
    window.localStorage.setItem(AUTH_REFRESH_TOKEN_STORAGE_KEY, "refresh-1");
    const fetchMock = vi.spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(new Response(JSON.stringify({ detail: "login required" }), {
        status: 401,
        statusText: "Unauthorized",
        headers: { "Content-Type": "application/json" }
      }))
      .mockResolvedValueOnce(new Response(JSON.stringify({
        token: "access-2",
        refresh_token: "refresh-2",
        enabled: true
      }), {
        status: 200,
        headers: { "Content-Type": "application/json" }
      }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ ok: true }), {
        status: 200,
        headers: { "Content-Type": "application/json" }
      }));

    await expect(request("/api/demo")).resolves.toEqual({ ok: true });

    expect(fetchMock).toHaveBeenCalledTimes(3);
    expect(new URL(String(fetchMock.mock.calls[1][0])).pathname).toBe("/api/auth/refresh");
    expect(JSON.parse(String(fetchMock.mock.calls[1][1]?.body))).toEqual({
      refresh_token: "refresh-1"
    });
    expect(new Headers(fetchMock.mock.calls[0][1]?.headers).get("Authorization")).toBe("Bearer access-1");
    expect(new Headers(fetchMock.mock.calls[2][1]?.headers).get("Authorization")).toBe("Bearer access-2");
    expect(window.localStorage.getItem(AUTH_TOKEN_STORAGE_KEY)).toBe("access-2");
    expect(window.localStorage.getItem(AUTH_REFRESH_TOKEN_STORAGE_KEY)).toBe("refresh-2");
  });

  it("clears auth state when refresh token exchange is rejected", async () => {
    window.localStorage.setItem(AUTH_TOKEN_STORAGE_KEY, "access-1");
    window.localStorage.setItem(AUTH_REFRESH_TOKEN_STORAGE_KEY, "refresh-1");
    const authChanged = vi.fn();
    window.addEventListener("web-terminal-auth-changed", authChanged);
    vi.spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(new Response(JSON.stringify({ detail: "login required" }), {
        status: 401,
        statusText: "Unauthorized",
        headers: { "Content-Type": "application/json" }
      }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ detail: "refresh token invalid" }), {
        status: 401,
        statusText: "Unauthorized",
        headers: { "Content-Type": "application/json" }
      }));

    await expect(request("/api/demo")).rejects.toMatchObject({ status: 401 });

    expect(window.localStorage.getItem(AUTH_TOKEN_STORAGE_KEY)).toBeNull();
    expect(window.localStorage.getItem(AUTH_REFRESH_TOKEN_STORAGE_KEY)).toBeNull();
    expect(authChanged).toHaveBeenCalledTimes(1);
    window.removeEventListener("web-terminal-auth-changed", authChanged);
  });
});
