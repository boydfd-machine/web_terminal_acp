import type { TerminalConnectionStatus } from "./components/TerminalPane";
import type { TranslateFn } from "./i18n";
import type { Client } from "./types";

export type TerminalViewportMode = "desktop" | "phone" | "fixed";
export type WorkspaceMode = "terminal" | "files" | "kanban";
export type DetailContext = "terminal" | "project";
export type ProjectTodoFocusRequest = {
  clientId: string;
  projectPath: string;
  todoId: string;
  nonce: number;
};
export type ProjectTodoCreationPendingRequest = {
  clientId: string;
  projectPath: string;
  title: string;
  nonce: number;
};
export type TerminalRecoveryIntent = {
  clientId: string;
  windowId: string;
  nonce: number;
};

export type TerminalRouteSelection = {
  clientId: string | null;
  windowId: string | null;
};

export type ClientWindowSelection = {
  windowId: string | null;
  usedAt: number;
};

export type ClientWindowSelections = Record<string, ClientWindowSelection>;

export const TERMINAL_VIEWPORT_STORAGE_KEY = "web-terminal-acp:terminal-viewport-mode";
export const WORKSPACE_MODE_STORAGE_KEY = "web-terminal-acp:workspace-mode";
export const CLIENT_WINDOW_SELECTION_STORAGE_KEY = "web-terminal-acp:client-window-selections";
export const CLIENT_RECENCY_STORAGE_KEY = "web-terminal-acp:client-recency";

export function terminalStatusLabel(status: TerminalConnectionStatus, t?: TranslateFn): string {
  switch (status) {
    case "connected":
      return t?.("terminal.status.connected") ?? "Terminal connected";
    case "connecting":
      return t?.("terminal.status.connecting") ?? "Terminal connecting...";
    case "reconnecting":
      return t?.("terminal.status.reconnecting") ?? "Terminal reconnecting...";
    case "unavailable":
      return t?.("terminal.status.unavailable") ?? "Client offline";
    case "error":
      return t?.("terminal.status.error") ?? "Terminal error";
  }
}

export function isTerminalViewportMode(value: string | null): value is TerminalViewportMode {
  return value === "desktop" || value === "phone" || value === "fixed";
}

export function readTerminalViewportMode(): TerminalViewportMode {
  if (typeof window === "undefined") {
    return "desktop";
  }

  const storedMode = window.localStorage.getItem(TERMINAL_VIEWPORT_STORAGE_KEY);
  return isTerminalViewportMode(storedMode) ? storedMode : "desktop";
}

export function readWorkspaceMode(): WorkspaceMode {
  if (typeof window === "undefined") {
    return "terminal";
  }

  const routeMode = workspaceModeFromUrl(`${window.location.pathname}${window.location.search}${window.location.hash}`);
  if (routeMode !== null) {
    return routeMode;
  }

  const storedMode = window.localStorage.getItem(WORKSPACE_MODE_STORAGE_KEY);
  return storedMode === "files" || storedMode === "kanban" ? storedMode : "terminal";
}

export function workspaceModeFromUrl(value: string, base?: string): WorkspaceMode | null {
  const fallbackBase = typeof window === "undefined" ? "http://localhost/" : window.location.href;
  let url: URL;
  try {
    url = new URL(value, base ?? fallbackBase);
  } catch {
    return null;
  }

  if (/^\/clients\/[^/]+\/files\/?$/.test(url.pathname)) {
    return "files";
  }
  if (/^\/clients\/[^/]+\/kanban\/?$/.test(url.pathname)) {
    return "kanban";
  }

  const view = url.searchParams.get("view");
  return view === "files" || view === "kanban" ? view : null;
}

export function readTerminalRouteSelection(): TerminalRouteSelection {
  if (typeof window === "undefined") {
    return { clientId: null, windowId: null };
  }

  return terminalRouteSelectionFromUrl(`${window.location.pathname}${window.location.search}${window.location.hash}`);
}

