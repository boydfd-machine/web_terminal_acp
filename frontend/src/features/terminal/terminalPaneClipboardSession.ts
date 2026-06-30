import type { Dispatch, SetStateAction } from "react";
import type { Terminal } from "@xterm/xterm";

import {
  copyTerminalSelection,
  terminalClipboardShortcutAction,
  writeClipboardText,
} from "../../terminalClipboard";
import { decodeOsc52ClipboardPayload } from "./terminalPaneUtils";

type Disposable = {
  dispose: () => void;
};

type ClipboardSessionArgs = {
  terminal: Terminal;
  isActive: () => boolean;
  setPendingClipboardText: Dispatch<SetStateAction<string | null>>;
  focusCurrentTerminal: () => void;
  restoreTerminalFocusAfterEscape: () => void;
};

export function attachTerminalClipboardHandlers({
  terminal,
  isActive,
  setPendingClipboardText,
  focusCurrentTerminal,
  restoreTerminalFocusAfterEscape,
}: ClipboardSessionArgs): Disposable {
  const osc52Disposable = terminal.parser.registerOscHandler(52, async (data) => {
    if (!isActive()) {
      return true;
    }

    const text = decodeOsc52ClipboardPayload(data);
    if (text === null) {
      return true;
    }

    try {
      await writeClipboardText(text);
      if (isActive()) {
        setPendingClipboardText(null);
      }
    } catch {
      if (isActive()) {
        setPendingClipboardText(text);
      }
    }
    return true;
  });

  terminal.attachCustomKeyEventHandler((event) => {
    const clipboardAction = terminalClipboardShortcutAction(event);
    if (clipboardAction === "copy") {
      if (terminal.hasSelection()) {
        event.preventDefault();
        event.stopPropagation();
        void copyTerminalSelection(terminal).then((copied) => {
          if (copied && isActive()) {
            setPendingClipboardText(null);
            focusCurrentTerminal();
          }
        }).catch(() => {});
        return false;
      }
      return true;
    }

    if (clipboardAction === "paste") {
      return false;
    }

    if (event.key !== "Escape") {
      return true;
    }

    event.preventDefault();
    event.stopPropagation();
    restoreTerminalFocusAfterEscape();
    return true;
  });

  return osc52Disposable;
}
