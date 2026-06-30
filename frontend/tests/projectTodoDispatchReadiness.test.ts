import { describe, expect, it, vi } from "vitest";

import { waitForProjectTodoDispatchWindow } from "../src/projectTodoDispatchReadiness";
import type { VirtualWindow } from "../src/types";

function virtualWindow(overrides: Partial<VirtualWindow> = {}): VirtualWindow {
  return {
    id: "window-1",
    client_id: "client-1",
    title: "Todo terminal",
    folder_id: null,
    parent_window_id: null,
    root_window_id: null,
    derived_mode: null,
    derived_context: null,
    status: "ACTIVE",
    tmux_session: null,
    tmux_window_id: null,
    tmux_window_index: null,
    remote_session_id: null,
    remote_window_id: null,
    cwd: null,
    shell_command: null,
    summary: null,
    title_tags: null,
    runtime_tags: [],
    work_status: { state: "LONG_IDLE", label: "Idle", color: "gray" },
    title_manually_overridden: false,
    folder_manually_overridden: false,
    command_capture_supported: false,
    summary_job: null,
    created_at: "2026-06-05T00:00:00Z",
    last_terminal_command_at: null,
    last_agent_event_at: null,
    last_active_at: "2026-06-05T00:00:00Z",
    ...overrides
  };
}

describe("projectTodoDispatchReadiness", () => {
  it("waits for the dispatched terminal to exist and expose runtime ids", async () => {
    let now = 0;
    const readyWindow = virtualWindow({ remote_session_id: "session", remote_window_id: "window" });
    const fetchLatestWindow = vi.fn()
      .mockRejectedValueOnce(new Error("404"))
      .mockResolvedValueOnce(virtualWindow())
      .mockResolvedValueOnce(readyWindow);

    const result = await waitForProjectTodoDispatchWindow("client-1", "window-1", {
      pollMs: 5,
      timeoutMs: 100,
      fetchLatestWindow,
      sleep: async () => {
        now += 5;
      },
      now: () => now
    });

    expect(result).toBe(readyWindow);
    expect(fetchLatestWindow).toHaveBeenCalledTimes(3);
  });
});
