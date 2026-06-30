import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, useState, type ReactNode } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { AppPromptProvider } from "../src/components/AppPromptProvider";
import { ProjectTodoPanel } from "../src/components/ProjectTodoPanel";
import { ProjectTodoCreateForm } from "../src/components/ProjectTodoCreateForm";
import { ProjectTodoSidebarControls } from "../src/components/ProjectTodoSidebarControls";
import { projectTodoCreateDraftStorageKey } from "../src/components/projectTodoCreateDraftStorage";
import type { ProjectTodoDateFilter } from "../src/features/projectTodos/projectTodoDateFilter";
import { defaultTodoType, todo } from "./projectTodoTestHarness";

globalThis.IS_REACT_ACT_ENVIRONMENT = true;

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
  fetchSystemModelPresets: vi.fn(),
  fetchProjectTodo: vi.fn(),
  fetchProjectTodoHistory: vi.fn(),
  fetchProjectTodoTypes: vi.fn(),
  fetchProjectTodos: vi.fn(),
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

let root: Root | null = null;
let container: HTMLDivElement | null = null;
let queryClient: QueryClient | null = null;

function renderWithQuery(element: ReactNode): void {
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
        <AppPromptProvider>{element}</AppPromptProvider>
      </QueryClientProvider>
    );
  });
}

async function waitForRequests(): Promise<void> {
  await act(async () => {
    await new Promise((resolve) => setTimeout(resolve, 0));
  });
}

async function waitForElement(selector: string): Promise<Element> {
  for (let attempt = 0; attempt < 20; attempt += 1) {
    await waitForRequests();
    const element = document.body.querySelector(selector);
    if (element !== null) {
      return element;
    }
  }
  throw new Error(`Element ${selector} was not ready`);
}

async function waitForElementText(selector: string, text: string): Promise<Element> {
  for (let attempt = 0; attempt < 20; attempt += 1) {
    await waitForRequests();
    const element = Array.from(document.body.querySelectorAll(selector)).find(
      (candidate) => candidate.textContent?.includes(text)
    );
    if (element !== undefined) {
      return element;
    }
  }
  throw new Error(`Element ${selector} containing ${text} was not ready`);
}

function setValue(target: HTMLInputElement | HTMLTextAreaElement, value: string): void {
  const prototype = target instanceof HTMLTextAreaElement ? HTMLTextAreaElement.prototype : HTMLInputElement.prototype;
  const setter = Object.getOwnPropertyDescriptor(prototype, "value")?.set;
  act(() => {
    setter?.call(target, value);
    target.dispatchEvent(new Event("input", { bubbles: true }));
  });
}

function setSelectValue(target: HTMLSelectElement, value: string): void {
  const setter = Object.getOwnPropertyDescriptor(HTMLSelectElement.prototype, "value")?.set;
  act(() => {
    setter?.call(target, value);
    target.dispatchEvent(new Event("input", { bubbles: true }));
    target.dispatchEvent(new Event("change", { bubbles: true }));
  });
}

function placeCaretAtEnd(target: HTMLInputElement | HTMLTextAreaElement): void {
  act(() => {
    target.setSelectionRange(target.value.length, target.value.length);
    target.dispatchEvent(new KeyboardEvent("keyup", { bubbles: true, key: "End" }));
  });
}

beforeEach(() => {
  vi.clearAllMocks();
  window.localStorage.clear();
  apiMocks.fetchAgentClients.mockResolvedValue({
    agent_clients: [{
      id: "codex",
      provider_id: "codex",
      label: "Codex",
      aliases: [],
      default_command: "codex",
      command_names: ["codex"],
      capabilities: { launch: true, client_config: true }
    }]
  });
  apiMocks.fetchAgentProfiles.mockResolvedValue({ profiles: [] });
  apiMocks.fetchArtifactPlugins.mockResolvedValue({ plugins: [] });
  apiMocks.fetchSystemModelPresets.mockResolvedValue({ presets: [] });
  apiMocks.fetchProjectTodoTypes.mockResolvedValue({ todo_types: [defaultTodoType] });
  apiMocks.fetchProjectTodos.mockResolvedValue({ todos: [] });
  apiMocks.fetchWindowActivity.mockResolvedValue({ windows: [] });
});

