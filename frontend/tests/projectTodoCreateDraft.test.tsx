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
import { clearRuntimeAppPreferencesForTests, writeArtifactModelSelectionSettings } from "../src/userPreferences";
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
  clearRuntimeAppPreferencesForTests();
  vi.restoreAllMocks();
});

describe("project todo create draft", () => {
  it("restores an unsaved sidebar quick-card draft after closing and reopening", async () => {
    function SidebarHarness() {
      const [open, setOpen] = useState(true);
      return (
        <>
          {open && (
            <ProjectTodoSidebarControls
              clientId="client-1"
              projectPath="/workspace"
            />
          )}
          <button type="button" onClick={() => setOpen(false)}>Close sidebar</button>
          <button type="button" onClick={() => setOpen(true)}>Reopen sidebar</button>
        </>
      );
    }
    renderWithQuery(<SidebarHarness />);
    const titleInput = await waitForElement(".project-todo-form input") as HTMLInputElement;
    const descriptionInput = await waitForElement(".project-todo-form textarea") as HTMLTextAreaElement;

    setValue(titleInput, "Draft board card");
    setValue(descriptionInput, "Keep this after close");
    await waitForRequests();
    act(() => {
      (Array.from(document.body.querySelectorAll("button")).find(
        (button) => button.textContent === "Close sidebar"
      ) as HTMLButtonElement).click();
    });
    await waitForRequests();
    expect(document.body.querySelector(".project-todo-sidebar-controls")).toBeNull();

    const reopenButton = Array.from(document.body.querySelectorAll("button")).find(
      (button) => button.textContent === "Reopen sidebar"
    ) as HTMLButtonElement;
    act(() => {
      reopenButton.click();
    });
    const restoredTitle = await waitForElement(".project-todo-form input") as HTMLInputElement;
    const restoredDescription = await waitForElement(".project-todo-form textarea") as HTMLTextAreaElement;
    const storageKey = projectTodoCreateDraftStorageKey("client-1", "/workspace");

    expect(restoredTitle.value).toBe("Draft board card");
    expect(restoredDescription.value).toBe("Keep this after close");
    expect(JSON.parse(window.localStorage.getItem(storageKey) ?? "null")).toEqual({
      title: "Draft board card",
      description: "Keep this after close"
    });
  });

  it("keeps quick creation out of the board and opens advanced creation from New task", async () => {
    renderWithQuery(
      <ProjectTodoPanel
        clientId="client-1"
        projectPath="/workspace"
        viewMode="board"
        onSelectWindow={() => {}}
      />
    );

    await waitForElement(".project-todo-board-new-button");
    expect(document.body.querySelector(".project-todo-form")).toBeNull();
    expect(document.body.querySelector(".project-todo-form-quick")).toBeNull();
    expect(document.body.querySelector(".project-todo-form-schedule")).toBeNull();
    expect(document.body.querySelector(".project-todo-create-dialog")).toBeNull();

    act(() => {
      (document.body.querySelector(".project-todo-board-new-button") as HTMLButtonElement).click();
    });
    const dialog = await waitForElement(".project-todo-create-dialog");

    expect(dialog.querySelector(".project-todo-form-schedule")).not.toBeNull();
    expect(dialog.textContent).toContain("Periodic");
  });

  it("shows custom date pickers in the sidebar time range control", async () => {
    function SidebarHarness() {
      const [dateFilter, setDateFilter] = useState<ProjectTodoDateFilter>({
        range: "all",
        customStart: "",
        customEnd: ""
      });
      return (
        <ProjectTodoSidebarControls
          clientId="client-1"
          dateFilter={dateFilter}
          projectPath="/workspace"
          onDateFilterChange={setDateFilter}
        />
      );
    }

    renderWithQuery(<SidebarHarness />);

    const rangeSelect = await waitForElement("select[aria-label='Updated']") as HTMLSelectElement;
    setSelectValue(rangeSelect, "custom");

    expect(await waitForElement("input[aria-label='Start date']")).toBeInstanceOf(HTMLInputElement);
    expect(await waitForElement("input[aria-label='End date']")).toBeInstanceOf(HTMLInputElement);
  });

  it("requests board cards with the project todo date filter", async () => {
    const recentTodo = {
      ...todo,
      title: "Recent board card",
      updated_at: "2099-06-03T12:00:00Z"
    };
    const oldTodo = {
      ...todo,
      id: "todo-old",
      title: "Old board card",
      updated_at: "2000-05-20T12:00:00Z"
    };
    apiMocks.fetchProjectTodos.mockResolvedValue({ todos: [recentTodo, oldTodo] });

    renderWithQuery(
      <ProjectTodoPanel
        clientId="client-1"
        dateFilter={{ range: "30d", customStart: "", customEnd: "" }}
        projectPath="/workspace"
        viewMode="board"
        onSelectWindow={() => {}}
      />
    );

    await waitForElementText(".project-todo-card", "Recent board card");
    expect(apiMocks.fetchProjectTodos).toHaveBeenCalledWith("client-1", "/workspace", { range: "30d" });
    const board = document.body.querySelector(".project-todo-board-shell");
    expect(board?.textContent).toContain("Recent board card");
    expect(board?.textContent).toContain("Old board card");
  });

  it("creates a quick board card with only title and description", async () => {
    apiMocks.createProjectTodo.mockResolvedValue({ id: "todo-6", title: "Quick board card" });
    renderWithQuery(
      <ProjectTodoCreateForm
        clientId="client-1"
        projectPath="/workspace"
        mode="quick"
        onCreated={() => {}}
        onPendingChange={() => {}}
      />
    );
    const titleInput = await waitForElement(".project-todo-form input") as HTMLInputElement;
    const descriptionInput = await waitForElement(".project-todo-form textarea") as HTMLTextAreaElement;

    setValue(titleInput, "Quick board card");
    setValue(descriptionInput, "Small context");
    act(() => {
      (document.body.querySelector(".project-todo-form button[data-create-action='add']") as HTMLButtonElement).click();
    });
    await waitForRequests();

    expect(apiMocks.createProjectTodo).toHaveBeenCalledWith("client-1", "/workspace", {
      title: "Quick board card",
      description: "Small context"
    });
  });

  it("creates a quick board card with a selected parent card", async () => {
    apiMocks.createProjectTodo.mockResolvedValue({ id: "todo-7", title: "Child board card" });
    renderWithQuery(
      <ProjectTodoCreateForm
        clientId="client-1"
        projectPath="/workspace"
        mode="quick"
        todos={[todo]}
        onCreated={() => {}}
        onPendingChange={() => {}}
      />
    );
    const titleInput = await waitForElement(".project-todo-form input") as HTMLInputElement;
    const descriptionInput = await waitForElement(".project-todo-form textarea") as HTMLTextAreaElement;
    const parentSelect = await waitForElement(".project-todo-parent-selector select") as HTMLSelectElement;

    setValue(titleInput, "Child board card");
    setValue(descriptionInput, "Build on the parent work");
    act(() => {
      parentSelect.value = "todo-1";
      parentSelect.dispatchEvent(new Event("change", { bubbles: true }));
    });
    await waitForRequests();

    expect(JSON.parse(window.localStorage.getItem(projectTodoCreateDraftStorageKey("client-1", "/workspace")) ?? "null")).toEqual({
      title: "Child board card",
      description: "Build on the parent work",
      parent_todo_id: "todo-1"
    });

    act(() => {
      (document.body.querySelector(".project-todo-form button[data-create-action='add']") as HTMLButtonElement).click();
    });
    await waitForRequests();

    expect(apiMocks.createProjectTodo).toHaveBeenCalledWith("client-1", "/workspace", {
      title: "Child board card",
      description: "Build on the parent work",
      parent_todo_id: "todo-1"
    });
  });

  it("creates a quick board card with a selected card type", async () => {
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
    apiMocks.createProjectTodo.mockResolvedValue({ id: "todo-8", title: "Quick research card" });
    renderWithQuery(
      <ProjectTodoCreateForm
        clientId="client-1"
        projectPath="/workspace"
        mode="quick"
        onCreated={() => {}}
        onPendingChange={() => {}}
      />
    );
    const titleInput = await waitForElement(".project-todo-form input") as HTMLInputElement;
    const descriptionInput = await waitForElement(".project-todo-form textarea") as HTMLTextAreaElement;
    const typeOption = await waitForElement(".project-todo-quick-type option[value='research']");
    const typeSelect = typeOption.parentElement;
    if (!(typeSelect instanceof HTMLSelectElement)) {
      throw new Error("Quick todo type selector was not rendered");
    }

    setValue(titleInput, "Quick research card");
    setValue(descriptionInput, "Small context");
    act(() => {
      typeSelect.value = "research";
      typeSelect.dispatchEvent(new Event("change", { bubbles: true }));
    });
    await waitForRequests();

    expect(JSON.parse(window.localStorage.getItem(projectTodoCreateDraftStorageKey("client-1", "/workspace")) ?? "null")).toEqual({
      title: "Quick research card",
      description: "Small context",
      todo_type_id: "research"
    });

    act(() => {
      (document.body.querySelector(".project-todo-form button[data-create-action='add']") as HTMLButtonElement).click();
    });
    await waitForRequests();

    expect(apiMocks.createProjectTodo).toHaveBeenCalledWith("client-1", "/workspace", {
      title: "Quick research card",
      description: "Small context",
      todo_type_id: "research"
    });
  });

  it("uses the artifact default model when creating a card for that agent-client", async () => {
    writeArtifactModelSelectionSettings({
      codex: {
        preset_id: "openai-artifacts",
        model: "gpt-5-codex",
        codex_model_reasoning_effort: "high"
      }
    });
    apiMocks.fetchProjectTodoTypes.mockResolvedValue({
      todo_types: [{
        ...defaultTodoType,
        id: "research",
        name: "Research",
        agent: "codex"
      }]
    });
    apiMocks.createProjectTodo.mockResolvedValue({ id: "todo-9", title: "Artifact model card" });
    renderWithQuery(
      <ProjectTodoCreateForm
        clientId="client-1"
        projectPath="/workspace"
        mode="quick"
        onCreated={() => {}}
        onPendingChange={() => {}}
      />
    );
    const titleInput = await waitForElement(".project-todo-form input") as HTMLInputElement;
    const typeOption = await waitForElement(".project-todo-quick-type option[value='research']");
    const typeSelect = typeOption.parentElement;
    if (!(typeSelect instanceof HTMLSelectElement)) {
      throw new Error("Quick todo type selector was not rendered");
    }

    setValue(titleInput, "Artifact model card");
    act(() => {
      typeSelect.value = "research";
      typeSelect.dispatchEvent(new Event("change", { bubbles: true }));
    });
    await waitForRequests();
    act(() => {
      (document.body.querySelector(".project-todo-form button[data-create-action='add']") as HTMLButtonElement).click();
    });
    await waitForRequests();

    expect(apiMocks.createProjectTodo).toHaveBeenCalledWith("client-1", "/workspace", {
      title: "Artifact model card",
      description: null,
      todo_type_id: "research",
      artifact_model_selection: {
        preset_id: "openai-artifacts",
        model: "gpt-5-codex",
        codex_model_reasoning_effort: "high"
      }
    });
  });

});
