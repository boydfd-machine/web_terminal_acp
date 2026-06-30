import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, type ReactNode } from "react";
import { createRoot, type Root } from "react-dom/client";
import { vi } from "vitest";

import { AppPromptProvider } from "../src/components/AppPromptProvider";
import type { ProjectTodo } from "../src/types";

globalThis.IS_REACT_ACT_ENVIRONMENT = true;

export type ProjectTodoApiMocks = {
  commentProjectTodo: ReturnType<typeof vi.fn>;
  createProjectTodo: ReturnType<typeof vi.fn>;
  createTerminalArtifact: ReturnType<typeof vi.fn>;
  deleteProjectTodo: ReturnType<typeof vi.fn>;
  deleteProjectTodoAttachment: ReturnType<typeof vi.fn>;
  downloadProjectTodoAttachment: ReturnType<typeof vi.fn>;
  dispatchProjectTodo: ReturnType<typeof vi.fn>;
  dispatchProjectTodoReview: ReturnType<typeof vi.fn>;
  fetchAgentClients: ReturnType<typeof vi.fn>;
  fetchAgentProfileConfig: ReturnType<typeof vi.fn>;
  fetchAgentProfiles: ReturnType<typeof vi.fn>;
  fetchArtifactPlugins: ReturnType<typeof vi.fn>;
  fetchAgentRecordChat: ReturnType<typeof vi.fn>;
  fetchAgentRecordDetail: ReturnType<typeof vi.fn>;
  fetchClientAgentConfig: ReturnType<typeof vi.fn>;
  fetchClientSystemAgentConfig?: ReturnType<typeof vi.fn>;
  fetchSystemModelPresets: ReturnType<typeof vi.fn>;
  fetchProjectTodo: ReturnType<typeof vi.fn>;
  fetchProjectTodoHistory: ReturnType<typeof vi.fn>;
  fetchProjectTodoTypes: ReturnType<typeof vi.fn>;
  fetchProjectTodos: ReturnType<typeof vi.fn>;
  fetchWindow: ReturnType<typeof vi.fn>;
  fetchWindowActivity: ReturnType<typeof vi.fn>;
  linkProjectTodoArtifact: ReturnType<typeof vi.fn>;
  retryProjectTodoArtifact: ReturnType<typeof vi.fn>;
  restoreProjectTodoVersion: ReturnType<typeof vi.fn>;
  uploadProjectTodoAttachmentImage: ReturnType<typeof vi.fn>;
  upsertSystemProjectTodoType: ReturnType<typeof vi.fn>;
  updateSystemProjectTodoType: ReturnType<typeof vi.fn>;
  deleteSystemProjectTodoType: ReturnType<typeof vi.fn>;
  updateProjectTodo: ReturnType<typeof vi.fn>;
};

let root: Root | null = null;
let container: HTMLDivElement | null = null;
let queryClient: QueryClient | null = null;
const fetchProjectTodosMockResolvedValue = new WeakMap<
  ProjectTodoApiMocks["fetchProjectTodos"],
  ProjectTodoApiMocks["fetchProjectTodos"]["mockResolvedValue"]
>();

export const defaultTodoType = {
  id: "default",
  scope: "system" as const,
  client_id: null,
  project_path: null,
  name: "Default",
  description: "Default project todo card type.",
  agent: null,
  agent_profile_id: null,
  artifact_kinds: [],
  input_artifact_ids: [],
  dispatch_template: null,
  created_at: "2026-06-05T00:00:00Z",
  updated_at: "2026-06-05T00:00:00Z"
};

export const todo: ProjectTodo = {
  id: "todo-1",
  client_id: "client-1",
  project_path: "/workspace",
  todo_type_id: "default",
  todo_type: defaultTodoType,
  parent_todo_id: null,
  parent_todo: null,
  title: "Fix dispatch",
  description: "Old details",
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
  input_artifact_ids: [],
  assigned_terminal: null,
  execution_runs: [],
  attachments: [],
  artifacts: [],
  dependencies: [],
  dependents: [],
  child_todos: [],
  referenced_todos: [],
  queued_dispatch: false,
  created_at: "2026-06-05T00:00:00Z",
  updated_at: "2026-06-05T00:00:00Z"
};

export function virtualWindow(overrides: Record<string, unknown> = {}) {
  return {
    id: "window-2",
    client_id: "client-1",
    title: "Todo terminal",
    folder_id: null,
    parent_window_id: null,
    root_window_id: null,
    derived_mode: null,
    derived_context: null,
    status: "ACTIVE",
    tmux_session: null,
    tmux_window_id: null,
    tmux_window_index: null,
    remote_session_id: null,
    remote_window_id: null,
    cwd: "/workspace",
    shell_command: null,
    summary: null,
    title_tags: null,
    runtime_tags: [],
    work_status: { state: "LONG_IDLE", label: "Idle", color: "gray" },
    title_manually_overridden: false,
    folder_manually_overridden: false,
    command_capture_supported: false,
    summary_job: null,
    created_at: "2026-06-05T00:00:00Z",
    last_terminal_command_at: null,
    last_agent_event_at: null,
    last_active_at: "2026-06-05T00:00:00Z",
    ...overrides
  };
}

