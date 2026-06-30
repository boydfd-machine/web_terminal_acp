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
  waitForRequests
} from "./projectTodoTestHarness";
import { ProjectTodoPanel } from "../src/components/ProjectTodoPanel";
import type { ProjectTodo } from "../src/types";

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

vi.mock("../src/api", () => apiMocks);

beforeEach(() => setupProjectTodoTest(apiMocks));
afterEach(cleanupProjectTodoTest);

describe("ProjectTodoPanel schedule controls", () => {
  it("toggles a cron periodic todo schedule from the list row", async () => {
    const periodicTodo: ProjectTodo = {
      ...todo,
      title: "Weekly cleanup",
      execution_kind: "PERIODIC",
      trigger_strategy: "CRON",
      cron_expression: "0 9 * * 1",
      schedule_enabled: false
    };
    apiMocks.fetchProjectTodos.mockResolvedValue({ todos: [periodicTodo] });
    apiMocks.fetchProjectTodo.mockResolvedValue(periodicTodo);
    apiMocks.updateProjectTodo.mockResolvedValue({
      ...periodicTodo,
      schedule_enabled: true,
      next_trigger_at: "2026-06-08T09:00:00Z"
    });
    renderWithQuery(<ProjectTodoPanel clientId="client-1" projectPath="/workspace" onSelectWindow={() => {}} />);

    const toggle = await waitForElement(
      'input[aria-label="Enable schedule for Weekly cleanup"]'
    ) as HTMLInputElement;
    expect(toggle.checked).toBe(false);

    act(() => {
      toggle.click();
    });
    await waitForRequests();

    expect(apiMocks.updateProjectTodo).toHaveBeenCalledWith("client-1", "/workspace", "todo-1", {
      schedule_enabled: true
    });
  });

  it("edits periodic schedule details without changing execution or terminal policy", async () => {
    const periodicTodo: ProjectTodo = {
      ...todo,
      title: "Weekly cleanup",
      execution_kind: "PERIODIC",
      terminal_policy: "REUSE_LATEST",
      trigger_strategy: "MANUAL",
      schedule_enabled: false
    };
    apiMocks.fetchProjectTodos.mockResolvedValue({ todos: [periodicTodo] });
    apiMocks.fetchProjectTodo.mockResolvedValue(periodicTodo);
    apiMocks.updateProjectTodo.mockResolvedValue({
      ...periodicTodo,
      trigger_strategy: "CRON",
      cron_expression: "*/30 * * * *",
      schedule_enabled: true,
      next_trigger_at: "2026-06-06T14:00:00Z"
    });
    renderWithQuery(<ProjectTodoPanel clientId="client-1" projectPath="/workspace" onSelectWindow={() => {}} />);

    const row = await waitForButton("Weekly cleanupTodo");
    act(() => row.click());
    const triggerSelect = await waitForElement('select[aria-label="Todo trigger"]') as HTMLSelectElement;
    act(() => {
      triggerSelect.value = "CRON";
      triggerSelect.dispatchEvent(new Event("change", { bubbles: true }));
    });
    const cronInput = await waitForElement('input[aria-label="Cron expression"]') as HTMLInputElement;
    setValue(cronInput, "*/30 * * * *");
    const enabledToggle = await waitForElement('input[aria-label="Enable schedule"]') as HTMLInputElement;
    act(() => {
      enabledToggle.click();
    });
    const saveButton = await waitForButton("Save schedule");
    act(() => saveButton.click());
    await waitForRequests();

    expect(apiMocks.updateProjectTodo).toHaveBeenCalledWith("client-1", "/workspace", "todo-1", {
      trigger_strategy: "CRON",
      cron_expression: "*/30 * * * *",
      schedule_enabled: true
    });
  });
});
