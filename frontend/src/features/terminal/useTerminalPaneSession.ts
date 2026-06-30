import { useEffect } from "react";
import { Terminal } from "@xterm/xterm";

import { webSocketAuthProtocols } from "../../auth";
import { createTerminalOutputBuffer } from "../../terminalOutputBuffer";
import {
  claimActiveTerminalView,
  isTerminalViewLowPriority,
  TERMINAL_VIEW_PRIORITY_CHANGED_EVENT,
} from "../../terminalViewPriority";
import { attachTerminalClipboardHandlers } from "./terminalPaneClipboardSession";
import { createTerminalFitSession } from "./terminalPaneFitSession";
import { createTerminalNativeInputHandlers } from "./terminalPaneNativeInput";
import { createPendingInputSession } from "./terminalPanePendingInput";
import { createTerminalSocketMessageHandler } from "./terminalPaneSocketMessages";
import {
  BACKGROUND_OUTPUT_FLUSH_CHARACTERS,
  BACKGROUND_OUTPUT_FLUSH_DELAY_MS,
  INPUT_VIEW_PRIORITY_CLAIM_INTERVAL_MS,
  LOW_PRIORITY_SOCKET_CLOSE_DELAY_MS,
  OUTPUT_REFIT_DEBOUNCE_MS,
  RECONNECT_DELAYS_MS,
  TERMINAL_OUTPUT_FLUSH_CHARACTERS,
  VIEW_PRIORITY_RECONCILE_INTERVAL_MS,
} from "./terminalPaneConstants";
import type { UseTerminalPaneSessionArgs } from "./terminalPaneSessionTypes";

