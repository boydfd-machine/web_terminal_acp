import { act } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ProjectTodoCreateForm } from "../src/components/ProjectTodoCreateForm";
import { projectTodoCreateDraftStorageKey } from "../src/components/projectTodoCreateDraftStorage";
import type { TerminalArtifact } from "../src/types";
import {
  cleanupProjectTodoTest,
  renderWithQuery,
  setValue,
  setupProjectTodoTest,
  waitForElement,
  waitForElementText,
  waitForRequests
} from "./projectTodoTestHarness";

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
  fetchClientSystemAgentConfig: vi.fn(),
  fetchProjectTodo: vi.fn(),
  fetchProjectTodoHistory: vi.fn(),
  fetchProjectTodoTypes: vi.fn(),
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
const projectApiMocks = vi.hoisted(() => ({
  fetchProjectArtifacts: vi.fn()
}));

vi.mock("../src/api", () => apiMocks);
vi.mock("../src/apiProjects", () => projectApiMocks);

beforeEach(() => {
  setupProjectTodoTest(apiMocks);
  window.localStorage.clear();
});
afterEach(cleanupProjectTodoTest);

describe("ProjectTodoInputArtifactIdsField", () => {
  it("selects input artifacts from the project artifact dropdown", async () => {
    projectApiMocks.fetchProjectArtifacts.mockResolvedValue({
      project_path: "/workspace",
      artifacts: [
        projectArtifact({
          id: "artifact-journey",
          artifact_kind: "user_journey",
          title: "User Journey Current"
        }),
        projectArtifact({
          id: "artifact-flow",
          virtual_window_id: "window-artifact-2",
          artifact_kind: "flow_model",
          title: "Flow Model Current",
          completed_at: "2026-06-05T00:04:00Z"
        })
      ],
      total: 2,
      limit: 100,
      offset: 0,
      has_more: false
    });
    apiMocks.createProjectTodo.mockResolvedValue({ id: "todo-4", title: "Implement flow update" });
    renderWithQuery(
      <ProjectTodoCreateForm
        clientId="client-1"
        projectPath="/workspace"
        onCreated={() => {}}
        onPendingChange={() => {}}
      />
    );
    const titleInput = await waitForElement(".project-todo-form input") as HTMLInputElement;
    const descriptionInput = await waitForElement(".project-todo-form textarea") as HTMLTextAreaElement;
    const inputArtifactSearch = await waitForElement(
      ".project-todo-input-artifacts .project-todo-artifact-select-input"
    ) as HTMLInputElement;

    setValue(titleInput, "Implement flow update");
    setValue(descriptionInput, "Use the current flow artifact");
    act(() => inputArtifactSearch.focus());
    await waitForElementText(".project-todo-input-artifacts .project-todo-artifact-options label", "User Journey Current");
    expect(projectApiMocks.fetchProjectArtifacts).toHaveBeenCalledWith("client-1", "/workspace", 100, 0);

    setValue(inputArtifactSearch, "flow");
    await waitForRequests();
    const visibleOptions = Array.from(document.body.querySelectorAll(
      ".project-todo-input-artifacts .project-todo-artifact-options label"
    ));
    expect(visibleOptions).toHaveLength(1);
    expect(visibleOptions[0]?.textContent).toContain("Flow Model Current");

    act(() => {
      (visibleOptions[0]?.querySelector("input") as HTMLInputElement).click();
    });
    await waitForRequests();
    await waitForElementText(".project-todo-input-artifacts .project-todo-artifact-selected-chip", "Flow Model Current");
    expect(JSON.parse(window.localStorage.getItem(projectTodoCreateDraftStorageKey("client-1", "/workspace")) ?? "null")).toEqual({
      title: "Implement flow update",
      description: "Use the current flow artifact",
      input_artifact_ids: ["artifact-flow"]
    });

    act(() => {
      (document.body.querySelector(".project-todo-form button[data-create-action='add']") as HTMLButtonElement).click();
    });
    await waitForRequests();

    expect(apiMocks.createProjectTodo).toHaveBeenCalledWith("client-1", "/workspace", {
      title: "Implement flow update",
      description: "Use the current flow artifact",
      input_artifact_ids: ["artifact-flow"]
    });
  });
});

function projectArtifact(overrides: Partial<TerminalArtifact>): TerminalArtifact {
  return {
    id: "artifact-1",
    client_id: "client-1",
    virtual_window_id: "window-artifact-1",
    source_window_id: null,
    ephemeral_window_id: null,
    artifact_scope: "project",
    project_path: "/workspace",
    artifact_kind: "user_journey",
    title: "Project Artifact",
    status: "SUCCEEDED",
    content_json: null,
    display_html: null,
    metadata_json: null,
    last_error: null,
    started_at: null,
    completed_at: "2026-06-05T00:02:00Z",
    created_at: "2026-06-05T00:00:00Z",
    updated_at: "2026-06-05T00:02:00Z",
    ...overrides
  };
}
