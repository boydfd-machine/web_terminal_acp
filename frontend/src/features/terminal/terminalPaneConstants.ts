import type { TerminalConnectionStatus } from "./TerminalPaneTypes";
import type { TranslateFn } from "../../i18n";

export type VirtualKey = {
  label: string;
  value: string;
};

export const VIRTUAL_KEYS: VirtualKey[] = [
  { label: "Esc", value: "\x1b" },
  { label: "Tab", value: "\t" },
  { label: "Ctrl-C", value: "\x03" },
  { label: "Ctrl-D", value: "\x04" },
  { label: "Ctrl-L", value: "\x0c" },
  { label: "Ctrl-A", value: "\x01" },
  { label: "Ctrl-E", value: "\x05" },
  { label: "Ctrl-U", value: "\x15" },
  { label: "↑", value: "\x1b[A" },
  { label: "↓", value: "\x1b[B" },
  { label: "←", value: "\x1b[D" },
  { label: "→", value: "\x1b[C" },
  { label: "Home", value: "\x1b[H" },
  { label: "End", value: "\x1b[F" },
  { label: "PgUp", value: "\x1b[5~" },
  { label: "PgDn", value: "\x1b[6~" },
];

export const RECONNECT_DELAYS_MS = [500, 1000, 2000, 5000, 10000];
export const FIT_RETRY_DELAYS_MS = [80, 250, 600, 1200, 2000, 3000, 5000, 10000, 15000, 30000] as const;
export const FIT_UNTIL_FILLED_INTERVAL_MS = 150;
export const FIT_UNTIL_FILLED_MAX_MS = 60000;
export const UNDERSIZED_REFIT_INTERVAL_MS = 2000;
export const OUTPUT_REFIT_DEBOUNCE_MS = 50;
export const WRITE_PARSED_REFIT_DEBOUNCE_MS = 100;
export const RESIZE_OBSERVER_DEBOUNCE_MS = 50;
export const TERMINAL_OUTPUT_FLUSH_CHARACTERS = 128 * 1024;
export const BACKGROUND_OUTPUT_FLUSH_DELAY_MS = 250;
export const BACKGROUND_OUTPUT_FLUSH_CHARACTERS = 1024;
export const LOW_PRIORITY_SOCKET_CLOSE_DELAY_MS = 1500;
export const VIEW_PRIORITY_RECONCILE_INTERVAL_MS = 750;
export const INPUT_VIEW_PRIORITY_CLAIM_INTERVAL_MS = 250;
export const PENDING_INPUT_QUEUE_MAX_SIZE = 64;
export const TOUCH_SCROLL_START_THRESHOLD_PX = 12;
export const TOUCH_SCROLL_FALLBACK_STEP_PX = 18;
export const TOUCH_SCROLL_MAX_WHEEL_EVENTS_PER_MOVE = 12;
export const NATIVE_TEXT_INPUT_FALLBACK_DELAY_MS = 0;
export const NATIVE_TEXT_INPUT_DEDUPE_MS = 250;

export function terminalStatusLabel(status: TerminalConnectionStatus, t?: TranslateFn): string {
  switch (status) {
    case "connected":
      return t?.("terminal.status.connected") ?? "Connected";
    case "connecting":
      return t?.("terminal.status.connecting") ?? "Connecting...";
    case "reconnecting":
      return t?.("terminal.status.reconnecting") ?? "Reconnecting...";
    case "unavailable":
      return t?.("terminal.status.unavailable") ?? "Client offline, reconnecting...";
    case "error":
      return t?.("terminal.status.error") ?? "Terminal error";
  }
}
