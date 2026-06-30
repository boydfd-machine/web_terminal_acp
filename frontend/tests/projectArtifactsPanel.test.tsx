import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ProjectArtifactsPanel } from "../src/components/ProjectArtifactsPanel";
import type { ProjectArtifactList, TerminalArtifact } from "../src/types";

globalThis.IS_REACT_ACT_ENVIRONMENT = true;

const apiMocks = vi.hoisted(() => ({
  fetchProjectArtifactHtml: vi.fn(),
  fetchProjectArtifacts: vi.fn()
}));

vi.mock("../src/api", () => apiMocks);

let root: Root | null = null;
let container: HTMLDivElement | null = null;
let queryClient: QueryClient | null = null;

function artifact(overrides: Partial<TerminalArtifact> = {}): TerminalArtifact {
  return {
    id: "artifact-1",
    client_id: "client-1",
    virtual_window_id: "window-1",
    source_window_id: "window-1",
    ephemeral_window_id: null,
    artifact_scope: "project",
    project_path: "/workspace/project",
    artifact_kind: "user_journey",
    title: "User Journey",
    status: "SUCCEEDED",
    content_json: null,
    display_html: null,
    metadata_json: null,
    last_error: null,
    started_at: null,
    completed_at: "2026-06-08T10:00:00Z",
    created_at: "2026-06-08T10:00:00Z",
    updated_at: "2026-06-08T10:00:00Z",
    ...overrides
  };
}

function artifactList(projectArtifact: TerminalArtifact): ProjectArtifactList {
  return {
    project_path: "/workspace/project",
    artifacts: [projectArtifact],
    artifact_groups: [{
      artifact_kind: projectArtifact.artifact_kind,
      latest_artifact: projectArtifact,
      version_count: 1,
      versions: [{
        artifact: projectArtifact,
        version_number: 1,
        created_at: projectArtifact.created_at,
        completed_at: projectArtifact.completed_at,
        source_window_id: projectArtifact.source_window_id,
        source_window_title: "Summary terminal",
        virtual_window_title: "Summary terminal"
      }]
    }],
    total: 1,
    limit: 50,
    offset: 0,
    has_more: false
  };
}

function renderPanel(): void {
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
        <ProjectArtifactsPanel clientId="client-1" projectPath="/workspace/project" />
      </QueryClientProvider>
    );
  });
}

async function flushPromises(): Promise<void> {
  await act(async () => {
    await new Promise((resolve) => setTimeout(resolve, 0));
  });
}

async function waitForElement<T extends Element>(
  selector: string,
  guard: (element: Element) => element is T
): Promise<T> {
  for (let attempt = 0; attempt < 30; attempt += 1) {
    await flushPromises();
    const element = container?.querySelector(selector);
    if (element !== undefined && element !== null && guard(element)) {
      return element;
    }
  }
  throw new Error(`Element ${selector} was not ready`);
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
  apiMocks.fetchProjectArtifactHtml.mockReset();
  apiMocks.fetchProjectArtifacts.mockReset();
});

describe("ProjectArtifactsPanel", () => {
  it("opens the selected project artifact in a fullscreen dialog", async () => {
    const projectArtifact = artifact();
    apiMocks.fetchProjectArtifacts.mockResolvedValue(artifactList(projectArtifact));
    apiMocks.fetchProjectArtifactHtml.mockResolvedValue("<html><body>User Journey HTML</body></html>");

    renderPanel();

    const fullscreenButton = await waitForElement(
      'button[aria-label="Open artifact fullscreen"]',
      (element): element is HTMLButtonElement => element instanceof HTMLButtonElement
    );

    expect(container?.querySelector(".artifact-fullscreen")).toBeNull();

    act(() => {
      fullscreenButton.click();
    });

    const dialog = await waitForElement(
      ".artifact-fullscreen",
      (element): element is HTMLElement => element instanceof HTMLElement
    );
    const iframe = dialog.querySelector("iframe");

    expect(dialog.getAttribute("role")).toBe("dialog");
    expect(dialog.textContent).toContain("User Journey");
    expect(iframe).toBeInstanceOf(HTMLIFrameElement);
    expect(iframe?.getAttribute("srcdoc")).toContain("User Journey HTML");
  });
});
