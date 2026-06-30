import { QueryClient } from "@tanstack/react-query";
import { act, createElement } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { writeAuthToken } from "../src/auth";
import { useUiInvalidationSocket } from "../src/hooks/useUiInvalidationSocket";
import {
  applyUiInvalidation,
  createUiInvalidationScheduler,
  markWindowActivityStale,
  nextUiEventReconnectDelay,
  parseUiEvent,
  reserveWindowActivityRefresh,
  queryKeysForUiInvalidation,
  scheduleWindowActivityRefresh
} from "../src/uiEvents";

globalThis.IS_REACT_ACT_ENVIRONMENT = true;

const invalidateEvent = {
  type: "invalidate" as const,
  seq: 42,
  resources: [
    "window",
    "tree",
    "terminal_notifications",
    "agent_record",
    "command_history",
    "title_history",
    "git_runs",
    "terminal_artifacts",
    "artifact_plugin_previews",
    "project_todos",
    "artifact_plugins"
  ],
  client_id: "client-1",
  window_id: "window-1",
  reason: "window_updated"
};

let root: Root | null = null;
let container: HTMLDivElement | null = null;
let queryClient: QueryClient | null = null;
let websocketUrls: string[] = [];
let websocketProtocols: string[][] = [];

class MockWebSocket {
  onclose: (() => void) | null = null;
  onerror: (() => void) | null = null;
  onmessage: ((message: MessageEvent) => void) | null = null;

  constructor(url: string, protocols?: string | string[]) {
    websocketUrls.push(url);
    websocketProtocols.push(
      Array.isArray(protocols) ? protocols : protocols === undefined ? [] : [protocols]
    );
  }

  close() {}
}

function UiInvalidationSocketProbe({
  authEnabled,
  client,
}: {
  authEnabled: boolean;
  client: QueryClient;
}) {
  useUiInvalidationSocket(client, authEnabled);
  return null;
}

function renderUiInvalidationSocket(authEnabled: boolean): void {
  container = document.createElement("div");
  document.body.appendChild(container);
  queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  });
  root = createRoot(container);
  act(() => {
    root?.render(createElement(UiInvalidationSocketProbe, {
      authEnabled,
      client: queryClient as QueryClient,
    }));
  });
}

beforeEach(() => {
  websocketUrls = [];
  websocketProtocols = [];
  vi.stubGlobal("WebSocket", MockWebSocket);
});

