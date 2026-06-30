import { act, useState } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ProjectTodoDispatchToast } from "../src/components/ProjectTodoDispatchToast";
import {
  cleanupProjectTodoTest,
  dataTransferStub,
  dragEvent,
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
import { WindowProjectTodoLinks } from "../src/components/WindowProjectTodoLinks";
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

async function waitForPromptAction(label: string): Promise<HTMLButtonElement> {
  for (let attempt = 0; attempt < 20; attempt += 1) {
    await waitForRequests();
    const dialog = document.body.querySelector('[role="alertdialog"]');
    const button = Array.from(dialog?.querySelectorAll("button") ?? [])
      .find((candidate) => candidate.textContent === label);
    if (button instanceof HTMLButtonElement) {
      return button;
    }
  }
  throw new Error(`Prompt action ${label} was not ready`);
}

describe("ProjectTodoDispatchToast", () => {
  it("dismisses the dispatch notification after two seconds", () => {
    vi.useFakeTimers();
    const onDismiss = vi.fn();
    renderWithQuery(
      <ProjectTodoDispatchToast
        toast={{ id: 7, message: "Dispatched Fix dispatch.", tone: "success" }}
        onDismiss={onDismiss}
      />
    );

    expect(document.body.querySelector(".project-todo-dispatch-toast.success")?.textContent).toBe("Dispatched Fix dispatch.");
    act(() => vi.advanceTimersByTime(1999));
    expect(onDismiss).not.toHaveBeenCalled();
    act(() => vi.advanceTimersByTime(1));
    expect(onDismiss).toHaveBeenCalledWith(7);
    vi.useRealTimers();
  });

  it("keeps the original dismiss deadline when the parent rerenders", async () => {
    vi.useFakeTimers();
    const onDismiss = vi.fn();
    const toast = { id: 8, message: "Dispatch started for Fix dispatch.", tone: "success" as const };

    function RerenderingToast() {
      const [renderCount, setRenderCount] = useState(0);
      return (
        <>
          <button type="button" onClick={() => setRenderCount((current) => current + 1)}>
            rerender {renderCount}
          </button>
          <ProjectTodoDispatchToast
            toast={toast}
            onDismiss={(id) => onDismiss(id)}
          />
        </>
      );
    }

    renderWithQuery(<RerenderingToast />);

    act(() => vi.advanceTimersByTime(1999));
    const rerender = Array.from(document.body.querySelectorAll("button"))
      .find((candidate) => candidate.textContent === "rerender 0");
    if (!(rerender instanceof HTMLButtonElement)) {
      throw new Error("rerender button was not ready");
    }
    act(() => rerender.click());
    act(() => vi.advanceTimersByTime(1));

    expect(onDismiss).toHaveBeenCalledWith(8);
    vi.useRealTimers();
  });
});

describe("WindowProjectTodoLinks", () => {
  it("links a terminal overview back to the assigned todo card", async () => {
    const onFocusProjectTodo = vi.fn();
    apiMocks.fetchProjectTodos.mockResolvedValue({ todos: [{ ...todo, assigned_window_id: "window-1" }] });
    renderWithQuery(
      <WindowProjectTodoLinks
        clientId="client-1"
        projectPath="/workspace"
        windowId="window-1"
        onFocusProjectTodo={onFocusProjectTodo}
      />
    );
    const link = await waitForButton("Fix dispatchTodo");

    act(() => link.click());

    expect(onFocusProjectTodo).toHaveBeenCalledWith("/workspace", "todo-1");
  });
});
