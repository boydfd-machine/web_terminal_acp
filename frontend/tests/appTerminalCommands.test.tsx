import { act } from "react";
import { describe, expect, it, vi } from "vitest";
import { CODEX_COMPOSER_SUBMIT_INPUT } from "../src/terminalQuickKeys";
import * as s from "./appTestHarness";

const container = s.currentContainer;

describe("App new terminal shortcut", () => {
  it("creates a shell terminal directly without opening the agent picker", async () => {
    s.renderApp();
    await s.waitForNewTerminalButton();

    act(() => {
      window.dispatchEvent(new KeyboardEvent("keydown", {
        bubbles: true,
        cancelable: true,
        key: "n",
        code: "KeyN",
        altKey: true
      }));
    });
    await s.waitForRequests();

    const createRequest = s.fetchMock.mock.calls.find(([input, init]) => (
      s.pathFor(input as RequestInfo | URL) === "/api/clients/client-1/windows"
      && init?.method === "POST"
    ));
    expect(createRequest).toBeDefined();
    expect(JSON.parse(createRequest?.[1]?.body as string)).toEqual({
      cwd: null,
      shell_command: null,
      folder_path: null,
      agent_launch: null
    });
    expect(container()?.querySelector(".terminal-create-modal")).toBeNull();
  });
  it("clones the selected terminal from the default shortcut", async () => {
    s.renderApp();
    await s.waitForNewTerminalButton();

    act(() => {
      window.dispatchEvent(new KeyboardEvent("keydown", {
        bubbles: true,
        cancelable: true,
        key: "p",
        code: "KeyP",
        altKey: true
      }));
    });
    await s.waitForRequests();

    const cloneRequest = s.fetchMock.mock.calls.find(([input, init]) => (
      s.pathFor(input as RequestInfo | URL) === "/api/clients/client-1/windows/window-1/clone"
      && init?.method === "POST"
    ));
    expect(cloneRequest).toBeDefined();
    expect(JSON.parse(cloneRequest?.[1]?.body as string)).toEqual({
      mode: "linked",
      prompt: null,
      collect_paths: null
    });
    await s.waitForElement(".terminal-clone-progress", (element): element is HTMLDivElement => element instanceof HTMLDivElement);
    expect(container()?.querySelector(".terminal-clone-progress")?.textContent).toContain("Terminal cloned");
  });
  it("opens a searchable related terminal switcher from the default shortcut", async () => {
    s.renderApp();
    await s.waitForSelectedProject("/workspace");
    await s.waitForButtonText("Codex clone", true);

    act(() => {
      window.dispatchEvent(new KeyboardEvent("keydown", {
        bubbles: true,
        cancelable: true,
        key: "t",
        code: "KeyT",
        altKey: true
      }));
    });

    const cloneButton = await s.waitForSwitcherWindowButton("Codex clone");
    expect(container()?.querySelector(".terminal-switcher-header h2")?.textContent).toBe("Related terminals");
    expect(cloneButton.className).toContain("switcher-window");

    const search = await s.waitForElement(
      ".terminal-switcher input",
      (element): element is HTMLInputElement => element instanceof HTMLInputElement
    );
    const descriptor = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value");
    act(() => {
      descriptor?.set?.call(search, "linked");
      search.dispatchEvent(new Event("input", { bubbles: true }));
    });
    await s.waitForRequests();

    expect(await s.waitForSwitcherWindowButton("Codex clone")).toBeDefined();
    expect(Array.from(container()?.querySelectorAll(".terminal-switcher .switcher-window") ?? []).some(
      (button) => button.textContent?.includes("Codex window")
    )).toBe(false);
  });
  it("submits inline Agent preview quick input to Codex with enhanced Enter", async () => {
    s.renderApp();
    const agentTab = await s.waitForButtonText("Agent");

    act(() => {
      agentTab.click();
    });

    const textarea = await s.waitForElement(
      ".agent-record-viewer .agent-record-quick-input textarea",
      (element): element is HTMLTextAreaElement => element instanceof HTMLTextAreaElement
    );
    const descriptor = Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype, "value");
    const scheduledTimeouts: Array<{ callback: TimerHandler; delay?: number }> = [];
    const setTimeoutSpy = vi.spyOn(window, "setTimeout").mockImplementation((callback, delay) => {
      scheduledTimeouts.push({ callback, delay });
      return scheduledTimeouts.length;
    });
    act(() => {
      descriptor?.set?.call(textarea, "fix this");
      textarea.dispatchEvent(new Event("input", { bubbles: true }));
      textarea.dispatchEvent(new KeyboardEvent("keydown", { bubbles: true, cancelable: true, key: "Enter" }));
    });

    expect(s.submitQuickInputMock).toHaveBeenCalledWith(`fix this${CODEX_COMPOSER_SUBMIT_INPUT}`);
    const firstFollowup = scheduledTimeouts.find((timeout) => timeout.delay === 500);
    expect(firstFollowup).toBeDefined();
    if (typeof firstFollowup?.callback === "function") {
      act(() => {
        firstFollowup.callback();
      });
    }
    expect(s.submitQuickInputMock).toHaveBeenNthCalledWith(2, CODEX_COMPOSER_SUBMIT_INPUT);
    setTimeoutSpy.mockRestore();
  });
  it("submits expanded Agent Record quick input to Codex with enhanced Enter", async () => {
    s.renderApp();
    const agentTab = await s.waitForButtonText("Agent");

    act(() => {
      agentTab.click();
    });
    const expandButton = await s.waitForElement(
      'button[aria-label="Expand agent record"]',
      (element): element is HTMLButtonElement => element instanceof HTMLButtonElement && !element.disabled
    );
    act(() => {
      expandButton.click();
    });

    const textarea = await s.waitForElement(
      ".agent-record-modal .agent-record-quick-input textarea",
      (element): element is HTMLTextAreaElement => element instanceof HTMLTextAreaElement
    );
    const descriptor = Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype, "value");
    act(() => {
      descriptor?.set?.call(textarea, "fix this");
      textarea.dispatchEvent(new Event("input", { bubbles: true }));
      textarea.dispatchEvent(new KeyboardEvent("keydown", { bubbles: true, cancelable: true, key: "Enter" }));
    });

    expect(s.submitQuickInputMock).toHaveBeenCalledWith(`fix this${CODEX_COMPOSER_SUBMIT_INPUT}`);
  });
  it("keeps Agent Preview open when the active terminal reports the same selection", async () => {
    s.renderApp();
    const previewButton = await s.waitForButtonText("Agent Preview", true);
    act(() => {
      previewButton.click();
    });
    await s.waitForElement(
      ".agent-record-modal",
      (element): element is HTMLElement => element instanceof HTMLElement
    );

    await s.reportTerminalPaneSelection("window-1");
    await s.waitForRequests();

    expect(container()?.querySelector(".agent-record-modal")).not.toBeNull();
    expect(container()?.querySelector(".agent-record-modal h3")?.textContent).toBe("Agent Record");
    expect(`${window.location.pathname}${window.location.search}`).toBe("/clients/client-1/terminals/window-1");
  });
  it("collapses and restores the right detail panel from the app shell", async () => {
    s.renderApp();
    await s.waitForNewTerminalButton();

    const collapseButton = await s.waitForElement(
      'button[aria-label="Collapse details"]',
      (element): element is HTMLButtonElement => element instanceof HTMLButtonElement && !element.disabled
    );
    act(() => {
      collapseButton.click();
    });
    await s.waitForRequests();

    const appShell = container()?.querySelector(".app-shell");
    expect(appShell?.classList.contains("detail-panel-collapsed")).toBe(true);

    const restoreButton = await s.waitForButtonText("Details", true);
    act(() => {
      restoreButton.click();
    });
    await s.waitForRequests();

    expect(appShell?.classList.contains("detail-panel-collapsed")).toBe(false);
  });
  it("shows built-in navigation actions in the mobile shortcut drawer", async () => {
    Object.defineProperty(window, "innerWidth", { configurable: true, value: 390 });
    Object.defineProperty(window, "innerHeight", { configurable: true, value: 844 });
    window.localStorage.setItem("web-terminal-acp:theme-skin", "stripe");
    s.useMobileMediaQueries();
    s.renderApp();

    const previewButton = await s.waitForButtonText("Agent Preview", true);
    expect(document.body.classList.contains("theme-skin-stripe")).toBe(true);
    expect(previewButton.className).toContain("mobile-agent-preview-button");
    expect(previewButton.closest(".terminal-toolbar")).not.toBeNull();
    await s.waitForButtonText("Controls", true);

    const fabButton = await s.waitForBodyElement(
      ".mobile-shortcut-fab-ball",
      (element): element is HTMLButtonElement => element instanceof HTMLButtonElement
    );
    act(() => {
      fabButton.click();
    });
    await s.waitForBodyElement(
      ".mobile-shortcut-fab-drawer",
      (element): element is HTMLElement => element instanceof HTMLElement
    );
    const shortcutLabels = Array.from(document.body.querySelectorAll(".mobile-shortcut-fab-item")).map(
      (item) => item.textContent ?? ""
    );
    expect(shortcutLabels.some((label) => label.includes("Kanban"))).toBe(true);
    expect(shortcutLabels.some((label) => label.includes("Agent Preview"))).toBe(true);
    expect(shortcutLabels.some((label) => label.includes("Switch terminals across clients"))).toBe(true);
    expect(shortcutLabels.some((label) => label.includes("Switch client"))).toBe(true);

    const kanbanButton = Array.from(document.body.querySelectorAll(".mobile-shortcut-fab-item")).find(
      (item): item is HTMLButtonElement => item instanceof HTMLButtonElement && item.textContent?.includes("Kanban") === true
    );
    expect(kanbanButton).toBeInstanceOf(HTMLButtonElement);
    act(() => {
      kanbanButton?.click();
    });
    await s.waitForElement(
      ".project-kanban-workspace",
      (element): element is HTMLElement => element instanceof HTMLElement
    );
    expect(container()?.querySelector(".project-todo-board-shell")).not.toBeNull();
    expect(container()?.querySelector('[data-testid="terminal-pane"]')?.getAttribute(
      "data-has-terminal-selection-handler"
    )).toBe("false");
    const terminalTab = await s.waitForButtonText("Terminal", true);
    act(() => {
      terminalTab.click();
    });
    await s.waitForRequests();

    const enabledPreviewButton = await s.waitForButtonText("Agent Preview", true);
    act(() => enabledPreviewButton.click());
    await s.waitForElement(
      ".agent-record-modal",
      (element): element is HTMLElement => element instanceof HTMLElement
    );
    expect(container()?.querySelector(".agent-record-modal h3")?.textContent).toBe("Agent Record");
  });
  it("opens a Kanban card terminal in a floating drawer and can jump to the terminal tab", async () => {
    s.renderApp();
    await s.waitForSelectedProject("/workspace");

    const kanbanButton = await s.waitForButtonText("Kanban", true);
    act(() => {
      kanbanButton.click();
    });
    await s.waitForElement(".project-kanban-workspace", (element): element is HTMLElement => element instanceof HTMLElement);

    const cardTerminalButton = await s.waitForElement(
      'button[aria-label="Open terminal for Fix board drag"]',
      (element): element is HTMLButtonElement => element instanceof HTMLButtonElement
    );
    act(() => {
      cardTerminalButton.click();
    });
    await s.waitForRequests();

    const drawer = await s.waitForElement(
      '.aux-terminal-drawer[data-mode="terminal"]',
      (element): element is HTMLElement => element instanceof HTMLElement
    );
    expect(drawer.getAttribute("data-open")).toBe("true");
    expect(container()?.querySelector(".project-kanban-workspace")).not.toBeNull();
    expect(container()?.querySelector('[data-testid="floating-terminal-pane"]')?.getAttribute("data-window-id")).toBe("window-1");

    const openTabButton = await s.waitForElement(
      'button[aria-label="Open in terminal tab"]',
      (element): element is HTMLButtonElement => element instanceof HTMLButtonElement
    );
    act(() => {
      openTabButton.click();
    });
    await s.waitForRequests();

    expect(container()?.querySelector(".aux-terminal-drawer")?.getAttribute("data-open")).toBe("false");
    expect(container()?.querySelector('[data-testid="floating-terminal-pane"]')).toBeNull();
    expect(s.terminalPaneUnmounts.get("floating-terminal-pane") ?? 0).toBe(1);
    expect(container()?.querySelector('.workspace-mode-toggle button[aria-pressed="true"]')?.textContent).toBe("Terminal");
    expect(container()?.querySelector(".project-kanban-workspace")?.closest(".workspace-mode-pane")?.hasAttribute("hidden")).toBe(true);
    await s.waitForTerminalPaneWindow("window-1");
  });
  it("opens an aux terminal drawer from the default shortcut", async () => {
    s.renderApp();
    await s.waitForNewTerminalButton();

    act(() => {
      window.dispatchEvent(new KeyboardEvent("keydown", {
        bubbles: true,
        cancelable: true,
        key: "A",
        code: "KeyA",
        altKey: true,
        shiftKey: true
      }));
    });
    await s.waitForRequests();

    const ensureRequest = s.fetchMock.mock.calls.find(([input, init]) => (
      s.pathFor(input as RequestInfo | URL) === "/api/clients/client-1/windows/window-1/aux-terminal/ensure"
      && init?.method === "POST"
    ));
    expect(ensureRequest).toBeDefined();
    expect(container()?.querySelector(".aux-terminal-drawer")).not.toBeNull();
    expect(container()?.querySelector('[data-testid="aux-terminal-pane"]')).not.toBeNull();
  });
  it("shows artifact terminals only after explicit artifact selection", async () => {
    s.renderApp();
    await s.waitForNewTerminalButton();
    await s.waitForRequests();

    expect(container()?.querySelector(".aux-terminal-drawer")).toBeNull();

    act(() => {
      window.dispatchEvent(new KeyboardEvent("keydown", {
        bubbles: true,
        cancelable: true,
        key: "a",
        code: "KeyA",
        altKey: true
      }));
    });

    const artifactButton = await s.waitForElement(
      ".artifact-quick-list button",
      (element): element is HTMLButtonElement => element instanceof HTMLButtonElement
    );
    expect(artifactButton.textContent).toContain("Trace graph");
    act(() => {
      artifactButton.click();
    });
    await s.waitForRequests();

    const drawer = container()?.querySelector(".aux-terminal-drawer");
    expect(drawer?.getAttribute("data-mode")).toBe("artifact");
    expect(drawer?.getAttribute("data-open")).toBe("true");
    expect(container()?.querySelector('[data-testid="aux-terminal-pane"]')?.getAttribute("data-window-id")).toBe("artifact-window-1");
  });
  it("keeps the aux terminal mounted when the drawer is closed", async () => {
    s.renderApp();
    await s.waitForNewTerminalButton();

    act(() => {
      window.dispatchEvent(new KeyboardEvent("keydown", {
        bubbles: true,
        cancelable: true,
        key: "A",
        code: "KeyA",
        altKey: true,
        shiftKey: true
      }));
    });
    await s.waitForRequests();

    const drawer = container()?.querySelector(".aux-terminal-drawer");
    expect(drawer?.getAttribute("data-open")).toBe("true");
    expect(container()?.querySelector('[data-testid="aux-terminal-pane"]')).not.toBeNull();

    const closeButton = await s.waitForButtonText("Close", true);
    act(() => {
      closeButton.click();
    });
    await s.waitForRequests();

    expect(container()?.querySelector(".aux-terminal-drawer")?.getAttribute("data-open")).toBe("false");
    expect(container()?.querySelector('[data-testid="aux-terminal-pane"]')).not.toBeNull();
    expect(s.terminalPaneUnmounts.get("aux-terminal-pane") ?? 0).toBe(0);
  });
  it("persists the dragged aux terminal window position in browser storage", async () => {
    Object.defineProperty(window, "innerWidth", { configurable: true, value: 1200 });
    Object.defineProperty(window, "innerHeight", { configurable: true, value: 800 });
    vi.spyOn(HTMLElement.prototype, "getBoundingClientRect").mockImplementation(function rectForElement() {
      if (this.classList.contains("workspace")) {
        return {
          x: 320,
          y: 0,
          left: 320,
          top: 0,
          right: 840,
          bottom: 800,
          width: 520,
          height: 800,
          toJSON: () => ({})
        };
      }

      return {
        x: 0,
        y: 0,
        left: 0,
        top: 0,
        right: 0,
        bottom: 0,
        width: 0,
        height: 0,
        toJSON: () => ({})
      };
    });

    s.renderApp();
    await s.waitForNewTerminalButton();

    act(() => {
      window.dispatchEvent(new KeyboardEvent("keydown", {
        bubbles: true,
        cancelable: true,
        key: "A",
        code: "KeyA",
        altKey: true,
        shiftKey: true
      }));
    });
    await s.waitForRequests();

    const drawer = await s.waitForElement(".aux-terminal-drawer", (element): element is HTMLElement => element instanceof HTMLElement);
    const header = await s.waitForElement(".aux-terminal-header", (element): element is HTMLElement => element instanceof HTMLElement);

    act(() => {
      header.dispatchEvent(new PointerEvent("pointerdown", {
        bubbles: true,
        cancelable: true,
        pointerId: 1,
        button: 0,
        clientX: 20,
        clientY: 100
      }));
      header.dispatchEvent(new PointerEvent("pointermove", {
        bubbles: true,
        cancelable: true,
        pointerId: 1,
        clientX: 120,
        clientY: 50
      }));
      header.dispatchEvent(new PointerEvent("pointerup", {
        bubbles: true,
        cancelable: true,
        pointerId: 1,
        clientX: 120,
        clientY: 50
      }));
    });
    await s.waitForRequests();

    expect(JSON.parse(window.localStorage.getItem(s.AUX_TERMINAL_POSITION_STORAGE_KEY) ?? "null")).toEqual({
      x: 420,
      y: 350
    });
    expect(drawer.style.left).toBe("420px");
    expect(drawer.style.top).toBe("350px");

    s.disposeRenderedApp();

    s.renderApp();
    await s.waitForNewTerminalButton();
    act(() => {
      window.dispatchEvent(new KeyboardEvent("keydown", {
        bubbles: true,
        cancelable: true,
        key: "A",
        code: "KeyA",
        altKey: true,
        shiftKey: true
      }));
    });
    await s.waitForRequests();

    const restoredDrawer = await s.waitForElement(".aux-terminal-drawer", (element): element is HTMLElement => element instanceof HTMLElement);
    expect(restoredDrawer.style.left).toBe("420px");
    expect(restoredDrawer.style.top).toBe("350px");
  });
});
