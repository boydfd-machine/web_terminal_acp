import { Terminal } from "@xterm/xterm";
import "./terminalPaneTestHooks";
import {
  forwardRef,
  useCallback,
  useEffect,
  useImperativeHandle,
  useLayoutEffect,
  useRef,
  useState,
} from "react";

import { terminalWebSocketUrl } from "../../api";
import { useI18n } from "../../i18n";
import {
  copyTerminalSelection,
  pasteClipboardToTerminal,
  writeClipboardText
} from "../../terminalClipboard";
import { createBrowserUuid } from "../../uuid";
import { useTerminalPaneTouch } from "./useTerminalPaneTouch";
import { useTerminalPaneSession } from "./useTerminalPaneSession";
import { selectWindowPayload } from "./terminalPaneSocketMessages";
import {
  shouldReuseSessionTarget,
  type TerminalSessionTarget
} from "./terminalPaneSessionTarget";
import {
  clearQuickInputDraft,
  quickInputDraftStorageKey,
  readQuickInputDraft,
  writeQuickInputDraft
} from "./TerminalQuickInput";
import type { CustomQuickKey } from "../../terminalQuickKeys";
import {
  TerminalConnectionOverlay,
  TerminalQuickInputOverlay,
  TerminalVirtualKeys
} from "./TerminalPaneOverlays";
import {
  FIT_RETRY_DELAYS_MS,
} from "./terminalPaneConstants";
import type {
  TerminalConnectionStatus,
  TerminalPaneHandle,
  TerminalPaneProps,
  TouchScrollGesture
} from "./TerminalPaneTypes";
export type { TerminalConnectionStatus, TerminalPaneHandle } from "./TerminalPaneTypes";

