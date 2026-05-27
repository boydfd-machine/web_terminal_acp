export type TerminalViewPriorityStorage = Pick<Storage, "getItem" | "setItem" | "removeItem">;

export type TerminalViewLease = {
  viewId: string;
  clientId: string;
  windowId: string;
  claimedAt: number;
};

export const TERMINAL_ACTIVE_VIEW_STORAGE_KEY = "web-terminal-acp:active-terminal-view";
export const TERMINAL_VIEW_PRIORITY_CHANGED_EVENT = "web-terminal-acp:terminal-view-priority-changed";
export const TERMINAL_ACTIVE_VIEW_TTL_MS = 5 * 60 * 1000;

function localStorageOrNull(): Storage | null {
  if (typeof window === "undefined") {
    return null;
  }

  try {
    return window.localStorage;
  } catch {
    return null;
  }
}

function isTerminalViewLease(value: unknown): value is TerminalViewLease {
  if (typeof value !== "object" || value === null) {
    return false;
  }

  const candidate = value as Partial<TerminalViewLease>;
  return typeof candidate.viewId === "string"
    && candidate.viewId.length > 0
    && typeof candidate.clientId === "string"
    && candidate.clientId.length > 0
    && typeof candidate.windowId === "string"
    && candidate.windowId.length > 0
    && typeof candidate.claimedAt === "number"
    && Number.isFinite(candidate.claimedAt);
}

export function readActiveTerminalView(
  storage: TerminalViewPriorityStorage | null = localStorageOrNull(),
  now = Date.now(),
  ttlMs = TERMINAL_ACTIVE_VIEW_TTL_MS,
): TerminalViewLease | null {
  if (storage === null) {
    return null;
  }

  let raw: string | null = null;
  try {
    raw = storage.getItem(TERMINAL_ACTIVE_VIEW_STORAGE_KEY);
  } catch {
    return null;
  }
  if (raw === null) {
    return null;
  }

  let parsed: unknown;
  try {
    parsed = JSON.parse(raw);
  } catch {
    try {
      storage.removeItem(TERMINAL_ACTIVE_VIEW_STORAGE_KEY);
    } catch {
      return null;
    }
    return null;
  }

  if (!isTerminalViewLease(parsed) || now - parsed.claimedAt > ttlMs) {
    try {
      storage.removeItem(TERMINAL_ACTIVE_VIEW_STORAGE_KEY);
    } catch {
      return null;
    }
    return null;
  }

  return parsed;
}

export function isTerminalViewLowPriority(
  viewId: string,
  storage: TerminalViewPriorityStorage | null = localStorageOrNull(),
  now = Date.now(),
  ttlMs = TERMINAL_ACTIVE_VIEW_TTL_MS,
): boolean {
  const activeView = readActiveTerminalView(storage, now, ttlMs);
  return activeView !== null && activeView.viewId !== viewId;
}

export function claimActiveTerminalView(
  lease: Omit<TerminalViewLease, "claimedAt">,
  storage: TerminalViewPriorityStorage | null = localStorageOrNull(),
  now = Date.now(),
): void {
  if (storage === null) {
    return;
  }

  const nextLease: TerminalViewLease = { ...lease, claimedAt: now };
  try {
    storage.setItem(TERMINAL_ACTIVE_VIEW_STORAGE_KEY, JSON.stringify(nextLease));
  } catch {
    return;
  }

  if (typeof window !== "undefined") {
    window.dispatchEvent(new Event(TERMINAL_VIEW_PRIORITY_CHANGED_EVENT));
  }
}
