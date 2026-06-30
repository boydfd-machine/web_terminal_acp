import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, describe, expect, it, vi } from "vitest";

import {
  ARTIFACT_PROJECT_TODO_CREATE_MESSAGE,
  ARTIFACT_PROJECT_TODO_MESSAGE_VERSION
} from "../src/artifactProjectTodoBridge";
import { ArtifactQuickOpen, ArtifactResultViewer } from "../src/components/ArtifactQuickOpen";
import type { TerminalArtifact } from "../src/types";

globalThis.IS_REACT_ACT_ENVIRONMENT = true;

const apiMocks = vi.hoisted(() => ({
  createProjectTodoFromArtifactCard: vi.fn(),
  fetchProjectArtifactHtml: vi.fn(),
  fetchTerminalArtifactHtml: vi.fn()
}));

vi.mock("../src/api", () => apiMocks);

let root: Root | null = null;
let container: HTMLDivElement | null = null;
let queryClient: QueryClient | null = null;

function artifact(overrides: Partial<TerminalArtifact>): TerminalArtifact {
  return {
    id: "artifact-1",
    client_id: "client-1",
    virtual_window_id: "window-1",
    source_window_id: "window-1",
    ephemeral_window_id: "ephemeral-1",
    artifact_scope: "terminal",
    project_path: null,
    artifact_kind: "agent_trace_graph",
    title: "Trace graph",
    status: "RUNNING",
    content_json: null,
    display_html: null,
    metadata_json: null,
    last_error: null,
    started_at: null,
    completed_at: null,
    created_at: "2026-06-02T00:00:00Z",
    updated_at: "2026-06-02T00:00:00Z",
    ...overrides
  };
}

function renderQuickOpen(props: Partial<Parameters<typeof ArtifactQuickOpen>[0]> = {}) {
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
        <ArtifactQuickOpen
          isOpen
          artifacts={[]}
          isLoading={false}
          isError={false}
          onClose={() => {}}
          onOpenTerminal={() => {}}
          onOpenResult={() => {}}
          {...props}
        />
      </QueryClientProvider>
    );
  });
}

function renderResultViewer(props: Partial<Parameters<typeof ArtifactResultViewer>[0]> = {}) {
  container = document.createElement("div");
  document.body.appendChild(container);
  queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false }
    }
  });
  root = createRoot(container);
  const resultArtifact = artifact({
    id: "requirement-artifact-1",
    title: "Requirement Review Report",
    artifact_kind: "requirement_review_report",
    status: "SUCCEEDED",
    ephemeral_window_id: null
  });
  const effectiveArtifact = props.artifact ?? resultArtifact;
  act(() => {
    root?.render(
      <QueryClientProvider client={queryClient as QueryClient}>
        <ArtifactResultViewer
          clientId="client-1"
          windowId="window-1"
          artifact={effectiveArtifact}
          projectPath="/workspace/project"
          onClose={() => {}}
          {...props}
        />
      </QueryClientProvider>
    );
  });
  return effectiveArtifact;
}

function dialog(): HTMLElement {
  const element = container?.querySelector(".artifact-quick-open");
  if (!(element instanceof HTMLElement)) {
    throw new Error("artifact quick-open dialog not found");
  }
  return element;
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
  apiMocks.createProjectTodoFromArtifactCard.mockReset();
  apiMocks.fetchProjectArtifactHtml.mockReset();
  apiMocks.fetchTerminalArtifactHtml.mockReset();
  vi.restoreAllMocks();
});

