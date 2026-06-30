import type { MutableRefObject } from "react";
import type { Terminal } from "@xterm/xterm";

import { pasteClipboardEventToTerminal } from "../../terminalClipboard";
import {
  NATIVE_TEXT_INPUT_DEDUPE_MS,
  NATIVE_TEXT_INPUT_FALLBACK_DELAY_MS,
} from "./terminalPaneConstants";
import type {
  RecentNativeFallbackInput,
  RecentXtermInput,
  TerminalConnectionStatus,
} from "./TerminalPaneTypes";

type NativeInputHandlersArgs = {
  terminal: Terminal;
  connectionStatusRef: MutableRefObject<TerminalConnectionStatus>;
  isActive: () => boolean;
  sendOrQueueInput: (data: string) => void;
  scheduleInputPriorityClaim: () => void;
  focusCurrentTerminal: () => void;
};

export type TerminalNativeInputHandlers = {
  handleTerminalData: (data: string) => void;
  attach: () => void;
  cleanup: () => void;
};

export function createTerminalNativeInputHandlers({
  terminal,
  connectionStatusRef,
  isActive,
  sendOrQueueInput,
  scheduleInputPriorityClaim,
  focusCurrentTerminal,
}: NativeInputHandlersArgs): TerminalNativeInputHandlers {
  let xtermInputSerial = 0;
  let nativeTextInputEventSerial = 0;
  let activeNativeTextInputEventSerial: number | null = null;
  let nativeTextInputEventClearTimer: number | null = null;
  let nativeInputFallbackTimer: number | null = null;
  let nativeInputFallbackCompositionActive = false;
  let nativeInputCompositionStartValue = "";
  let nativeInputCompositionLatestData = "";
  let nativePasteElement: HTMLElement | undefined;
  let nativePasteTextarea: HTMLTextAreaElement | undefined;
  let nativeInputTextarea: HTMLTextAreaElement | undefined;
  const recentNativeFallbackInputs: RecentNativeFallbackInput[] = [];
  const recentXtermInputs: RecentXtermInput[] = [];

  const pruneRecentNativeFallbackInputs = (now = performance.now()) => {
    while (
      recentNativeFallbackInputs.length > 0
      && now - recentNativeFallbackInputs[0].sentAt > NATIVE_TEXT_INPUT_DEDUPE_MS
    ) {
      recentNativeFallbackInputs.shift();
    }
  };

  const pruneRecentXtermInputs = (now = performance.now()) => {
    while (
      recentXtermInputs.length > 0
      && now - recentXtermInputs[0].seenAt > NATIVE_TEXT_INPUT_DEDUPE_MS
    ) {
      recentXtermInputs.shift();
    }
  };

  const consumeMatchingNativeFallbackInput = (data: string): boolean => {
    const now = performance.now();
    pruneRecentNativeFallbackInputs(now);
    const activeInputEventSerial = activeNativeTextInputEventSerial;
    const index = recentNativeFallbackInputs.findIndex((entry) => (
      entry.data === data
      && (
        activeInputEventSerial === entry.inputEventSerial
        || (activeInputEventSerial === null && nativeTextInputEventSerial === entry.inputEventSerial)
      )
    ));
    if (index < 0) {
      return false;
    }
    recentNativeFallbackInputs.splice(index, 1);
    return true;
  };

  const rememberNativeFallbackInput = (data: string, inputEventSerial: number) => {
    const now = performance.now();
    pruneRecentNativeFallbackInputs(now);
    recentNativeFallbackInputs.push({ data, inputEventSerial, sentAt: now });
  };

  const rememberXtermInput = (data: string) => {
    const now = performance.now();
    pruneRecentXtermInputs(now);
    recentXtermInputs.push({ data, seenAt: now });
  };

  const hasRecentXtermInput = (data: string): boolean => {
    const now = performance.now();
    pruneRecentXtermInputs(now);
    return recentXtermInputs.some((entry) => entry.data === data);
  };

  const markNativeTextInputEventSerial = () => {
    nativeTextInputEventSerial += 1;
    activeNativeTextInputEventSerial = nativeTextInputEventSerial;
    if (nativeTextInputEventClearTimer !== null) {
      window.clearTimeout(nativeTextInputEventClearTimer);
    }
    const markedInputEventSerial = nativeTextInputEventSerial;
    nativeTextInputEventClearTimer = window.setTimeout(() => {
      nativeTextInputEventClearTimer = null;
      if (activeNativeTextInputEventSerial === markedInputEventSerial) {
        activeNativeTextInputEventSerial = null;
      }
    }, 0);
    return markedInputEventSerial;
  };

  const sendNativeTextInputFallback = (
    data: string,
    inputEventSerial: number,
    xtermSerialBeforeFallback: number,
    { allowAfterComposition = false }: { allowAfterComposition?: boolean } = {},
  ) => {
    if (
      data.length === 0
      || !isActive()
      || connectionStatusRef.current !== "connected"
      || (!allowAfterComposition && nativeInputFallbackCompositionActive)
      || xtermInputSerial !== xtermSerialBeforeFallback
      || hasRecentXtermInput(data)
    ) {
      return;
    }

    rememberNativeFallbackInput(data, inputEventSerial);
    sendOrQueueInput(data);
    scheduleInputPriorityClaim();
  };

  const handleNativePaste = (event: ClipboardEvent) => {
    if (connectionStatusRef.current !== "connected") {
      return;
    }

    const pasted = pasteClipboardEventToTerminal(
      event,
      sendOrQueueInput,
      terminal.modes.bracketedPasteMode,
    );
    if (pasted) {
      focusCurrentTerminal();
    }
  };

  const handleNativeInputCompositionStart = () => {
    nativeInputFallbackCompositionActive = true;
    nativeInputCompositionStartValue = nativeInputTextarea?.value ?? "";
    nativeInputCompositionLatestData = "";
    if (nativeInputFallbackTimer !== null) {
      window.clearTimeout(nativeInputFallbackTimer);
      nativeInputFallbackTimer = null;
    }
  };

  const handleNativeInputCompositionUpdate = (event: CompositionEvent) => {
    nativeInputCompositionLatestData = event.data;
  };

  const handleNativeInputCompositionEnd = (event: CompositionEvent) => {
    nativeInputFallbackCompositionActive = false;
    nativeInputCompositionLatestData = event.data || nativeInputCompositionLatestData;
    const compositionStartValue = nativeInputCompositionStartValue;
    const compositionEventData = event.data;
    const fallbackInputEventSerial = markNativeTextInputEventSerial();
    const xtermSerialBeforeFallback = xtermInputSerial;
    if (nativeInputFallbackTimer !== null) {
      window.clearTimeout(nativeInputFallbackTimer);
    }
    nativeInputFallbackTimer = window.setTimeout(() => {
      nativeInputFallbackTimer = null;
      const textareaValue = nativeInputTextarea?.value ?? "";
      const insertedText = textareaValue.startsWith(compositionStartValue)
        ? textareaValue.slice(compositionStartValue.length)
        : "";
      const data = insertedText || compositionEventData || nativeInputCompositionLatestData;
      nativeInputCompositionStartValue = "";
      nativeInputCompositionLatestData = "";
      sendNativeTextInputFallback(data, fallbackInputEventSerial, xtermSerialBeforeFallback, {
        allowAfterComposition: true,
      });
    }, NATIVE_TEXT_INPUT_FALLBACK_DELAY_MS);
  };

  const markNativeTextInputEvent = (event: InputEvent) => {
    if (
      (event.inputType === "insertText" || event.inputType === "insertCompositionText")
      && event.data !== null
      && event.data.length > 1
    ) {
      markNativeTextInputEventSerial();
    }
  };

  const handleNativeTextInputFallback = (event: InputEvent) => {
    if (event.inputType === "insertCompositionText" && event.data !== null) {
      nativeInputCompositionLatestData = event.data;
    }
    if (
      connectionStatusRef.current !== "connected"
      || nativeInputFallbackCompositionActive
      || event.isComposing
      || event.inputType !== "insertText"
      || event.data === null
      || event.data.length <= 1
      || event.defaultPrevented
    ) {
      return;
    }

    const data = event.data;
    const xtermSerialBeforeFallback = xtermInputSerial;
    const inputEventSerial = nativeTextInputEventSerial;
    if (nativeInputFallbackTimer !== null) {
      window.clearTimeout(nativeInputFallbackTimer);
    }
    nativeInputFallbackTimer = window.setTimeout(() => {
      nativeInputFallbackTimer = null;
      sendNativeTextInputFallback(data, inputEventSerial, xtermSerialBeforeFallback);
    }, NATIVE_TEXT_INPUT_FALLBACK_DELAY_MS);
  };

  const detach = () => {
    nativePasteElement?.removeEventListener("paste", handleNativePaste, true);
    nativePasteElement?.removeEventListener("input", markNativeTextInputEvent as EventListener, true);
    nativePasteTextarea?.removeEventListener("paste", handleNativePaste, true);
    nativeInputTextarea?.removeEventListener("compositionstart", handleNativeInputCompositionStart);
    nativeInputTextarea?.removeEventListener("compositionupdate", handleNativeInputCompositionUpdate);
    nativeInputTextarea?.removeEventListener("compositionend", handleNativeInputCompositionEnd);
    nativeInputTextarea?.removeEventListener("input", handleNativeTextInputFallback as EventListener, true);
  };

  const attach = () => {
    const element = terminal.element;
    const textarea = terminal.textarea;
    if (element !== undefined && nativePasteElement !== element) {
      nativePasteElement?.removeEventListener("paste", handleNativePaste, true);
      nativePasteElement?.removeEventListener("input", markNativeTextInputEvent as EventListener, true);
      element.addEventListener("paste", handleNativePaste, true);
      element.addEventListener("input", markNativeTextInputEvent as EventListener, true);
      nativePasteElement = element;
    }
    if (textarea !== undefined && nativePasteTextarea !== textarea) {
      nativePasteTextarea?.removeEventListener("paste", handleNativePaste, true);
      textarea.addEventListener("paste", handleNativePaste, true);
      nativePasteTextarea = textarea;
    }
    if (textarea !== undefined && nativeInputTextarea !== textarea) {
      nativeInputTextarea?.removeEventListener("compositionstart", handleNativeInputCompositionStart);
      nativeInputTextarea?.removeEventListener("compositionupdate", handleNativeInputCompositionUpdate);
      nativeInputTextarea?.removeEventListener("compositionend", handleNativeInputCompositionEnd);
      nativeInputTextarea?.removeEventListener("input", handleNativeTextInputFallback as EventListener, true);
      textarea.addEventListener("compositionstart", handleNativeInputCompositionStart);
      textarea.addEventListener("compositionupdate", handleNativeInputCompositionUpdate);
      textarea.addEventListener("compositionend", handleNativeInputCompositionEnd);
      textarea.addEventListener("input", handleNativeTextInputFallback as EventListener, true);
      nativeInputTextarea = textarea;
    }
  };

  const handleTerminalData = (data: string) => {
    xtermInputSerial += 1;
    if (consumeMatchingNativeFallbackInput(data)) {
      return;
    }
    rememberXtermInput(data);
    window.__WEB_TERMINAL_TEST_ON_TERMINAL_DATA__?.(data, performance.now());
    sendOrQueueInput(data);
    scheduleInputPriorityClaim();
  };

  const cleanup = () => {
    if (nativeInputFallbackTimer !== null) {
      window.clearTimeout(nativeInputFallbackTimer);
    }
    if (nativeTextInputEventClearTimer !== null) {
      window.clearTimeout(nativeTextInputEventClearTimer);
    }
    detach();
  };

  return { handleTerminalData, attach, cleanup };
}
