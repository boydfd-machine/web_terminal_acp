import type { MutableRefObject } from "react";

import type { TerminalConnectionStatus } from "./TerminalPaneTypes";
import { parseTerminalSocketControlMessage } from "../../terminalSocketProtocol";
import { terminalOutputByteLength } from "./terminalPaneUtils";

type OutputBuffer = {
  enqueue: (
    data: string | Uint8Array,
    options?: { onWrite?: (writtenChunk: string | Uint8Array) => void }
  ) => void;
  enqueueInteractive: (
    data: string | Uint8Array,
    options?: { onWrite?: (writtenChunk: string | Uint8Array) => void }
  ) => boolean;
};

type SocketMessageHandlerArgs = {
  activeWindowIdRef: MutableRefObject<string | null>;
  allowMissingWindowRecreateRef?: MutableRefObject<boolean>;
  connectionStatusRef: MutableRefObject<TerminalConnectionStatus>;
  initialWindowId: string;
  outputBuffer: OutputBuffer;
  pendingExplicitWindowIdRef?: MutableRefObject<string | null>;
  selectionEnabled: boolean;
  terminalSwitchingEnabled: boolean;
  socketOpenRef: MutableRefObject<boolean>;
  socketWorkerRef: MutableRefObject<Worker | null>;
  updateConnectionStatus: (status: TerminalConnectionStatus) => void;
  viewId: string;
  closeSocketWorker: (worker: Worker) => void;
  flushPendingInputs: () => void;
  isActive: () => boolean;
  onTerminalSelection: (windowId: string) => void;
  scheduleFitAndNotifyResize: () => void;
  scheduleFitUntilFilled: () => void;
  scheduleReconnect: (retryAfterMs?: number) => void;
  sendSocketJson: (payload: unknown) => void;
  resetLastSentResize: () => void;
  resetReconnectAttempt: () => void;
};

export type SocketWorkerMessage = {
  type?: unknown;
  data?: unknown;
  closedByCommand?: unknown;
};

export function selectWindowPayload(windowId: string, allowMissingWindowRecreate: boolean) {
  return allowMissingWindowRecreate
    ? { type: "select_window", window_id: windowId, allow_missing_window_recreate: true }
    : { type: "select_window", window_id: windowId };
}

