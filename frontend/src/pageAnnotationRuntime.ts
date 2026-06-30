import { isDebugAnnotationEnabled } from "./debugFeatures";
import {
  buildPageAnnotationTodoInput,
  normalizePageAnnotationSelection,
  type PageAnnotationPendingTodoCreation,
  type PageAnnotationPoint,
  type PageAnnotationTodoTarget,
} from "./pageAnnotation";
import { collectPageAnnotationEvidence, type PageAnnotationRect } from "./pageAnnotationEvidence";
import { runtimeHtml } from "./pageAnnotationRuntimeTemplate";
import { canCapturePageAnnotationScreenshot, capturePageAnnotationScreenshot } from "./pageAnnotationScreenshot";

type RuntimeState = "idle" | "selecting" | "drafting" | "submitting";
type AnnotationTargetMode = "new" | "existing";

type PageAnnotationRuntime = {
  destroy: () => void;
};

let runtime: PageAnnotationRuntime | null = null;

export function startPageAnnotationRuntime(): PageAnnotationRuntime | null {
  if (!isDebugAnnotationEnabled() || runtime !== null || typeof document === "undefined") {
    return runtime;
  }
  runtime = createRuntime();
  return runtime;
}

function createRuntime(): PageAnnotationRuntime {
  const hostElement = document.createElement("div");
  hostElement.dataset.pageAnnotationUi = "root";
  const shadow = hostElement.attachShadow({ mode: "open" });
  shadow.innerHTML = runtimeHtml();
  document.body.appendChild(hostElement);

  const button = requiredElement<HTMLButtonElement>(shadow, ".page-annotation-button");
  const overlay = requiredElement<HTMLDivElement>(shadow, ".page-annotation-overlay");
  const rectangle = requiredElement<HTMLDivElement>(shadow, ".page-annotation-rectangle");
  const form = requiredElement<HTMLFormElement>(shadow, ".page-annotation-form");
  const textarea = requiredElement<HTMLTextAreaElement>(shadow, "textarea");
  const includeScreenshot = requiredElement<HTMLInputElement>(shadow, ".page-annotation-screenshot-input");
  const screenshotLabel = requiredElement<HTMLSpanElement>(shadow, ".page-annotation-screenshot-label");
  const screenshotHelp = requiredElement<HTMLAnchorElement>(shadow, ".page-annotation-screenshot-help");
  const submit = requiredElement<HTMLButtonElement>(shadow, "button[type='submit']");
  const cancel = requiredElement<HTMLButtonElement>(shadow, ".page-annotation-cancel");
  const error = requiredElement<HTMLParagraphElement>(shadow, ".page-annotation-error");
  const newTarget = requiredElement<HTMLButtonElement>(shadow, "[data-page-annotation-target='new']");
  const existingTarget = requiredElement<HTMLButtonElement>(shadow, "[data-page-annotation-target='existing']");
  const todoSelectField = requiredElement<HTMLLabelElement>(shadow, ".page-annotation-todo-field");
  const todoSelect = requiredElement<HTMLSelectElement>(shadow, ".page-annotation-todo-select");

  let state: RuntimeState = "idle";
  let startPoint: PageAnnotationPoint | null = null;
  let selection: PageAnnotationRect | null = null;
  let targetMode: AnnotationTargetMode = "new";
  const screenshotCaptureAvailable = canCapturePageAnnotationScreenshot();

  const setState = (nextState: RuntimeState) => {
    state = nextState;
    overlay.hidden = nextState === "idle";
    form.hidden = nextState !== "drafting" && nextState !== "submitting";
    button.setAttribute("aria-pressed", nextState === "idle" ? "false" : "true");
    submit.disabled = nextState === "submitting" || (targetMode === "existing" && todoSelect.value === "");
    includeScreenshot.disabled = !screenshotCaptureAvailable || nextState === "submitting";
    document.body.classList.toggle("page-annotation-selecting", nextState === "selecting");
  };

  const reset = () => {
    startPoint = null;
    selection = null;
    textarea.value = "";
    error.textContent = "";
    rectangle.hidden = true;
    targetMode = "new";
    includeScreenshot.checked = false;
    screenshotHelp.hidden = screenshotCaptureAvailable;
    updateTargetMode();
    setState("idle");
  };

  button.addEventListener("click", () => {
    window.__WEB_TERMINAL_PAGE_ANNOTATION_HOST__?.closeCompetingOverlays?.();
    error.textContent = "";
    setState("selecting");
  });
  cancel.addEventListener("click", reset);
  newTarget.addEventListener("click", () => {
    targetMode = "new";
    error.textContent = "";
    updateTargetMode();
    setState(state);
  });
  existingTarget.addEventListener("click", () => {
    targetMode = "existing";
    error.textContent = "";
    updateTargetMode();
    setState(state);
    void loadTodos();
  });
  todoSelect.addEventListener("change", () => {
    setState(state);
  });
  overlay.addEventListener("pointerdown", (event) => {
    if (state !== "selecting" || event.target !== overlay) {
      return;
    }
    event.preventDefault();
    startPoint = { x: event.clientX, y: event.clientY };
    selection = null;
    rectangle.hidden = false;
    updateRectangle(rectangle, { left: event.clientX, top: event.clientY, width: 0, height: 0 });
    overlay.setPointerCapture(event.pointerId);
  });
  overlay.addEventListener("pointermove", (event) => {
    if (state !== "selecting" || startPoint === null) {
      return;
    }
    const draftSelection = normalizePageAnnotationSelection(startPoint, { x: event.clientX, y: event.clientY })
      ?? draftRect(startPoint, { x: event.clientX, y: event.clientY });
    updateRectangle(rectangle, draftSelection);
  });
  overlay.addEventListener("pointerup", (event) => {
    if (state !== "selecting" || startPoint === null) {
      return;
    }
    event.preventDefault();
    selection = normalizePageAnnotationSelection(startPoint, { x: event.clientX, y: event.clientY });
    if (overlay.hasPointerCapture(event.pointerId)) {
      overlay.releasePointerCapture(event.pointerId);
    }
    if (selection === null) {
      rectangle.hidden = true;
      startPoint = null;
      return;
    }
    updateRectangle(rectangle, selection);
    placeForm(form, selection);
    setState("drafting");
    textarea.focus();
  });
  overlay.addEventListener("pointercancel", reset);
  form.addEventListener("pointerdown", (event) => event.stopPropagation());
  form.addEventListener("click", (event) => event.stopPropagation());
  form.addEventListener("submit", (event) => {
    event.preventDefault();
    void submitAnnotation();
  });
  window.addEventListener("keydown", onKeyDown, true);

  if (!screenshotCaptureAvailable) {
    includeScreenshot.checked = false;
    screenshotLabel.textContent = "Screenshot unavailable in this browser";
    includeScreenshot.title = "Screenshot capture is unavailable in this browser.";
    screenshotHelp.hidden = false;
  }

  async function submitAnnotation() {
    const host = window.__WEB_TERMINAL_PAGE_ANNOTATION_HOST__;
    if (host === undefined || selection === null) {
      error.textContent = "Page annotation host is not ready.";
      return;
    }
    const context = host.getContext();
    if (context.clientId === null || context.projectPath === null) {
      error.textContent = "Select a project before creating an annotation card.";
      return;
    }
    setState("submitting");
    let pendingCreation: PageAnnotationPendingTodoCreation | null = null;
    let createdTodo = false;
    try {
      const evidence = collectPageAnnotationEvidence({ selection, appState: context });
      const input = buildPageAnnotationTodoInput({
        evidence,
        userCommand: textarea.value
      });
      const uploadImage = includeScreenshot.checked ? host.uploadImage : undefined;
      if (includeScreenshot.checked && uploadImage === undefined) {
        throw new Error("Page annotation host cannot upload screenshot images.");
      }
      const screenshot = includeScreenshot.checked ? await captureSelectedScreenshotWithHelp(selection) : null;
      if (targetMode === "new") {
        pendingCreation = host.beginTodoCreation?.(input) ?? null;
        if (pendingCreation !== null) {
          reset();
        }
      }
      const todo = targetMode === "existing"
        ? await appendAnnotation(host, input.description)
        : await host.createTodo(input);
      createdTodo = true;
      if (pendingCreation !== null) {
        host.focusTodo?.(todo);
      }
      if (screenshot !== null && uploadImage !== undefined) {
        await uploadImage(todo.id, screenshot);
      }
      if (pendingCreation === null) {
        host.focusTodo?.(todo);
        reset();
      }
    } catch (caught) {
      if (pendingCreation !== null) {
        if (!createdTodo) {
          pendingCreation.onFailed();
        }
        return;
      }
      error.textContent = caught instanceof Error ? caught.message : "Failed to create annotation card.";
      setState("drafting");
    }
  }

  function onKeyDown(event: KeyboardEvent) {
    if (event.key === "Escape" && state !== "idle") {
      event.preventDefault();
      reset();
    }
  }

  async function appendAnnotation(
    host: NonNullable<typeof window.__WEB_TERMINAL_PAGE_ANNOTATION_HOST__>,
    annotation: string
  ) {
    if (host.appendAnnotation === undefined) {
      throw new Error("Page annotation host cannot append to existing cards.");
    }
    if (todoSelect.value === "") {
      throw new Error("Select a card before appending the annotation.");
    }
    return host.appendAnnotation(todoSelect.value, { annotation });
  }

  async function captureSelectedScreenshot(selectedArea: PageAnnotationRect): Promise<File> {
    const previousDisplay = hostElement.style.display;
    hostElement.style.display = "none";
    await nextAnimationFrame();
    try {
      return await capturePageAnnotationScreenshot(selectedArea);
    } finally {
      hostElement.style.display = previousDisplay;
    }
  }

  async function captureSelectedScreenshotWithHelp(selectedArea: PageAnnotationRect): Promise<File> {
    try {
      return await captureSelectedScreenshot(selectedArea);
    } catch (caught) {
      screenshotHelp.hidden = false;
      throw caught;
    }
  }

  async function loadTodos() {
    const host = window.__WEB_TERMINAL_PAGE_ANNOTATION_HOST__;
    if (host?.listTodos === undefined) {
      return;
    }
    todoSelect.disabled = true;
    try {
      renderTodoOptions(todoSelect, await host.listTodos());
    } catch (caught) {
      error.textContent = caught instanceof Error ? caught.message : "Failed to load cards.";
    } finally {
      todoSelect.disabled = false;
      setState(state);
    }
  }

  function updateTargetMode() {
    newTarget.setAttribute("aria-pressed", targetMode === "new" ? "true" : "false");
    existingTarget.setAttribute("aria-pressed", targetMode === "existing" ? "true" : "false");
    todoSelectField.hidden = targetMode !== "existing";
    submit.textContent = targetMode === "existing" ? "Append to card" : "Create card";
  }

  updateTargetMode();
  setState("idle");

  return {
    destroy: () => {
      window.removeEventListener("keydown", onKeyDown, true);
      reset();
      hostElement.remove();
      runtime = null;
    }
  };
}

