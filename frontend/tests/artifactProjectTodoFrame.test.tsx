import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, describe, expect, it, vi } from "vitest";

import {
  ARTIFACT_PROJECT_TODO_CREATED_MESSAGE,
  ARTIFACT_PROJECT_TODO_CREATE_FAILED_MESSAGE,
  ARTIFACT_PROJECT_TODO_CREATE_MESSAGE,
  ARTIFACT_PROJECT_TODO_MESSAGE_VERSION
} from "../src/artifactProjectTodoBridge";
import { ArtifactProjectTodoFrame } from "../src/components/ArtifactProjectTodoFrame";
import type { ProjectTodo } from "../src/types";

globalThis.IS_REACT_ACT_ENVIRONMENT = true;

let root: Root | null = null;
let container: HTMLDivElement | null = null;

function renderFrame(props: Partial<Parameters<typeof ArtifactProjectTodoFrame>[0]> = {}) {
  container = document.createElement("div");
  document.body.appendChild(container);
  root = createRoot(container);
  const onCreateProjectTodo = vi.fn().mockResolvedValue(todo({
    id: "todo-1",
    project_path: "/workspace/project",
    title: "Created from artifact"
  }));
  act(() => {
    root?.render(
      <ArtifactProjectTodoFrame
        artifactId="artifact-1"
        clientId="client-1"
        projectPath="/workspace/project"
        srcDoc="<html><body>artifact</body></html>"
        title="Artifact"
        onCreateProjectTodo={onCreateProjectTodo}
        {...props}
      />
    );
  });
  const iframe = container.querySelector("iframe");
  if (!(iframe instanceof HTMLIFrameElement)) {
    throw new Error("iframe not rendered");
  }
  const frameWindow = iframe.contentWindow as Window;
  const postMessage = vi.spyOn(frameWindow, "postMessage").mockImplementation(() => {});
  return { frameWindow, onCreateProjectTodo, postMessage };
}

function dispatchArtifactMessage(source: Window | null, data: unknown): void {
  act(() => {
    window.dispatchEvent(new MessageEvent("message", { data, source }));
  });
}

async function flushPromises(): Promise<void> {
  await act(async () => {
    await new Promise((resolve) => setTimeout(resolve, 0));
  });
}

afterEach(() => {
  act(() => {
    root?.unmount();
  });
  container?.remove();
  root = null;
  container = null;
  vi.restoreAllMocks();
});

describe("ArtifactProjectTodoFrame", () => {
  it("renders artifact HTML in an isolated script-only sandbox", () => {
    renderFrame();

    const iframe = container?.querySelector("iframe");

    expect(iframe).toBeInstanceOf(HTMLIFrameElement);
    expect(iframe?.getAttribute("sandbox")).toBe("allow-scripts");
    expect(iframe?.getAttribute("referrerpolicy")).toBe("no-referrer");
    expect(iframe?.getAttribute("sandbox")).not.toContain("allow-same-origin");
  });

  it("creates a project todo only for messages from its own iframe", async () => {
    const { frameWindow, onCreateProjectTodo, postMessage } = renderFrame();
    const payload = {
      type: ARTIFACT_PROJECT_TODO_CREATE_MESSAGE,
      version: ARTIFACT_PROJECT_TODO_MESSAGE_VERSION,
      request_id: "request-1",
      card: {
        title: "Created from artifact",
        description: "Use this as the card body"
      }
    };

    dispatchArtifactMessage(window, payload);
    await flushPromises();
    expect(onCreateProjectTodo).not.toHaveBeenCalled();

    dispatchArtifactMessage(frameWindow, payload);
    await flushPromises();

    expect(onCreateProjectTodo).toHaveBeenCalledWith(
      {
        title: "Created from artifact",
        description: "Use this as the card body"
      },
      "artifact-1"
    );
    expect(postMessage).toHaveBeenCalledWith({
      type: ARTIFACT_PROJECT_TODO_CREATED_MESSAGE,
      version: ARTIFACT_PROJECT_TODO_MESSAGE_VERSION,
      request_id: "request-1",
      todo: {
        id: "todo-1",
        project_path: "/workspace/project",
        title: "Created from artifact"
      }
    }, "*");
  });

  it("reports a failure when the host frame has no project path", async () => {
    const { frameWindow, onCreateProjectTodo, postMessage } = renderFrame({ projectPath: null });

    dispatchArtifactMessage(frameWindow, {
      type: ARTIFACT_PROJECT_TODO_CREATE_MESSAGE,
      version: ARTIFACT_PROJECT_TODO_MESSAGE_VERSION,
      request_id: "request-2",
      card: { title: "Needs a project" }
    });
    await flushPromises();

    expect(onCreateProjectTodo).not.toHaveBeenCalled();
    expect(postMessage).toHaveBeenCalledWith({
      type: ARTIFACT_PROJECT_TODO_CREATE_FAILED_MESSAGE,
      version: ARTIFACT_PROJECT_TODO_MESSAGE_VERSION,
      request_id: "request-2",
      detail: "project path is required"
    }, "*");
  });
});

function todo(overrides: Partial<ProjectTodo>): ProjectTodo {
  return {
    id: "todo-1",
    client_id: "client-1",
    project_path: "/workspace/project",
    todo_type_id: "default",
    todo_type: {
      id: "default",
      scope: "system",
      client_id: null,
      project_path: null,
      name: "Default",
      description: null,
      agent: null,
      agent_profile_id: null,
      artifact_kinds: [],
      dispatch_template: null,
      created_at: "2026-06-07T00:00:00Z",
      updated_at: "2026-06-07T00:00:00Z"
    },
    title: "Created from artifact",
    description: null,
    status: "TODO",
    sort_order: 1,
    assigned_window_id: null,
    assigned_agent: null,
    agent_profile_id: null,
    dispatch_prompt: null,
    dispatch_stage: null,
    dispatch_error: null,
    dispatched_at: null,
    awaiting_review_at: null,
    completed_at: null,
    review_strategy: "LOCAL_CARD",
    review_status: "NOT_REQUESTED",
    review_agent: null,
    review_agent_profile_id: null,
    review_window_id: null,
    review_prompt: null,
    review_dispatched_at: null,
    reviewed_at: null,
    review_unseen: false,
    needs_human_review: false,
    review_notes: null,
    implementation_worktree: null,
    execution_kind: "ONCE",
    terminal_policy: "NEW_TERMINAL",
    trigger_strategy: "MANUAL",
    cron_expression: null,
    schedule_enabled: false,
    next_trigger_at: null,
    last_triggered_at: null,
    execution_run_count: 0,
    artifact_kinds: [],
    assigned_terminal: null,
    execution_runs: [],
    attachments: [],
    artifacts: [],
    dependencies: [],
    dependents: [],
    child_todos: [],
    referenced_todos: [],
    queued_dispatch: false,
    created_at: "2026-06-07T00:00:00Z",
    updated_at: "2026-06-07T00:00:00Z",
    ...overrides
  };
}
