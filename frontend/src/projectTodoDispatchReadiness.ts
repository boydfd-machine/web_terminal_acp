import { fetchWindow } from "./api";
import {
  terminalRuntimeReadiness,
  waitForTerminalRuntime,
} from "./terminalCreateReadiness";
import type { VirtualWindow } from "./types";

const DEFAULT_PROJECT_TODO_DISPATCH_POLL_MS = 500;
const DEFAULT_PROJECT_TODO_DISPATCH_TIMEOUT_MS = 65000;

type WaitForProjectTodoDispatchWindowOptions = {
  pollMs?: number;
  timeoutMs?: number;
  sleep?: (ms: number) => Promise<void>;
  now?: () => number;
  fetchLatestWindow?: (clientId: string, windowId: string) => Promise<VirtualWindow>;
};

function delay(ms: number): Promise<void> {
  return new Promise((resolve) => {
    globalThis.setTimeout(resolve, ms);
  });
}

export async function waitForProjectTodoDispatchWindow(
  clientId: string,
  windowId: string,
  options: WaitForProjectTodoDispatchWindowOptions = {}
): Promise<VirtualWindow> {
  const pollMs = options.pollMs ?? DEFAULT_PROJECT_TODO_DISPATCH_POLL_MS;
  const timeoutMs = options.timeoutMs ?? DEFAULT_PROJECT_TODO_DISPATCH_TIMEOUT_MS;
  const sleep = options.sleep ?? delay;
  const now = options.now ?? (() => Date.now());
  const fetchLatestWindow = options.fetchLatestWindow ?? fetchWindow;
  const deadline = now() + timeoutMs;
  let lastError: unknown = null;

  while (now() < deadline) {
    try {
      const window = await fetchLatestWindow(clientId, windowId);
      if (terminalRuntimeReadiness(window) !== "pending") {
        return window;
      }
      return await waitForTerminalRuntime(window, fetchLatestWindow, {
        pollMs,
        timeoutMs: Math.max(0, deadline - now()),
        sleep,
        now,
      });
    } catch (error) {
      lastError = error;
      await sleep(pollMs);
    }
  }

  throw lastError instanceof Error
    ? lastError
    : new Error("Timed out waiting for dispatched terminal");
}