afterEach(() => {
  act(() => {
    root?.unmount();
  });
  document.body.replaceChildren();
  queryClient?.clear();
  root = null;
  container = null;
  queryClient = null;
  vi.restoreAllMocks();
});

describe("project todo create draft", () => {
  it("shows artifact selection in the sidebar quick create form", async () => {
    apiMocks.fetchArtifactPlugins.mockResolvedValue({
      plugins: [{
        domain: "terminal",
        artifact_kind: "qa_release_readiness",
        label: "Release Readiness",
        default_title: "Release Readiness",
        origin: "built_in",
        editable: false,
        plugin_format: "legacy_python",
        downloadable: false
      }]
    });
    apiMocks.createProjectTodo.mockResolvedValue({ id: "todo-9", title: "Quick release card" });
    renderWithQuery(
      <ProjectTodoSidebarControls
        clientId="client-1"
        projectPath="/workspace"
      />
    );
    const titleInput = await waitForElement(".project-todo-form input") as HTMLInputElement;
    const descriptionInput = await waitForElement(".project-todo-form textarea") as HTMLTextAreaElement;
    const artifactInput = await waitForElement(
      ".project-todo-form-artifacts .project-todo-artifact-select-input"
    ) as HTMLInputElement;

    act(() => artifactInput.focus());
    const artifactOption = await waitForElement(".project-todo-form-artifacts input[type='checkbox']") as HTMLInputElement;

    setValue(titleInput, "Quick release card");
    setValue(descriptionInput, "Need a release checklist");
    act(() => artifactOption.click());
    await waitForRequests();

    expect(JSON.parse(window.localStorage.getItem(projectTodoCreateDraftStorageKey("client-1", "/workspace")) ?? "null")).toEqual({
      title: "Quick release card",
      description: "Need a release checklist",
      artifact_kinds: ["qa_release_readiness"]
    });

    act(() => {
      (document.body.querySelector(".project-todo-form button[data-create-action='add']") as HTMLButtonElement).click();
    });
    await waitForRequests();

    expect(apiMocks.createProjectTodo).toHaveBeenCalledWith("client-1", "/workspace", {
      title: "Quick release card",
      description: "Need a release checklist",
      artifact_kinds: ["qa_release_readiness"]
    });
  });

  it("directly dispatches a quick sidebar card with default options", async () => {
    const createdTodo = {
      ...todo,
      id: "todo-10",
      title: "Direct dispatch",
      description: "Launch immediately",
      assigned_agent: "codex",
      agent_profile_id: null
    };
    apiMocks.createProjectTodo.mockResolvedValue(createdTodo);
    apiMocks.dispatchProjectTodo.mockResolvedValue({
      ...createdTodo,
      status: "DISPATCHED",
      dispatch_stage: "STARTING"
    });
    renderWithQuery(
      <ProjectTodoSidebarControls
        clientId="client-1"
        projectPath="/workspace"
      />
    );
    const titleInput = await waitForElement(".project-todo-form input") as HTMLInputElement;
    const descriptionInput = await waitForElement(".project-todo-form textarea") as HTMLTextAreaElement;

    setValue(titleInput, "Direct dispatch");
    setValue(descriptionInput, "Launch immediately");
    act(() => {
      (document.body.querySelector(".project-todo-form button[data-create-action='direct-dispatch']") as HTMLButtonElement).click();
    });
    await waitForRequests();

    expect(apiMocks.createProjectTodo).toHaveBeenCalledWith("client-1", "/workspace", {
      title: "Direct dispatch",
      description: "Launch immediately"
    });
    expect(apiMocks.dispatchProjectTodo).toHaveBeenCalledWith("client-1", "/workspace", "todo-10", {
      agent_launch: {
        agent: "codex",
        command: "codex",
        config: null,
        profile_id: null
      },
      dispatch_mode: "submit",
      dispatch_after_todo_ids: [],
      prompt: null
    });
    expect(document.body.querySelector(".terminal-create-modal")).toBeNull();
    expect(document.body.querySelector(".project-todo-dispatch-toast.success")?.textContent).toBe(
      "Dispatch started for Direct dispatch."
    );
  });

  it("ignores stale advanced draft settings when creating from the quick board form", async () => {
    const storageKey = projectTodoCreateDraftStorageKey("client-1", "/workspace");
    window.localStorage.setItem(storageKey, JSON.stringify({
      title: "Saved advanced title",
      description: "Saved advanced content",
      todo_type_id: "research",
      execution_kind: "PERIODIC",
      terminal_policy: "REUSE_LATEST",
      trigger_strategy: "CRON",
      cron_expression: "0 9 * * 1",
      artifact_kinds: ["agent_trace_graph"]
    }));
    apiMocks.createProjectTodo.mockResolvedValue({ id: "todo-7", title: "Saved advanced title" });
    renderWithQuery(
      <ProjectTodoCreateForm
        clientId="client-1"
        projectPath="/workspace"
        mode="quick"
        onCreated={() => {}}
        onPendingChange={() => {}}
      />
    );

    await waitForElement(".project-todo-form input");
    act(() => {
      (document.body.querySelector(".project-todo-form button[data-create-action='add']") as HTMLButtonElement).click();
    });
    await waitForRequests();

    expect(apiMocks.createProjectTodo).toHaveBeenCalledWith("client-1", "/workspace", {
      title: "Saved advanced title",
      description: "Saved advanced content"
    });
  });

  it("clears the persisted add-card draft after creating a todo", async () => {
    apiMocks.createProjectTodo.mockResolvedValue({ id: "todo-2", title: "Draft board card" });
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

    setValue(titleInput, "Draft board card");
    setValue(descriptionInput, "Ready to create");
    act(() => {
      (document.body.querySelector(".project-todo-form button[data-create-action='add']") as HTMLButtonElement).click();
    });
    await waitForRequests();

    expect(apiMocks.createProjectTodo).toHaveBeenCalledWith("client-1", "/workspace", {
      title: "Draft board card",
      description: "Ready to create"
    });
    expect(window.localStorage.getItem(projectTodoCreateDraftStorageKey("client-1", "/workspace"))).toBeNull();
    expect(titleInput.value).toBe("");
    expect(descriptionInput.value).toBe("");
  });

  it("persists a selected card type and sends it when creating a todo", async () => {
    apiMocks.fetchProjectTodoTypes.mockResolvedValue({
      todo_types: [
        defaultTodoType,
        {
          ...defaultTodoType,
          id: "research",
          name: "Research",
          description: "Collect background first",
          agent: "codex",
          artifact_kinds: ["deep_research_report"]
        }
      ]
    });
    apiMocks.createProjectTodo.mockResolvedValue({ id: "todo-5", title: "Research options" });
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
    const typeOption = await waitForElement(".project-todo-form-schedule option[value='research']");
    const typeSelect = typeOption.parentElement;
    if (!(typeSelect instanceof HTMLSelectElement)) {
      throw new Error("Todo type selector was not rendered");
    }

    setValue(titleInput, "Research options");
    setValue(descriptionInput, "Compare alternatives");
    act(() => {
      typeSelect.value = "research";
      typeSelect.dispatchEvent(new Event("change", { bubbles: true }));
    });
    await waitForRequests();
    const storageKey = projectTodoCreateDraftStorageKey("client-1", "/workspace");

    expect(JSON.parse(window.localStorage.getItem(storageKey) ?? "null")).toEqual({
      title: "Research options",
      description: "Compare alternatives",
      todo_type_id: "research",
      artifact_kinds: ["deep_research_report"]
    });

    act(() => {
      (document.body.querySelector(".project-todo-form button[data-create-action='add']") as HTMLButtonElement).click();
    });
    await waitForRequests();

    expect(apiMocks.createProjectTodo).toHaveBeenCalledWith("client-1", "/workspace", {
      title: "Research options",
      description: "Compare alternatives",
      todo_type_id: "research",
      artifact_kinds: ["deep_research_report"]
    });
  });

});
