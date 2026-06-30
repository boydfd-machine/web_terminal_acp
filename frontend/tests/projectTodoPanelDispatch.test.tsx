import { act } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  cleanupProjectTodoTest,
  renderWithQuery,
  setValue,
  setupProjectTodoTest,
  todo,
  waitForButton,
  waitForElement,
  waitForElementText,
  waitForLabeledButton,
  waitForRequests
} from "./projectTodoTestHarness";
import { ProjectTodoPanel } from "../src/components/ProjectTodoPanel";
import type { Project, ProjectTodo } from "../src/types";

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

beforeEach(() => setupProjectTodoTest(apiMocks));
afterEach(cleanupProjectTodoTest);

describe("ProjectTodoPanel dispatch", () => {
  it("uses the project agent preference when dispatching an unassigned todo", async () => {
    const project: Project = {
      client_id: "client-1",
      path: "/workspace",
      display_name: null,
      summary_status: null,
      summary_updated_at: null,
      window_count: 0,
      agent_preference: {
        agent_profile_id: "builtin/developer",
        agent_client: "codex",
        agent_command: "codex --model gpt-5-codex",
        agent_model_selection: { preset_id: "openai-main", model: "gpt-5-codex" }
      }
    };
    apiMocks.fetchSystemModelPresets.mockResolvedValue({
      presets: [{
        id: "openai-main",
        name: "OpenAI Main",
        provider: "openai_compatible",
        base_url: "https://models.example.com/v1",
        api_key: "secret-key",
        models: ["gpt-5-codex"]
      }]
    });
    apiMocks.fetchAgentProfiles.mockResolvedValue({
      profiles: [{
        id: "builtin/developer",
        name: "Developer",
        description: null,
        default_agent_client: "codex",
        agent_md: "",
        created_at: "2026-06-12T00:00:00Z",
        updated_at: "2026-06-12T00:00:00Z"
      }]
    });
    apiMocks.dispatchProjectTodo.mockResolvedValue({
      ...todo,
      dispatch_stage: "STARTING",
      assigned_agent: "codex"
    });
    renderWithQuery(
      <ProjectTodoPanel
        clientId="client-1"
        projectPath="/workspace"
        projects={[project]}
        onSelectWindow={() => {}}
      />
    );

    const row = await waitForButton("Fix dispatchTodo");
    act(() => row.click());
    const cardDispatch = await waitForButton("Dispatch", ".project-todo-actions button");
    act(() => cardDispatch.click());
    await waitForElementText(".terminal-create-modal", "OpenAI Main");
    const modalDispatch = await waitForButton("Dispatch", ".terminal-create-actions button");
    act(() => modalDispatch.click());
    await waitForRequests();

    expect(apiMocks.dispatchProjectTodo).toHaveBeenCalledWith("client-1", "/workspace", "todo-1", {
      agent_launch: {
        agent: "codex",
        command: "codex --model gpt-5-codex",
        config: null,
        model_selection: { preset_id: "openai-main", model: "gpt-5-codex" },
        profile_id: "builtin/developer"
      },
      dispatch_mode: "submit",
      dispatch_after_todo_ids: [],
      prompt: null
    });
  });

  it("dispatches a todo without selecting the assigned terminal", async () => {
    const onSelectWindow = vi.fn();
    apiMocks.dispatchProjectTodo.mockResolvedValue({
      ...todo,
      dispatch_stage: "STARTING",
      assigned_agent: "codex"
    });
    renderWithQuery(<ProjectTodoPanel clientId="client-1" projectPath="/workspace" onSelectWindow={onSelectWindow} />);

    const row = await waitForButton("Fix dispatchTodo");
    act(() => row.click());
    const cardDispatch = await waitForButton("Dispatch", ".project-todo-actions button");
    act(() => cardDispatch.click());
    const modalDispatch = await waitForButton("Dispatch", ".terminal-create-actions button");
    act(() => modalDispatch.click());
    await waitForRequests();

    expect(apiMocks.dispatchProjectTodo).toHaveBeenCalledWith("client-1", "/workspace", "todo-1", {
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
    expect(apiMocks.fetchWindow).not.toHaveBeenCalled();
    expect(onSelectWindow).not.toHaveBeenCalled();
    expect(document.body.querySelector(".terminal-create-modal")).toBeNull();
    expect(document.body.querySelector(".project-todo-dispatch-toast.success")?.textContent).toBe(
      "Dispatch started for Fix dispatch."
    );
  });

  it("shows disabled system skills as editable board dispatch options", async () => {
    apiMocks.fetchClientSystemAgentConfig.mockResolvedValue({
      agent: "system",
      sections: [
        {
          id: "skills",
          name: "System Skills",
          items: [{ id: "image-to-ppt", name: "Image to PPT", enabled: false, path: null, origin: "system_config" }]
        },
        { id: "mcp", name: "System MCP Servers", items: [] }
      ]
    });
    apiMocks.dispatchProjectTodo.mockResolvedValue({
      ...todo,
      dispatch_stage: "STARTING",
      assigned_agent: "codex"
    });
    renderWithQuery(<ProjectTodoPanel clientId="client-1" projectPath="/workspace" viewMode="board" onSelectWindow={() => {}} />);

    const dispatchButton = await waitForLabeledButton("Dispatch Fix dispatch");
    act(() => dispatchButton.click());
    await waitForElementText(".terminal-create-modal", "Image to PPT");

    const skillRow = Array.from(document.body.querySelectorAll(".agent-config-item"))
      .find((row) => row.textContent?.includes("Image to PPT"));
    const skillToggle = skillRow?.querySelector("input");
    expect(skillToggle).toBeInstanceOf(HTMLInputElement);
    expect((skillToggle as HTMLInputElement).checked).toBe(false);
    expect((skillToggle as HTMLInputElement).disabled).toBe(false);
    act(() => {
      (skillToggle as HTMLInputElement).click();
    });

    const modalDispatch = await waitForButton("Dispatch", ".terminal-create-actions button");
    act(() => modalDispatch.click());
    await waitForRequests();

    expect(apiMocks.dispatchProjectTodo).toHaveBeenCalledWith("client-1", "/workspace", "todo-1", {
      agent_launch: {
        agent: "codex",
        command: "codex",
        config: {
          agent: "codex",
          sections: [
            { id: "skills", items: [{ id: "image-to-ppt", enabled: true }] },
            { id: "plugins", items: [] },
            { id: "hooks", items: [] },
            { id: "mcp", items: [] }
          ]
        },
        profile_id: null
      },
      dispatch_mode: "submit",
      dispatch_after_todo_ids: [],
      prompt: null
    });
  });

  it("expands the todo dispatch agent config directly below the config button", async () => {
    apiMocks.fetchClientSystemAgentConfig.mockResolvedValue({
      agent: "system",
      sections: [
        {
          id: "skills",
          name: "System Skills",
          items: [{
            id: "image-to-ppt",
            name: "Image to PPT",
            enabled: false,
            path: null,
            origin: "system_config"
          }]
        },
        { id: "mcp", name: "System MCP Servers", items: [] }
      ]
    });
    renderWithQuery(<ProjectTodoPanel clientId="client-1" projectPath="/workspace" viewMode="board" onSelectWindow={() => {}} />);

    const dispatchButton = await waitForLabeledButton("Dispatch Fix dispatch");
    act(() => dispatchButton.click());
    const configButton = await waitForElement(".terminal-create-config-row");
    const configPanel = await waitForElement(".terminal-create-config-panel");
    expect(configButton).toBeInstanceOf(HTMLButtonElement);
    expect(configButton.getAttribute("aria-expanded")).toBe("true");
    expect(configButton.nextElementSibling).toBe(configPanel);

    act(() => {
      (configButton as HTMLButtonElement).click();
    });
    await waitForRequests();
    const collapsedButton = document.body.querySelector(".terminal-create-config-row");
    expect(collapsedButton).toBeInstanceOf(HTMLButtonElement);
    expect(collapsedButton?.getAttribute("aria-expanded")).toBe("false");
    expect(document.body.querySelector(".terminal-create-config-panel")).toBeNull();

    act(() => {
      (collapsedButton as HTMLButtonElement).click();
    });
    const reopenedPanel = await waitForElement(".terminal-create-config-panel");
    const reopenedButton = document.body.querySelector(".terminal-create-config-row");
    expect(reopenedButton?.getAttribute("aria-expanded")).toBe("true");
    expect(reopenedButton?.nextElementSibling).toBe(reopenedPanel);
  });

  it("can dispatch into the agent composer without selecting the assigned terminal", async () => {
    const onSelectWindow = vi.fn();
    apiMocks.dispatchProjectTodo.mockResolvedValue({
      ...todo,
      dispatch_stage: "STARTING",
      assigned_agent: "codex"
    });
    renderWithQuery(<ProjectTodoPanel clientId="client-1" projectPath="/workspace" onSelectWindow={onSelectWindow} />);

    const row = await waitForButton("Fix dispatchTodo");
    act(() => row.click());
    const cardDispatch = await waitForButton("Dispatch", ".project-todo-actions button");
    act(() => cardDispatch.click());
    const composeButton = await waitForButton("Compose", ".project-todo-dispatch-mode-options button");
    act(() => composeButton.click());
    const modalDispatch = await waitForButton("Dispatch", ".terminal-create-actions button");
    act(() => modalDispatch.click());
    await waitForRequests();

    expect(apiMocks.dispatchProjectTodo).toHaveBeenCalledWith("client-1", "/workspace", "todo-1", {
      agent_launch: {
        agent: "codex",
        command: "codex",
        config: null,
        profile_id: null
      },
      dispatch_mode: "compose",
      dispatch_after_todo_ids: [],
      prompt: null
    });
    expect(apiMocks.fetchWindow).not.toHaveBeenCalled();
    expect(onSelectWindow).not.toHaveBeenCalled();
  });

  it("uses the streamlined default dispatch prompt without the validation sentence", async () => {
    renderWithQuery(<ProjectTodoPanel clientId="client-1" projectPath="/workspace" onSelectWindow={() => {}} />);

    const row = await waitForButton("Fix dispatchTodo");
    act(() => row.click());
    const cardDispatch = await waitForButton("Dispatch", ".project-todo-actions button");
    act(() => cardDispatch.click());

    const promptField = document.body.querySelector(
      ".project-todo-dispatch-template textarea"
    );
    expect(promptField).toBeInstanceOf(HTMLTextAreaElement);
    expect((promptField as HTMLTextAreaElement).value).toContain("You are assigned to complete this project todo.");
    expect((promptField as HTMLTextAreaElement).value).toContain("Project path: /workspace");
    expect((promptField as HTMLTextAreaElement).value).toContain("Todo: Fix dispatch");
    expect((promptField as HTMLTextAreaElement).value).toContain("Context:\nOld details");
    expect((promptField as HTMLTextAreaElement).value).not.toContain(
      "When finished, report what changed and what validation you ran."
    );
  });

  it("creates a board card and opens dispatch options for the created todo", async () => {
    const createdTodo: ProjectTodo = {
      ...todo,
      id: "todo-new",
      title: "Implement add and dispatch",
      description: "Launch this immediately",
      sort_order: 2
    };
    apiMocks.createProjectTodo.mockResolvedValue(createdTodo);
    apiMocks.fetchProjectTodo.mockImplementation((_clientId, _projectPath, todoId) => Promise.resolve(
      todoId === "todo-new" ? createdTodo : todo
    ));
    apiMocks.dispatchProjectTodo.mockResolvedValue({
      ...createdTodo,
      dispatch_stage: "STARTING",
      assigned_agent: "codex"
    });
    renderWithQuery(
      <ProjectTodoPanel
        clientId="client-1"
        projectPath="/workspace"
        viewMode="board"
        onSelectWindow={() => {}}
      />
    );

    const newTaskButton = await waitForButton("New task", ".project-todo-board-new-button");
    act(() => newTaskButton.click());
    const createDialog = await waitForElement(".project-todo-create-dialog");
    const titleInput = createDialog.querySelector(".project-todo-form input") as HTMLInputElement;
    const descriptionInput = createDialog.querySelector(".project-todo-form textarea") as HTMLTextAreaElement;
    expect(titleInput).toBeInstanceOf(HTMLInputElement);
    expect(descriptionInput).toBeInstanceOf(HTMLTextAreaElement);
    setValue(titleInput, "Implement add and dispatch");
    setValue(descriptionInput, "Launch this immediately");

    const addAndDispatch = await waitForLabeledButton("Add and dispatch todo");
    act(() => addAndDispatch.click());
    await waitForRequests();

    expect(apiMocks.createProjectTodo).toHaveBeenCalledWith("client-1", "/workspace", {
      title: "Implement add and dispatch",
      description: "Launch this immediately"
    });
    expect(apiMocks.dispatchProjectTodo).not.toHaveBeenCalled();
    await waitForElementText(".terminal-create-modal", "Implement add and dispatch");

    const modalDispatch = await waitForButton("Dispatch", ".terminal-create-actions button");
    act(() => modalDispatch.click());
    await waitForRequests();

    expect(apiMocks.dispatchProjectTodo).toHaveBeenCalledWith("client-1", "/workspace", "todo-new", {
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
  });

  it("creates and directly dispatches a board modal card with default options", async () => {
    const createdTodo: ProjectTodo = {
      ...todo,
      id: "todo-direct",
      title: "Direct modal dispatch",
      description: "Launch this without options",
      assigned_agent: "codex",
      sort_order: 2
    };
    apiMocks.createProjectTodo.mockResolvedValue(createdTodo);
    apiMocks.dispatchProjectTodo.mockResolvedValue({
      ...createdTodo,
      dispatch_stage: "STARTING"
    });
    renderWithQuery(
      <ProjectTodoPanel
        clientId="client-1"
        projectPath="/workspace"
        viewMode="board"
        onSelectWindow={() => {}}
      />
    );

    const newTaskButton = await waitForButton("New task", ".project-todo-board-new-button");
    act(() => newTaskButton.click());
    const createDialog = await waitForElement(".project-todo-create-dialog");
    const titleInput = createDialog.querySelector(".project-todo-form input") as HTMLInputElement;
    const descriptionInput = createDialog.querySelector(".project-todo-form textarea") as HTMLTextAreaElement;

    setValue(titleInput, "Direct modal dispatch");
    setValue(descriptionInput, "Launch this without options");
    const directDispatch = await waitForLabeledButton("Add and dispatch todo directly");
    act(() => directDispatch.click());
    await waitForRequests();

    expect(apiMocks.createProjectTodo).toHaveBeenCalledWith("client-1", "/workspace", {
      title: "Direct modal dispatch",
      description: "Launch this without options"
    });
    expect(apiMocks.dispatchProjectTodo).toHaveBeenCalledWith("client-1", "/workspace", "todo-direct", {
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
    expect(document.body.querySelector(".project-todo-create-dialog")).toBeNull();
    expect(document.body.querySelector(".terminal-create-modal")).toBeNull();
    expect(document.body.querySelector(".project-todo-dispatch-toast.success")?.textContent).toBe(
      "Dispatch started for Direct modal dispatch."
    );
  });

  it("shows a newly created direct-dispatch card in pending while a date filter is active", async () => {
    const createdTodo: ProjectTodo = {
      ...todo,
      id: "todo-direct-filtered",
      title: "Filtered direct modal dispatch",
      description: "Show this before dispatch returns",
      assigned_agent: "codex",
      sort_order: 2,
      updated_at: new Date().toISOString()
    };
    apiMocks.createProjectTodo.mockResolvedValue(createdTodo);
    apiMocks.dispatchProjectTodo.mockImplementation(() => new Promise(() => {}));
    renderWithQuery(
      <ProjectTodoPanel
        clientId="client-1"
        dateFilter={{ range: "30d", customStart: "", customEnd: "" }}
        projectPath="/workspace"
        viewMode="board"
        onSelectWindow={() => {}}
      />
    );

    const newTaskButton = await waitForButton("New task", ".project-todo-board-new-button");
    act(() => newTaskButton.click());
    const createDialog = await waitForElement(".project-todo-create-dialog");
    const titleInput = createDialog.querySelector(".project-todo-form input") as HTMLInputElement;
    const descriptionInput = createDialog.querySelector(".project-todo-form textarea") as HTMLTextAreaElement;

    setValue(titleInput, "Filtered direct modal dispatch");
    setValue(descriptionInput, "Show this before dispatch returns");
    const directDispatch = await waitForLabeledButton("Add and dispatch todo directly");
    act(() => directDispatch.click());
    await waitForRequests();

    const pendingColumn = document.body.querySelector("[data-project-todo-column='PENDING']");
    expect(apiMocks.dispatchProjectTodo).toHaveBeenCalledWith("client-1", "/workspace", "todo-direct-filtered", {
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
    expect(pendingColumn?.textContent).toContain("Filtered direct modal dispatch");
  });
});
