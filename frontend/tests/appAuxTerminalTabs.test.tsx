import { act } from "react";
import { describe, expect, it } from "vitest";

import * as s from "./appTestHarness";

const container = s.currentContainer;

describe("App aux terminal tabs", () => {
  it("shows terminal and todo aux terminals as tabs after jumping a todo terminal to the terminal page", async () => {
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
    await s.waitForElement(
      '[data-testid="floating-terminal-pane"]',
      (element): element is HTMLElement => element instanceof HTMLElement
    );

    const openTabButton = await s.waitForElement(
      'button[aria-label="Open in terminal tab"]',
      (element): element is HTMLButtonElement => element instanceof HTMLButtonElement
    );
    act(() => {
      openTabButton.click();
    });
    await s.waitForRequests();

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

    const terminalAuxTab = await s.waitForButtonText("terminal aux terminal", true);
    const todoAuxTab = await s.waitForButtonText("todo aux terminal", true);
    expect(terminalAuxTab.getAttribute("aria-selected")).toBe("true");
    expect(todoAuxTab.getAttribute("aria-selected")).toBe("false");
    expect(container()?.querySelector('[data-testid="aux-terminal-pane"]')?.getAttribute("data-window-id")).toBe("window-1");
    expect(container()?.querySelector('[data-testid="floating-terminal-pane"]')).toBeNull();

    act(() => {
      window.dispatchEvent(new KeyboardEvent("keydown", {
        bubbles: true,
        cancelable: true,
        key: "]",
        code: "BracketRight",
        altKey: true
      }));
    });
    await s.waitForRequests();

    expect(terminalAuxTab.getAttribute("aria-selected")).toBe("false");
    expect(todoAuxTab.getAttribute("aria-selected")).toBe("true");
    expect(container()?.querySelector('[data-testid="aux-terminal-pane"]')).toBeNull();
    expect(container()?.querySelector('[data-testid="floating-terminal-pane"]')?.getAttribute("data-window-id")).toBe("window-1");

    act(() => {
      window.dispatchEvent(new KeyboardEvent("keydown", {
        bubbles: true,
        cancelable: true,
        key: "[",
        code: "BracketLeft",
        altKey: true
      }));
    });
    await s.waitForRequests();

    expect(terminalAuxTab.getAttribute("aria-selected")).toBe("true");
    expect(todoAuxTab.getAttribute("aria-selected")).toBe("false");
    expect(container()?.querySelector('[data-testid="aux-terminal-pane"]')?.getAttribute("data-window-id")).toBe("window-1");
    expect(container()?.querySelector('[data-testid="floating-terminal-pane"]')).toBeNull();
  });
});
