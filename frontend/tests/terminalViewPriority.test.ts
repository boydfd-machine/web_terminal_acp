import { describe, expect, it } from "vitest";

import {
  claimActiveTerminalView,
  isTerminalViewLowPriority,
  readActiveTerminalView,
  TERMINAL_ACTIVE_VIEW_STORAGE_KEY,
} from "../src/terminalViewPriority.js";

class MemoryStorage {
  private values = new Map<string, string>();

  getItem(key: string): string | null {
    return this.values.get(key) ?? null;
  }

  setItem(key: string, value: string): void {
    this.values.set(key, value);
  }

  removeItem(key: string): void {
    this.values.delete(key);
  }
}

describe("terminal view priority", () => {
  it("keeps the claimed terminal view high priority", () => {
    const storage = new MemoryStorage();
    claimActiveTerminalView(
      { viewId: "view-a", clientId: "client-a", windowId: "window-a" },
      storage,
      1000,
    );

    const activeView = readActiveTerminalView(storage, 1001);
    expect(activeView?.viewId).toBe("view-a");
    expect(isTerminalViewLowPriority("view-a", storage, 1001)).toBe(false);
    expect(isTerminalViewLowPriority("view-b", storage, 1001)).toBe(true);
  });

  it("removes expired claims instead of throttling other views", () => {
    const storage = new MemoryStorage();
    storage.setItem(TERMINAL_ACTIVE_VIEW_STORAGE_KEY, JSON.stringify({
      viewId: "old-view",
      clientId: "client-a",
      windowId: "window-a",
      claimedAt: 1000,
    }));

    expect(readActiveTerminalView(storage, 2000, 500)).toBeNull();
    expect(isTerminalViewLowPriority("new-view", storage, 2000, 500)).toBe(false);
    expect(storage.getItem(TERMINAL_ACTIVE_VIEW_STORAGE_KEY)).toBeNull();
  });
});