export function useTerminalPaneSession({
  activeWindowIdRef,
  allowMissingWindowRecreateRef,
  autoFocusRef,
  claimActiveTerminalViewRef,
  clearScheduledFits,
  clientId,
  connectionStatusRef,
  containerRef,
  fitAndNotifyResizeRef,
  initialWindowIdRef,
  onTerminalSelectionRef,
  pendingExplicitWindowIdRef,
  priorityEnabled,
  scheduleFitAndNotifyResize,
  selectionEnabled,
  terminalSwitchingEnabled,
  setPendingClipboardText,
  sendTerminalInputRef,
  socketOpenRef,
  socketWorkerRef,
  stageRef,
  terminalRef,
  theme,
  updateConnectionStatus,
  viewIdRef,
  webSocketUrl,
  sessionWindowId,
  xtermHostRef,
}: UseTerminalPaneSessionArgs) {
  useEffect(() => {
    if (clientId === null || sessionWindowId === null) {
      return;
    }

    const initialWindowId = sessionWindowId;
    initialWindowIdRef.current = initialWindowId;
    activeWindowIdRef.current = initialWindowId;
    pendingExplicitWindowIdRef.current = null;

    const terminal = new Terminal({
      cursorBlink: true,
      fontFamily: "ui-monospace, SFMono-Regular, Menlo, monospace",
      theme,
    });
    let closedByCleanup = false;
    let disposed = false;
    let openFrame: number | null = null;
    let escapeFocusFrame: number | null = null;
    const isActive = () => !closedByCleanup && !disposed;

    let outputRefitTimer: number | null = null;
    let reconnectAttempt = 0;
    let reconnectTimer: number | null = null;
    let lowPriorityCloseTimer: number | null = null;
    let inputPriorityClaimTimer: number | null = null;
    let lastSentResize: { cols: number; rows: number } | null = null;
    let lastInputPriorityClaimedAt = 0;

    const terminalViewLease = { viewId: viewIdRef.current, clientId, windowId: initialWindowId };
    const isCurrentViewLowPriority = () => {
      return document.hidden || (priorityEnabled && isTerminalViewLowPriority(viewIdRef.current));
    };
    const claimCurrentTerminalView = () => {
      if (!priorityEnabled) {
        return;
      }
      claimActiveTerminalView(terminalViewLease);
    };
    const claimVisibleCurrentTerminalView = () => {
      if (!document.hidden) {
        claimCurrentTerminalView();
      }
    };
    claimActiveTerminalViewRef.current = claimCurrentTerminalView;
    claimVisibleCurrentTerminalView();

    const scheduleInputPriorityClaim = () => {
      if (inputPriorityClaimTimer !== null) {
        return;
      }
      inputPriorityClaimTimer = window.setTimeout(() => {
        inputPriorityClaimTimer = null;
        if (!isActive()) {
          return;
        }
        const now = Date.now();
        if (now - lastInputPriorityClaimedAt < INPUT_VIEW_PRIORITY_CLAIM_INTERVAL_MS) {
          return;
        }
        lastInputPriorityClaimedAt = now;
        claimCurrentTerminalView();
      }, INPUT_VIEW_PRIORITY_CLAIM_INTERVAL_MS);
    };

    const focusCurrentTerminal = () => {
      const stage = stageRef.current;
      const scrollLeft = stage?.scrollLeft ?? 0;
      const scrollTop = stage?.scrollTop ?? 0;
      claimVisibleCurrentTerminalView();
      terminal.focus();
      if (stage) {
        stage.scrollLeft = scrollLeft;
        stage.scrollTop = scrollTop;
      }
    };

    const restoreTerminalFocusAfterEscape = () => {
      if (escapeFocusFrame !== null) {
        window.cancelAnimationFrame(escapeFocusFrame);
      }

      escapeFocusFrame = window.requestAnimationFrame(() => {
        escapeFocusFrame = null;
        if (!isActive()) {
          return;
        }

        focusCurrentTerminal();
      });
    };

    const outputBuffer = createTerminalOutputBuffer({
      write: (data, onWrite) => {
        const writeHook = window.__WEB_TERMINAL_TEST_ON_TERMINAL_WRITE__;
        if (writeHook !== undefined) {
          terminal.write(data, () => {
            writeHook(data, performance.now());
            onWrite?.(data);
          });
        } else {
          terminal.write(data, onWrite === undefined ? undefined : () => onWrite(data));
        }
        if (outputRefitTimer !== null) {
          return;
        }
        outputRefitTimer = window.setTimeout(() => {
          outputRefitTimer = null;
          if (!isActive()) {
            return;
          }
          fitAndNotifyResizeRef.current?.();
        }, OUTPUT_REFIT_DEBOUNCE_MS);
      },
      maxFlushCharacters: TERMINAL_OUTPUT_FLUSH_CHARACTERS,
      isLowPriority: isCurrentViewLowPriority,
      lowPriorityFlushDelayMs: BACKGROUND_OUTPUT_FLUSH_DELAY_MS,
      lowPriorityMaxFlushCharacters: BACKGROUND_OUTPUT_FLUSH_CHARACTERS,
    });
    terminalRef.current = terminal;
    setPendingClipboardText(null);
    updateConnectionStatus("connecting");

    const clipboardDisposable = attachTerminalClipboardHandlers({
      terminal,
      isActive,
      setPendingClipboardText,
      focusCurrentTerminal,
      restoreTerminalFocusAfterEscape,
    });

    const sendSocketJson = (payload: unknown) => {
      const worker = socketWorkerRef.current;
      if (worker === null || !socketOpenRef.current) {
        return;
      }
      worker.postMessage({ type: "json", data: JSON.stringify(payload) });
    };

    const { flushPendingInputs, sendOrQueueInput } = createPendingInputSession({
      connectionStatusRef,
      socketOpenRef,
      socketWorkerRef,
      claimCurrentTerminalView,
      reconcileViewPriority,
    });
    sendTerminalInputRef.current = sendOrQueueInput;

    const sendResize = () => {
      const nextResize = { cols: terminal.cols, rows: terminal.rows };
      if (lastSentResize?.cols === nextResize.cols && lastSentResize.rows === nextResize.rows) {
        return;
      }

      sendSocketJson({ type: "resize", ...nextResize });
      lastSentResize = nextResize;
    };

    const fitSession = createTerminalFitSession({
      containerRef,
      fitAndNotifyResizeRef,
      isActive,
      sendResize,
      stageRef,
      terminal,
      xtermHostRef,
    });
    const { fitAndNotifyResize, scheduleFitUntilFilled } = fitSession;

    void document.fonts.ready.then(() => {
      if (!isActive()) {
        return;
      }
      fitAndNotifyResize();
      scheduleFitUntilFilled();
    });

    const clearReconnectTimer = () => {
      if (reconnectTimer !== null) {
        window.clearTimeout(reconnectTimer);
        reconnectTimer = null;
      }
    };

    const clearLowPriorityCloseTimer = () => {
      if (lowPriorityCloseTimer !== null) {
        window.clearTimeout(lowPriorityCloseTimer);
        lowPriorityCloseTimer = null;
      }
    };

    const closeSocketWorker = (worker: Worker) => {
      if (socketWorkerRef.current === worker) {
        socketWorkerRef.current = null;
        socketOpenRef.current = false;
      }
      worker.postMessage({ type: "close" });
      worker.terminate();
    };

    const scheduleReconnect = (retryAfterMs?: number) => {
      if (!isActive() || reconnectTimer !== null || isCurrentViewLowPriority()) {
        return;
      }

      const fallbackDelay = RECONNECT_DELAYS_MS[Math.min(reconnectAttempt, RECONNECT_DELAYS_MS.length - 1)];
      reconnectAttempt += 1;
      if (connectionStatusRef.current !== "unavailable") {
        updateConnectionStatus("reconnecting");
      }
      reconnectTimer = window.setTimeout(() => {
        reconnectTimer = null;
        connectSocketWorker();
      }, retryAfterMs ?? fallbackDelay);
    };

    const connectSocketWorker = () => {
      if (!isActive()) {
        return;
      }

      if (reconnectTimer !== null) {
        return;
      }

      if (isCurrentViewLowPriority()) {
        return;
      }

      if (socketWorkerRef.current !== null) {
        return;
      }

      if (initialWindowId === null) {
        return;
      }

      const worker = new Worker(new URL("../../terminalSocketWorker.ts", import.meta.url), { type: "module" });
      socketWorkerRef.current = worker;
      socketOpenRef.current = false;
      updateConnectionStatus(reconnectAttempt === 0 ? "connecting" : "reconnecting");

      const handleWorkerMessage = createTerminalSocketMessageHandler({
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
        viewId: viewIdRef.current,
        closeSocketWorker,
        flushPendingInputs,
        isActive,
        onTerminalSelection: (selectedWindowId) => onTerminalSelectionRef.current?.(selectedWindowId),
        scheduleFitAndNotifyResize,
        scheduleFitUntilFilled,
        scheduleReconnect,
        sendSocketJson,
        resetLastSentResize: () => {
          lastSentResize = null;
        },
        resetReconnectAttempt: () => {
          reconnectAttempt = 0;
        },
      });
      worker.onmessage = (event) => {
        handleWorkerMessage(worker, event);
      };

      worker.postMessage({
        type: "connect",
        url: webSocketUrl(clientId, initialWindowId, viewIdRef.current, {
          allowMissingWindowRecreate: allowMissingWindowRecreateRef.current,
        }),
        protocols: webSocketAuthProtocols(),
      });
    };

    function reconcileViewPriority() {
      if (!isActive()) {
        return;
      }

      if (isCurrentViewLowPriority()) {
        clearReconnectTimer();
        outputBuffer.clear();
        if (lowPriorityCloseTimer === null && socketWorkerRef.current !== null) {
          lowPriorityCloseTimer = window.setTimeout(() => {
            lowPriorityCloseTimer = null;
            if (!isActive() || !isCurrentViewLowPriority()) {
              return;
            }
            const worker = socketWorkerRef.current;
            if (worker !== null) {
              closeSocketWorker(worker);
            }
          }, LOW_PRIORITY_SOCKET_CLOSE_DELAY_MS);
        }
        return;
      }

      clearLowPriorityCloseTimer();
      scheduleFitAndNotifyResize();
      scheduleFitUntilFilled();
      connectSocketWorker();
      flushPendingInputs();
    }

    const handleTerminalVisibilityChange = () => {
      if (autoFocusRef.current && !document.hidden) {
        focusCurrentTerminal();
      }
      reconcileViewPriority();
    };
    const handleTerminalViewPriorityChange = () => {
      reconcileViewPriority();
    };
    document.addEventListener("visibilitychange", handleTerminalVisibilityChange);
    window.addEventListener("storage", handleTerminalViewPriorityChange);
    window.addEventListener(TERMINAL_VIEW_PRIORITY_CHANGED_EVENT, handleTerminalViewPriorityChange);
    const viewPriorityReconcileInterval = window.setInterval(
      reconcileViewPriority,
      VIEW_PRIORITY_RECONCILE_INTERVAL_MS,
    );

    const nativeInputHandlers = createTerminalNativeInputHandlers({
      terminal,
      connectionStatusRef,
      isActive,
      sendOrQueueInput,
      scheduleInputPriorityClaim,
      focusCurrentTerminal,
    });

    const disposable = terminal.onData(nativeInputHandlers.handleTerminalData);

    fitSession.observeLayout();

    const openTerminalWhenReady = () => {
      if (!isActive()) {
        return;
      }

      const xtermHost = xtermHostRef.current;
      if (xtermHost === null) {
        openFrame = window.requestAnimationFrame(openTerminalWhenReady);
        return;
      }

      if (xtermHost.clientWidth <= 0 || xtermHost.clientHeight <= 0) {
        openFrame = window.requestAnimationFrame(openTerminalWhenReady);
        return;
      }

      terminal.open(xtermHost);
      nativeInputHandlers.attach();
      fitSession.attachRenderResizeObserver();
      scheduleFitAndNotifyResize();
      scheduleFitUntilFilled();
      if (autoFocusRef.current) {
        focusCurrentTerminal();
      }
      connectSocketWorker();
    };

    openTerminalWhenReady();

    return () => {
      closedByCleanup = true;
      disposed = true;
      if (openFrame !== null) {
        window.cancelAnimationFrame(openFrame);
      }
      if (escapeFocusFrame !== null) {
        window.cancelAnimationFrame(escapeFocusFrame);
      }
      clearReconnectTimer();
      clearLowPriorityCloseTimer();
      if (inputPriorityClaimTimer !== null) {
        window.clearTimeout(inputPriorityClaimTimer);
      }
      if (outputRefitTimer !== null) {
        window.clearTimeout(outputRefitTimer);
      }
      nativeInputHandlers.cleanup();
      window.clearInterval(viewPriorityReconcileInterval);
      document.removeEventListener("visibilitychange", handleTerminalVisibilityChange);
      window.removeEventListener("storage", handleTerminalViewPriorityChange);
      window.removeEventListener(TERMINAL_VIEW_PRIORITY_CHANGED_EVENT, handleTerminalViewPriorityChange);
      disposable.dispose();
      clipboardDisposable.dispose();
      outputBuffer.dispose();
      const worker = socketWorkerRef.current;
      worker?.postMessage({ type: "close" });
      worker?.terminate();
      terminal.dispose();
      clearScheduledFits();
      socketWorkerRef.current = null;
      socketOpenRef.current = false;
      if (terminalRef.current === terminal) {
        terminalRef.current = null;
      }
      fitSession.cleanup();
      if (claimActiveTerminalViewRef.current === claimCurrentTerminalView) {
        claimActiveTerminalViewRef.current = null;
      }
      if (sendTerminalInputRef.current === sendOrQueueInput) {
        sendTerminalInputRef.current = null;
      }
    };
  }, [
    clearScheduledFits,
    clientId,
    priorityEnabled,
    scheduleFitAndNotifyResize,
    selectionEnabled,
    sessionWindowId,
    terminalSwitchingEnabled,
    updateConnectionStatus,
    webSocketUrl,
  ]);

}
