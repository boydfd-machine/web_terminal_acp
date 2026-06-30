import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, expect, vi } from "vitest";

import App from "../src/App";
import { AppPromptProvider } from "../src/components/AppPromptProvider";
import {
  TestPointerEvent,
} from "./appTestFixtures";
import { createAppTestFetchMock } from "./appTestFetchMock";

globalThis.IS_REACT_ACT_ENVIRONMENT = true;

const AUX_TERMINAL_POSITION_STORAGE_KEY = "web-terminal-acp:aux-terminal-window-position";
const { submitQuickInputMock, terminalPanePropsByTestId, terminalPaneUnmounts } = vi.hoisted(() => ({
  submitQuickInputMock: vi.fn(),
  terminalPanePropsByTestId: new Map<string, {
    onTerminalSelection?: (windowId: string) => void;
    onTerminalConnectionStatusChange?: (status: "connecting" | "connected" | "reconnecting" | "unavailable" | "error") => void;
  }>(),
  terminalPaneUnmounts: new Map<string, number>()
}));

vi.mock("../src/components/TerminalPane", async () => {
  const React = await import("react");
  return {
    TerminalPane: React.forwardRef((props: {
      allowMissingWindowRecreate?: boolean;
      selectionEnabled?: boolean;
      terminalSwitchingEnabled?: boolean;
      windowId?: string | null;
    }, ref) => {
      const testId = props.selectionEnabled === false
        ? props.onTerminalSelection !== undefined
          ? "terminal-pane"
          : props.terminalSwitchingEnabled === true ? "floating-terminal-pane" : "aux-terminal-pane"
        : "terminal-pane";
      terminalPanePropsByTestId.set(testId, props);
      React.useImperativeHandle(ref, () => ({
        focus: vi.fn(),
        openQuickInput: vi.fn(),
        refit: vi.fn(),
        setQuickInputDraft: vi.fn(),
        submitQuickInput: submitQuickInputMock
      }));
      React.useEffect(() => {
        return () => {
          terminalPaneUnmounts.set(testId, (terminalPaneUnmounts.get(testId) ?? 0) + 1);
          terminalPanePropsByTestId.delete(testId);
        };
      }, [testId]);
      return React.createElement("div", {
        "data-testid": testId,
        "data-window-id": props.windowId ?? "",
        "data-has-terminal-selection-handler": props.onTerminalSelection === undefined ? "false" : "true",
        "data-selection-enabled": props.selectionEnabled === false ? "false" : "true",
        "data-allow-missing-window-recreate": props.allowMissingWindowRecreate === true ? "true" : "false"
      });
    })
  };
});

let root: Root | null = null;
let container: HTMLDivElement | null = null;
let queryClient: QueryClient | null = null;
let fetchMock: ReturnType<typeof vi.fn>;

function useMobileMediaQueries(): void {
  vi.stubGlobal("matchMedia", vi.fn((query: string) => ({
    matches: query === "(max-width: 1024px)",
    media: query,
    onchange: null,
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    addListener: vi.fn(),
    removeListener: vi.fn(),
    dispatchEvent: vi.fn()
  })));
}

async function waitForRequests(): Promise<void> {
  await act(async () => {
    await new Promise((resolve) => setTimeout(resolve, 0));
  });
}

async function waitForNewTerminalButton(): Promise<void> {
  for (let attempt = 0; attempt < 20; attempt += 1) {
    await waitForRequests();
    const button = Array.from(container?.querySelectorAll("button") ?? []).find(
      (candidate) => candidate.textContent === "New terminal" && !candidate.disabled
    );
    if (button instanceof HTMLButtonElement) {
      return;
    }
  }

  throw new Error("New terminal button was not ready");
}

async function waitForElement<T extends Element>(
  selector: string,
  guard: (element: Element) => element is T
): Promise<T> {
  for (let attempt = 0; attempt < 20; attempt += 1) {
    await waitForRequests();
    const element = container?.querySelector(selector);
    if (element !== undefined && element !== null && guard(element)) {
      return element;
    }
  }

  throw new Error(`Element ${selector} was not ready`);
}

async function waitForBodyElement<T extends Element>(
  selector: string,
  guard: (element: Element) => element is T
): Promise<T> {
  for (let attempt = 0; attempt < 20; attempt += 1) {
    await waitForRequests();
    const element = document.body.querySelector(selector);
    if (element !== null && guard(element)) {
      return element;
    }
  }

  throw new Error(`Body element ${selector} was not ready`);
}

async function waitForButtonText(text: string, enabled = false): Promise<HTMLButtonElement> {
  for (let attempt = 0; attempt < 20; attempt += 1) {
    await waitForRequests();
    const button = Array.from(container?.querySelectorAll("button") ?? []).find(
      (candidate) => candidate.textContent === text && (!enabled || !candidate.disabled)
    );
    if (button instanceof HTMLButtonElement) {
      return button;
    }
  }

  throw new Error(`Button ${text} was not ready`);
}

async function waitForProjectCard(projectPath: string): Promise<HTMLButtonElement> {
  for (let attempt = 0; attempt < 20; attempt += 1) {
    await waitForRequests();
    const button = container?.querySelector(`button.terminal-project-card[title="${projectPath}"]`);
    if (button instanceof HTMLButtonElement) {
      return button;
    }
  }

  throw new Error(`Project card ${projectPath} was not ready`);
}

