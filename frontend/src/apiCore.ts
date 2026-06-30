import { readApiBase } from "./apiBase";
import {
  clearAuthToken,
  readAuthRefreshToken,
  readAuthToken,
  writeAuthTokens,
} from "./auth";

export function apiBaseUrl(): URL {
  const base = new URL(readApiBase());
  if (!base.pathname.endsWith("/")) {
    base.pathname = `${base.pathname}/`;
  }
  return base;
}

export function apiUrl(path: string): string {
  return new URL(path.replace(/^\/+/, ""), apiBaseUrl()).toString();
}

export function pathSegment(segment: string): string {
  return encodeURIComponent(segment);
}

export function authHeaders(): Headers {
  const headers = new Headers();
  const authToken = readAuthToken();
  if (authToken !== null) {
    headers.set("Authorization", `Bearer ${authToken}`);
  }
  return headers;
}

export function asWebSocketUrl(path: string, viewId?: string): string {
  const url = new URL(apiUrl(path));
  if (viewId !== undefined) {
    url.searchParams.set("view_id", viewId);
  }
  if (url.protocol === "http:") {
    url.protocol = "ws:";
  } else if (url.protocol === "https:") {
    url.protocol = "wss:";
  }
  return url.toString();
}

export class ApiError extends Error {
  status: number;
  statusText: string;
  detail: unknown;
  body: unknown;

  constructor(status: number, statusText: string, detail: unknown, body: unknown = detail) {
    const detailText = apiErrorDetailText(detail);
    super(detailText ? `${status} ${detailText}` : `${status} ${statusText}`);
    this.name = "ApiError";
    this.status = status;
    this.statusText = statusText;
    this.detail = detail;
    this.body = body;
  }
}

export class ApiNetworkError extends Error {
  cause: unknown;

  constructor(cause: unknown) {
    const message = cause instanceof Error && cause.message.trim().length > 0
      ? cause.message
      : "Network request failed";
    super(message);
    this.name = "ApiNetworkError";
    this.cause = cause;
  }
}

export type ApiFailure = ApiError | ApiNetworkError;

let authRefreshPromise: Promise<string | null> | null = null;

export function isApiFailure(error: unknown): error is ApiFailure {
  return error instanceof ApiError || error instanceof ApiNetworkError;
}

export function apiErrorDetailText(detail: unknown): string | null {
  if (typeof detail === "string") {
    const trimmed = detail.trim();
    return trimmed.length > 0 ? trimmed : null;
  }
  return null;
}

export async function fetchApi(input: RequestInfo | URL, init?: RequestInit): Promise<Response> {
  try {
    const response = await fetch(input, init);
    if (response.status !== 401 || shouldSkipAuthRefresh(input)) {
      return response;
    }
    const authToken = readAuthToken();
    if (authToken === null) {
      return response;
    }
    const refreshToken = readAuthRefreshToken();
    if (refreshToken === null) {
      clearAuthToken();
      return response;
    }
    const refreshedToken = await refreshAccessToken(refreshToken);
    if (refreshedToken === null) {
      return response;
    }
    return await fetch(...retryRequestWithAuth(input, init, refreshedToken));
  } catch (error) {
    throw new ApiNetworkError(error);
  }
}

function shouldSkipAuthRefresh(input: RequestInfo | URL): boolean {
  const path = requestPath(input);
  return path === null || path.startsWith("/api/auth/");
}

function requestPath(input: RequestInfo | URL): string | null {
  const value = input instanceof Request ? input.url : input.toString();
  try {
    return new URL(value, window.location.href).pathname;
  } catch {
    return null;
  }
}

async function refreshAccessToken(refreshToken: string): Promise<string | null> {
  if (authRefreshPromise === null) {
    authRefreshPromise = refreshAccessTokenOnce(refreshToken).finally(() => {
      authRefreshPromise = null;
    });
  }
  return authRefreshPromise;
}

async function refreshAccessTokenOnce(refreshToken: string): Promise<string | null> {
  let response: Response;
  try {
    response = await fetch(apiUrl("/api/auth/refresh"), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh_token: refreshToken })
    });
  } catch {
    return null;
  }
  if (!response.ok) {
    if (response.status >= 400 && response.status < 500) {
      clearAuthToken();
    }
    return null;
  }
  let body: { token?: unknown; refresh_token?: unknown };
  try {
    body = await response.json() as { token?: unknown; refresh_token?: unknown };
  } catch {
    clearAuthToken();
    return null;
  }
  if (typeof body.token !== "string" || body.token.trim() === "") {
    clearAuthToken();
    return null;
  }
  const nextRefreshToken = typeof body.refresh_token === "string" && body.refresh_token.trim() !== ""
    ? body.refresh_token
    : refreshToken;
  writeAuthTokens(body.token, nextRefreshToken);
  return body.token;
}

function retryRequestWithAuth(
  input: RequestInfo | URL,
  init: RequestInit | undefined,
  token: string,
): [RequestInfo | URL, RequestInit | undefined] {
  const headers = new Headers(init?.headers ?? (input instanceof Request ? input.headers : undefined));
  headers.set("Authorization", `Bearer ${token}`);
  if (input instanceof Request && init === undefined) {
    return [new Request(input, { headers }), undefined];
  }
  return [input, { ...init, headers }];
}

export async function apiErrorFromResponse(response: Response): Promise<ApiError> {
  let detail: unknown = null;
  let body: unknown = null;
  try {
    body = await response.json();
    detail = typeof body === "object" && body !== null && "detail" in body
      ? (body as { detail?: unknown }).detail ?? null
      : null;
  } catch {
    detail = null;
  }
  return new ApiError(response.status, response.statusText, detail, body);
}

export async function throwApiError(response: Response): Promise<never> {
  throw await apiErrorFromResponse(response);
}

export async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const headers = new Headers(init?.headers);
  if (init?.body !== undefined && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  const authToken = readAuthToken();
  if (authToken !== null && !headers.has("Authorization")) {
    headers.set("Authorization", `Bearer ${authToken}`);
  }
  const response = await fetchApi(apiUrl(path), {
    ...init,
    headers
  });
  if (!response.ok) {
    await throwApiError(response);
  }
  return response.json() as Promise<T>;
}

export async function requestVoid(path: string, init: RequestInit): Promise<void> {
  const response = await fetchApi(apiUrl(path), {
    ...init,
    headers: init.headers ?? authHeaders()
  });
  if (!response.ok) {
    await throwApiError(response);
  }
}
