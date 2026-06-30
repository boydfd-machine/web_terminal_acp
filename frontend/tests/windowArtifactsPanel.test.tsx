import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, describe, expect, it, vi } from "vitest";

import {
  ARTIFACT_PROJECT_TODO_CREATE_MESSAGE,
  ARTIFACT_PROJECT_TODO_MESSAGE_VERSION
} from "../src/artifactProjectTodoBridge";
import { WindowArtifactsPanel } from "../src/components/WindowArtifactsPanel";
import type { ArtifactListItem, ProjectTodo, TerminalArtifact } from "../src/types";

globalThis.IS_REACT_ACT_ENVIRONMENT = true;

let root: Root | null = null;
let container: HTMLDivElement | null = null;
let queryClient: QueryClient | null = null;

function renderPanel(props: Partial<Parameters<typeof WindowArtifactsPanel>[0]> = {}) {
  container = document.createElement("div");
  document.body.appendChild(container);
  queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false }
    }
  });
  root = createRoot(container);
  act(() => {
    root?.render(
      <QueryClientProvider client={queryClient as QueryClient}>
        <WindowArtifactsPanel
          artifactFullscreen={false}
          artifactPage={0}
          artifactScope="terminal"
          artifactItems={[]}
          artifactsData={null}
          artifactsError={false}
          artifactsFetching={false}
          artifactsLoading={false}
          clientId="client-1"
          createArtifactError={null}
          createArtifactPending={false}
          createPageReviewTodoError={null}
          creatingPageReviewTodo={null}
          itemWindowId="window-1"
          artifactModelAgent={null}
          artifactModelSelection={null}
          projectPath="/workspace/project"
          selectedItem={null}
          selectedItemCanDisplay={false}
          selectedItemId={null}
          selectedItemReady={false}
          selectedItemSrcDoc={null}
          selectedItemHtmlError={false}
          windowId="window-1"
          onArtifactScopeChange={() => {}}
          onCreateArtifact={() => {}}
          onCreatePageReviewTodo={() => {}}
          onArtifactModelSelectionChange={() => {}}
          setArtifactFullscreen={() => {}}
          setArtifactPage={() => {}}
          setSelectedItemId={() => {}}
          {...props}
        />
      </QueryClientProvider>
    );
  });
}

function jsonResponse(body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status: 200,
    headers: { "Content-Type": "application/json" }
  });
}

function pageReviewArtifact(contentJson: Record<string, unknown>): TerminalArtifact {
  return {
    id: "artifact-1",
    client_id: "client-1",
    virtual_window_id: "window-1",
    source_window_id: "window-1",
    ephemeral_window_id: null,
    artifact_scope: "terminal",
    project_path: null,
    artifact_kind: "page_review_cards",
    title: "Page review",
    status: "SUCCEEDED",
    content_json: contentJson,
    display_html: null,
    metadata_json: null,
    last_error: null,
    started_at: null,
    completed_at: "2026-06-06T00:00:00Z",
    created_at: "2026-06-06T00:00:00Z",
    updated_at: "2026-06-06T00:00:00Z"
  };
}

function terminalArtifactItem(artifact: TerminalArtifact): ArtifactListItem {
  return {
    kind: "terminal_artifact",
    id: `terminal_artifact:${artifact.id}`,
    artifact
  };
}

function clickButton(label: string): void {
  const button = Array.from(container?.querySelectorAll("button") ?? [])
    .find((candidate) => candidate.textContent === label);
  if (!(button instanceof HTMLButtonElement)) {
    throw new Error(`button not found: ${label}`);
  }
  act(() => {
    button.click();
  });
}

afterEach(() => {
  act(() => {
    root?.unmount();
  });
  container?.remove();
  root = null;
  container = null;
  queryClient?.clear();
  queryClient = null;
  vi.restoreAllMocks();
});