function requiredElement<T extends Element>(root: ShadowRoot, selector: string): T {
  const element = root.querySelector(selector);
  if (element === null) {
    throw new Error(`Missing page annotation runtime element: ${selector}`);
  }
  return element as T;
}

function draftRect(start: PageAnnotationPoint, end: PageAnnotationPoint): PageAnnotationRect {
  return {
    left: Math.min(start.x, end.x),
    top: Math.min(start.y, end.y),
    width: Math.abs(end.x - start.x),
    height: Math.abs(end.y - start.y)
  };
}

function updateRectangle(element: HTMLElement, rect: PageAnnotationRect) {
  element.style.left = `${rect.left}px`;
  element.style.top = `${rect.top}px`;
  element.style.width = `${rect.width}px`;
  element.style.height = `${rect.height}px`;
}

function placeForm(form: HTMLElement, selection: PageAnnotationRect) {
  const margin = 12;
  const formWidth = Math.min(360, window.innerWidth - margin * 2);
  const formHeight = 230;
  const belowTop = selection.top + selection.height + margin;
  const top = belowTop + formHeight <= window.innerHeight
    ? belowTop
    : Math.max(margin, selection.top - formHeight - margin);
  const left = Math.min(
    Math.max(margin, selection.left),
    Math.max(margin, window.innerWidth - formWidth - margin)
  );
  form.style.left = `${Math.round(left)}px`;
  form.style.top = `${Math.round(top)}px`;
}

function renderTodoOptions(select: HTMLSelectElement, todos: PageAnnotationTodoTarget[]) {
  select.replaceChildren();
  if (todos.length === 0) {
    const option = document.createElement("option");
    option.value = "";
    option.textContent = "No cards in this project";
    select.appendChild(option);
    return;
  }
  for (const todo of todos) {
    const option = document.createElement("option");
    option.value = todo.id;
    option.textContent = `${todo.title} (${todo.status})`;
    select.appendChild(option);
  }
}

function nextAnimationFrame(): Promise<void> {
  if (typeof requestAnimationFrame !== "function") {
    return Promise.resolve();
  }
  return new Promise((resolve) => requestAnimationFrame(() => resolve()));
}
