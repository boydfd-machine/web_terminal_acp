import { act } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  cleanupProjectTodoTest,
  renderWithQuery,
  setValue,
  setupProjectTodoTest,
  defaultTodoType,
  todo,
  waitForButton,
  waitForElement,
  waitForElementText,
  waitForLabeledButton,
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

function placeCaretAtEnd(target: HTMLInputElement | HTMLTextAreaElement): void {
  act(() => {
    target.setSelectionRange(target.value.length, target.value.length);
    target.dispatchEvent(new KeyboardEvent("keyup", { bubbles: true, key: "End" }));
  });
}

async function beginDescriptionEdit(): Promise<void> {
  await waitForElementText(".project-todo-detail-description", "Old details");
  const editDescriptionButton = await waitForElement('button[aria-label="Edit todo description"]:not(:disabled)') as HTMLButtonElement;
  act(() => {
    editDescriptionButton.click();
  });
  await waitForRequests();
}

describe("ProjectTodoPanel", () => {
  it("edits todo title and description inline from the detail dialog", async () => {
    apiMocks.updateProjectTodo
      .mockResolvedValueOnce({ ...todo, title: "Updated" })
      .mockResolvedValueOnce({ ...todo, description: "New details" });
    renderWithQuery(<ProjectTodoPanel clientId="client-1" projectPath="/workspace" onSelectWindow={() => {}} />);

    const row = await waitForButton("Fix dispatchTodo");
    act(() => row.click());
    const titleButton = await waitForLabeledButton("Edit todo title");
    act(() => titleButton.click());
    await waitForRequests();

    const titleForm = document.body.querySelector(".project-todo-title-edit-form") as HTMLFormElement;
    const titleInput = titleForm.querySelector('input[aria-label="Todo title"]') as HTMLInputElement;
    expect(titleForm.querySelector('button[aria-label="Save"]')).toBeNull();
    expect(titleForm.querySelector(".project-todo-title-cancel-edit-button")).toBeInstanceOf(HTMLButtonElement);
    setValue(titleInput, "Updated");
    const callCountBeforeTitleBlur = apiMocks.updateProjectTodo.mock.calls.length;
    act(() => {
      titleInput.focus();
      titleInput.blur();
    });
    await waitForRequests();

    expect(apiMocks.updateProjectTodo).toHaveBeenCalledTimes(callCountBeforeTitleBlur + 1);
    expect(apiMocks.updateProjectTodo).toHaveBeenCalledWith("client-1", "/workspace", "todo-1", {
      title: "Updated"
    });

    const description = await waitForElementText(".project-todo-detail-description", "Old details");
    act(() => {
      description.dispatchEvent(new MouseEvent("click", { bubbles: true }));
    });
    await waitForRequests();
    expect(document.body.querySelector('textarea[aria-label="Todo description"]')).toBeNull();

    await beginDescriptionEdit();
    const descriptionForm = await waitForElement(".project-todo-description-edit-form") as HTMLFormElement;
    const descriptionInput = await waitForElement('textarea[aria-label="Todo description"]') as HTMLTextAreaElement;
    expect(descriptionForm.querySelector('button[aria-label="Save"]')).toBeNull();
    expect(descriptionForm.querySelector(".project-todo-description-cancel-edit-button")).toBeInstanceOf(HTMLButtonElement);

    setValue(descriptionInput, "New details");
    const callCountBeforeBlur = apiMocks.updateProjectTodo.mock.calls.length;
    act(() => {
      descriptionInput.focus();
      descriptionInput.blur();
    });
    await waitForRequests();

    expect(apiMocks.updateProjectTodo).toHaveBeenCalledTimes(callCountBeforeBlur + 1);
    expect(apiMocks.updateProjectTodo).toHaveBeenLastCalledWith("client-1", "/workspace", "todo-1", {
      description: "New details"
    });
  });

  it("saves todo title and description edits when the detail dialog closes from the backdrop", async () => {
    apiMocks.updateProjectTodo
      .mockResolvedValueOnce({ ...todo, title: "Backdrop title" })
      .mockResolvedValueOnce({ ...todo, description: "Backdrop description" });
    renderWithQuery(<ProjectTodoPanel clientId="client-1" projectPath="/workspace" onSelectWindow={() => {}} />);

    const row = await waitForButton("Fix dispatchTodo");
    act(() => row.click());
    const titleButton = await waitForLabeledButton("Edit todo title");
    act(() => titleButton.click());
    await waitForRequests();

    const titleInput = await waitForElement('input[aria-label="Todo title"]') as HTMLInputElement;
    setValue(titleInput, "Backdrop title");
    const titleBackdrop = await waitForElement(".project-todo-detail-backdrop");
    act(() => {
      titleBackdrop.dispatchEvent(new MouseEvent("mousedown", { bubbles: true }));
    });
    await waitForRequests();

    expect(apiMocks.updateProjectTodo).toHaveBeenCalledWith("client-1", "/workspace", "todo-1", {
      title: "Backdrop title"
    });
    expect(document.body.querySelector(".project-todo-detail-dialog")).toBeNull();

    const reopenedRow = await waitForButton("Fix dispatchTodo");
    act(() => reopenedRow.click());
    await beginDescriptionEdit();

    const descriptionInput = await waitForElement('textarea[aria-label="Todo description"]') as HTMLTextAreaElement;
    setValue(descriptionInput, "Backdrop description");
    const descriptionBackdrop = await waitForElement(".project-todo-detail-backdrop");
    act(() => {
      descriptionBackdrop.dispatchEvent(new MouseEvent("mousedown", { bubbles: true }));
    });
    await waitForRequests();

    expect(apiMocks.updateProjectTodo).toHaveBeenLastCalledWith("client-1", "/workspace", "todo-1", {
      description: "Backdrop description"
    });
    expect(document.body.querySelector(".project-todo-detail-dialog")).toBeNull();
  });

  it("cancels todo title editing from the floating control without saving", async () => {
    renderWithQuery(<ProjectTodoPanel clientId="client-1" projectPath="/workspace" onSelectWindow={() => {}} />);

    const row = await waitForButton("Fix dispatchTodo");
    act(() => row.click());
    const titleButton = await waitForLabeledButton("Edit todo title");
    act(() => titleButton.click());

    const titleForm = document.body.querySelector(".project-todo-title-edit-form") as HTMLFormElement;
    const titleInput = titleForm.querySelector('input[aria-label="Todo title"]') as HTMLInputElement;
    const cancelButton = titleForm.querySelector(".project-todo-title-cancel-edit-button") as HTMLButtonElement;
    setValue(titleInput, "Discard this");
    act(() => cancelButton.click());
    await waitForRequests();

    expect(apiMocks.updateProjectTodo).not.toHaveBeenCalled();
    expect(document.body.querySelector('input[aria-label="Todo title"]')).toBeNull();
    expect(document.body.querySelector(".project-todo-title-button")?.textContent).toContain("Fix dispatch");
  });

  it("cancels todo description editing from the floating control without saving", async () => {
    renderWithQuery(<ProjectTodoPanel clientId="client-1" projectPath="/workspace" onSelectWindow={() => {}} />);

    const row = await waitForButton("Fix dispatchTodo");
    act(() => row.click());
    await beginDescriptionEdit();

    const descriptionForm = await waitForElement(".project-todo-description-edit-form") as HTMLFormElement;
    const descriptionInput = await waitForElement('textarea[aria-label="Todo description"]') as HTMLTextAreaElement;
    const cancelButton = descriptionForm.querySelector(".project-todo-description-cancel-edit-button") as HTMLButtonElement;
    setValue(descriptionInput, "Discard this");
    act(() => cancelButton.click());
    await waitForRequests();

    expect(apiMocks.updateProjectTodo).not.toHaveBeenCalled();
    expect(document.body.querySelector('textarea[aria-label="Todo description"]')).toBeNull();
    expect(document.body.querySelector(".project-todo-detail-description")?.textContent).toContain("Old details");
  });

  it("inserts a searched card reference while editing a todo description", async () => {
    const targetTodo: ProjectTodo = {
      ...todo,
      id: "todo-2",
      title: "Write docs",
      description: "Document the card link behavior",
      sort_order: 2
    };
    apiMocks.fetchProjectTodos.mockResolvedValue({ todos: [todo, targetTodo] });
    apiMocks.updateProjectTodo.mockResolvedValue({
      ...todo,
      description: "Coordinate with @[其它需求：$Write docs|todo-2]"
    });
    renderWithQuery(<ProjectTodoPanel clientId="client-1" projectPath="/workspace" onSelectWindow={() => {}} />);

    const row = await waitForButton("Fix dispatchTodo");
    act(() => row.click());
    await beginDescriptionEdit();

    const descriptionInput = await waitForElement('textarea[aria-label="Todo description"]') as HTMLTextAreaElement;
    setValue(descriptionInput, "Coordinate with @docs");
    placeCaretAtEnd(descriptionInput);
    const option = await waitForElement(".project-todo-mention-option") as HTMLButtonElement;

    expect(option.textContent).toContain("Write docs");

    act(() => option.click());
    await waitForRequests();
    expect(descriptionInput.value).toBe("Coordinate with @[其它需求：$Write docs|todo-2]");

    act(() => {
      descriptionInput.focus();
      descriptionInput.blur();
    });
    await waitForRequests();

    expect(apiMocks.updateProjectTodo).toHaveBeenCalledWith("client-1", "/workspace", "todo-1", {
      description: "Coordinate with @[其它需求：$Write docs|todo-2]"
    });
  });

  it("inserts a searched card reference while commenting on a todo", async () => {
    const assignedTodo: ProjectTodo = {
      ...todo,
      assigned_window_id: "window-2"
    };
    const targetTodo: ProjectTodo = {
      ...todo,
      id: "todo-2",
      title: "Write docs",
      description: "Document the card link behavior",
      sort_order: 2
    };
    apiMocks.fetchProjectTodos.mockResolvedValue({ todos: [assignedTodo, targetTodo] });
    apiMocks.commentProjectTodo.mockResolvedValue(assignedTodo);
    renderWithQuery(<ProjectTodoPanel clientId="client-1" projectPath="/workspace" onSelectWindow={() => {}} />);

    const row = await waitForButton("Fix dispatchTodo");
    act(() => row.click());
    const commentButton = await waitForButton("Comment", ".project-todo-terminal-actions button");
    act(() => commentButton.click());

    const commentInput = await waitForElement('textarea[aria-label="Comment"]') as HTMLTextAreaElement;
    setValue(commentInput, "Please check @docs");
    placeCaretAtEnd(commentInput);
    const option = await waitForElement(".project-todo-mention-option") as HTMLButtonElement;

    expect(option.textContent).toContain("Write docs");

    act(() => option.click());
    await waitForRequests();
    expect(commentInput.value).toBe("Please check @[其它需求：$Write docs|todo-2]");

    const sendButton = await waitForButton("Send", ".project-todo-comment-actions button");
    act(() => sendButton.click());
    await waitForRequests();

    expect(apiMocks.commentProjectTodo).toHaveBeenCalledWith("client-1", "/workspace", "todo-1", {
      comment: "Please check @[其它需求：$Write docs|todo-2]"
    });
  });

  it("only moves focus to the card search when a bare todo mention appears", async () => {
    const targetTodo: ProjectTodo = {
      ...todo,
      id: "todo-2",
      title: "Write docs",
      description: "Document the card link behavior",
      sort_order: 2
    };
    apiMocks.fetchProjectTodos.mockResolvedValue({ todos: [todo, targetTodo] });
    renderWithQuery(<ProjectTodoPanel clientId="client-1" projectPath="/workspace" onSelectWindow={() => {}} />);

    const row = await waitForButton("Fix dispatchTodo");
    act(() => row.click());
    await beginDescriptionEdit();

    const descriptionInput = await waitForElement('textarea[aria-label="Todo description"]') as HTMLTextAreaElement;
    setValue(descriptionInput, "Coordinate with @");
    placeCaretAtEnd(descriptionInput);
    const searchInput = await waitForElement(".project-todo-mention-search") as HTMLInputElement;

    expect(document.activeElement).toBe(searchInput);

    act(() => {
      descriptionInput.focus();
      descriptionInput.setSelectionRange(descriptionInput.value.length, descriptionInput.value.length);
      descriptionInput.dispatchEvent(new Event("select", { bubbles: true }));
    });
    await waitForRequests();

    expect(document.activeElement).toBe(descriptionInput);

    setValue(descriptionInput, "Coordinate with @docs");
    placeCaretAtEnd(descriptionInput);
    await waitForRequests();

    expect(document.activeElement).toBe(descriptionInput);

    setValue(descriptionInput, "Coordinate with @");
    placeCaretAtEnd(descriptionInput);
    await waitForRequests();

    expect(document.activeElement).toBe(searchInput);
  });
});