export function terminalRouteSelectionFromPath(pathname: string): TerminalRouteSelection {
  const clientTerminalMatch = pathname.match(/^\/clients\/([^/]+)\/terminals\/([^/]+)\/?$/);
  if (clientTerminalMatch) {
    return {
      clientId: decodeURIComponent(clientTerminalMatch[1]),
      windowId: decodeURIComponent(clientTerminalMatch[2])
    };
  }

  const clientMatch = pathname.match(/^\/clients\/([^/]+)\/?$/);
  if (clientMatch) {
    return {
      clientId: decodeURIComponent(clientMatch[1]),
      windowId: null
    };
  }

  return { clientId: null, windowId: null };
}

export function terminalRouteSelectionFromUrl(value: string, base?: string): TerminalRouteSelection {
  const fallbackBase = typeof window === "undefined" ? "http://localhost/" : window.location.href;
  let url: URL;
  try {
    url = new URL(value, base ?? fallbackBase);
  } catch {
    return { clientId: null, windowId: null };
  }
  if (url.searchParams.has("view")) {
    return { clientId: null, windowId: null };
  }
  return terminalRouteSelectionFromPath(url.pathname);
}

export function terminalRoutePath(clientId: string | null, windowId: string | null): string {
  if (clientId === null) {
    return "/";
  }

  const encodedClientId = encodeURIComponent(clientId);
  if (windowId === null) {
    return `/clients/${encodedClientId}`;
  }

  return `/clients/${encodedClientId}/terminals/${encodeURIComponent(windowId)}`;
}

export function writeTerminalRoute(clientId: string | null, windowId: string | null, mode: "push" | "replace") {
  if (typeof window === "undefined") {
    return;
  }

  const nextPath = terminalRoutePath(clientId, windowId);
  if (`${window.location.pathname}${window.location.search}${window.location.hash}` === nextPath) {
    return;
  }

  const method = mode === "push" ? "pushState" : "replaceState";
  window.history[method]({ clientId, windowId }, "", nextPath);
}

export function readJsonObjectStorage(key: string): Record<string, unknown> {
  if (typeof window === "undefined") {
    return {};
  }

  try {
    const parsed = JSON.parse(window.localStorage.getItem(key) ?? "{}");
    return parsed && typeof parsed === "object" && !Array.isArray(parsed)
      ? parsed as Record<string, unknown>
      : {};
  } catch {
    return {};
  }
}

export function readClientWindowSelections(): ClientWindowSelections {
  const parsed = readJsonObjectStorage(CLIENT_WINDOW_SELECTION_STORAGE_KEY);
  const selections: ClientWindowSelections = {};
  for (const [clientId, value] of Object.entries(parsed)) {
    if (!value || typeof value !== "object" || Array.isArray(value)) {
      continue;
    }
    const record = value as Record<string, unknown>;
    selections[clientId] = {
      windowId: typeof record.windowId === "string" ? record.windowId : null,
      usedAt: typeof record.usedAt === "number" && Number.isFinite(record.usedAt) ? record.usedAt : 0
    };
  }
  return selections;
}

export function writeClientWindowSelections(selections: ClientWindowSelections): void {
  if (typeof window === "undefined") {
    return;
  }

  window.localStorage.setItem(CLIENT_WINDOW_SELECTION_STORAGE_KEY, JSON.stringify(selections));
}

export function readClientRecency(): string[] {
  if (typeof window === "undefined") {
    return [];
  }

  try {
    const parsed = JSON.parse(window.localStorage.getItem(CLIENT_RECENCY_STORAGE_KEY) ?? "[]");
    return Array.isArray(parsed) ? parsed.filter((value): value is string => typeof value === "string") : [];
  } catch {
    return [];
  }
}

export function writeClientRecency(clientIds: string[]): void {
  if (typeof window === "undefined") {
    return;
  }

  window.localStorage.setItem(CLIENT_RECENCY_STORAGE_KEY, JSON.stringify(clientIds));
}

export function rememberClientRecency(clientIds: string[], clientId: string): string[] {
  return [clientId, ...clientIds.filter((candidate) => candidate !== clientId)].slice(0, 100);
}

export function isRemoteClientOffline(client: Client | null | undefined): boolean {
  if (client === null || client === undefined) {
    return false;
  }

  return client.runtime === "remote" && client.status !== "ONLINE";
}
