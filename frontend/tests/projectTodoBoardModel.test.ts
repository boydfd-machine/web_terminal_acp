import { beforeEach, describe, expect, it } from "vitest";

import {
  buildProjectTodoBoardGroups,
  defaultProjectTodoBoardFilters,
  filterProjectTodos,
  projectTodoMergePayload
} from "../src/features/projectTodos/projectTodoBoardModel";
import {
  PROJECT_TODO_DATE_FILTER_STORAGE_KEY,
  projectTodoDateFilterQueryKey,
  projectTodoDateFilterRequest,
  projectTodoDateFilterActive,
  projectTodoUpdatedAtMatchesDateFilter,
  readProjectTodoDateFilter,
  writeProjectTodoDateFilter
} from "../src/features/projectTodos/projectTodoDateFilter";
import type { ProjectTodoListItem } from "../src/types";
import { todo } from "./projectTodoTestHarness";

describe("project todo board model", () => {
  beforeEach(() => {
    window.localStorage.clear();
  });

  it("matches search against list card names, tags, todo types, terminal summary names, and terminal tree paths", () => {
    const searchableTodo: ProjectTodoListItem = {
      ...todo,
      assigned_window_id: "window-1",
      agent_profile_id: "builtin/default",
      assigned_terminal: {
        id: "window-1",
        title: "Board grouping terminal",
        summary: "Implementing tree grouped project todos.",
        title_tags: ["kanban", "frontend"],
        runtime_tags: ["codex", "/workspace"],
        work_status: { state: "WORKING", label: "Working", color: "green" },
        topic_path: "/Web Terminal ACP/Frontend UI/Board",
        git_worktree: null,
        parent_window_id: null,
        root_window_id: null,
        derived_mode: null,
        created_at: "2026-06-05T00:00:00Z"
      }
    };
    const otherTodo: ProjectTodoListItem = {
      ...todo,
      id: "todo-2",
      title: "Document MCP",
      sort_order: 2,
      assigned_window_id: "window-2",
      assigned_terminal: {
        id: "window-2",
        title: "MCP docs terminal",
        summary: "Document MCP settings.",
        title_tags: ["mcp"],
        runtime_tags: ["claude", "/workspace"],
        work_status: { state: "LONG_IDLE", label: "Idle", color: "gray" },
        topic_path: "/Skill and MCP/Docs",
        git_worktree: null,
        parent_window_id: null,
        root_window_id: null,
        derived_mode: null,
        created_at: "2026-06-05T00:01:00Z"
      }
    };
    const todos = [searchableTodo, otherTodo];
    const matchingTitles = (search: string) => (
      filterProjectTodos(todos, { ...defaultProjectTodoBoardFilters(), search }).map((item) => item.title)
    );

    expect(matchingTitles("frontend")).toEqual(["Fix dispatch"]);
    expect(matchingTitles("old details")).toEqual([]);
    expect(matchingTitles("Fix dispatch")).toEqual(["Fix dispatch"]);
    expect(matchingTitles("Board grouping terminal")).toEqual(["Fix dispatch"]);
    expect(matchingTitles("Frontend UI")).toEqual(["Fix dispatch"]);
    expect(matchingTitles("Implementing tree grouped")).toEqual(["Fix dispatch"]);
    expect(matchingTitles("Document MCP")).toEqual(["Document MCP"]);
  });

  it("places locally dispatching todos in the pending board column immediately", () => {
    const waitingTodo: ProjectTodoListItem = {
      ...todo,
      dispatch_stage: null,
      queued_dispatch: false,
      status: "TODO"
    };
    const groups = buildProjectTodoBoardGroups([waitingTodo], "flat", {
      dispatchingTodoIds: new Set([waitingTodo.id])
    });

    expect(groups[0].columns.get("TODO")).toEqual([]);
    expect(groups[0].columns.get("PENDING")?.map((item) => item.id)).toEqual([waitingTodo.id]);
    expect(filterProjectTodos([waitingTodo], {
      ...defaultProjectTodoBoardFilters(),
      status: "PENDING"
    }, {
      dispatchingTodoIds: new Set([waitingTodo.id])
    })).toEqual([waitingTodo]);
  });

  it("filters cards to the selected parent card and its children", () => {
    const parentTodo: ProjectTodoListItem = {
      ...todo,
      id: "todo-parent",
      title: "Parent feature",
      child_todos: [{
        id: "todo-child",
        title: "Child task",
        status: "TODO",
        completed_at: null
      }]
    };
    const childTodo: ProjectTodoListItem = {
      ...todo,
      id: "todo-child",
      title: "Child task",
      parent_todo_id: "todo-parent",
      parent_todo: {
        id: "todo-parent",
        title: "Parent feature",
        status: "TODO",
        completed_at: null
      }
    };
    const siblingTodo: ProjectTodoListItem = {
      ...todo,
      id: "todo-sibling",
      title: "Sibling task",
      parent_todo_id: "todo-other"
    };

    expect(filterProjectTodos([parentTodo, childTodo, siblingTodo], {
      ...defaultProjectTodoBoardFilters(),
      parentTodoId: "todo-parent"
    }).map((item) => item.title)).toEqual(["Parent feature", "Child task"]);
  });

  it("stacks dragged card title and description onto the hovered target card", () => {
    const target = {
      ...todo,
      title: "Keep target",
      description: "Target details"
    };
    const source = {
      ...todo,
      id: "todo-2",
      title: "Merge source",
      description: "Source details"
    };

    expect(projectTodoMergePayload({ target, source })).toEqual({
      title: "Keep target / Merge source",
      description: "Target details\n\nSource details"
    });
  });

  it("skips empty descriptions when stacking card content", () => {
    const target = {
      ...todo,
      title: "Keep target",
      description: null
    };
    const source = {
      ...todo,
      id: "todo-2",
      title: "Merge source",
      description: "Source details"
    };

    expect(projectTodoMergePayload({ target, source })).toEqual({
      title: "Keep target / Merge source",
      description: "Source details"
    });
  });

  it("builds project todo date filter API requests", () => {
    expect(projectTodoDateFilterRequest({
      range: "7d",
      customStart: "",
      customEnd: ""
    })).toEqual({ range: "7d" });
    expect(projectTodoDateFilterRequest({
      range: "custom",
      customStart: "2026-06-01",
      customEnd: "2026-06-03"
    })).toEqual({
      range: "custom",
      start_date: "2026-06-01",
      end_date: "2026-06-03"
    });
    expect(projectTodoDateFilterQueryKey({
      range: "custom",
      customStart: "2026-06-01",
      customEnd: "2026-06-03"
    })).toEqual(["custom", "2026-06-01", "2026-06-03"]);
  });

  it("treats empty custom date bounds as inactive", () => {
    const filter = {
      range: "custom" as const,
      customStart: "",
      customEnd: ""
    };

    expect(projectTodoDateFilterActive(filter)).toBe(false);
    expect(projectTodoDateFilterRequest(filter)).toBeUndefined();
  });

  it("matches newly created todos against the active updated date filter", () => {
    const now = new Date("2026-06-08T12:00:00Z");

    expect(projectTodoUpdatedAtMatchesDateFilter({
      ...todo,
      updated_at: "2026-06-07T12:00:00Z"
    }, { range: "30d", customStart: "", customEnd: "" }, now)).toBe(true);
    expect(projectTodoUpdatedAtMatchesDateFilter({
      ...todo,
      updated_at: "2026-05-01T12:00:00Z"
    }, { range: "30d", customStart: "", customEnd: "" }, now)).toBe(false);
    expect(projectTodoUpdatedAtMatchesDateFilter({
      ...todo,
      updated_at: "2026-06-03T23:59:59Z"
    }, { range: "custom", customStart: "2026-06-02", customEnd: "2026-06-03" }, now)).toBe(true);
    expect(projectTodoUpdatedAtMatchesDateFilter({
      ...todo,
      updated_at: "2026-06-04T00:00:00Z"
    }, { range: "custom", customStart: "2026-06-02", customEnd: "2026-06-03" }, now)).toBe(false);
  });

  it("persists the selected project todo date filter in browser storage", () => {
    writeProjectTodoDateFilter({
      range: "custom",
      customStart: "2026-06-01",
      customEnd: "2026-06-03"
    });

    expect(readProjectTodoDateFilter()).toEqual({
      range: "custom",
      customStart: "2026-06-01",
      customEnd: "2026-06-03"
    });
  });

  it("ignores unsupported stored project todo date filters", () => {
    window.localStorage.setItem(PROJECT_TODO_DATE_FILTER_STORAGE_KEY, JSON.stringify({
      range: "custom",
      customStart: "2026-99-99",
      customEnd: "bad"
    }));

    expect(readProjectTodoDateFilter()).toEqual({
      range: "custom",
      customStart: "",
      customEnd: ""
    });

    window.localStorage.setItem(PROJECT_TODO_DATE_FILTER_STORAGE_KEY, JSON.stringify({
      range: "2d",
      customStart: "2026-06-01",
      customEnd: "2026-06-03"
    }));

    expect(readProjectTodoDateFilter()).toEqual({
      range: "all",
      customStart: "",
      customEnd: ""
    });

    window.localStorage.setItem(PROJECT_TODO_DATE_FILTER_STORAGE_KEY, "{");
    expect(readProjectTodoDateFilter()).toEqual({
      range: "all",
      customStart: "",
      customEnd: ""
    });
  });
});
