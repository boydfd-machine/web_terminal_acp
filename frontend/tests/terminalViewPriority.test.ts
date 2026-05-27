declare const process: { exitCode?: number };

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

function assert(condition: unknown, message: string): void {
  if (!condition) {
    throw new Error(message);
  }
}

async function testClaimedViewBecomesOnlyActiveView(): Promise<void> {
  const storage = new MemoryStorage();
  claimActiveTerminalView(
    { viewId: "view-a", clientId: "client-a", windowId: "window-a" },
    storage,
    1000,
  );

  const activeView = readActiveTerminalView(storage, 1001);
  assert(activeView?.viewId === "view-a", "claimed view should be readable");
  assert(isTerminalViewLowPriority("view-a", storage, 1001) === false, "claimed view should stay high priority");
  assert(isTerminalViewLowPriority("view-b", storage, 1001) === true, "other views should become low priority");
}

async function testExpiredClaimDoesNotThrottleOtherViews(): Promise<void> {
  const storage = new MemoryStorage();
  storage.setItem(TERMINAL_ACTIVE_VIEW_STORAGE_KEY, JSON.stringify({
    viewId: "old-view",
    clientId: "client-a",
    windowId: "window-a",
    claimedAt: 1000,
  }));

  assert(readActiveTerminalView(storage, 2000, 500) === null, "expired active view should be ignored");
  assert(isTerminalViewLowPriority("new-view", storage, 2000, 500) === false, "expired claims should not throttle views");
  assert(storage.getItem(TERMINAL_ACTIVE_VIEW_STORAGE_KEY) === null, "expired claims should be removed");
}

async function run(): Promise<void> {
  await testClaimedViewBecomesOnlyActiveView();
  await testExpiredClaimDoesNotThrottleOtherViews();
}

run().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
