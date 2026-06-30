import type { Terminal } from "@xterm/xterm";

import { TOUCH_SCROLL_FALLBACK_STEP_PX } from "./terminalPaneConstants";

export function terminalOutputByteLength(data: string | Uint8Array): number {
  return typeof data === "string" ? new TextEncoder().encode(data).byteLength : data.byteLength;
}

export function readTerminalCellHeight(terminal: Terminal, host: HTMLElement): number {
  const core = (terminal as unknown as {
    _core?: {
      _renderService?: {
        dimensions?: {
          css?: {
            cell?: {
              height?: number;
            };
          };
        };
      };
    };
  })._core;
  const measuredHeight = core?._renderService?.dimensions?.css?.cell?.height;
  if (typeof measuredHeight === "number" && measuredHeight > 0) {
    return measuredHeight;
  }

  const rowHeight = terminal.rows > 0 ? host.clientHeight / terminal.rows : 0;
  return rowHeight > 0 ? rowHeight : TOUCH_SCROLL_FALLBACK_STEP_PX;
}

export function decodeOsc52ClipboardPayload(data: string): string | null {
  const separatorIndex = data.indexOf(";");
  if (separatorIndex < 0) {
    return null;
  }

  const encoded = data.slice(separatorIndex + 1).replace(/\s/g, "");
  if (!encoded || encoded === "?") {
    return null;
  }

  try {
    const binary = window.atob(encoded);
    const bytes = Uint8Array.from(binary, (character) => character.charCodeAt(0));
    return new TextDecoder().decode(bytes);
  } catch {
    return null;
  }
}
