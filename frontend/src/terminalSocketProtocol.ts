export type TerminalSocketControlMessage = {
  type?: unknown;
  status?: unknown;
  retry_after_ms?: unknown;
  window_id?: unknown;
  view_id?: unknown;
};

export function parseTerminalSocketControlMessage(data: string): TerminalSocketControlMessage | null {
  try {
    const message = JSON.parse(data) as TerminalSocketControlMessage;
    return message.type === "terminal_status" || message.type === "terminal_selection" ? message : null;
  } catch {
    return null;
  }
}
