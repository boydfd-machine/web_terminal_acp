import type { TerminalConnectionStatus } from "./TerminalPaneTypes";

export type TerminalSessionTarget = { clientId: string; windowId: string };

export function shouldReuseSessionTarget(
  current: TerminalSessionTarget | null,
  clientId: string,
  windowId: string,
  status: TerminalConnectionStatus,
) {
  return current?.clientId === clientId
    && (current.windowId === windowId || (status !== "unavailable" && status !== "error"));
}
