import { act } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  cleanupProjectTodoTest,
  defaultTodoType,
  renderWithQuery,
  setupProjectTodoTest,
  todo,
  waitForButton,
  waitForElement,
  waitForElementText,
  waitForRequests
} from "./projectTodoTestHarness";
import { ProjectTodoPanel } from "../src/components/ProjectTodoPanel";
import type { ArtifactPluginDescriptor, ProjectTodo, ProjectTodoArtifact, ProjectTodoStatus } from "../src/types";

const apiMocks = vi.hoisted(() => ({
  commentProjectTodo: vi.fn(),
  createProjectTodo: vi.fn(),
  createTerminalArtifact: vi.fn(),
  deleteProjectTodo: vi.fn(),
  deleteProjectTodoAttachment: vi.fn(),
  downloadProjectTodoAttachment: vi.fn(),
  dispatchProjectTodo: vi.fn(),
  dispatchProjectTodoReview: vi.fn(),
  fetchAgentClients: vi.fn(),
  fetchAgentProfileConfig: vi.fn(),
  fetchAgentProfiles: vi.fn(),
  fetchArtifactPlugins: vi.fn(),
  fetchAgentRecordChat: vi.fn(),
  fetchAgentRecordDetail: vi.fn(),
  fetchClientAgentConfig: vi.fn(),
  fetchProjectTodoTypes: vi.fn(),
  fetchProjectTodo: vi.fn(),
  fetchProjectTodoHistory: vi.fn(),
  fetchProjectTodos: vi.fn(),
  fetchSystemModelPresets: vi.fn(),
  fetchWindow: vi.fn(),
  fetchWindowActivity: vi.fn(),
  linkProjectTodoArtifact: vi.fn(),
  retryProjectTodoArtifact: vi.fn(),
  restoreProjectTodoVersion: vi.fn(),
  uploadProjectTodoAttachmentImage: vi.fn(),
  upsertSystemProjectTodoType: vi.fn(),
  updateSystemProjectTodoType: vi.fn(),
  deleteSystemProjectTodoType: vi.fn(),
  updateProjectTodo: vi.fn()
}));

vi.mock("../src/api", () => apiMocks);

beforeEach(() => setupProjectTodoTest(apiMocks));
afterEach(cleanupProjectTodoTest);

const artifactPlugin: ArtifactPluginDescriptor = {
  domain: "terminal",
  artifact_kind: "agent_trace_graph",
  label: "Agent Trace Graph",
  default_title: "Agent Trace Graph",
  origin: "built_in",
  editable: false,
  plugin_format: "legacy_python",
  downloadable: false
};
const listButtonTextByStatus: Record<ProjectTodoStatus, string> = {
  TODO: "Fix dispatchTodo",
  BLOCKED: "Fix dispatchBlocked",
  DISPATCHED: "Fix dispatchRunning",
  AWAITING_REVIEW: "Fix dispatchReview",
  DONE: "Fix dispatchDone"
};

