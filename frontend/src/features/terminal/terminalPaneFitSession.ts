import type { MutableRefObject } from "react";
import type { Terminal } from "@xterm/xterm";

import {
  fitTerminalToContainer,
  isTerminalViewportFilled,
  readTerminalCanvas,
  terminalViewportNeedsRefit,
} from "../../terminalFit";
import {
  FIT_UNTIL_FILLED_INTERVAL_MS,
  FIT_UNTIL_FILLED_MAX_MS,
  RESIZE_OBSERVER_DEBOUNCE_MS,
  UNDERSIZED_REFIT_INTERVAL_MS,
  WRITE_PARSED_REFIT_DEBOUNCE_MS,
} from "./terminalPaneConstants";

type FitSessionArgs = {
  containerRef: MutableRefObject<HTMLDivElement | null>;
  fitAndNotifyResizeRef: MutableRefObject<(() => void) | null>;
  isActive: () => boolean;
  sendResize: () => void;
  stageRef: MutableRefObject<HTMLDivElement | null>;
  terminal: Terminal;
  xtermHostRef: MutableRefObject<HTMLDivElement | null>;
};

export type TerminalFitSession = {
  fitAndNotifyResize: () => void;
  scheduleFitUntilFilled: () => void;
  attachRenderResizeObserver: () => boolean;
  observeLayout: () => void;
  cleanup: () => void;
};

export function createTerminalFitSession({
  containerRef,
  fitAndNotifyResizeRef,
  isActive,
  sendResize,
  stageRef,
  terminal,
  xtermHostRef,
}: FitSessionArgs): TerminalFitSession {
  let canvasResizeObserver: ResizeObserver | null = null;
  let fitUntilFilledTimer: number | null = null;
  let fitUntilFilledStartedAt = Date.now();
  let resizeDebounceTimer: number | null = null;
  let writeParsedRefitTimer: number | null = null;

  const resolveFitContainer = (): HTMLElement | null => xtermHostRef.current ?? containerRef.current;

  const clearFitUntilFilled = () => {
    if (fitUntilFilledTimer !== null) {
      window.clearTimeout(fitUntilFilledTimer);
      fitUntilFilledTimer = null;
    }
  };

  const fitAndNotifyResize = () => {
    if (terminal.element === undefined) {
      return;
    }

    const container = resolveFitContainer();
    if (container === null) {
      return;
    }

    const rect = container.getBoundingClientRect();
    if (rect.width <= 0 || rect.height <= 0) {
      return;
    }

    if (!fitTerminalToContainer(terminal, container)) {
      return;
    }

    sendResize();
  };

  const scheduleFitUntilFilled = () => {
    clearFitUntilFilled();
    fitUntilFilledStartedAt = Date.now();
    const tick = () => {
      if (!isActive()) {
        clearFitUntilFilled();
        return;
      }

      const container = resolveFitContainer();
      if (container !== null) {
        fitAndNotifyResize();
        if (isTerminalViewportFilled(terminal, container)) {
          clearFitUntilFilled();
          return;
        }
      }

      if (Date.now() - fitUntilFilledStartedAt >= FIT_UNTIL_FILLED_MAX_MS) {
        clearFitUntilFilled();
        return;
      }

      fitUntilFilledTimer = window.setTimeout(tick, FIT_UNTIL_FILLED_INTERVAL_MS);
    };
    tick();
  };

  const writeParsedDisposable = terminal.onWriteParsed(() => {
    if (!isActive()) {
      return;
    }
    if (writeParsedRefitTimer !== null) {
      return;
    }
    writeParsedRefitTimer = window.setTimeout(() => {
      writeParsedRefitTimer = null;
      if (!isActive()) {
        return;
      }
      const container = resolveFitContainer();
      if (container === null || !terminalViewportNeedsRefit(terminal, container)) {
        return;
      }
      fitAndNotifyResize();
    }, WRITE_PARSED_REFIT_DEBOUNCE_MS);
  });

  const onResizeObserved = () => {
    if (resizeDebounceTimer !== null) {
      window.clearTimeout(resizeDebounceTimer);
    }
    resizeDebounceTimer = window.setTimeout(() => {
      resizeDebounceTimer = null;
      fitAndNotifyResize();
    }, RESIZE_OBSERVER_DEBOUNCE_MS);
  };

  const resizeObserver = new ResizeObserver(onResizeObserved);
  const attachRenderResizeObserver = () => {
    const canvas = readTerminalCanvas(terminal);
    const rowsElement = terminal.element?.querySelector(".xterm-rows");
    if (canvas === null && !(rowsElement instanceof HTMLElement)) {
      return false;
    }

    if (canvasResizeObserver === null) {
      canvasResizeObserver = new ResizeObserver(() => {
        if (!isActive()) {
          return;
        }
        fitAndNotifyResize();
      });
    }

    if (canvas !== null) {
      canvasResizeObserver.observe(canvas);
    }
    if (rowsElement instanceof HTMLElement) {
      canvasResizeObserver.observe(rowsElement);
    }
    return true;
  };

  const canvasObserver = new MutationObserver(() => {
    if (!isActive()) {
      return;
    }
    if (attachRenderResizeObserver()) {
      fitAndNotifyResize();
    }
  });

  const observeLayout = () => {
    const pane = containerRef.current;
    const host = xtermHostRef.current;
    if (pane !== null) {
      resizeObserver.observe(pane);
    }
    if (host !== null && host !== pane) {
      resizeObserver.observe(host);
    }
    const stage = stageRef.current;
    if (stage !== null && stage !== pane) {
      resizeObserver.observe(stage);
    }
    const workspace = stage?.closest(".workspace");
    if (workspace instanceof HTMLElement) {
      resizeObserver.observe(workspace);
    }
    if (pane !== null) {
      canvasObserver.observe(pane, { childList: true, subtree: true });
    }
  };

  const undersizedCheckInterval = window.setInterval(() => {
    if (!isActive() || document.hidden) {
      return;
    }

    const container = resolveFitContainer();
    if (container === null || !terminalViewportNeedsRefit(terminal, container)) {
      return;
    }

    fitAndNotifyResize();
  }, UNDERSIZED_REFIT_INTERVAL_MS);

  const cleanup = () => {
    canvasResizeObserver?.disconnect();
    clearFitUntilFilled();
    if (writeParsedRefitTimer !== null) {
      window.clearTimeout(writeParsedRefitTimer);
    }
    if (resizeDebounceTimer !== null) {
      window.clearTimeout(resizeDebounceTimer);
    }
    window.clearInterval(undersizedCheckInterval);
    resizeObserver.disconnect();
    canvasObserver.disconnect();
    writeParsedDisposable.dispose();
    if (fitAndNotifyResizeRef.current === fitAndNotifyResize) {
      fitAndNotifyResizeRef.current = null;
    }
  };

  fitAndNotifyResizeRef.current = fitAndNotifyResize;

  return {
    fitAndNotifyResize,
    scheduleFitUntilFilled,
    attachRenderResizeObserver,
    observeLayout,
    cleanup,
  };
}