export const TerminalPane = forwardRef<TerminalPaneHandle, TerminalPaneProps>(function TerminalPane({
  clientId,
  windowId,
  viewportMode = "desktop",
  layoutVersion = 0,
  virtualKeysVisible = false,
  onTerminalSelection,
  onQuickInputOpenChange,
  onQuickInputDraftChange,
  customQuickKeys = [],
  onCustomQuickKeySubmit,
  onTerminalConnectionStatusChange,
  webSocketUrl = terminalWebSocketUrl,
  selectionEnabled = true,
  terminalSwitchingEnabled = selectionEnabled,
  priorityEnabled = true,
  autoFocus = true,
  allowMissingWindowRecreate = false,
  theme,
}, ref) {
  const { t } = useI18n();
  const stageRef = useRef<HTMLDivElement | null>(null);
  const containerRef = useRef<HTMLDivElement | null>(null);
  const xtermHostRef = useRef<HTMLDivElement | null>(null);
  const terminalRef = useRef<Terminal | null>(null);
  const touchScrollGestureRef = useRef<TouchScrollGesture | null>(null);
  const socketWorkerRef = useRef<Worker | null>(null);
  const socketOpenRef = useRef(false);
  const activeWindowIdRef = useRef<string | null>(null);
  const allowMissingWindowRecreateRef = useRef(allowMissingWindowRecreate);
  const initialWindowIdRef = useRef<string | null>(null);
  const pendingExplicitWindowIdRef = useRef<string | null>(null);
  const viewIdRef = useRef<string>(createBrowserUuid());
  const autoFocusRef = useRef(autoFocus);
  const onTerminalSelectionRef = useRef<TerminalPaneProps["onTerminalSelection"]>(onTerminalSelection);
  const onQuickInputOpenChangeRef = useRef<TerminalPaneProps["onQuickInputOpenChange"]>(onQuickInputOpenChange);
  const onQuickInputDraftChangeRef = useRef<TerminalPaneProps["onQuickInputDraftChange"]>(onQuickInputDraftChange);
  const onTerminalConnectionStatusChangeRef = useRef<TerminalPaneProps["onTerminalConnectionStatusChange"]>(onTerminalConnectionStatusChange);
  const fitAndNotifyResizeRef = useRef<(() => void) | null>(null);
  const claimActiveTerminalViewRef = useRef<(() => void) | null>(null);
  const sendTerminalInputRef = useRef<((data: string) => void) | null>(null);
  const scheduledFitFramesRef = useRef<number[]>([]);
  const scheduledFitTimeoutsRef = useRef<number[]>([]);
  const connectionStatusRef = useRef<TerminalConnectionStatus>("connecting");
  const [pendingClipboardText, setPendingClipboardText] = useState<string | null>(null);
  const [connectionStatus, setConnectionStatus] = useState<TerminalConnectionStatus>("connecting");
  const [quickInputOpen, setQuickInputOpen] = useState(false);
  const [quickInputDraft, setQuickInputDraft] = useState("");
  const [sessionTarget, setSessionTarget] = useState<TerminalSessionTarget | null>(() => (
    clientId !== null && windowId !== null ? { clientId, windowId } : null
  ));
  const hasSelectedWindow = windowId !== null;
  const sessionWindowId = clientId !== null && windowId !== null && sessionTarget?.clientId === clientId
    ? sessionTarget.windowId
    : null;
  const quickInputStorageKey = clientId !== null && windowId !== null
    ? quickInputDraftStorageKey(clientId, windowId)
    : null;
  const canSendQuickInput = connectionStatus === "connected";

  const updateQuickInputDraft = useCallback((draft: string) => {
    setQuickInputDraft(draft);
    onQuickInputDraftChangeRef.current?.(draft);
    if (quickInputStorageKey !== null) {
      writeQuickInputDraft(quickInputStorageKey, draft);
    }
  }, [quickInputStorageKey]);

  const updateConnectionStatus = useCallback((status: TerminalConnectionStatus) => {
    connectionStatusRef.current = status;
    onTerminalConnectionStatusChangeRef.current?.(status);
    setConnectionStatus(status);
  }, []);

  useEffect(() => {
    if (clientId === null || windowId === null) {
      setSessionTarget((current) => current === null ? current : null);
      return;
    }

    setSessionTarget((current) => (
      shouldReuseSessionTarget(current, clientId, windowId, connectionStatusRef.current)
        ? current
        : { clientId, windowId }
    ));
  }, [clientId, connectionStatus, windowId]);

  useEffect(() => {
    autoFocusRef.current = autoFocus;
  }, [autoFocus]);

  useEffect(() => {
    allowMissingWindowRecreateRef.current = allowMissingWindowRecreate;
  }, [allowMissingWindowRecreate]);

  useEffect(() => {
    onTerminalSelectionRef.current = onTerminalSelection;
  }, [onTerminalSelection]);

  useEffect(() => {
    onQuickInputOpenChangeRef.current = onQuickInputOpenChange;
  }, [onQuickInputOpenChange]);

  useEffect(() => {
    onQuickInputDraftChangeRef.current = onQuickInputDraftChange;
  }, [onQuickInputDraftChange]);

  useEffect(() => {
    onTerminalConnectionStatusChangeRef.current = onTerminalConnectionStatusChange;
    onTerminalConnectionStatusChangeRef.current?.(connectionStatusRef.current);
  }, [onTerminalConnectionStatusChange]);

  useEffect(() => {
    if (theme) {
      const terminal = terminalRef.current;
      if (terminal) {
        terminal.options.theme = theme;
      }
    }
  }, [theme]);

  useEffect(() => {
    onQuickInputOpenChangeRef.current?.(quickInputOpen);
    return () => {
      if (quickInputOpen) {
        onQuickInputOpenChangeRef.current?.(false);
      }
    };
  }, [quickInputOpen]);

  useEffect(() => {
    if (quickInputStorageKey === null) {
      setQuickInputOpen(false);
      updateQuickInputDraft("");
      return;
    }

    const storedDraft = readQuickInputDraft(quickInputStorageKey);
    setQuickInputDraft(storedDraft);
    onQuickInputDraftChangeRef.current?.(storedDraft);
  }, [quickInputStorageKey, updateQuickInputDraft]);

  const clearScheduledFits = useCallback(() => {
    for (const frame of scheduledFitFramesRef.current) {
      window.cancelAnimationFrame(frame);
    }
    for (const timeout of scheduledFitTimeoutsRef.current) {
      window.clearTimeout(timeout);
    }
    scheduledFitFramesRef.current = [];
    scheduledFitTimeoutsRef.current = [];
  }, []);

  const fitAndNotifyResize = useCallback(() => {
    fitAndNotifyResizeRef.current?.();
  }, []);

  const claimTerminalViewPriority = useCallback(() => {
    claimActiveTerminalViewRef.current?.();
  }, []);

  const scheduleFitAndNotifyResize = useCallback(() => {
    clearScheduledFits();
    fitAndNotifyResize();

    const firstFrame = window.requestAnimationFrame(() => {
      fitAndNotifyResize();
      const secondFrame = window.requestAnimationFrame(fitAndNotifyResize);
      scheduledFitFramesRef.current.push(secondFrame);
    });
    scheduledFitFramesRef.current.push(firstFrame);

    for (const delay of FIT_RETRY_DELAYS_MS) {
      scheduledFitTimeoutsRef.current.push(window.setTimeout(fitAndNotifyResize, delay));
    }
  }, [clearScheduledFits, fitAndNotifyResize]);

  const focusTerminal = useCallback(() => {
    claimTerminalViewPriority();
    const stage = stageRef.current;
    const scrollLeft = stage?.scrollLeft ?? 0;
    const scrollTop = stage?.scrollTop ?? 0;
    terminalRef.current?.focus();
    if (stage) {
      stage.scrollLeft = scrollLeft;
      stage.scrollTop = scrollTop;
    }
  }, [claimTerminalViewPriority]);

  const openQuickInput = useCallback(() => {
    if (clientId === null || windowId === null) {
      return;
    }
    claimTerminalViewPriority();
    setQuickInputOpen(true);
  }, [claimTerminalViewPriority, clientId, windowId]);

  const closeQuickInput = useCallback(() => {
    setQuickInputOpen(false);
    focusTerminal();
  }, [focusTerminal]);

  const sendTerminalInput = (data: string, { focusAfterSend = true }: { focusAfterSend?: boolean } = {}) => {
    claimTerminalViewPriority();
    sendTerminalInputRef.current?.(data);
    if (focusAfterSend) {
      focusTerminal();
    }
  };
  const copyTerminalClipboardSelection = useCallback(async () => {
    const terminal = terminalRef.current;
    if (terminal === null) {
      return false;
    }

    try {
      const copied = await copyTerminalSelection(terminal);
      if (copied) {
        setPendingClipboardText(null);
        focusTerminal();
      }
      return copied;
    } catch {
      return false;
    }
  }, [focusTerminal]);
  const pasteTerminalClipboardText = useCallback(async () => {
    if (connectionStatusRef.current !== "connected") {
      return false;
    }

    try {
      const pasted = await pasteClipboardToTerminal(
        (data) => sendTerminalInput(data, { focusAfterSend: false }),
        terminalRef.current?.modes.bracketedPasteMode ?? false
      );
      if (pasted) {
        focusTerminal();
      }
      return pasted;
    } catch {
      return false;
    }
  }, [focusTerminal]);

  const submitQuickInput = useCallback((draftOverride?: string) => {
    claimTerminalViewPriority();
    const draft = draftOverride ?? quickInputDraft;
    if (draft.length === 0 || connectionStatusRef.current !== "connected") {
      return false;
    }

    sendTerminalInputRef.current?.(draft);
    if (quickInputStorageKey !== null) {
      clearQuickInputDraft(quickInputStorageKey);
    }
    updateQuickInputDraft("");
    setQuickInputOpen(false);
    focusTerminal();
    return true;
  }, [claimTerminalViewPriority, focusTerminal, quickInputDraft, quickInputStorageKey, updateQuickInputDraft]);

  const {
    handleTerminalPointerDown,
    handleTerminalPointerMove,
    handleTerminalPointerEnd,
  } = useTerminalPaneTouch({
    terminalRef,
    xtermHostRef,
    connectionStatusRef,
    touchScrollGestureRef,
    focusTerminal,
    sendTerminalInput,
    claimTerminalViewPriority,
  });

  useImperativeHandle(ref, () => ({
    focus: focusTerminal,
    refit: scheduleFitAndNotifyResize,
    openQuickInput,
    setQuickInputDraft: updateQuickInputDraft,
    submitQuickInput,
    connectionStatus: () => connectionStatusRef.current,
  }), [focusTerminal, openQuickInput, scheduleFitAndNotifyResize, submitQuickInput, updateQuickInputDraft]);

  const sendSelectWindow = useCallback((nextWindowId: string) => {
    if (!terminalSwitchingEnabled) {
      return;
    }

    const worker = socketWorkerRef.current;
    if (worker === null || !socketOpenRef.current) {
      return;
    }

    worker.postMessage({
      type: "json",
      data: JSON.stringify(selectWindowPayload(
        nextWindowId,
        allowMissingWindowRecreateRef.current,
      )),
    });
  }, [terminalSwitchingEnabled]);

  useTerminalPaneSession({
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
  });

  useEffect(() => {
    if (clientId === null || windowId === null) {
      return;
    }

    if (activeWindowIdRef.current === windowId) {
      return;
    }

    activeWindowIdRef.current = windowId;
    pendingExplicitWindowIdRef.current = windowId;
    sendSelectWindow(windowId);
  }, [clientId, sendSelectWindow, windowId]);

  useLayoutEffect(() => {
    const stage = stageRef.current;
    if (stage !== null) {
      stage.scrollLeft = 0;
      stage.scrollTop = 0;
    }

    scheduleFitAndNotifyResize();
  }, [layoutVersion, scheduleFitAndNotifyResize, viewportMode, virtualKeysVisible]);

  useEffect(() => {
    const handleResizeCue = () => scheduleFitAndNotifyResize();
    const handleVisibilityChange = () => {
      if (!document.hidden) {
        scheduleFitAndNotifyResize();
      }
    };

    window.addEventListener("resize", handleResizeCue);
    window.addEventListener("orientationchange", handleResizeCue);
    window.addEventListener("focus", handleResizeCue);
    document.addEventListener("visibilitychange", handleVisibilityChange);
    return () => {
      window.removeEventListener("resize", handleResizeCue);
      window.removeEventListener("orientationchange", handleResizeCue);
      window.removeEventListener("focus", handleResizeCue);
      document.removeEventListener("visibilitychange", handleVisibilityChange);
      clearScheduledFits();
    };
  }, [clearScheduledFits, scheduleFitAndNotifyResize]);

  if (clientId === null || windowId === null) {
    return <div className="empty-terminal" data-onboarding-id="terminal-pane">{t("terminal.empty")}</div>;
  }

  return (
    <div
      ref={stageRef}
      data-debug-id="terminal-container"
      data-onboarding-id="terminal-pane"
      className={[
        "terminal-stage",
        `terminal-stage-${viewportMode}`,
        virtualKeysVisible ? "terminal-stage-with-virtual-keys" : "",
        quickInputOpen ? "terminal-stage-quick-input-open" : "",
      ].filter(Boolean).join(" ")}
      onPointerDown={handleTerminalPointerDown}
      onPointerMove={handleTerminalPointerMove}
      onPointerUp={handleTerminalPointerEnd}
      onPointerCancel={handleTerminalPointerEnd}
    >
      {virtualKeysVisible && (
        <TerminalVirtualKeys
          connectionStatus={connectionStatus}
          onKeyInput={(data) => sendTerminalInput(data, { focusAfterSend: false })}
          onPaste={() => void pasteTerminalClipboardText()}
          onCopy={() => void copyTerminalClipboardSelection()}
        />
      )}
      <div ref={containerRef} className={`terminal-pane terminal-pane-${viewportMode}`}>
        <div ref={xtermHostRef} className="terminal-xterm-host" />
      </div>
      <TerminalQuickInputOverlay
        open={quickInputOpen}
        draft={quickInputDraft}
        canSend={canSendQuickInput}
        onDraftChange={updateQuickInputDraft}
        onSubmit={submitQuickInput}
        onCancel={closeQuickInput}
        customQuickKeys={customQuickKeys}
        onCustomQuickKeySubmit={onCustomQuickKeySubmit}
      />
      <TerminalConnectionOverlay status={connectionStatus} />
      {pendingClipboardText !== null && (
        <button
          type="button"
          className="terminal-clipboard-copy"
          onMouseDown={(event) => event.stopPropagation()}
          onTouchStart={(event) => event.stopPropagation()}
          onClick={async (event) => {
            event.stopPropagation();
            try {
              await writeClipboardText(pendingClipboardText, true);
              setPendingClipboardText(null);
              focusTerminal();
            } catch {
              return;
            }
          }}
        >
          Copy pending clipboard
        </button>
      )}
    </div>
  );
});