export function createTerminalSocketMessageHandler({
  activeWindowIdRef,
  allowMissingWindowRecreateRef,
  connectionStatusRef,
  initialWindowId,
  outputBuffer,
  pendingExplicitWindowIdRef,
  selectionEnabled,
  terminalSwitchingEnabled,
  socketOpenRef,
  socketWorkerRef,
  updateConnectionStatus,
  viewId,
  closeSocketWorker,
  flushPendingInputs,
  isActive,
  onTerminalSelection,
  scheduleFitAndNotifyResize,
  scheduleFitUntilFilled,
  scheduleReconnect,
  sendSocketJson,
  resetLastSentResize,
  resetReconnectAttempt,
}: SocketMessageHandlerArgs) {
  return (worker: Worker, event: MessageEvent<SocketWorkerMessage>) => {
    if (!isActive() || socketWorkerRef.current !== worker) {
      return;
    }

    if (event.data.type === "open") {
      socketOpenRef.current = true;
      resetLastSentResize();
      scheduleFitAndNotifyResize();
      scheduleFitUntilFilled();
      const pendingWindowId = activeWindowIdRef.current;
      if (terminalSwitchingEnabled && pendingWindowId !== null && pendingWindowId !== initialWindowId) {
        sendSocketJson(selectWindowPayload(
          pendingWindowId,
          allowMissingWindowRecreateRef?.current === true,
        ));
      }
      return;
    }

    const handleControlMessage = (data: string) => {
      const statusMessage = parseTerminalSocketControlMessage(data);
      if (
        statusMessage?.type === "terminal_selection"
        && typeof statusMessage.window_id === "string"
        && statusMessage.view_id === viewId
      ) {
        const pendingExplicitWindowId = pendingExplicitWindowIdRef?.current ?? null;
        if (pendingExplicitWindowId !== null && statusMessage.window_id !== pendingExplicitWindowId) {
          worker.postMessage({ type: "output-ack" });
          return true;
        }
        if (statusMessage.window_id === pendingExplicitWindowId && pendingExplicitWindowIdRef !== undefined) {
          pendingExplicitWindowIdRef.current = null;
        }
        activeWindowIdRef.current = statusMessage.window_id;
        if (selectionEnabled) {
          onTerminalSelection(statusMessage.window_id);
        }
        worker.postMessage({ type: "output-ack" });
        return true;
      }
      if (statusMessage?.status === "connected") {
        resetReconnectAttempt();
        updateConnectionStatus("connected");
        scheduleFitUntilFilled();
        flushPendingInputs();
      } else if (statusMessage?.status === "unavailable") {
        updateConnectionStatus("unavailable");
        if (pendingExplicitWindowIdRef !== undefined) {
          pendingExplicitWindowIdRef.current = null;
        }
        const retryAfterMs = typeof statusMessage.retry_after_ms === "number"
          ? statusMessage.retry_after_ms
          : undefined;
        closeSocketWorker(worker);
        scheduleReconnect(retryAfterMs);
      } else if (statusMessage?.status === "error") {
        updateConnectionStatus("error");
        if (pendingExplicitWindowIdRef !== undefined) {
          pendingExplicitWindowIdRef.current = null;
        }
      } else if (statusMessage?.status === "reconnecting") {
        updateConnectionStatus("reconnecting");
        if (pendingExplicitWindowIdRef !== undefined) {
          pendingExplicitWindowIdRef.current = null;
        }
        const retryAfterMs = typeof statusMessage.retry_after_ms === "number"
          ? statusMessage.retry_after_ms
          : undefined;
        closeSocketWorker(worker);
        scheduleReconnect(retryAfterMs);
      }
      worker.postMessage({ type: "output-ack" });
      return true;
    };

    if (event.data.type === "control" && typeof event.data.data === "string") {
      handleControlMessage(event.data.data);
      return;
    }
    if (
      (event.data.type === "output" || event.data.type === "interactive-output")
      && event.data.data instanceof Uint8Array
    ) {
      handleTerminalOutput(worker, event.data.type, event.data.data);
      return;
    }
    if (
      (event.data.type === "output" || event.data.type === "interactive-output")
      && typeof event.data.data === "string"
    ) {
      const data = event.data.data;
      if (parseTerminalSocketControlMessage(data) !== null) {
        handleControlMessage(data);
        return;
      }

      handleTerminalOutput(worker, event.data.type, data);
      return;
    }
    if (event.data.type === "error") {
      closeSocketWorker(worker);
      scheduleReconnect();
      return;
    }
    if (event.data.type === "close") {
      if (socketWorkerRef.current !== worker) {
        return;
      }
      closeSocketWorker(worker);
      if (event.data.closedByCommand !== true) {
        scheduleReconnect();
      }
    }
  };

  function handleTerminalOutput(worker: Worker, type: unknown, data: string | Uint8Array) {
    if (connectionStatusRef.current !== "connected") {
      resetReconnectAttempt();
      updateConnectionStatus("connected");
      scheduleFitUntilFilled();
    }
    flushPendingInputs();
    const acknowledgeServerOutput = (writtenChunk: string | Uint8Array) => {
      worker.postMessage({ type: "server-output-ack", bytes: terminalOutputByteLength(writtenChunk) });
    };
    if (type === "interactive-output") {
      window.__WEB_TERMINAL_TEST_ON_INTERACTIVE_OUTPUT__?.(data, performance.now());
      let outputAcknowledged = false;
      const acknowledgeOutput = () => {
        if (outputAcknowledged) {
          return;
        }
        outputAcknowledged = true;
        worker.postMessage({ type: "output-ack" });
      };
      const wroteImmediately = outputBuffer.enqueueInteractive(data, {
        onWrite: (writtenChunk) => {
          acknowledgeServerOutput(writtenChunk);
          acknowledgeOutput();
        },
      });
      if (!wroteImmediately) {
        acknowledgeOutput();
      }
      return;
    }
    outputBuffer.enqueue(data, { onWrite: acknowledgeServerOutput });
    worker.postMessage({ type: "output-ack" });
  }
}
