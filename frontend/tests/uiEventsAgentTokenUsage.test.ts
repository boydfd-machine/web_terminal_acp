import { describe, expect, it, vi } from "vitest";

import {
  applyUiInvalidation,
  createUiInvalidationScheduler,
  type UiInvalidateEvent
} from "../src/uiEvents";

const invalidateEvent: UiInvalidateEvent = {
  type: "invalidate",
  seq: 42,
  resources: ["window", "agent_record"],
  client_id: "client-1",
  window_id: "window-1",
  reason: "ai_event"
};

describe("agent token usage UI invalidation", () => {
  it("refreshes window detail for agent record events because token usage lives there", () => {
    const queryClient = {
      invalidateQueries: vi.fn()
    };

    applyUiInvalidation(queryClient as never, invalidateEvent);

    expect(queryClient.invalidateQueries).toHaveBeenCalledWith({
      queryKey: ["window", "client-1", "window-1"],
      exact: true
    });
  });

  it("coalesces active window detail refreshes for agent token usage updates", () => {
    vi.useFakeTimers();
    const queryClient = {
      invalidateQueries: vi.fn(),
      refetchQueries: vi.fn()
    };
    const scheduler = createUiInvalidationScheduler(queryClient as never, 350);

    scheduler.schedule(invalidateEvent);

    expect(queryClient.invalidateQueries).toHaveBeenCalledWith({
      queryKey: ["window", "client-1", "window-1"],
      exact: true,
      refetchType: "none"
    });
    vi.advanceTimersByTime(350);
    expect(queryClient.refetchQueries).toHaveBeenCalledWith({
      queryKey: ["window", "client-1", "window-1"],
      exact: true,
      type: "active"
    });

    scheduler.dispose();
    vi.useRealTimers();
  });
});
