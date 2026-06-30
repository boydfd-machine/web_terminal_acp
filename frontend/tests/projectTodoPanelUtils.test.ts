import { describe, expect, it } from "vitest";

import { projectTodoDetailFromListItem } from "../src/features/projectTodos/projectTodoPanelUtils";
import type { ProjectTodoListItem } from "../src/types";
import { todo } from "./projectTodoTestHarness";

describe("projectTodoDetailFromListItem", () => {
  it("keeps the list item description available while full detail loads", () => {
    const listItem: ProjectTodoListItem = {
      ...todo,
      description: "Visible from list cache",
      dispatch_stage: null,
      dispatch_error: null,
      review_status: "NOT_REQUESTED",
      review_unseen: false,
      needs_human_review: false,
      implementation_worktree: null,
      execution_kind: "ONCE",
      terminal_policy: "NEW_TERMINAL",
      trigger_strategy: "MANUAL",
      cron_expression: null,
      schedule_enabled: false,
      execution_run_count: 0,
      assigned_terminal: null,
      attachments: [],
      artifacts: [],
      child_todos: [],
      queued_dispatch: false
    };

    expect(projectTodoDetailFromListItem(listItem).description).toBe("Visible from list cache");
  });
});
