import type { QueryClient, QueryKey } from "@tanstack/react-query";

export type UiInvalidateEvent = {
  type: "invalidate";
  seq: number;
  resources: string[];
  client_id: string | null;
  window_id: string | null;
  reason: string | null;
};

export type UiConnectedEvent = {
  type: "connected";
  seq: number;
};

export type UiTerminalSelectionEvent = {
  type: "terminal_selection";
  seq: number;
  client_id: string;
  window_id: string;
};

export type UiEvent = UiConnectedEvent | UiInvalidateEvent | UiTerminalSelectionEvent;

const UI_EVENT_RECONNECT_BASE_MS = 500;
const UI_EVENT_RECONNECT_MAX_MS = 10000;
const UI_INVALIDATION_COALESCE_MS = 350;
const WINDOW_ACTIVITY_REFRESH_DELAY_MS = 1200;
const WINDOW_ACTIVITY_REFRESH_MIN_INTERVAL_MS = 3000;
const ACTIVITY_ONLY_INVALIDATION_REASONS = new Set([
  "agent_work_presence",
  "ai_event",
  "claude_jsonl_ingested",
  "git_worktree",
  "terminal_command",
  "terminal_output",
  "trace_ingested"
]);

function isStringArray(value: unknown): value is string[] {
  return Array.isArray(value) && value.every((item) => typeof item === "string");
}

export function parseUiEvent(rawValue: string): UiEvent | null {
  try {
    const value: unknown = JSON.parse(rawValue);
    if (!value || typeof value !== "object") {
      return null;
    }

    const candidate = value as Record<string, unknown>;
    const seq = typeof candidate.seq === "number" ? candidate.seq : 0;
    if (candidate.type === "connected") {
      return { type: "connected", seq };
    }
    if (candidate.type === "terminal_selection") {
      if (typeof candidate.client_id !== "string" || typeof candidate.window_id !== "string") {
        return null;
      }
      return {
        type: "terminal_selection",
        seq,
        client_id: candidate.client_id,
        window_id: candidate.window_id
      };
    }
    if (candidate.type !== "invalidate" || !isStringArray(candidate.resources)) {
      return null;
    }
    return {
      type: "invalidate",
      seq,
      resources: candidate.resources,
      client_id: typeof candidate.client_id === "string" ? candidate.client_id : null,
      window_id: typeof candidate.window_id === "string" ? candidate.window_id : null,
      reason: typeof candidate.reason === "string" ? candidate.reason : null
    };
  } catch {
    return null;
  }
}

export function queryKeysForUiInvalidation(event: UiInvalidateEvent): QueryKey[] {
  const keys: QueryKey[] = [];
  const clientId = event.client_id;
  const windowId = event.window_id;
  const resources = new Set(event.resources);
  const activityOnlyWindowInvalidation = isActivityOnlyWindowInvalidation(event);
  const agentRecordWindowUpdate = isAgentRecordWindowUpdate(event);

  if (resources.has("clients")) {
    keys.push(["clients"]);
  }
  if (resources.has("ui_settings")) {
    keys.push(["custom-quick-keys"]);
    keys.push(["app-preferences"]);
  }
  if (resources.has("artifact_plugins")) {
    keys.push(["artifact-plugins"]);
  }
  if (clientId !== null && resources.has("tree") && !activityOnlyWindowInvalidation) {
    keys.push(["tree", clientId]);
    keys.push(["terminal-projects", clientId]);
    keys.push(["projects", clientId]);
  }
  if (clientId !== null && resources.has("terminal_notifications")) {
    keys.push(["terminal-notifications", clientId]);
  }
  if (clientId !== null && resources.has("project_todos")) {
    keys.push(["project-todos", clientId]);
  }
  if (resources.has("terminal_recents")) {
    keys.push(["terminal-recents"]);
  }
  if (clientId !== null && resources.has("project_review_config")) {
    keys.push(["project-review-config", clientId]);
  }
  if (clientId !== null && resources.has("window") && !activityOnlyWindowInvalidation) {
    keys.push(["window-activity", clientId]);
  }
  if (
    clientId !== null
    && windowId !== null
    && resources.has("window")
    && (!activityOnlyWindowInvalidation || agentRecordWindowUpdate)
  ) {
    keys.push(["window", clientId, windowId]);
  }
  if (clientId !== null && windowId !== null && resources.has("command_history")) {
    keys.push(["command-history", clientId, windowId]);
  }
  if (clientId !== null && windowId !== null && resources.has("title_history")) {
    keys.push(["title-history", clientId, windowId]);
  }
  if (clientId !== null && windowId !== null && resources.has("agent_record")) {
    keys.push(["agent-record", "chat", clientId, windowId]);
    keys.push(["agent-record", "detail", clientId, windowId]);
  }
  if (clientId !== null && windowId !== null && resources.has("git_runs")) {
    keys.push(["git-runs", clientId, windowId]);
  }
  if (clientId !== null && windowId !== null && resources.has("terminal_artifacts")) {
    keys.push(["terminal-artifacts", clientId, windowId]);
  }
  if (clientId !== null && windowId !== null && resources.has("artifact_plugin_previews")) {
    keys.push(["artifact-plugin-previews", clientId, windowId]);
  }

  return keys;
}