describe("ProjectTodoPanel detail dialog", () => {
  it("opens from list metadata before the full detail request finishes", async () => {
    apiMocks.fetchProjectTodos.mockResolvedValue({
      todos: [{ ...todo, description: undefined } as ProjectTodo]
    });
    apiMocks.fetchProjectTodo.mockImplementation(() => new Promise(() => {}));
    renderWithQuery(<ProjectTodoPanel clientId="client-1" projectPath="/workspace" onSelectWindow={() => {}} />);

    const row = await waitForButton("Fix dispatchTodo");
    act(() => row.click());

    await waitForElementText(".project-todo-detail-dialog", "Fix dispatch");
    const editDescriptionButton = await waitForElement(
      ".project-todo-detail-dialog .project-todo-description-edit-button"
    ) as HTMLButtonElement;
    expect(editDescriptionButton.disabled).toBe(true);
    expect(apiMocks.fetchProjectTodo).toHaveBeenCalledWith("client-1", "/workspace", "todo-1");
  });

  it("shows the card type in the detail header and metadata", async () => {
    const researchTodo: ProjectTodo = {
      ...todo,
      todo_type_id: "research",
      todo_type: {
        ...defaultTodoType,
        id: "research",
        name: "Research"
      }
    };
    apiMocks.fetchProjectTodos.mockResolvedValue({ todos: [researchTodo] });
    renderWithQuery(<ProjectTodoPanel clientId="client-1" projectPath="/workspace" onSelectWindow={() => {}} />);

    const row = await waitForButton("Fix dispatchTodo");
    act(() => row.click());

    await waitForElementText(".project-todo-detail-badges .project-todo-type-pill", "Research");
    await waitForElementText(".project-todo-metadata-panel", "Research");
  });

  it("updates the card type from an open TODO detail dialog", async () => {
    const researchType = {
      ...defaultTodoType,
      id: "research",
      name: "Research",
      agent: "codex",
      agent_profile_id: "research-profile",
      artifact_kinds: ["agent_trace_graph"]
    };
    apiMocks.fetchProjectTodoTypes.mockResolvedValue({ todo_types: [defaultTodoType, researchType] });
    apiMocks.updateProjectTodo.mockResolvedValue({
      ...todo,
      todo_type_id: "research",
      todo_type: researchType,
      assigned_agent: "codex",
      agent_profile_id: "research-profile",
      artifact_kinds: ["agent_trace_graph"]
    });
    renderWithQuery(<ProjectTodoPanel clientId="client-1" projectPath="/workspace" onSelectWindow={() => {}} />);

    const row = await waitForButton("Fix dispatchTodo");
    act(() => row.click());
    const expandButton = await waitForElement(
      ".project-todo-detail-dialog .project-todo-metadata-toggle"
    ) as HTMLButtonElement;
    act(() => expandButton.click());
    const selector = await waitForElement(
      ".project-todo-detail-dialog .project-todo-type-select"
    ) as HTMLSelectElement;

    act(() => {
      selector.value = "research";
      selector.dispatchEvent(new Event("change", { bubbles: true }));
    });
    await waitForRequests();

    expect(apiMocks.updateProjectTodo).toHaveBeenCalledWith("client-1", "/workspace", "todo-1", {
      todo_type_id: "research"
    });
  });

  it("renders dependency and dependent lists in the detail dialog", async () => {
    const relatedTodo: ProjectTodo = {
      ...todo,
      queued_dispatch: true,
      dependencies: [{
        id: "todo-2",
        title: "Build API",
        status: "AWAITING_REVIEW",
        completed_at: null
      }],
      dependents: [{
        id: "todo-3",
        title: "Write docs",
        status: "TODO",
        completed_at: null
      }],
      parent_todo_id: "todo-parent",
      parent_todo: {
        id: "todo-parent",
        title: "Parent feature",
        status: "TODO",
        completed_at: null
      },
      child_todos: [{
        id: "todo-child",
        title: "Child task",
        status: "BLOCKED",
        completed_at: null
      }]
    };
    apiMocks.fetchProjectTodos.mockResolvedValue({ todos: [{ ...relatedTodo, description: undefined } as ProjectTodo] });
    apiMocks.fetchProjectTodo.mockResolvedValue(relatedTodo);
    renderWithQuery(<ProjectTodoPanel clientId="client-1" projectPath="/workspace" onSelectWindow={() => {}} />);

    const row = await waitForButton(listButtonTextByStatus.TODO);
    act(() => row.click());
    expect(apiMocks.fetchProjectTodo).toHaveBeenCalledWith("client-1", "/workspace", "todo-1");
    await waitForElementText(".project-todo-relations", "Build API");
    await waitForElementText(".project-todo-relations", "Write docs");
    await waitForElementText(".project-todo-relations", "Parent feature");
    await waitForElementText(".project-todo-child-cards-panel", "Child task");

    expect(document.body.querySelector(".project-todo-relations")?.textContent).toContain("Queued");
  });

  it("hides empty related card groups in the detail dialog", async () => {
    const relatedTodo: ProjectTodo = {
      ...todo,
      queued_dispatch: true,
      parent_todo: null,
      child_todos: [],
      dependencies: [{
        id: "todo-2",
        title: "Build API",
        status: "AWAITING_REVIEW",
        completed_at: null
      }],
      dependents: []
    };
    apiMocks.fetchProjectTodos.mockResolvedValue({ todos: [{ ...relatedTodo, description: undefined } as ProjectTodo] });
    apiMocks.fetchProjectTodo.mockResolvedValue(relatedTodo);
    renderWithQuery(<ProjectTodoPanel clientId="client-1" projectPath="/workspace" onSelectWindow={() => {}} />);

    const row = await waitForButton(listButtonTextByStatus.TODO);
    act(() => row.click());
    const relations = await waitForElementText(".project-todo-relations", "Build API");

    expect(relations.textContent).not.toContain("No parent card");
    expect(relations.textContent).not.toContain("No child cards");
    expect(relations.textContent).not.toContain("No downstream todos");
  });

  it("hides the related cards section when there are no related cards", async () => {
    const unrelatedTodo: ProjectTodo = {
      ...todo,
      queued_dispatch: true,
      parent_todo: null,
      child_todos: [],
      dependencies: [],
      dependents: []
    };
    apiMocks.fetchProjectTodos.mockResolvedValue({ todos: [{ ...unrelatedTodo, description: undefined } as ProjectTodo] });
    apiMocks.fetchProjectTodo.mockResolvedValue(unrelatedTodo);
    renderWithQuery(<ProjectTodoPanel clientId="client-1" projectPath="/workspace" onSelectWindow={() => {}} />);

    const row = await waitForButton(listButtonTextByStatus.TODO);
    act(() => row.click());
    await waitForElement(".project-todo-detail-dialog");

    expect(document.body.querySelector(".project-todo-relations")).toBeNull();
  });

  it("opens a linked artifact from the detail dialog", async () => {
    const onOpenArtifact = vi.fn();
    const linkedArtifact: ProjectTodoArtifact = {
      id: "todo-artifact-link-1",
      artifact_id: "artifact-1",
      client_id: "client-1",
      window_id: "window-2",
      source_window_id: "window-2",
      ephemeral_window_id: "window-artifact-1",
      artifact_scope: "terminal",
      project_path: null,
      review_run_id: null,
      created_by_window_id: "window-2",
      title: "Fix dispatch - Agent Trace Graph",
      artifact_kind: "agent_trace_graph",
      status: "RUNNING",
      purpose: "todo_artifact",
      agent_name: "codex",
      agent_status: {
        state: "WORKING",
        label: "Working",
        color: "green",
        last_activity_at: null
      },
      metadata_json: { project_todo_id: "todo-1", purpose: "todo_artifact" },
      last_error: null,
      started_at: "2026-06-05T00:01:00Z",
      completed_at: null,
      created_at: "2026-06-05T00:00:00Z",
      updated_at: "2026-06-05T00:01:00Z"
    };
    apiMocks.fetchProjectTodos.mockResolvedValue({
      todos: [{ ...todo, description: undefined, artifacts: undefined } as ProjectTodo]
    });
    apiMocks.fetchProjectTodo.mockResolvedValue({ ...todo, artifacts: [linkedArtifact] });
    renderWithQuery(
      <ProjectTodoPanel
        clientId="client-1"
        projectPath="/workspace"
        onSelectWindow={() => {}}
        onOpenArtifact={onOpenArtifact}
      />
    );

    const row = await waitForButton(listButtonTextByStatus.TODO);
    act(() => row.click());
    const artifactRow = await waitForElementText(".project-todo-artifacts button", "Fix dispatch - Agent Trace Graph");
    act(() => {
      (artifactRow as HTMLButtonElement).click();
    });

    expect(onOpenArtifact).toHaveBeenCalledWith(linkedArtifact, "/workspace");
  });

  it("previews an attachment in a dismissible dialog", async () => {
    const openWindow = vi.spyOn(window, "open").mockReturnValue(null);
    const todoWithAttachment: ProjectTodo = {
      ...todo,
      attachments: [{
        id: "attachment-1",
        todo_id: "todo-1",
        filename: "screen.png",
        content_type: "image/png",
        size_bytes: 12,
        status: "uploaded",
        uploaded_at: "2026-06-05T00:00:00Z",
        created_at: "2026-06-05T00:00:00Z",
        updated_at: "2026-06-05T00:00:00Z"
      }]
    };
    apiMocks.fetchProjectTodos.mockResolvedValue({
      todos: [{ ...todoWithAttachment, description: undefined } as ProjectTodo]
    });
    apiMocks.fetchProjectTodo.mockResolvedValue(todoWithAttachment);
    renderWithQuery(<ProjectTodoPanel clientId="client-1" projectPath="/workspace" onSelectWindow={() => {}} />);

    const row = await waitForButton(listButtonTextByStatus.TODO);
    act(() => row.click());
    const attachmentButton = await waitForElementText(
      ".project-todo-attachments-panel .project-todo-attachment-open",
      "screen.png"
    ) as HTMLButtonElement;
    act(() => attachmentButton.click());
    const preview = await waitForElement(".project-todo-attachment-preview-dialog");

    expect(apiMocks.downloadProjectTodoAttachment).toHaveBeenCalledWith("client-1", "/workspace", "todo-1", "attachment-1");
    expect(openWindow).not.toHaveBeenCalled();
    expect(preview.textContent).toContain("screen.png");
    expect(preview.querySelector("img")?.getAttribute("src")).toBe("https://objects.example/screen.png");

    act(() => {
      window.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape", bubbles: true }));
    });
    await waitForRequests();

    expect(document.body.querySelector(".project-todo-attachment-preview-dialog")).toBeNull();
    expect(document.body.querySelector(".project-todo-detail-dialog")).toBeInstanceOf(HTMLElement);
  });

  it("updates requested artifacts from an editable detail dialog", async () => {
    apiMocks.fetchArtifactPlugins.mockResolvedValue({
      plugins: [
        artifactPlugin,
        {
          ...artifactPlugin,
          artifact_kind: "release_readiness",
          label: "Release Readiness",
          default_title: "Release Readiness"
        }
      ]
    });
    apiMocks.updateProjectTodo.mockResolvedValue({ ...todo, artifact_kinds: ["agent_trace_graph"] });
    renderWithQuery(<ProjectTodoPanel clientId="client-1" projectPath="/workspace" onSelectWindow={() => {}} />);

    const row = await waitForButton(listButtonTextByStatus.TODO);
    act(() => row.click());
    const selector = await waitForElement(".project-todo-detail-dialog .project-todo-detail-artifacts");
    expect(selector.querySelector(".project-todo-artifact-options")).toBeNull();

    const input = await waitForElement(
      ".project-todo-detail-dialog .project-todo-detail-artifacts .project-todo-artifact-select-input"
    ) as HTMLInputElement;
    expect(input.getAttribute("aria-expanded")).toBe("false");
    act(() => input.focus());

    const artifactOption = await waitForElement(
      ".project-todo-detail-dialog .project-todo-detail-artifacts input[type='checkbox']"
    ) as HTMLInputElement;
    expect(artifactOption.checked).toBe(false);
    expect(input.getAttribute("aria-expanded")).toBe("true");

    act(() => artifactOption.click());
    await waitForRequests();
    const selectedChip = await waitForElementText(
      ".project-todo-detail-dialog .project-todo-detail-artifacts .project-todo-artifact-selected-chip",
      "Agent Trace Graph"
    );
    const selectedOptions = Array.from(document.body.querySelectorAll(
      ".project-todo-detail-dialog .project-todo-detail-artifacts .project-todo-artifact-options label"
    ));

    expect(selectedChip.querySelector("button[aria-label='Remove Agent Trace Graph']")).toBeInstanceOf(HTMLButtonElement);
    expect(selectedOptions.map((option) => option.textContent?.trim())).toEqual(["Release Readiness"]);

    expect(apiMocks.updateProjectTodo).toHaveBeenCalledWith("client-1", "/workspace", "todo-1", {
      artifact_kinds: ["agent_trace_graph"]
    });

    apiMocks.updateProjectTodo.mockClear();
    apiMocks.updateProjectTodo.mockResolvedValue({ ...todo, artifact_kinds: [] });
    act(() => {
      (selectedChip.querySelector("button") as HTMLButtonElement).click();
    });
    await waitForRequests();

    expect(apiMocks.updateProjectTodo).toHaveBeenCalledWith("client-1", "/workspace", "todo-1", {
      artifact_kinds: []
    });
  });

  it("generates the selected artifact type from the detail action rail", async () => {
    apiMocks.fetchArtifactPlugins.mockResolvedValue({
      plugins: [
        artifactPlugin,
        {
          ...artifactPlugin,
          artifact_kind: "qa_release_readiness",
          label: "Release Readiness",
          default_title: "Release Readiness"
        },
        {
          ...artifactPlugin,
          domain: "project",
          artifact_kind: "user_journey",
          label: "User Journey",
          default_title: "User Journey"
        }
      ]
    });
    apiMocks.fetchProjectTodos.mockResolvedValue({
      todos: [{
        ...todo,
        assigned_window_id: "window-2",
        artifact_kinds: ["qa_release_readiness"]
      }]
    });
    renderWithQuery(<ProjectTodoPanel clientId="client-1" projectPath="/workspace" onSelectWindow={() => {}} />);

    const row = await waitForButton(listButtonTextByStatus.TODO);
    act(() => row.click());
    const selector = await waitForElement(
      ".project-todo-detail-dialog .project-todo-generate-artifact-select"
    ) as HTMLSelectElement;
    expect(selector.value).toBe("qa_release_readiness");

    act(() => {
      selector.value = "project:user_journey";
      selector.dispatchEvent(new Event("change", { bubbles: true }));
    });
    const generateButton = await waitForElementText(
      ".project-todo-detail-dialog .project-todo-generate-artifact-control button",
      "Generate artifact"
    ) as HTMLButtonElement;
    act(() => generateButton.click());
    await waitForRequests();

    expect(apiMocks.createTerminalArtifact).toHaveBeenCalledWith("client-1", "window-2", {
      artifact_kind: "user_journey",
      artifact_scope: "project",
      project_path: "/workspace",
      title: "Fix dispatch - User Journey",
      metadata_json: { project_todo_id: "todo-1", purpose: "todo_artifact" }
    });
    expect(apiMocks.linkProjectTodoArtifact).toHaveBeenCalledWith("client-1", "/workspace", "todo-1", {
      artifact_id: "artifact-1",
      purpose: "todo_artifact"
    });
  });

  it.each(["AWAITING_REVIEW", "DONE", "BLOCKED"] as ProjectTodoStatus[])(
    "does not expose requested artifact editing for %s cards",
    async (status) => {
      apiMocks.fetchArtifactPlugins.mockResolvedValue({ plugins: [artifactPlugin] });
      apiMocks.fetchProjectTodos.mockResolvedValue({
        todos: [{ ...todo, status, artifact_kinds: ["agent_trace_graph"] }]
      });
      renderWithQuery(<ProjectTodoPanel clientId="client-1" projectPath="/workspace" onSelectWindow={() => {}} />);

      const row = await waitForButton(listButtonTextByStatus[status]);
      act(() => row.click());
      await waitForElement(".project-todo-detail-dialog");

      expect(document.body.querySelector(".project-todo-detail-dialog .project-todo-detail-artifacts")).toBeNull();
    }
  );

});
