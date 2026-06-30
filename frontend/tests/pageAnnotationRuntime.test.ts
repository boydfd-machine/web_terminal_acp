import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { startPageAnnotationRuntime } from "../src/pageAnnotationRuntime";
import { canCapturePageAnnotationScreenshot, capturePageAnnotationScreenshot } from "../src/pageAnnotationScreenshot";

vi.mock("../src/pageAnnotationScreenshot", () => ({
  canCapturePageAnnotationScreenshot: vi.fn(() => true),
  capturePageAnnotationScreenshot: vi.fn()
}));

beforeEach(() => {
  vi.mocked(canCapturePageAnnotationScreenshot).mockReturnValue(true);
});

afterEach(() => {
  startPageAnnotationRuntime()?.destroy();
  document.body.replaceChildren();
  vi.clearAllMocks();
  vi.unstubAllGlobals();
});

describe("page annotation runtime", () => {
  it("opens selection mode, drafts after drag, and cancels with Escape", () => {
    window.__WEB_TERMINAL_PAGE_ANNOTATION_ENABLED__ = true;
    HTMLElement.prototype.setPointerCapture = () => {};
    HTMLElement.prototype.releasePointerCapture = () => {};
    HTMLElement.prototype.hasPointerCapture = () => true;
    const runtime = startPageAnnotationRuntime();
    expect(runtime).not.toBeNull();

    const shadow = annotationShadow();
    const button = shadow.querySelector(".page-annotation-button") as HTMLButtonElement;
    const overlay = shadow.querySelector(".page-annotation-overlay") as HTMLDivElement;
    const form = shadow.querySelector(".page-annotation-form") as HTMLFormElement;

    button.click();
    expect(button.getAttribute("aria-pressed")).toBe("true");
    expect(overlay.hidden).toBe(false);

    overlay.dispatchEvent(pointerEvent("pointerdown", 80, 90));
    overlay.dispatchEvent(pointerEvent("pointermove", 220, 190));
    overlay.dispatchEvent(pointerEvent("pointerup", 220, 190));

    expect(form.hidden).toBe(false);
    expect(shadow.querySelector(".page-annotation-rectangle")?.getAttribute("hidden")).toBeNull();

    window.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape", bubbles: true }));
    expect(button.getAttribute("aria-pressed")).toBe("false");
    expect(overlay.hidden).toBe(true);
    runtime?.destroy();
  });

  it("submits selected evidence to an existing todo when append mode is selected", async () => {
    window.__WEB_TERMINAL_PAGE_ANNOTATION_ENABLED__ = true;
    HTMLElement.prototype.setPointerCapture = () => {};
    HTMLElement.prototype.releasePointerCapture = () => {};
    HTMLElement.prototype.hasPointerCapture = () => true;
    const appendAnnotation = vi.fn().mockResolvedValue({
      id: "todo-1",
      client_id: "client-1",
      project_path: "/workspace",
      title: "Fix board drag"
    });
    const createTodo = vi.fn();
    const focusTodo = vi.fn();
    window.__WEB_TERMINAL_PAGE_ANNOTATION_HOST__ = {
      getContext: () => ({
        clientId: "client-1",
        projectPath: "/workspace",
        windowId: "window-1",
        workspaceMode: "kanban",
      }),
      createTodo,
      listTodos: vi.fn().mockResolvedValue([
        { id: "todo-1", title: "Fix board drag", status: "TODO" }
      ]),
      appendAnnotation,
      focusTodo,
    };
    startPageAnnotationRuntime();

    const shadow = annotationShadow();
    const button = shadow.querySelector(".page-annotation-button") as HTMLButtonElement;
    const overlay = shadow.querySelector(".page-annotation-overlay") as HTMLDivElement;
    button.click();
    overlay.dispatchEvent(pointerEvent("pointerdown", 80, 90));
    overlay.dispatchEvent(pointerEvent("pointermove", 220, 190));
    overlay.dispatchEvent(pointerEvent("pointerup", 220, 190));
    const appendMode = shadow.querySelector("[data-page-annotation-target='existing']") as HTMLButtonElement;
    appendMode.click();
    await waitForMicrotasks();

    const todoSelect = shadow.querySelector(".page-annotation-todo-select") as HTMLSelectElement;
    const textarea = shadow.querySelector("textarea") as HTMLTextAreaElement;
    const includeScreenshot = shadow.querySelector(".page-annotation-screenshot-input") as HTMLInputElement;
    const form = shadow.querySelector(".page-annotation-form") as HTMLFormElement;
    expect(todoSelect.value).toBe("todo-1");
    expect(includeScreenshot.checked).toBe(false);
    textarea.value = "Investigate whether this card is easy to scan. Do not change code yet.";
    form.dispatchEvent(new Event("submit", { bubbles: true, cancelable: true }));
    await waitForMicrotasks();

    expect(createTodo).not.toHaveBeenCalled();
    expect(appendAnnotation).toHaveBeenCalledWith("todo-1", {
      annotation: expect.stringContaining("Source: Debug page annotation")
    });
    expect(appendAnnotation.mock.calls[0][1].annotation).toContain(
      "Follow the user's command:\nInvestigate whether this card is easy to scan. Do not change code yet."
    );
    expect(appendAnnotation.mock.calls[0][1].annotation).not.toContain("Requested change:");
    expect(capturePageAnnotationScreenshot).not.toHaveBeenCalled();
    expect(focusTodo).toHaveBeenCalledWith(expect.objectContaining({ id: "todo-1" }));
  });

  it("moves new card creation into host pending state before create resolves", async () => {
    window.__WEB_TERMINAL_PAGE_ANNOTATION_ENABLED__ = true;
    HTMLElement.prototype.setPointerCapture = () => {};
    HTMLElement.prototype.releasePointerCapture = () => {};
    HTMLElement.prototype.hasPointerCapture = () => true;
    let resolveCreate: (todo: { id: string; client_id: string; project_path: string; title: string }) => void = () => {};
    const createTodo = vi.fn().mockImplementation(() => new Promise((resolve) => {
      resolveCreate = resolve;
    }));
    const pendingFailed = vi.fn();
    const beginTodoCreation = vi.fn(() => ({ onFailed: pendingFailed }));
    const focusTodo = vi.fn();
    window.__WEB_TERMINAL_PAGE_ANNOTATION_HOST__ = {
      getContext: () => ({
        clientId: "client-1",
        projectPath: "/workspace",
        windowId: "window-1",
        workspaceMode: "terminal",
      }),
      beginTodoCreation,
      createTodo,
      focusTodo,
    };
    startPageAnnotationRuntime();

    const shadow = annotationShadow();
    const button = shadow.querySelector(".page-annotation-button") as HTMLButtonElement;
    const overlay = shadow.querySelector(".page-annotation-overlay") as HTMLDivElement;
    const form = shadow.querySelector(".page-annotation-form") as HTMLFormElement;
    const textarea = shadow.querySelector("textarea") as HTMLTextAreaElement;
    button.click();
    overlay.dispatchEvent(pointerEvent("pointerdown", 80, 90));
    overlay.dispatchEvent(pointerEvent("pointermove", 220, 190));
    overlay.dispatchEvent(pointerEvent("pointerup", 220, 190));

    textarea.value = "Keep the creation state visible.";
    form.dispatchEvent(new Event("submit", { bubbles: true, cancelable: true }));
    await waitForMicrotasks();

    expect(beginTodoCreation).toHaveBeenCalledWith(expect.objectContaining({
      title: "Annotation: Keep the creation state visible.",
      description: expect.stringContaining("Follow the user's command:\nKeep the creation state visible.")
    }));
    expect(createTodo).toHaveBeenCalled();
    expect(overlay.hidden).toBe(true);
    expect(form.hidden).toBe(true);
    expect(button.getAttribute("aria-pressed")).toBe("false");

    resolveCreate({
      id: "todo-pending",
      client_id: "client-1",
      project_path: "/workspace",
      title: "Annotation: Keep the creation state visible."
    });
    await waitForAsyncSubmit();

    expect(focusTodo).toHaveBeenCalledWith(expect.objectContaining({ id: "todo-pending" }));
    expect(pendingFailed).not.toHaveBeenCalled();
  });

  it("captures and uploads a selected-area screenshot with a new annotation todo", async () => {
    window.__WEB_TERMINAL_PAGE_ANNOTATION_ENABLED__ = true;
    vi.stubGlobal("requestAnimationFrame", (callback: FrameRequestCallback) => {
      callback(0);
      return 1;
    });
    HTMLElement.prototype.setPointerCapture = () => {};
    HTMLElement.prototype.releasePointerCapture = () => {};
    HTMLElement.prototype.hasPointerCapture = () => true;
    const screenshot = new File(["png"], "debug-annotation.png", { type: "image/png" });
    vi.mocked(capturePageAnnotationScreenshot).mockResolvedValue(screenshot);
    const createTodo = vi.fn().mockResolvedValue({
      id: "todo-screenshot",
      client_id: "client-1",
      project_path: "/workspace",
      title: "UI: Fix selected area"
    });
    const uploadImage = vi.fn().mockResolvedValue(undefined);
    const focusTodo = vi.fn();
    window.__WEB_TERMINAL_PAGE_ANNOTATION_HOST__ = {
      getContext: () => ({
        clientId: "client-1",
        projectPath: "/workspace",
        windowId: "window-1",
        workspaceMode: "kanban",
      }),
      createTodo,
      uploadImage,
      focusTodo,
    };
    startPageAnnotationRuntime();

    const shadow = annotationShadow();
    const button = shadow.querySelector(".page-annotation-button") as HTMLButtonElement;
    const overlay = shadow.querySelector(".page-annotation-overlay") as HTMLDivElement;
    const textarea = shadow.querySelector("textarea") as HTMLTextAreaElement;
    const includeScreenshot = shadow.querySelector(".page-annotation-screenshot-input") as HTMLInputElement;
    const form = shadow.querySelector(".page-annotation-form") as HTMLFormElement;
    button.click();
    overlay.dispatchEvent(pointerEvent("pointerdown", 80, 90));
    overlay.dispatchEvent(pointerEvent("pointermove", 220, 190));
    overlay.dispatchEvent(pointerEvent("pointerup", 220, 190));
    expect(includeScreenshot.checked).toBe(false);

    textarea.value = "Fix selected area";
    includeScreenshot.checked = true;
    form.dispatchEvent(new Event("submit", { bubbles: true, cancelable: true }));
    await waitForAsyncSubmit();

    expect(capturePageAnnotationScreenshot).toHaveBeenCalledWith({
      left: 80,
      top: 90,
      width: 140,
      height: 100
    });
    expect(createTodo).toHaveBeenCalledWith(expect.objectContaining({
      title: "Annotation: Fix selected area",
      description: expect.stringContaining("Follow the user's command:\nFix selected area")
    }));
    expect(uploadImage).toHaveBeenCalledWith("todo-screenshot", screenshot);
    expect(focusTodo).toHaveBeenCalledWith(expect.objectContaining({ id: "todo-screenshot" }));
  });

  it("keeps the annotation UI out of screenshots while capture is in progress", async () => {
    window.__WEB_TERMINAL_PAGE_ANNOTATION_ENABLED__ = true;
    let frameCallback: FrameRequestCallback | null = null;
    vi.stubGlobal("requestAnimationFrame", (callback: FrameRequestCallback) => {
      frameCallback = callback;
      return 1;
    });
    HTMLElement.prototype.setPointerCapture = () => {};
    HTMLElement.prototype.releasePointerCapture = () => {};
    HTMLElement.prototype.hasPointerCapture = () => true;
    const screenshot = new File(["png"], "debug-annotation.png", { type: "image/png" });
    vi.mocked(capturePageAnnotationScreenshot).mockImplementation(async () => {
      const hostElement = document.querySelector("[data-page-annotation-ui]") as HTMLElement;
      if (hostElement.style.display !== "none") {
        throw new Error("Annotation UI was visible during screenshot capture.");
      }
      return screenshot;
    });
    window.__WEB_TERMINAL_PAGE_ANNOTATION_HOST__ = {
      getContext: () => ({
        clientId: "client-1",
        projectPath: "/workspace",
        windowId: "window-1",
        workspaceMode: "kanban",
      }),
      createTodo: vi.fn().mockResolvedValue({
        id: "todo-screenshot",
        client_id: "client-1",
        project_path: "/workspace",
        title: "UI: Fix selected area"
      }),
      uploadImage: vi.fn().mockResolvedValue(undefined),
    };
    startPageAnnotationRuntime();

    const shadow = annotationShadow();
    const button = shadow.querySelector(".page-annotation-button") as HTMLButtonElement;
    const overlay = shadow.querySelector(".page-annotation-overlay") as HTMLDivElement;
    const includeScreenshot = shadow.querySelector(".page-annotation-screenshot-input") as HTMLInputElement;
    const form = shadow.querySelector(".page-annotation-form") as HTMLFormElement;
    button.click();
    overlay.dispatchEvent(pointerEvent("pointerdown", 80, 90));
    overlay.dispatchEvent(pointerEvent("pointermove", 220, 190));
    overlay.dispatchEvent(pointerEvent("pointerup", 220, 190));

    includeScreenshot.checked = true;
    form.dispatchEvent(new Event("submit", { bubbles: true, cancelable: true }));
    frameCallback?.(0);
    await waitForAsyncSubmit();

    expect(capturePageAnnotationScreenshot).toHaveBeenCalled();
    expect((document.querySelector("[data-page-annotation-ui]") as HTMLElement).style.display).toBe("");
    expect((shadow.querySelector(".page-annotation-error") as HTMLParagraphElement).textContent).toBe("");
  });

  it("disables the screenshot option when the browser has no capture capability", () => {
    window.__WEB_TERMINAL_PAGE_ANNOTATION_ENABLED__ = true;
    vi.mocked(canCapturePageAnnotationScreenshot).mockReturnValue(false);
    startPageAnnotationRuntime();

    const shadow = annotationShadow();
    const includeScreenshot = shadow.querySelector(".page-annotation-screenshot-input") as HTMLInputElement;
    const screenshotLabel = shadow.querySelector(".page-annotation-screenshot span") as HTMLSpanElement;
    const screenshotHelp = shadow.querySelector(".page-annotation-screenshot-help") as HTMLAnchorElement;

    expect(includeScreenshot.checked).toBe(false);
    expect(includeScreenshot.disabled).toBe(true);
    expect(screenshotLabel.textContent).toContain("Screenshot unavailable");
    expect(screenshotHelp.hidden).toBe(false);
    expect(screenshotHelp.getAttribute("href")).toBe("/docs/page-annotation-screenshots.html");
    expect(screenshotHelp.getAttribute("target")).toBe("_blank");
  });

  it("shows screenshot help when browser capture fails after submission", async () => {
    window.__WEB_TERMINAL_PAGE_ANNOTATION_ENABLED__ = true;
    vi.stubGlobal("requestAnimationFrame", (callback: FrameRequestCallback) => {
      callback(0);
      return 1;
    });
    HTMLElement.prototype.setPointerCapture = () => {};
    HTMLElement.prototype.releasePointerCapture = () => {};
    HTMLElement.prototype.hasPointerCapture = () => true;
    vi.mocked(capturePageAnnotationScreenshot).mockRejectedValue(
      new Error("Permission denied by browser screen capture policy.")
    );
    window.__WEB_TERMINAL_PAGE_ANNOTATION_HOST__ = {
      getContext: () => ({
        clientId: "client-1",
        projectPath: "/workspace",
        windowId: "window-1",
        workspaceMode: "kanban",
      }),
      createTodo: vi.fn(),
      uploadImage: vi.fn(),
    };
    startPageAnnotationRuntime();

    const shadow = annotationShadow();
    const button = shadow.querySelector(".page-annotation-button") as HTMLButtonElement;
    const overlay = shadow.querySelector(".page-annotation-overlay") as HTMLDivElement;
    const includeScreenshot = shadow.querySelector(".page-annotation-screenshot-input") as HTMLInputElement;
    const form = shadow.querySelector(".page-annotation-form") as HTMLFormElement;
    const screenshotHelp = shadow.querySelector(".page-annotation-screenshot-help") as HTMLAnchorElement;
    button.click();
    overlay.dispatchEvent(pointerEvent("pointerdown", 80, 90));
    overlay.dispatchEvent(pointerEvent("pointermove", 220, 190));
    overlay.dispatchEvent(pointerEvent("pointerup", 220, 190));
    expect(screenshotHelp.hidden).toBe(true);

    includeScreenshot.checked = true;
    form.dispatchEvent(new Event("submit", { bubbles: true, cancelable: true }));
    await waitForAsyncSubmit();

    expect(screenshotHelp.hidden).toBe(false);

    const cancel = shadow.querySelector(".page-annotation-cancel") as HTMLButtonElement;
    cancel.click();
    expect(screenshotHelp.hidden).toBe(true);
  });
});

function annotationShadow(): ShadowRoot {
  const shadow = document.querySelector("[data-page-annotation-ui]")?.shadowRoot;
  if (shadow === null || shadow === undefined) {
    throw new Error("Annotation shadow root missing");
  }
  return shadow;
}

function pointerEvent(type: string, clientX: number, clientY: number): PointerEvent {
  const event = new MouseEvent(type, {
    bubbles: true,
    clientX,
    clientY
  }) as PointerEvent;
  Object.defineProperty(event, "pointerId", { value: 1 });
  return event;
}

async function waitForMicrotasks(): Promise<void> {
  await Promise.resolve();
  await Promise.resolve();
}

async function waitForAsyncSubmit(): Promise<void> {
  await waitForMicrotasks();
  await new Promise((resolve) => setTimeout(resolve, 0));
  await waitForMicrotasks();
}