async function waitForProjectDetailButton(projectPath: string): Promise<HTMLButtonElement> {
  for (let attempt = 0; attempt < 20; attempt += 1) {
    await waitForRequests();
    const button = container?.querySelector(`button.terminal-project-detail-button[title="Open ${projectPath} details"]`);
    if (button instanceof HTMLButtonElement) {
      return button;
    }
  }

  throw new Error(`Project detail button ${projectPath} was not ready`);
}

async function waitForSelectedProject(projectPath: string): Promise<void> {
  for (let attempt = 0; attempt < 20; attempt += 1) {
    const button = await waitForProjectCard(projectPath);
    if (button.getAttribute("aria-current") === "true") {
      return;
    }
  }

  throw new Error(`Project ${projectPath} was not selected`);
}

async function waitForTerminalPaneWindow(windowId: string): Promise<void> {
  for (let attempt = 0; attempt < 20; attempt += 1) {
    await waitForRequests();
    const pane = container?.querySelector('[data-testid="terminal-pane"]');
    if (pane?.getAttribute("data-window-id") === windowId) {
      return;
    }
  }

  throw new Error(`Terminal pane did not switch to ${windowId}`);
}

async function reportTerminalPaneStatus(
  status: "connecting" | "connected" | "reconnecting" | "unavailable" | "error",
  testId = "terminal-pane"
): Promise<void> {
  await act(async () => {
    terminalPanePropsByTestId.get(testId)?.onTerminalConnectionStatusChange?.(status);
    await new Promise((resolve) => setTimeout(resolve, 0));
  });
}

async function reportTerminalPaneSelection(windowId: string, testId = "terminal-pane"): Promise<void> {
  await act(async () => {
    terminalPanePropsByTestId.get(testId)?.onTerminalSelection?.(windowId);
    await new Promise((resolve) => setTimeout(resolve, 0));
  });
}

async function waitForSwitcherWindowButton(text: string): Promise<HTMLButtonElement> {
  for (let attempt = 0; attempt < 20; attempt += 1) {
    await waitForRequests();
    const button = Array.from(container?.querySelectorAll(".terminal-switcher .switcher-window") ?? []).find(
      (candidate) => candidate.textContent?.includes(text)
    );
    if (button instanceof HTMLButtonElement && !button.disabled) {
      return button;
    }
  }

  throw new Error(`Switcher window ${text} was not ready`);
}

async function waitForSwitcherWindowButtonText(
  text: string,
  expectedText: string
): Promise<HTMLButtonElement> {
  for (let attempt = 0; attempt < 20; attempt += 1) {
    const button = await waitForSwitcherWindowButton(text);
    if (button.textContent?.includes(expectedText)) {
      return button;
    }
  }

  throw new Error(`Switcher window ${text} did not include ${expectedText}`);
}

function renderApp(): void {
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
        <AppPromptProvider>
          <App />
        </AppPromptProvider>
      </QueryClientProvider>
    );
  });
}

beforeEach(() => {
  window.history.replaceState(null, "", "/clients/client-1/terminals/window-1");
  window.localStorage.clear();
  Object.defineProperty(window, "innerWidth", { configurable: true, value: 1024 });
  Object.defineProperty(window, "innerHeight", { configurable: true, value: 768 });
  Object.defineProperty(window, "PointerEvent", { configurable: true, value: TestPointerEvent });
  HTMLElement.prototype.setPointerCapture = vi.fn();
  HTMLElement.prototype.releasePointerCapture = vi.fn();
  HTMLElement.prototype.hasPointerCapture = vi.fn(() => true);
  HTMLElement.prototype.scrollIntoView = vi.fn();
  submitQuickInputMock.mockReset();
  submitQuickInputMock.mockReturnValue(true);
  terminalPaneUnmounts.clear();
  fetchMock = createAppTestFetchMock();
  vi.stubGlobal("fetch", fetchMock);
  vi.stubGlobal("WebSocket", class {
    close() {}
  });
  vi.stubGlobal("matchMedia", vi.fn((query: string) => ({
    matches: false,
    media: query,
    onchange: null,
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    addListener: vi.fn(),
    removeListener: vi.fn(),
    dispatchEvent: vi.fn()
  })));
  vi.spyOn(window, "requestAnimationFrame").mockImplementation((callback: FrameRequestCallback) => {
    callback(0);
    return 1;
  });
  vi.spyOn(window, "cancelAnimationFrame").mockImplementation(() => {});
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
  vi.useRealTimers();
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
  window.localStorage.clear();
});


function currentContainer(): HTMLDivElement | null {
  return container;
}

function disposeRenderedApp(): void {
  act(() => {
    root?.unmount();
  });
  document.body.replaceChildren();
  queryClient?.clear();
  root = null;
  container = null;
  queryClient = null;
}

export {
  AUX_TERMINAL_POSITION_STORAGE_KEY,
  submitQuickInputMock,
  reportTerminalPaneStatus,
  reportTerminalPaneSelection,
  terminalPaneUnmounts,
  fetchMock,
  renderApp,
  disposeRenderedApp,
  currentContainer,
  useMobileMediaQueries,
  waitForRequests,
  waitForNewTerminalButton,
  waitForElement,
  waitForBodyElement,
  waitForButtonText,
  waitForProjectCard,
  waitForProjectDetailButton,
  waitForSelectedProject,
  waitForTerminalPaneWindow,
  waitForSwitcherWindowButton,
  waitForSwitcherWindowButtonText
};

export { pathFor, searchParamFor } from "./appTestFetchMock";
