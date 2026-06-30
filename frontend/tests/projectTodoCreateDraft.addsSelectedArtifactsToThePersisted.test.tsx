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
  it("adds selected artifacts to the persisted draft and create request", async () => {
    apiMocks.fetchArtifactPlugins.mockResolvedValue({
      plugins: [
        {
          domain: "terminal",
          artifact_kind: "agent_trace_graph",
          label: "Agent Trace Graph",
          default_title: "Agent Trace Graph",
          origin: "built_in",
          editable: false,
          plugin_format: "legacy_python",
          downloadable: false
        },
        {
          domain: "terminal",
          artifact_kind: "release_readiness",
          label: "Release Readiness",
          default_title: "Release Readiness",
          origin: "built_in",
          editable: false,
          plugin_format: "legacy_python",
          downloadable: false
        }
      ]
    });
    apiMocks.createProjectTodo.mockResolvedValue({ id: "todo-3", title: "Trace work" });
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
    const artifactInput = await waitForElement(
      ".project-todo-form-artifacts .project-todo-artifact-select-input"
    ) as HTMLInputElement;

    act(() => artifactInput.focus());
    const artifactOption = await waitForElement(".project-todo-form-artifacts input[type='checkbox']") as HTMLInputElement;

    setValue(titleInput, "Trace work");
    setValue(descriptionInput, "Generate a trace artifact");
    act(() => artifactOption.click());
    await waitForRequests();
    const storageKey = projectTodoCreateDraftStorageKey("client-1", "/workspace");
    const selectedChip = await waitForElementText(
      ".project-todo-form-artifacts .project-todo-artifact-selected-chip",
      "Agent Trace Graph"
    );
    const selectedOptions = Array.from(document.body.querySelectorAll(".project-todo-form-artifacts .project-todo-artifact-options label"));

    expect(selectedChip.querySelector("button[aria-label='Remove Agent Trace Graph']")).toBeInstanceOf(HTMLButtonElement);
    expect(selectedOptions.map((option) => option.textContent?.trim())).toEqual(["Release Readiness"]);

    expect(JSON.parse(window.localStorage.getItem(storageKey) ?? "null")).toEqual({
      title: "Trace work",
      description: "Generate a trace artifact",
      artifact_kinds: ["agent_trace_graph"]
    });

    act(() => {
      (selectedOptions[0]?.querySelector("input") as HTMLInputElement).click();
    });
    await waitForRequests();
    expect(Array.from(document.body.querySelectorAll(".project-todo-form-artifacts .project-todo-artifact-selected-chip")).map(
      (chip) => chip.textContent?.trim()
    )).toEqual(["Agent Trace Graph", "Release Readiness"]);
    expect(document.body.querySelector(".project-todo-form-artifacts .project-todo-artifact-options")).toBeNull();
    expect(JSON.parse(window.localStorage.getItem(storageKey) ?? "null")).toEqual({
      title: "Trace work",
      description: "Generate a trace artifact",
      artifact_kinds: ["agent_trace_graph", "release_readiness"]
    });

    act(() => {
      (selectedChip.querySelector("button") as HTMLButtonElement).click();
    });
    await waitForRequests();
    expect(Array.from(document.body.querySelectorAll(".project-todo-form-artifacts .project-todo-artifact-selected-chip")).map(
      (chip) => chip.textContent?.trim()
    )).toEqual(["Release Readiness"]);

    act(() => {
      artifactInput.click();
    });
    await waitForRequests();
    expect(Array.from(document.body.querySelectorAll(".project-todo-form-artifacts .project-todo-artifact-options label")).map(
      (option) => option.textContent?.trim()
    )).toEqual(["Agent Trace Graph"]);
    act(() => {
      (document.body.querySelector(".project-todo-form button[data-create-action='add']") as HTMLButtonElement).click();
    });
    await waitForRequests();

    expect(apiMocks.createProjectTodo).toHaveBeenCalledWith("client-1", "/workspace", {
      title: "Trace work",
      description: "Generate a trace artifact",
      artifact_kinds: ["release_readiness"]
    });
  });

  it("filters artifact choices in the create form dropdown", async () => {
    apiMocks.fetchArtifactPlugins.mockResolvedValue({
      plugins: [
        {
          domain: "terminal",
          artifact_kind: "agent_trace_graph",
          label: "Agent Trace Graph",
          default_title: "Agent Trace Graph",
          origin: "built_in",
          editable: false,
          plugin_format: "legacy_python",
          downloadable: false
        },
        {
          domain: "terminal",
          artifact_kind: "release_readiness",
          label: "Release Readiness",
          default_title: "Release Readiness",
          origin: "built_in",
          editable: false,
          plugin_format: "legacy_python",
          downloadable: false
        },
        {
          domain: "project",
          artifact_kind: "page_review_cards",
          label: "Page Review Cards",
          default_title: "Page Review Cards",
          origin: "built_in",
          editable: false,
          plugin_format: "template",
          downloadable: false
        }
      ]
    });
    renderWithQuery(
      <ProjectTodoCreateForm
        clientId="client-1"
        projectPath="/workspace"
        onCreated={() => {}}
        onPendingChange={() => {}}
      />
    );

    const searchInput = await waitForElement(
      ".project-todo-form-artifacts .project-todo-artifact-select-input"
    ) as HTMLInputElement;
    act(() => {
      searchInput.focus();
    });

    setValue(searchInput, "page");
    await waitForRequests();
    expect(document.body.querySelector(".project-todo-form-artifacts .project-todo-artifact-options .project-todo-artifact-search")).toBeNull();
    expect(Array.from(document.body.querySelectorAll(".project-todo-form-artifacts .project-todo-artifact-options label")).map(
      (option) => option.textContent?.trim()
    )).toEqual(["Page Review Cards (Project)"]);

    act(() => {
      (document.body.querySelector(".project-todo-form-artifacts input[type='checkbox']") as HTMLInputElement).click();
    });
    await waitForRequests();

    expect(Array.from(document.body.querySelectorAll(".project-todo-form-artifacts .project-todo-artifact-selected-chip")).map(
      (chip) => chip.textContent?.trim()
    )).toEqual(["Page Review Cards (Project)"]);
  });

  it("inserts a searched card reference into the add-card description", async () => {
    apiMocks.createProjectTodo.mockResolvedValue({ id: "todo-4", title: "Draft board card" });
    renderWithQuery(
      <ProjectTodoCreateForm
        clientId="client-1"
        projectPath="/workspace"
        todos={[
          { ...todo, id: "todo-2", title: "Build API", description: "Backend contract" },
          { ...todo, id: "todo-3", title: "Write docs", description: "Release notes" }
        ]}
        onCreated={() => {}}
        onPendingChange={() => {}}
      />
    );
    const titleInput = await waitForElement(".project-todo-form input") as HTMLInputElement;
    const descriptionInput = await waitForElement(".project-todo-form textarea") as HTMLTextAreaElement;

    setValue(titleInput, "Draft board card");
    setValue(descriptionInput, "Use @api");
    placeCaretAtEnd(descriptionInput);

    const option = await waitForElement(".project-todo-mention-option") as HTMLButtonElement;
    expect(option.textContent).toContain("Build API");
    expect(mentionOptionTexts()).not.toContain("Write docs");

    act(() => option.click());
    await waitForRequests();
    expect(descriptionInput.value).toBe("Use @[其它需求：$Build API|todo-2]");

    act(() => {
      (document.body.querySelector(".project-todo-form button[data-create-action='add']") as HTMLButtonElement).click();
    });
    await waitForRequests();

    expect(apiMocks.createProjectTodo).toHaveBeenCalledWith("client-1", "/workspace", {
      title: "Draft board card",
      description: "Use @[其它需求：$Build API|todo-2]"
    });
  });

  it("opens a card picker at @ and lets the menu search pick a card", async () => {
    renderWithQuery(
      <ProjectTodoCreateForm
        clientId="client-1"
        projectPath="/workspace"
        todos={[
          { ...todo, id: "todo-2", title: "Build API", description: "Backend contract" },
          { ...todo, id: "todo-3", title: "Write docs", description: "Release notes" }
        ]}
        onCreated={() => {}}
        onPendingChange={() => {}}
      />
    );
    const descriptionInput = await waitForElement(".project-todo-form textarea") as HTMLTextAreaElement;

    setValue(descriptionInput, "Use@");
    placeCaretAtEnd(descriptionInput);

    const searchInput = await waitForElement(".project-todo-mention-search") as HTMLInputElement;
    expect(document.body.textContent).toContain("Build API");
    expect(document.body.textContent).toContain("Write docs");

    setValue(searchInput, "docs");
    const option = await waitForElement(".project-todo-mention-option") as HTMLButtonElement;

    expect(option.textContent).toContain("Write docs");
    expect(mentionOptionTexts()).not.toContain("Build API");

    act(() => option.click());
    await waitForRequests();
    expect(descriptionInput.value).toBe("Use@[其它需求：$Write docs|todo-3]");
  });
});

function mentionOptionTexts(): string {
  return Array.from(document.body.querySelectorAll(".project-todo-mention-option"))
    .map((option) => option.textContent ?? "")
    .join("\n");
}