afterEach(() => {
  act(() => {
    root?.unmount();
  });
  document.body.replaceChildren();
  queryClient?.clear();
  root = null;
  container = null;
  queryClient = null;
  window.localStorage.clear();
  vi.useRealTimers();
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

describe("useUiInvalidationSocket", () => {
  it("does not open ui-events websocket while auth is required and no token exists", () => {
    renderUiInvalidationSocket(true);

    expect(websocketUrls).toEqual([]);
  });

  it("opens ui-events websocket after an auth token is written", () => {
    renderUiInvalidationSocket(true);

    act(() => {
      writeAuthToken("token-1");
    });

    expect(websocketUrls).toHaveLength(1);
    const url = new URL(websocketUrls[0]);
    expect(url.pathname).toBe("/api/ui-events");
    expect(url.searchParams.get("auth_token")).toBeNull();
    expect(websocketProtocols[0]).toEqual(["web-terminal-auth.token-1"]);
  });

  it("opens ui-events websocket without a token when auth is disabled", () => {
    renderUiInvalidationSocket(false);

    expect(websocketUrls).toHaveLength(1);
    const url = new URL(websocketUrls[0]);
    expect(url.pathname).toBe("/api/ui-events");
    expect(url.searchParams.get("auth_token")).toBeNull();
  });

  it("ignores unrelated storage writes when auth is enabled", () => {
    renderUiInvalidationSocket(true);

    act(() => {
      writeAuthToken("token-1");
    });
    expect(websocketUrls).toHaveLength(1);

    act(() => {
      window.dispatchEvent(new StorageEvent("storage", {
        key: "web-terminal-acp:terminal-time-range",
        newValue: "7d",
        oldValue: "all",
        storageArea: window.localStorage
      }));
    });

    expect(websocketUrls).toHaveLength(1);
  });

  it("reconnects on auth token storage changes", () => {
    renderUiInvalidationSocket(true);

    act(() => {
      window.localStorage.setItem("web-terminal-acp:auth-token", "token-1");
      window.dispatchEvent(new StorageEvent("storage", {
        key: "web-terminal-acp:auth-token",
        newValue: "token-1",
        oldValue: null,
        storageArea: window.localStorage
      }));
    });

    expect(websocketUrls).toHaveLength(1);
    expect(new URL(websocketUrls[0]).searchParams.get("auth_token")).toBeNull();
    expect(websocketProtocols[0]).toEqual(["web-terminal-auth.token-1"]);
  });
});

describe("parseUiEvent", () => {
  it("parses backend invalidation payloads", () => {
    expect(parseUiEvent(JSON.stringify(invalidateEvent))).toEqual(invalidateEvent);
  });

  it("ignores malformed payloads", () => {
    expect(parseUiEvent("{")).toBeNull();
    expect(parseUiEvent(JSON.stringify({ type: "invalidate", resources: [1] }))).toBeNull();
  });
});

describe("queryKeysForUiInvalidation", () => {
  it("maps backend resources to the queries that drive terminal notifications", () => {
    expect(queryKeysForUiInvalidation(invalidateEvent)).toEqual([
      ["artifact-plugins"],
      ["tree", "client-1"],
      ["terminal-projects", "client-1"],
      ["projects", "client-1"],
      ["terminal-notifications", "client-1"],
      ["project-todos", "client-1"],
      ["window-activity", "client-1"],
      ["window", "client-1", "window-1"],
      ["command-history", "client-1", "window-1"],
      ["title-history", "client-1", "window-1"],
      ["agent-record", "chat", "client-1", "window-1"],
      ["agent-record", "detail", "client-1", "window-1"],
      ["git-runs", "client-1", "window-1"],
      ["terminal-artifacts", "client-1", "window-1"],
      ["artifact-plugin-previews", "client-1", "window-1"]
    ]);
  });

  it("does not immediately refetch detail or activity queries for activity-only window events", () => {
    expect(queryKeysForUiInvalidation({
      ...invalidateEvent,
      resources: ["window"],
      reason: "terminal_output"
    })).toEqual([]);
  });

  it("keeps activity-only tree events from refreshing heavy project lists", () => {
    expect(queryKeysForUiInvalidation({
      ...invalidateEvent,
      resources: ["window", "tree", "git_runs"],
      reason: "git_worktree"
    })).toEqual([
      ["git-runs", "client-1", "window-1"]
    ]);
  });

  it("maps ui settings invalidations to custom quick keys and app preferences", () => {
    expect(queryKeysForUiInvalidation({
      ...invalidateEvent,
      resources: ["ui_settings"],
      client_id: null,
      window_id: null,
    })).toEqual([
      ["custom-quick-keys"],
      ["app-preferences"],
    ]);
  });
});

describe("applyUiInvalidation", () => {
  it("invalidates every mapped query key", () => {
    const queryClient = {
      invalidateQueries: vi.fn()
    };

    applyUiInvalidation(queryClient as never, {
      ...invalidateEvent,
      resources: ["clients", "window"],
      window_id: null
    });

    expect(queryClient.invalidateQueries).toHaveBeenCalledWith({ queryKey: ["clients"], exact: true });
    expect(queryClient.invalidateQueries).toHaveBeenCalledWith({
      queryKey: ["window-activity", "client-1"],
      exact: false
    });
    expect(queryClient.invalidateQueries).toHaveBeenCalledTimes(2);
  });

  it("invalidates project todo queries by client prefix", () => {
    const queryClient = {
      invalidateQueries: vi.fn()
    };

    applyUiInvalidation(queryClient as never, {
      ...invalidateEvent,
      resources: ["project_todos"],
      window_id: null
    });

    expect(queryClient.invalidateQueries).toHaveBeenCalledWith({
      queryKey: ["project-todos", "client-1"],
      exact: false
    });
  });

  it("invalidates terminal recent queries by prefix", () => {
    const queryClient = {
      invalidateQueries: vi.fn()
    };

    applyUiInvalidation(queryClient as never, {
      ...invalidateEvent,
      resources: ["terminal_recents"],
      window_id: null
    });

    expect(queryClient.invalidateQueries).toHaveBeenCalledWith({
      queryKey: ["terminal-recents"],
      exact: false
    });
  });

  it("invalidates artifact plugin preview queries by window prefix", () => {
    const queryClient = {
      invalidateQueries: vi.fn()
    };

    applyUiInvalidation(queryClient as never, {
      ...invalidateEvent,
      resources: ["artifact_plugin_previews"]
    });

    expect(queryClient.invalidateQueries).toHaveBeenCalledWith({
      queryKey: ["artifact-plugin-previews", "client-1", "window-1"],
      exact: false
    });
  });

  it("invalidates agent record queries by window prefix", () => {
    const queryClient = {
      invalidateQueries: vi.fn()
    };

    applyUiInvalidation(queryClient as never, {
      ...invalidateEvent,
      resources: ["agent_record"]
    });

    expect(queryClient.invalidateQueries).toHaveBeenCalledWith({
      queryKey: ["agent-record", "chat", "client-1", "window-1"],
      exact: false
    });
    expect(queryClient.invalidateQueries).toHaveBeenCalledWith({
      queryKey: ["agent-record", "detail", "client-1", "window-1"],
      exact: false
    });
  });

  it("keeps activity-only invalidations from refetching window detail immediately", () => {
    const queryClient = {
      invalidateQueries: vi.fn()
    };

    applyUiInvalidation(queryClient as never, {
      ...invalidateEvent,
      resources: ["window"],
      reason: "ai_event"
    });

    expect(queryClient.invalidateQueries).not.toHaveBeenCalled();
  });
});

describe("markWindowActivityStale", () => {
  it("marks active activity queries stale without immediately refetching them", () => {
    const queryClient = {
      invalidateQueries: vi.fn()
    };

    markWindowActivityStale(queryClient as never, invalidateEvent);

    expect(queryClient.invalidateQueries).toHaveBeenCalledWith({
      queryKey: ["window-activity", "client-1"],
      exact: false,
      refetchType: "none"
    });
  });
});

describe("scheduleWindowActivityRefresh", () => {
  it("refetches active activity queries after stale-cache refresh has time to complete", () => {
    vi.useFakeTimers();
    const queryClient = {
      refetchQueries: vi.fn()
    };
    const onComplete = vi.fn();

    const timer = scheduleWindowActivityRefresh(queryClient as never, invalidateEvent, onComplete);

    expect(timer).not.toBeNull();
    expect(queryClient.refetchQueries).not.toHaveBeenCalled();
    vi.advanceTimersByTime(1200);
    expect(queryClient.refetchQueries).toHaveBeenCalledWith({
      queryKey: ["window-activity", "client-1"],
      exact: false,
      type: "active"
    });
    expect(onComplete).toHaveBeenCalledWith(timer);
    vi.useRealTimers();
  });
});

describe("createUiInvalidationScheduler", () => {
  it("coalesces heavy invalidations before refetching active queries", () => {
    vi.useFakeTimers();
    const queryClient = {
      invalidateQueries: vi.fn(),
      refetchQueries: vi.fn()
    };
    const scheduler = createUiInvalidationScheduler(queryClient as never, 350);

    scheduler.schedule({
      ...invalidateEvent,
      resources: ["tree"],
      window_id: null
    });
    scheduler.schedule({
      ...invalidateEvent,
      resources: ["tree"],
      window_id: null,
      seq: 43
    });

    expect(queryClient.refetchQueries).not.toHaveBeenCalled();
    vi.advanceTimersByTime(350);
    expect(queryClient.refetchQueries).toHaveBeenCalledTimes(3);
    expect(queryClient.refetchQueries).toHaveBeenCalledWith({
      queryKey: ["tree", "client-1"],
      exact: false,
      type: "active"
    });
    expect(queryClient.refetchQueries).toHaveBeenCalledWith({
      queryKey: ["terminal-projects", "client-1"],
      exact: false,
      type: "active"
    });
    expect(queryClient.refetchQueries).toHaveBeenCalledWith({
      queryKey: ["projects", "client-1"],
      exact: false,
      type: "active"
    });

    scheduler.dispose();
    vi.useRealTimers();
  });

  it("limits activity-only events to window activity refreshes and local query keys", () => {
    vi.useFakeTimers();
    const queryClient = {
      invalidateQueries: vi.fn(),
      refetchQueries: vi.fn()
    };
    const scheduler = createUiInvalidationScheduler(queryClient as never, 350);

    scheduler.schedule({
      ...invalidateEvent,
      resources: ["window", "tree", "git_runs"],
      reason: "git_worktree"
    });

    expect(queryClient.invalidateQueries).toHaveBeenCalledWith({
      queryKey: ["window-activity", "client-1"],
      exact: false,
      refetchType: "none"
    });
    expect(queryClient.invalidateQueries).toHaveBeenCalledWith({
      queryKey: ["git-runs", "client-1", "window-1"],
      exact: true,
      refetchType: "none"
    });
    expect(queryClient.invalidateQueries).not.toHaveBeenCalledWith({
      queryKey: ["tree", "client-1"],
      exact: false,
      refetchType: "none"
    });

    vi.advanceTimersByTime(350);
    expect(queryClient.refetchQueries).toHaveBeenCalledWith({
      queryKey: ["git-runs", "client-1", "window-1"],
      exact: true,
      type: "active"
    });
    vi.advanceTimersByTime(1200);
    expect(queryClient.refetchQueries).toHaveBeenCalledWith({
      queryKey: ["window-activity", "client-1"],
      exact: false,
      type: "active"
    });

    scheduler.dispose();
    vi.useRealTimers();
  });
});

describe("reserveWindowActivityRefresh", () => {
  it("rate limits high-frequency activity invalidations by client", () => {
    const lastRefreshAtByClient = new Map<string, number>();

    expect(reserveWindowActivityRefresh(invalidateEvent, lastRefreshAtByClient, 10_000)).toBe(true);
    expect(reserveWindowActivityRefresh(invalidateEvent, lastRefreshAtByClient, 11_000)).toBe(false);
    expect(reserveWindowActivityRefresh(invalidateEvent, lastRefreshAtByClient, 13_000)).toBe(true);
  });

  it("ignores events that cannot affect window activity", () => {
    const lastRefreshAtByClient = new Map<string, number>();

    expect(reserveWindowActivityRefresh({
      ...invalidateEvent,
      resources: ["clients"],
    }, lastRefreshAtByClient, 10_000)).toBe(false);
    expect(lastRefreshAtByClient.size).toBe(0);
  });
});

describe("nextUiEventReconnectDelay", () => {
  it("uses capped exponential backoff", () => {
    expect(nextUiEventReconnectDelay(1)).toBe(500);
    expect(nextUiEventReconnectDelay(2)).toBe(1000);
    expect(nextUiEventReconnectDelay(10)).toBe(10000);
  });
});
