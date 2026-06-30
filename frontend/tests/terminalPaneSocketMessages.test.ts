import { describe, expect, it, vi } from "vitest";

import { createTerminalSocketMessageHandler } from "../src/components/terminalPaneSocketMessages";

function createRef<T>(current: T) {
  return { current };
}

function createWorker() {
  return { postMessage: vi.fn() } as unknown as Worker;
}

describe("terminalPaneSocketMessages", () => {
  it("resets the cached resize on every socket open so reconnects resend dimensions", () => {
    const worker = createWorker();
    const socketWorkerRef = createRef<Worker | null>(worker);
    const socketOpenRef = createRef(false);
    const resetLastSentResize = vi.fn();
    const scheduleFitAndNotifyResize = vi.fn();
    const scheduleFitUntilFilled = vi.fn();

    const handleMessage = createTerminalSocketMessageHandler({
      activeWindowIdRef: createRef("window-a"),
      connectionStatusRef: createRef("connecting"),
      initialWindowId: "window-a",
      outputBuffer: {
        enqueue: vi.fn(),
        enqueueInteractive: vi.fn(() => true),
      },
      selectionEnabled: true,
      terminalSwitchingEnabled: true,
      socketOpenRef,
      socketWorkerRef,
      updateConnectionStatus: vi.fn(),
      viewId: "view-a",
      closeSocketWorker: vi.fn(),
      flushPendingInputs: vi.fn(),
      isActive: () => true,
      onTerminalSelection: vi.fn(),
      scheduleFitAndNotifyResize,
      scheduleFitUntilFilled,
      scheduleReconnect: vi.fn(),
      sendSocketJson: vi.fn(),
      resetLastSentResize,
      resetReconnectAttempt: vi.fn(),
    });

    handleMessage(worker, { data: { type: "open" } } as MessageEvent);
    handleMessage(worker, { data: { type: "open" } } as MessageEvent);

    expect(socketOpenRef.current).toBe(true);
    expect(resetLastSentResize).toHaveBeenCalledTimes(2);
    expect(scheduleFitAndNotifyResize).toHaveBeenCalledTimes(2);
    expect(scheduleFitUntilFilled).toHaveBeenCalledTimes(2);
  });

  it("acks only the bytes for each written output slice", () => {
    const worker = createWorker();
    const socketWorkerRef = createRef<Worker | null>(worker);
    const socketOpenRef = createRef(true);
    const writeCallbacks: Array<(writtenChunk: string | Uint8Array) => void> = [];

    const handleMessage = createTerminalSocketMessageHandler({
      activeWindowIdRef: createRef("window-a"),
      connectionStatusRef: createRef("connected"),
      initialWindowId: "window-a",
      outputBuffer: {
        enqueue: vi.fn((_data, options) => {
          if (options?.onWrite !== undefined) {
            writeCallbacks.push(options.onWrite);
          }
        }),
        enqueueInteractive: vi.fn(() => true),
      },
      selectionEnabled: true,
      terminalSwitchingEnabled: true,
      socketOpenRef,
      socketWorkerRef,
      updateConnectionStatus: vi.fn(),
      viewId: "view-a",
      closeSocketWorker: vi.fn(),
      flushPendingInputs: vi.fn(),
      isActive: () => true,
      onTerminalSelection: vi.fn(),
      scheduleFitAndNotifyResize: vi.fn(),
      scheduleFitUntilFilled: vi.fn(),
      scheduleReconnect: vi.fn(),
      sendSocketJson: vi.fn(),
      resetLastSentResize: vi.fn(),
      resetReconnectAttempt: vi.fn(),
    });

    handleMessage(worker, { data: { type: "output", data: "abcdef" } } as MessageEvent);
    writeCallbacks[0]?.("abcd");
    writeCallbacks[0]?.("ef");

    expect(worker.postMessage).toHaveBeenCalledWith({ type: "server-output-ack", bytes: 4 });
    expect(worker.postMessage).toHaveBeenCalledWith({ type: "server-output-ack", bytes: 2 });
  });

  it("acks interactive output bytes by written slice while releasing worker output once", () => {
    const worker = createWorker();
    const socketWorkerRef = createRef<Worker | null>(worker);
    const socketOpenRef = createRef(true);
    const writeCallbacks: Array<(writtenChunk: string | Uint8Array) => void> = [];

    const handleMessage = createTerminalSocketMessageHandler({
      activeWindowIdRef: createRef("window-a"),
      connectionStatusRef: createRef("connected"),
      initialWindowId: "window-a",
      outputBuffer: {
        enqueue: vi.fn(),
        enqueueInteractive: vi.fn((_data, options) => {
          if (options?.onWrite !== undefined) {
            writeCallbacks.push(options.onWrite);
          }
          return false;
        }),
      },
      selectionEnabled: true,
      terminalSwitchingEnabled: true,
      socketOpenRef,
      socketWorkerRef,
      updateConnectionStatus: vi.fn(),
      viewId: "view-a",
      closeSocketWorker: vi.fn(),
      flushPendingInputs: vi.fn(),
      isActive: () => true,
      onTerminalSelection: vi.fn(),
      scheduleFitAndNotifyResize: vi.fn(),
      scheduleFitUntilFilled: vi.fn(),
      scheduleReconnect: vi.fn(),
      sendSocketJson: vi.fn(),
      resetLastSentResize: vi.fn(),
      resetReconnectAttempt: vi.fn(),
    });

    handleMessage(worker, { data: { type: "interactive-output", data: "abcdef" } } as MessageEvent);
    writeCallbacks[0]?.("abcd");
    writeCallbacks[0]?.("ef");

    expect(worker.postMessage).toHaveBeenCalledWith({ type: "server-output-ack", bytes: 4 });
    expect(worker.postMessage).toHaveBeenCalledWith({ type: "server-output-ack", bytes: 2 });
    expect(
      vi.mocked(worker.postMessage).mock.calls.filter(([message]) => (
        typeof message === "object"
        && message !== null
        && (message as { type?: unknown }).type === "output-ack"
      ))
    ).toHaveLength(1);
  });

  it("can switch terminal windows without publishing app selection", () => {
    const worker = createWorker();
    const socketWorkerRef = createRef<Worker | null>(worker);
    const socketOpenRef = createRef(false);
    const activeWindowIdRef = createRef<string | null>("window-b");
    const onTerminalSelection = vi.fn();
    const sendSocketJson = vi.fn();

    const handleMessage = createTerminalSocketMessageHandler({
      activeWindowIdRef,
      connectionStatusRef: createRef("connecting"),
      initialWindowId: "window-a",
      outputBuffer: {
        enqueue: vi.fn(),
        enqueueInteractive: vi.fn(() => true),
      },
      selectionEnabled: false,
      terminalSwitchingEnabled: true,
      socketOpenRef,
      socketWorkerRef,
      updateConnectionStatus: vi.fn(),
      viewId: "view-a",
      closeSocketWorker: vi.fn(),
      flushPendingInputs: vi.fn(),
      isActive: () => true,
      onTerminalSelection,
      scheduleFitAndNotifyResize: vi.fn(),
      scheduleFitUntilFilled: vi.fn(),
      scheduleReconnect: vi.fn(),
      sendSocketJson,
      resetLastSentResize: vi.fn(),
      resetReconnectAttempt: vi.fn(),
    });

    handleMessage(worker, { data: { type: "open" } } as MessageEvent);
    handleMessage(worker, {
      data: {
        type: "control",
        data: JSON.stringify({ type: "terminal_selection", window_id: "window-b", view_id: "view-a" }),
      }
    } as MessageEvent);

    expect(sendSocketJson).toHaveBeenCalledWith({ type: "select_window", window_id: "window-b" });
    expect(activeWindowIdRef.current).toBe("window-b");
    expect(onTerminalSelection).not.toHaveBeenCalled();
  });

  it("acks stale selection events while waiting for an explicit window switch confirmation", () => {
    const worker = createWorker();
    const socketWorkerRef = createRef<Worker | null>(worker);
    const socketOpenRef = createRef(true);
    const activeWindowIdRef = createRef<string | null>("window-b");
    const pendingExplicitWindowIdRef = createRef<string | null>("window-b");
    const onTerminalSelection = vi.fn();

    const handleMessage = createTerminalSocketMessageHandler({
      activeWindowIdRef,
      pendingExplicitWindowIdRef,
      connectionStatusRef: createRef("connected"),
      initialWindowId: "window-a",
      outputBuffer: {
        enqueue: vi.fn(),
        enqueueInteractive: vi.fn(() => true),
      },
      selectionEnabled: true,
      terminalSwitchingEnabled: true,
      socketOpenRef,
      socketWorkerRef,
      updateConnectionStatus: vi.fn(),
      viewId: "view-a",
      closeSocketWorker: vi.fn(),
      flushPendingInputs: vi.fn(),
      isActive: () => true,
      onTerminalSelection,
      scheduleFitAndNotifyResize: vi.fn(),
      scheduleFitUntilFilled: vi.fn(),
      scheduleReconnect: vi.fn(),
      sendSocketJson: vi.fn(),
      resetLastSentResize: vi.fn(),
      resetReconnectAttempt: vi.fn(),
    });

    handleMessage(worker, {
      data: {
        type: "control",
        data: JSON.stringify({ type: "terminal_selection", window_id: "window-a", view_id: "view-a" }),
      }
    } as MessageEvent);

    expect(activeWindowIdRef.current).toBe("window-b");
    expect(pendingExplicitWindowIdRef.current).toBe("window-b");
    expect(onTerminalSelection).not.toHaveBeenCalled();
    expect(worker.postMessage).toHaveBeenCalledWith({ type: "output-ack" });

    handleMessage(worker, {
      data: {
        type: "control",
        data: JSON.stringify({ type: "terminal_selection", window_id: "window-b", view_id: "view-a" }),
      }
    } as MessageEvent);

    expect(activeWindowIdRef.current).toBe("window-b");
    expect(pendingExplicitWindowIdRef.current).toBeNull();
    expect(onTerminalSelection).toHaveBeenCalledWith("window-b");
  });

  it("marks pending window switches as recoverable only when the visible pane allows it", () => {
    const worker = createWorker();
    const socketWorkerRef = createRef<Worker | null>(worker);
    const socketOpenRef = createRef(false);
    const activeWindowIdRef = createRef<string | null>("window-b");
    const sendSocketJson = vi.fn();

    const handleMessage = createTerminalSocketMessageHandler({
      activeWindowIdRef,
      allowMissingWindowRecreateRef: createRef(true),
      connectionStatusRef: createRef("connecting"),
      initialWindowId: "window-a",
      outputBuffer: {
        enqueue: vi.fn(),
        enqueueInteractive: vi.fn(() => true),
      },
      selectionEnabled: true,
      terminalSwitchingEnabled: true,
      socketOpenRef,
      socketWorkerRef,
      updateConnectionStatus: vi.fn(),
      viewId: "view-a",
      closeSocketWorker: vi.fn(),
      flushPendingInputs: vi.fn(),
      isActive: () => true,
      onTerminalSelection: vi.fn(),
      scheduleFitAndNotifyResize: vi.fn(),
      scheduleFitUntilFilled: vi.fn(),
      scheduleReconnect: vi.fn(),
      sendSocketJson,
      resetLastSentResize: vi.fn(),
      resetReconnectAttempt: vi.fn(),
    });

    handleMessage(worker, { data: { type: "open" } } as MessageEvent);

    expect(sendSocketJson).toHaveBeenCalledWith({
      type: "select_window",
      window_id: "window-b",
      allow_missing_window_recreate: true,
    });
  });
});