export function exactForUiInvalidationQueryKey(queryKey: QueryKey): boolean {
  return (
    queryKey.length > 0
    && queryKey[0] !== "tree"
    && queryKey[0] !== "terminal-projects"
    && queryKey[0] !== "projects"
    && queryKey[0] !== "project-todos"
    && queryKey[0] !== "agent-record"
    && queryKey[0] !== "terminal-recents"
    && queryKey[0] !== "project-review-config"
    && queryKey[0] !== "window-activity"
    && queryKey[0] !== "terminal-artifacts"
    && queryKey[0] !== "artifact-plugin-previews"
  );
}

export function applyUiInvalidation(queryClient: QueryClient, event: UiInvalidateEvent): void {
  for (const queryKey of queryKeysForUiInvalidation(event)) {
    void queryClient.invalidateQueries({
      queryKey,
      exact: exactForUiInvalidationQueryKey(queryKey)
    });
  }
}

export function markUiInvalidationStale(queryClient: QueryClient, event: UiInvalidateEvent): void {
  for (const queryKey of queryKeysForUiInvalidation(event)) {
    void queryClient.invalidateQueries({
      queryKey,
      exact: exactForUiInvalidationQueryKey(queryKey),
      refetchType: "none"
    });
  }
}

export function markTerminalListsStale(queryClient: QueryClient, clientId: string): void {
  const queryKeys: QueryKey[] = [
    ["tree", clientId],
    ["terminal-projects", clientId],
    ["projects", clientId],
    ["window-activity", clientId]
  ];
  for (const queryKey of queryKeys) {
    void queryClient.invalidateQueries({ queryKey, exact: false, refetchType: "none" });
  }
}

type CoalescedInvalidation = {
  queryKeys: Map<string, QueryKey>;
  timer: number;
};

export type UiInvalidationScheduler = {
  schedule: (event: UiInvalidateEvent) => void;
  dispose: () => void;
};

