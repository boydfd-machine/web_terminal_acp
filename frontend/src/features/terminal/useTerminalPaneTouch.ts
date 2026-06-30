import type { MutableRefObject, PointerEvent as ReactPointerEvent } from "react";
import { useCallback } from "react";
import type { Terminal } from "@xterm/xterm";

import { terminalTouchScrollSequence } from "../../terminalTouchScroll";
import {
  TOUCH_SCROLL_MAX_WHEEL_EVENTS_PER_MOVE,
  TOUCH_SCROLL_START_THRESHOLD_PX,
} from "./terminalPaneConstants";
import type { TerminalConnectionStatus, TouchScrollGesture } from "./TerminalPaneTypes";
import { readTerminalCellHeight } from "./terminalPaneUtils";

type UseTerminalPaneTouchArgs = {
  terminalRef: MutableRefObject<Terminal | null>;
  xtermHostRef: MutableRefObject<HTMLDivElement | null>;
  connectionStatusRef: MutableRefObject<TerminalConnectionStatus>;
  touchScrollGestureRef: MutableRefObject<TouchScrollGesture | null>;
  focusTerminal: () => void;
  sendTerminalInput: (data: string, options?: { focusAfterSend?: boolean }) => void;
  claimTerminalViewPriority: () => void;
};

export function useTerminalPaneTouch({
  terminalRef,
  xtermHostRef,
  connectionStatusRef,
  touchScrollGestureRef,
  focusTerminal,
  sendTerminalInput,
  claimTerminalViewPriority,
}: UseTerminalPaneTouchArgs) {
  const sendTouchScrollWheelEvents = useCallback((
    deltaY: number,
    clientX: number,
    clientY: number,
  ): number => {
    const terminal = terminalRef.current;
    const host = xtermHostRef.current;
    if (terminal === null || host === null || connectionStatusRef.current !== "connected") {
      return 0;
    }

    const cellHeight = readTerminalCellHeight(terminal, host);
    const result = terminalTouchScrollSequence({
      deltaY,
      clientX,
      clientY,
      hostRect: host.getBoundingClientRect(),
      cols: terminal.cols,
      rows: terminal.rows,
      cellHeight,
      maxWheelEvents: TOUCH_SCROLL_MAX_WHEEL_EVENTS_PER_MOVE,
    });
    if (result === null) {
      return 0;
    }

    sendTerminalInput(result.sequence, { focusAfterSend: false });
    claimTerminalViewPriority();
    return result.consumedY;
  }, [
    claimTerminalViewPriority,
    connectionStatusRef,
    sendTerminalInput,
    terminalRef,
    xtermHostRef,
  ]);

  const handleTerminalPointerDown = useCallback((event: ReactPointerEvent<HTMLDivElement>) => {
    focusTerminal();
    if (event.pointerType !== "touch" && event.pointerType !== "pen") {
      touchScrollGestureRef.current = null;
      return;
    }
    if (event.button !== 0) {
      return;
    }
    if (event.target instanceof HTMLElement && event.target.closest(".terminal-quick-input-panel") !== null) {
      return;
    }

    touchScrollGestureRef.current = {
      pointerId: event.pointerId,
      startX: event.clientX,
      startY: event.clientY,
      lastY: event.clientY,
      accumulatedY: 0,
      scrolling: false,
    };
  }, [focusTerminal, touchScrollGestureRef]);

  const handleTerminalPointerMove = useCallback((event: ReactPointerEvent<HTMLDivElement>) => {
    const gesture = touchScrollGestureRef.current;
    if (gesture === null || gesture.pointerId !== event.pointerId) {
      return;
    }

    const movedX = event.clientX - gesture.startX;
    const movedY = event.clientY - gesture.startY;
    if (!gesture.scrolling) {
      if (
        Math.abs(movedY) < TOUCH_SCROLL_START_THRESHOLD_PX
        || Math.abs(movedY) <= Math.abs(movedX)
      ) {
        return;
      }
      gesture.scrolling = true;
    }

    event.preventDefault();
    event.stopPropagation();
    const deltaY = gesture.lastY - event.clientY;
    gesture.lastY = event.clientY;
    gesture.accumulatedY += deltaY;
    const consumedY = sendTouchScrollWheelEvents(
      gesture.accumulatedY,
      event.clientX,
      event.clientY,
    );
    if (consumedY !== 0) {
      gesture.accumulatedY -= consumedY;
    }
  }, [sendTouchScrollWheelEvents, touchScrollGestureRef]);

  const handleTerminalPointerEnd = useCallback((event: ReactPointerEvent<HTMLDivElement>) => {
    const gesture = touchScrollGestureRef.current;
    if (gesture !== null && gesture.pointerId === event.pointerId) {
      touchScrollGestureRef.current = null;
    }
  }, [touchScrollGestureRef]);

  return {
    handleTerminalPointerDown,
    handleTerminalPointerMove,
    handleTerminalPointerEnd,
  };
}