describe("ArtifactQuickOpen", () => {
  it("opens running and retained completed artifacts in the terminal tab", () => {
    const running = artifact({ id: "running", title: "Running trace", status: "RUNNING" });
    const completed = artifact({ id: "done", title: "Finished trace", status: "SUCCEEDED" });
    const onOpenTerminal = vi.fn();

    renderQuickOpen({
      artifacts: [completed, running],
      onOpenTerminal
    });

    expect(container?.textContent).toContain("Running trace");
    expect(container?.textContent).toContain("Finished trace");

    act(() => {
      dialog().dispatchEvent(new KeyboardEvent("keydown", {
        bubbles: true,
        cancelable: true,
        key: "Enter"
      }));
    });

    expect(onOpenTerminal).toHaveBeenCalledWith(completed);
  });

  it("omits completed artifacts whose terminal was cleaned up from the terminal tab", () => {
    const running = artifact({ id: "running", title: "Running trace", status: "RUNNING" });
    const completed = artifact({
      id: "done",
      title: "Finished trace",
      status: "SUCCEEDED",
      ephemeral_window_id: null
    });

    renderQuickOpen({
      artifacts: [completed, running]
    });

    expect(container?.textContent).toContain("Running trace");
    expect(container?.textContent).not.toContain("Finished trace");
  });

  it("switches tabs with Tab and opens finished artifact results", () => {
    const running = artifact({ id: "running", title: "Running trace", status: "RUNNING" });
    const completed = artifact({ id: "done", title: "Finished trace", status: "SUCCEEDED" });
    const onOpenResult = vi.fn();

    renderQuickOpen({
      artifacts: [completed, running],
      onOpenResult
    });

    act(() => {
      dialog().dispatchEvent(new KeyboardEvent("keydown", {
        bubbles: true,
        cancelable: true,
        key: "Tab"
      }));
    });

    expect(container?.textContent).toContain("Finished trace");
    expect(container?.textContent).not.toContain("Running trace");

    act(() => {
      dialog().dispatchEvent(new KeyboardEvent("keydown", {
        bubbles: true,
        cancelable: true,
        key: "Enter"
      }));
    });

    expect(onOpenResult).toHaveBeenCalledWith(completed);
  });

  it("lets result artifact HTML add cards to the project board", async () => {
    apiMocks.fetchTerminalArtifactHtml.mockResolvedValue("<html><body><button>Add to board</button></body></html>");
    apiMocks.createProjectTodoFromArtifactCard.mockResolvedValue({
      id: "todo-1",
      project_path: "/workspace/project",
      title: "Created card"
    });
    const resultArtifact = renderResultViewer();

    const iframe = await waitForIframe();

    const frameWindow = iframe.contentWindow as Window;
    act(() => {
      window.dispatchEvent(new MessageEvent("message", {
        source: frameWindow,
        data: {
          type: ARTIFACT_PROJECT_TODO_CREATE_MESSAGE,
          version: ARTIFACT_PROJECT_TODO_MESSAGE_VERSION,
          request_id: "request-1",
          card: {
            title: "在项目看板添加卡片类型过滤器",
            description: "Add a card type filter to the board.",
            todo_type_id: "ui-change",
            artifact_kinds: ["qa_ux_review"],
            status: "TODO",
            review_strategy: "LOCAL_CARD"
          }
        }
      }));
    });
    await flushPromises();

    expect(apiMocks.createProjectTodoFromArtifactCard).toHaveBeenCalledWith("client-1", "/workspace/project", {
      artifact_id: resultArtifact.id,
      card: {
        title: "在项目看板添加卡片类型过滤器",
        description: "Add a card type filter to the board.",
        todo_type_id: "ui-change",
        artifact_kinds: ["qa_ux_review"],
        status: "TODO",
        review_strategy: "LOCAL_CARD"
      },
      purpose: "artifact_card"
    });
  });

  it("uses the surrounding project path for terminal-scope linked artifact cards", async () => {
    apiMocks.fetchTerminalArtifactHtml.mockResolvedValue("<html><body><button>Add to board</button></body></html>");
    apiMocks.createProjectTodoFromArtifactCard.mockResolvedValue({
      id: "todo-1",
      project_path: "/workspace/project",
      title: "Created card"
    });
    const resultArtifact = renderResultViewer({
      artifact: artifact({
        id: "terminal-linked-artifact",
        title: "Requirement Review Report",
        artifact_kind: "requirement_review_report",
        artifact_scope: "terminal",
        project_path: null,
        status: "SUCCEEDED",
        ephemeral_window_id: null
      }),
      projectPath: "/workspace/project"
    });

    const iframe = await waitForIframe();

    act(() => {
      window.dispatchEvent(new MessageEvent("message", {
        source: iframe.contentWindow,
        data: {
          type: ARTIFACT_PROJECT_TODO_CREATE_MESSAGE,
          version: ARTIFACT_PROJECT_TODO_MESSAGE_VERSION,
          request_id: "request-2",
          card: {
            title: "Add the board card type filter",
            todo_type_id: "ui-change"
          }
        }
      }));
    });
    await flushPromises();

    expect(apiMocks.createProjectTodoFromArtifactCard).toHaveBeenCalledWith("client-1", "/workspace/project", {
      artifact_id: resultArtifact.id,
      card: {
        title: "Add the board card type filter",
        todo_type_id: "ui-change"
      },
      purpose: "artifact_card"
    });
  });
});

async function flushPromises(): Promise<void> {
  await act(async () => {
    await new Promise((resolve) => setTimeout(resolve, 0));
  });
}

async function waitForIframe(): Promise<HTMLIFrameElement> {
  for (let attempt = 0; attempt < 10; attempt += 1) {
    await flushPromises();
    const iframe = container?.querySelector("iframe");
    if (iframe instanceof HTMLIFrameElement) {
      return iframe;
    }
  }
  throw new Error("artifact iframe not found");
}