export function renderWithQuery(element: ReactNode): void {
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

export async function waitForRequests(): Promise<void> {
  await act(async () => {
    await new Promise((resolve) => setTimeout(resolve, 0));
  });
}

export async function waitForButton(text: string, selector = "button"): Promise<HTMLButtonElement> {
  for (let attempt = 0; attempt < 20; attempt += 1) {
    await waitForRequests();
    const button = Array.from(document.body.querySelectorAll(selector)).find(
      (candidate) => candidate.textContent === text
    );
    if (button instanceof HTMLButtonElement) {
      return button;
    }
  }
  throw new Error(`Button ${text} was not ready`);
}

export async function waitForLabeledButton(label: string): Promise<HTMLButtonElement> {
  for (let attempt = 0; attempt < 20; attempt += 1) {
    await waitForRequests();
    const button = Array.from(document.body.querySelectorAll("button")).find(
      (candidate) => candidate.getAttribute("aria-label") === label
    );
    if (button instanceof HTMLButtonElement) {
      return button;
    }
  }
  throw new Error(`Button ${label} was not ready`);
}

export async function waitForElement(selector: string): Promise<Element> {
  for (let attempt = 0; attempt < 20; attempt += 1) {
    await waitForRequests();
    const element = document.body.querySelector(selector);
    if (element !== null) {
      return element;
    }
  }
  throw new Error(`Element ${selector} was not ready`);
}

export async function waitForElementText(selector: string, text: string): Promise<Element> {
  for (let attempt = 0; attempt < 20; attempt += 1) {
    await waitForRequests();
    const element = Array.from(document.body.querySelectorAll(selector)).find(
      (candidate) => candidate.textContent?.includes(text)
    );
    if (element !== undefined) {
      return element;
    }
  }
  throw new Error(`Element ${selector} with text ${text} was not ready`);
}

export function setValue(target: HTMLInputElement | HTMLTextAreaElement, value: string): void {
  const setter = Object.getOwnPropertyDescriptor(Object.getPrototypeOf(target), "value")?.set;
  if (typeof setter !== "function") {
    throw new Error("Element does not expose a writable value property");
  }
  act(() => {
    setter.call(target, value);
    target.dispatchEvent(new Event("input", { bubbles: true }));
  });
}

export function setInputFiles(target: HTMLInputElement, files: File[]): void {
  Object.defineProperty(target, "files", {
    configurable: true,
    value: files
  });
  target.dispatchEvent(new Event("change", { bubbles: true }));
}

export function dataTransferStub(): DataTransfer {
  const values = new Map<string, string>();
  return {
    dropEffect: "none",
    effectAllowed: "all",
    getData: vi.fn((type: string) => values.get(type) ?? ""),
    setData: vi.fn((type: string, value: string) => values.set(type, value))
  } as unknown as DataTransfer;
}

export function dragEvent(type: string, dataTransfer: DataTransfer): Event {
  const event = new Event(type, { bubbles: true, cancelable: true });
  Object.defineProperty(event, "dataTransfer", { value: dataTransfer });
  return event;
}

export function setupProjectTodoTest(apiMocks: ProjectTodoApiMocks): void {
  vi.clearAllMocks();
  let mockResolvedProjectTodoList = fetchProjectTodosMockResolvedValue.get(apiMocks.fetchProjectTodos);
  if (mockResolvedProjectTodoList === undefined) {
    mockResolvedProjectTodoList = apiMocks.fetchProjectTodos.mockResolvedValue.bind(apiMocks.fetchProjectTodos);
    fetchProjectTodosMockResolvedValue.set(apiMocks.fetchProjectTodos, mockResolvedProjectTodoList);
  }
  apiMocks.fetchProjectTodo.mockResolvedValue(todo);
  apiMocks.fetchProjectTodos.mockResolvedValue = ((payload: { todos: ProjectTodo[] }) => {
    apiMocks.fetchProjectTodo.mockImplementation((_clientId, _projectPath, todoId) => Promise.resolve(
      payload.todos.find((candidate) => candidate.id === todoId) ?? todo
    ));
    return mockResolvedProjectTodoList(payload);
  }) as typeof apiMocks.fetchProjectTodos.mockResolvedValue;
  apiMocks.fetchProjectTodos.mockResolvedValue({ todos: [todo] });
  apiMocks.fetchProjectTodoHistory.mockResolvedValue({ todo_id: "todo-1", versions: [], audit_logs: [] });
  apiMocks.fetchWindowActivity.mockResolvedValue({ windows: [] });
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
  apiMocks.fetchClientAgentConfig.mockResolvedValue({
    agent: "codex",
    sections: [
      { id: "skills", name: "Skills", items: [] },
      { id: "plugins", name: "Plugins", items: [] },
      { id: "hooks", name: "Hooks", items: [] },
      { id: "mcp", name: "MCP Servers", items: [] }
    ]
  });
  apiMocks.fetchAgentProfileConfig.mockResolvedValue({
    agent: "codex",
    sections: [
      { id: "skills", name: "Skills", items: [] },
      { id: "plugins", name: "Plugins", items: [] },
      { id: "hooks", name: "Hooks", items: [] },
      { id: "mcp", name: "MCP Servers", items: [] }
    ]
  });
  apiMocks.fetchClientSystemAgentConfig?.mockResolvedValue({
    agent: "system",
    sections: [
      { id: "skills", name: "System Skills", items: [] },
      { id: "mcp", name: "System MCP Servers", items: [] }
    ]
  });
  apiMocks.fetchArtifactPlugins.mockResolvedValue({ plugins: [] });
  apiMocks.fetchSystemModelPresets.mockResolvedValue({ presets: [] });
  apiMocks.fetchProjectTodoTypes.mockResolvedValue({ todo_types: [defaultTodoType] });
  apiMocks.fetchAgentRecordChat.mockResolvedValue({
    window_id: "window-2",
    messages: [],
    messages_total: 0,
    messages_limit: 3,
    messages_offset: 0,
    messages_has_more: false
  });
  apiMocks.fetchAgentRecordDetail.mockResolvedValue({
    window_id: "window-2",
    sessions: [],
    events: [],
    events_total: 0,
    events_limit: 6,
    events_offset: 0,
    events_has_more: false
  });
  apiMocks.fetchWindow.mockResolvedValue(virtualWindow({
    remote_session_id: "session-1",
    remote_window_id: "window-remote-2"
  }));
  apiMocks.createTerminalArtifact.mockResolvedValue({
    id: "artifact-1",
    client_id: "client-1",
    virtual_window_id: "window-2",
    source_window_id: "window-2",
    ephemeral_window_id: "artifact-window-1",
    artifact_scope: "terminal",
    project_path: null,
    artifact_kind: "agent_trace_graph",
    title: "Agent Trace Graph",
    status: "PENDING",
    content_json: null,
    display_html: null,
    metadata_json: null,
    last_error: null,
    started_at: null,
    completed_at: null,
    created_at: "2026-06-05T00:00:00Z",
    updated_at: "2026-06-05T00:00:00Z"
  });
  apiMocks.commentProjectTodo.mockResolvedValue(todo);
  apiMocks.linkProjectTodoArtifact.mockResolvedValue(todo);
  apiMocks.retryProjectTodoArtifact.mockResolvedValue(todo);
  apiMocks.uploadProjectTodoAttachmentImage.mockResolvedValue({
    id: "attachment-1",
    todo_id: "todo-1",
    filename: "screen.png",
    content_type: "image/png",
    size_bytes: 12,
    status: "uploaded",
    uploaded_at: "2026-06-05T00:00:00Z",
    created_at: "2026-06-05T00:00:00Z",
    updated_at: "2026-06-05T00:00:00Z"
  });
  apiMocks.downloadProjectTodoAttachment.mockResolvedValue({
    attachment: {
      id: "attachment-1",
      todo_id: "todo-1",
      filename: "screen.png",
      content_type: "image/png",
      size_bytes: 12,
      status: "uploaded",
      uploaded_at: "2026-06-05T00:00:00Z",
      created_at: "2026-06-05T00:00:00Z",
      updated_at: "2026-06-05T00:00:00Z"
    },
    download_url: "https://objects.example/screen.png",
    expires_at: "2026-06-05T00:15:00Z"
  });
  apiMocks.deleteProjectTodoAttachment.mockResolvedValue(undefined);
  vi.spyOn(window, "requestAnimationFrame").mockImplementation((callback: FrameRequestCallback) => {
    callback(0);
    return 1;
  });
  vi.spyOn(window, "cancelAnimationFrame").mockImplementation(() => {});
  HTMLElement.prototype.scrollIntoView = vi.fn();
}

export function cleanupProjectTodoTest(): void {
  vi.useRealTimers();
  act(() => {
    root?.unmount();
  });
  document.body.replaceChildren();
  queryClient?.clear();
  root = null;
  container = null;
  queryClient = null;
  window.history.replaceState(null, "", "/");
  vi.restoreAllMocks();
}