export function createUiInvalidationScheduler(
  queryClient: QueryClient,
  coalesceMs = UI_INVALIDATION_COALESCE_MS
): UiInvalidationScheduler {
  const pendingByClient = new Map<string, CoalescedInvalidation>();
  const delayedActivityTimers = new Map<string, number>();
  const lastActivityRefetchAt = new Map<string, number>();

  const clearDelayedActivityTimer = (clientId: string) => {
    const timer = delayedActivityTimers.get(clientId);
    if (timer === undefined) {
      return;
    }
    window.clearTimeout(timer);
    delayedActivityTimers.delete(clientId);
  };

  const scheduleActivityRefresh = (event: UiInvalidateEvent) => {
    if (
      event.client_id === null
      || !event.resources.includes("window")
      || !reserveWindowActivityRefresh(event, lastActivityRefetchAt)
    ) {
      return;
    }
    markWindowActivityStale(queryClient, event);
    clearDelayedActivityTimer(event.client_id);
    const timer = scheduleWindowActivityRefresh(queryClient, event, (completedTimer) => {
      if (event.client_id !== null && delayedActivityTimers.get(event.client_id) === completedTimer) {
        delayedActivityTimers.delete(event.client_id);
      }
    });
    if (timer !== null) {
      delayedActivityTimers.set(event.client_id, timer);
    }
  };

  const flushClientInvalidations = (clientKey: string) => {
    const pending = pendingByClient.get(clientKey);
    if (pending === undefined) {
      return;
    }
    pendingByClient.delete(clientKey);
    for (const queryKey of pending.queryKeys.values()) {
      void queryClient.refetchQueries({
        queryKey,
        exact: exactForUiInvalidationQueryKey(queryKey),
        type: "active"
      });
    }
  };

  const schedule = (event: UiInvalidateEvent) => {
    if (isActivityOnlyWindowInvalidation(event)) {
      scheduleActivityRefresh(event);
    }

    const queryKeys = queryKeysForUiInvalidation(event);
    for (const queryKey of queryKeys) {
      void queryClient.invalidateQueries({
        queryKey,
        exact: exactForUiInvalidationQueryKey(queryKey),
        refetchType: "none"
      });
    }

    if (queryKeys.length === 0) {
      return;
    }
    const clientKey = event.client_id ?? "global";
    const pending = pendingByClient.get(clientKey);
    if (pending !== undefined) {
      for (const queryKey of queryKeys) {
        pending.queryKeys.set(JSON.stringify(queryKey), queryKey);
      }
      return;
    }
    const nextPending: CoalescedInvalidation = {
      queryKeys: new Map(queryKeys.map((queryKey) => [JSON.stringify(queryKey), queryKey])),
      timer: window.setTimeout(() => flushClientInvalidations(clientKey), coalesceMs)
    };
    pendingByClient.set(clientKey, nextPending);
  };

  const dispose = () => {
    for (const pending of pendingByClient.values()) {
      window.clearTimeout(pending.timer);
    }
    pendingByClient.clear();
    for (const timer of delayedActivityTimers.values()) {
      window.clearTimeout(timer);
    }
    delayedActivityTimers.clear();
    lastActivityRefetchAt.clear();
  };

  return { dispose, schedule };
}

export function markWindowActivityStale(queryClient: QueryClient, event: UiInvalidateEvent): void {
  if (event.client_id === null || !event.resources.includes("window")) {
    return;
  }
  void queryClient.invalidateQueries({
    queryKey: ["window-activity", event.client_id],
    exact: false,
    refetchType: "none"
  });
}

export function isActivityOnlyWindowInvalidation(event: UiInvalidateEvent): boolean {
  return (
    event.reason !== null &&
    event.resources.includes("window") &&
    ACTIVITY_ONLY_INVALIDATION_REASONS.has(event.reason)
  );
}

function isAgentRecordWindowUpdate(event: UiInvalidateEvent): boolean {
  return (
    event.reason === "ai_event"
    && event.resources.includes("agent_record")
    && event.resources.includes("window")
  );
}

export function scheduleWindowActivityRefresh(
  queryClient: QueryClient,
  event: UiInvalidateEvent,
  onComplete?: (timer: number) => void
): number | null {
  if (event.client_id === null || !event.resources.includes("window")) {
    return null;
  }

  const timer = window.setTimeout(() => {
    void queryClient.refetchQueries({
      queryKey: ["window-activity", event.client_id],
      exact: false,
      type: "active"
    });
    onComplete?.(timer);
  }, WINDOW_ACTIVITY_REFRESH_DELAY_MS);
  return timer;
}

export function reserveWindowActivityRefresh(
  event: UiInvalidateEvent,
  lastRefreshAtByClient: Map<string, number>,
  nowMs = Date.now()
): boolean {
  if (event.client_id === null || !event.resources.includes("window")) {
    return false;
  }
  const lastRefreshAt = lastRefreshAtByClient.get(event.client_id);
  if (
    lastRefreshAt !== undefined &&
    nowMs - lastRefreshAt < WINDOW_ACTIVITY_REFRESH_MIN_INTERVAL_MS
  ) {
    return false;
  }
  lastRefreshAtByClient.set(event.client_id, nowMs);
  return true;
}

export function nextUiEventReconnectDelay(attempt: number): number {
  const exponentialDelay = UI_EVENT_RECONNECT_BASE_MS * (2 ** Math.max(0, attempt - 1));
  return Math.min(exponentialDelay, UI_EVENT_RECONNECT_MAX_MS);
}
