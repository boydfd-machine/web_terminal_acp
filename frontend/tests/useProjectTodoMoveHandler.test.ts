import { describe, expect, it } from "vitest";

import { projectTodoBoardColumn } from "../src/features/projectTodos/projectTodoDisplay";
import { optimisticProjectTodoMove } from "../src/features/projectTodos/useProjectTodoMoveHandler";
import type { ProjectTodoListItem } from "../src/types";
import { todo } from "./projectTodoTestHarness";

describe("optimisticProjectTodoMove", () => {
  it("clears stale dispatch and review state when moving a review card back to todo", () => {
    const reviewingTodo: ProjectTodoListItem = {
      ...todo,
      status: "AWAITING_REVIEW",
      sort_order: 2,
      dispatch_stage: "verifying",
      dispatch_error: "verification attempt still running",
      review_status: "PENDING",
      review_unseen: true,
      needs_human_review: true,
      implementation_worktree: {
        branch: "agent/say-hi",
        merge_status: "unmerged"
      }
    };

    const movedTodo = optimisticProjectTodoMove(reviewingTodo, "TODO", 9);

    expect(movedTodo).toMatchObject({
      status: "TODO",
      sort_order: 9,
      queued_dispatch: false,
      dispatch_stage: null,
      dispatch_error: null,
      review_status: "NOT_REQUESTED",
      review_unseen: false,
      needs_human_review: false,
      implementation_worktree: null
    });
    expect(projectTodoBoardColumn(movedTodo)).toBe("TODO");
  });
});

describe("projectTodoBoardColumn during verifying stage", () => {
  it("keeps a dispatched todo in the DISPATCHED column while the aux verification is running", () => {
    // While the post-completion verification (dispatch_stage="verifying") is
    // running, the card must stay in the "running" column instead of dropping
    // into "pending"/"waiting". The aux agent is still doing work for this
    // todo; the user should not see running → waiting → running flicker.
    const verifyingTodo: ProjectTodoListItem = {
      ...todo,
      status: "DISPATCHED",
      dispatch_stage: "verifying",
      dispatch_error: null,
    };
    expect(projectTodoBoardColumn(verifyingTodo)).toBe("DISPATCHED");
  });

  it("still routes pre-dispatch stages through the pending column", () => {
    // Stages that mean "the terminal has not been created yet" must keep the
    // card in pending so the user sees the card waiting for dispatch.
    const startingTodo: ProjectTodoListItem = {
      ...todo,
      status: "DISPATCHED",
      dispatch_stage: "STARTING",
      dispatch_error: null,
    };
    expect(projectTodoBoardColumn(startingTodo)).toBe("PENDING");
  });
});