describe("WindowArtifactsPanel", () => {
  it("creates artifacts with distinct artifact kinds", () => {
    const onCreateArtifact = vi.fn();

        renderPanel({ onCreateArtifact });

    clickButton("Generate Trace");
    clickButton("Generate Pitfalls");
    clickButton("Generate Page Review");

    expect(onCreateArtifact).toHaveBeenNthCalledWith(
      1,
      "client-1",
      "window-1",
      "agent_trace_graph",
      "terminal",
      null
    );
    expect(onCreateArtifact).toHaveBeenNthCalledWith(
      2,
      "client-1",
      "window-1",
      "agent_pitfalls",
      "terminal",
      null
    );
    expect(onCreateArtifact).toHaveBeenNthCalledWith(
      3,
      "client-1",
      "window-1",
      "page_review_cards",
      "terminal",
      null
    );
  });

  it("passes the selected artifact model selection when creating artifacts", () => {
    const onCreateArtifact = vi.fn();
    vi.spyOn(globalThis, "fetch").mockResolvedValue(jsonResponse({
      presets: [{
        id: "openai-artifacts",
        name: "OpenAI Artifacts",
        provider: "openai_compatible",
        providers: ["openai_compatible"],
        base_url: "https://models.example.test/v1",
        api_key: null,
        models: ["gpt-5-codex"],
        model_configs: [{ name: "gpt-5-codex" }]
      }]
    }));

    renderPanel({
      artifactModelAgent: "codex",
      artifactModelSelection: {
        preset_id: "openai-artifacts",
        model: "gpt-5-codex",
        codex_model_reasoning_effort: "high"
      },
      onCreateArtifact
    });

    clickButton("Generate Trace");

    expect(onCreateArtifact).toHaveBeenCalledWith(
      "client-1",
      "window-1",
      "agent_trace_graph",
      "terminal",
      {
        preset_id: "openai-artifacts",
        model: "gpt-5-codex",
        codex_model_reasoning_effort: "high"
      }
    );
  });

  it("adds page review cards to project todos", () => {
    const onCreatePageReviewTodo = vi.fn();
    const artifact = pageReviewArtifact({
      artifact_kind: "page_review_cards",
      title: "Page review",
      page: "/settings",
      review_scope: "Settings page",
      executive_summary: "Two improvements",
      cards: [
        {
          id: "PRC-001",
          title: "Clarify empty state",
          type: "interaction",
          priority: "P1",
          severity: "high",
          proposal: "Show an action next to the empty state."
        }
      ]
    });

    renderPanel({
      artifactItems: [terminalArtifactItem(artifact)],
      selectedItem: terminalArtifactItem(artifact),
      selectedItemCanDisplay: true,
      selectedItemReady: true,
      selectedItemSrcDoc: "<html><body>review</body></html>",
      onCreatePageReviewTodo
    });

    clickButton("Add Todo");

    expect(onCreatePageReviewTodo).toHaveBeenCalledWith(
      expect.objectContaining({ id: "artifact-1" }),
      "PRC-001"
    );
  });

  it("disables adding page review cards when the window has no project path", () => {
    const onCreatePageReviewTodo = vi.fn();
    const artifact = pageReviewArtifact({
      artifact_kind: "page_review_cards",
      cards: [{ id: "PRC-001", title: "Clarify empty state", proposal: "Show an action." }]
    });

    renderPanel({
      projectPath: null,
      artifactItems: [terminalArtifactItem(artifact)],
      selectedItem: terminalArtifactItem(artifact),
      selectedItemCanDisplay: true,
      selectedItemReady: true,
      selectedItemSrcDoc: "<html><body>review</body></html>",
      onCreatePageReviewTodo
    });

    const button = Array.from(container?.querySelectorAll("button") ?? [])
      .find((candidate) => candidate.textContent === "Add Todo");

    expect(button).toBeInstanceOf(HTMLButtonElement);
    expect((button as HTMLButtonElement).disabled).toBe(true);
    expect(onCreatePageReviewTodo).not.toHaveBeenCalled();
  });

  it("bridges artifact iframe project todo create messages", async () => {
    const artifact = pageReviewArtifact({
      artifact_kind: "custom_cards",
      cards: []
    });
    const onCreateProjectTodoFromArtifact = vi.fn().mockResolvedValue(todo({
      id: "todo-7",
      title: "Iframe card"
    }));

    renderPanel({
      artifactItems: [terminalArtifactItem(artifact)],
      selectedItem: terminalArtifactItem(artifact),
      selectedItemCanDisplay: true,
      selectedItemReady: true,
      selectedItemSrcDoc: "<html><body>custom cards</body></html>",
      onCreateProjectTodoFromArtifact
    });

    const iframe = container?.querySelector("iframe");
    if (!(iframe instanceof HTMLIFrameElement) || iframe.contentWindow === null) {
      throw new Error("iframe not rendered");
    }
    act(() => {
      window.dispatchEvent(new MessageEvent("message", {
        source: iframe.contentWindow,
        data: {
          type: ARTIFACT_PROJECT_TODO_CREATE_MESSAGE,
          version: ARTIFACT_PROJECT_TODO_MESSAGE_VERSION,
          card: {
            title: "Iframe card",
            description: "From artifact HTML"
          }
        }
      }));
    });
    await act(async () => {
      await new Promise((resolve) => setTimeout(resolve, 0));
    });

    expect(onCreateProjectTodoFromArtifact).toHaveBeenCalledWith(
      {
        title: "Iframe card",
        description: "From artifact HTML"
      },
      "artifact-1"
    );
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
      created_at: "2026-06-06T00:00:00Z",
      updated_at: "2026-06-06T00:00:00Z"
    },
    title: "Iframe card",
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
    created_at: "2026-06-06T00:00:00Z",
    updated_at: "2026-06-06T00:00:00Z",
    ...overrides
  };
}
