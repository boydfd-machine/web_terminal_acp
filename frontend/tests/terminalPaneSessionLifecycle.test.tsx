import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, describe, expect, it, vi } from "vitest";

import { TerminalPane } from "../src/components/TerminalPane";

vi.mock("@xterm/xterm", () => ({
  Terminal: class {
    public cols = 80;
    public rows = 24;
    public element: HTMLElement | undefined;
    public options: { theme?: unknown };
    public modes = { bracketedPasteMode: false };
    public parser = {
      registerOscHandler: vi.fn(() => ({ dispose: vi.fn() }))
    };

    constructor(options: { theme?: unknown } = {}) {
      this.options = options;
    }

    open(host: HTMLElement) {
      this.element = document.createElement("div");
      this.element.className = "xterm";
      const textarea = document.createElement("textarea");
      textarea.className = "xterm-helper-textarea";
      this.element.appendChild(textarea);
      host.appendChild(this.element);
    }

    focus() {}
    dispose() {}
    write(_data: string | Uint8Array, callback?: () => void) {
      callback?.();
    }
    onWriteParsed() {
      return { dispose: vi.fn() };
    }
    onData() {
      return { dispose: vi.fn() };
    }
    attachCustomKeyEventHandler() {}
    resize(cols: number, rows: number) {
      this.cols = cols;
      this.rows = rows;
    }
    clearTextureAtlas() {}
    refresh() {}
  }
}));

globalThis.IS_REACT_ACT_ENVIRONMENT = true;

class ResizeObserverMock {
  observe() {}
  disconnect() {}
}

class WorkerMock {
  onmessage: ((event: MessageEvent) => void) | null = null;
  messages: Array<{ type?: unknown; data?: unknown; url?: string; protocols?: string[] }> = [];

  postMessage(message: { type?: unknown; data?: unknown; url?: string; protocols?: string[] }) {
    this.messages.push(message);
    if (message.type === "connect") {
      this.onmessage?.({ data: { type: "open" } } as MessageEvent);
      if (message.url?.includes("window-unavailable") === true) {
        this.onmessage?.({
          data: {
            type: "control",
            data: JSON.stringify({
              type: "terminal_status",
              status: "unavailable",
              retry_after_ms: 5000,
            }),
          },
        } as MessageEvent);
        return;
      }
      this.onmessage?.({
        data: { type: "control", data: JSON.stringify({ type: "terminal_status", status: "connected" }) }
      } as MessageEvent);
    }
  }

  terminate() {}
}

let root: Root | null = null;
let container: HTMLDivElement | null = null;
let workerInstances: WorkerMock[] = [];
const testWebSocketUrl = (
  clientId: string,
  windowId: string,
  viewId: string,
  options?: { allowMissingWindowRecreate?: boolean },
) => {
  const url = new URL(`ws://terminal/${clientId}/${windowId}`);
  url.searchParams.set("view_id", viewId);
  if (options?.allowMissingWindowRecreate === true) {
    url.searchParams.set("allow_missing_window_recreate", "1");
  }
  return url.toString();
};

function installTerminalPaneDomMocks() {
  workerInstances = [];
  globalThis.ResizeObserver = ResizeObserverMock as never;
  Object.defineProperty(HTMLElement.prototype, "clientWidth", { configurable: true, value: 400 });
  Object.defineProperty(HTMLElement.prototype, "clientHeight", { configurable: true, value: 300 });
  Object.defineProperty(document, "fonts", {
    configurable: true,
    value: { ready: Promise.resolve() },
  });
  globalThis.Worker = class extends WorkerMock {
    constructor() {
      super();
      workerInstances.push(this);
    }
  } as never;
  Element.prototype.getBoundingClientRect = vi.fn(() => ({
    width: 400,
    height: 300,
    top: 0,
    right: 400,
    bottom: 300,
    left: 0,
    x: 0,
    y: 0,
    toJSON: () => ({})
  })) as never;
  container = document.createElement("div");
  document.body.appendChild(container);
  root = createRoot(container);
}

async function flushReactEffects(): Promise<void> {
  await act(async () => {
    await Promise.resolve();
  });
}

afterEach(() => {
  act(() => {
    root?.unmount();
  });
  container?.remove();
  root = null;
  container = null;
  window.localStorage.clear();
  vi.restoreAllMocks();
  vi.useRealTimers();
});

describe("TerminalPane session lifecycle", () => {
  it("starts the terminal session after a previously empty selection receives a window", async () => {
    installTerminalPaneDomMocks();
    window.localStorage.setItem("web-terminal-acp:auth-token", "token-1");

    act(() => {
      root?.render(
        <TerminalPane
          clientId="client-1"
          windowId={null}
        />
      );
    });

    expect(workerInstances).toHaveLength(0);
    expect(container?.querySelector(".empty-terminal")?.textContent).toContain("Create or select");

    act(() => {
      root?.render(
        <TerminalPane
          clientId="client-1"
          windowId="window-1"
          webSocketUrl={testWebSocketUrl}
        />
      );
    });
    await flushReactEffects();

    expect(workerInstances).toHaveLength(1);
    const connectMessage = workerInstances[0].messages.find((message) => message.type === "connect");
    expect(connectMessage?.url).toMatch(/^ws:\/\/terminal\/client-1\/window-1\?view_id=/);
    expect(new URL(connectMessage?.url ?? "").searchParams.get("auth_token")).toBeNull();
    expect(connectMessage?.protocols).toEqual(["web-terminal-auth.token-1"]);
  });

  it("switches windows through the active session without rebuilding the websocket", async () => {
    installTerminalPaneDomMocks();

    act(() => {
      root?.render(
        <TerminalPane
          clientId="client-1"
          windowId="window-1"
          webSocketUrl={testWebSocketUrl}
        />
      );
    });
    await flushReactEffects();

    act(() => {
      root?.render(
        <TerminalPane
          clientId="client-1"
          windowId="window-2"
          webSocketUrl={testWebSocketUrl}
        />
      );
    });

    expect(workerInstances).toHaveLength(1);
    expect(workerInstances[0].messages.filter((message) => message.type === "connect")).toHaveLength(1);
    expect(workerInstances[0].messages).toContainEqual({
      type: "json",
      data: JSON.stringify({ type: "select_window", window_id: "window-2" }),
    });
  });

  it("ignores stale terminal selection confirmations from the previous window after an explicit switch", async () => {
    installTerminalPaneDomMocks();
    const onTerminalSelection = vi.fn();

    act(() => {
      root?.render(
        <TerminalPane
          clientId="client-1"
          windowId="window-1"
          webSocketUrl={testWebSocketUrl}
          onTerminalSelection={onTerminalSelection}
        />
      );
    });
    await flushReactEffects();

    const connectUrl = workerInstances[0].messages.find((message) => message.type === "connect")?.url;
    const viewId = new URL(connectUrl ?? "").searchParams.get("view_id");
    expect(viewId).not.toBeNull();

    act(() => {
      root?.render(
        <TerminalPane
          clientId="client-1"
          windowId="window-2"
          webSocketUrl={testWebSocketUrl}
          onTerminalSelection={onTerminalSelection}
        />
      );
    });

    act(() => {
      workerInstances[0].onmessage?.({
        data: {
          type: "control",
          data: JSON.stringify({
            type: "terminal_selection",
            window_id: "window-1",
            view_id: viewId,
          }),
        },
      } as MessageEvent);
    });

    expect(onTerminalSelection).not.toHaveBeenCalledWith("window-1");

    act(() => {
      workerInstances[0].onmessage?.({
        data: {
          type: "control",
          data: JSON.stringify({
            type: "terminal_selection",
            window_id: "window-2",
            view_id: viewId,
          }),
        },
      } as MessageEvent);
    });

    expect(onTerminalSelection).toHaveBeenCalledWith("window-2");
  });

  it("sends recover permission only when the pane is explicitly allowed to recreate missing windows", async () => {
    installTerminalPaneDomMocks();

    act(() => {
      root?.render(
        <TerminalPane
          clientId="client-1"
          windowId="window-1"
          webSocketUrl={testWebSocketUrl}
          allowMissingWindowRecreate={true}
        />
      );
    });
    await flushReactEffects();

    expect(workerInstances[0].messages.find((message) => message.type === "connect")?.url)
      .toMatch(/allow_missing_window_recreate=1/);

    act(() => {
      root?.render(
        <TerminalPane
          clientId="client-1"
          windowId="window-2"
          webSocketUrl={testWebSocketUrl}
          allowMissingWindowRecreate={true}
        />
      );
    });

    expect(workerInstances[0].messages).toContainEqual({
      type: "json",
      data: JSON.stringify({
        type: "select_window",
        window_id: "window-2",
        allow_missing_window_recreate: true,
      }),
    });
  });

  it("waits for the reconnect timer instead of reconnecting during priority reconciliation", async () => {
    vi.useFakeTimers();
    installTerminalPaneDomMocks();

    act(() => {
      root?.render(
        <TerminalPane
          clientId="client-1"
          windowId="window-unavailable"
          webSocketUrl={testWebSocketUrl}
        />
      );
    });
    await flushReactEffects();

    expect(workerInstances).toHaveLength(1);

    await act(async () => {
      vi.advanceTimersByTime(4999);
      await Promise.resolve();
    });
    expect(workerInstances).toHaveLength(1);

    await act(async () => {
      vi.advanceTimersByTime(1);
      await Promise.resolve();
    });
    expect(workerInstances).toHaveLength(2);
  });

  it("rebuilds an unavailable same-client session when the selected window changes", async () => {
    installTerminalPaneDomMocks();

    act(() => {
      root?.render(
        <TerminalPane
          clientId="client-1"
          windowId="window-unavailable"
          webSocketUrl={testWebSocketUrl}
        />
      );
    });
    await flushReactEffects();

    expect(workerInstances).toHaveLength(1);
    expect(workerInstances[0].messages.find((message) => message.type === "connect")?.url)
      .toMatch(/^ws:\/\/terminal\/client-1\/window-unavailable\?view_id=/);

    act(() => {
      root?.render(
        <TerminalPane
          clientId="client-1"
          windowId="window-2"
          webSocketUrl={testWebSocketUrl}
        />
      );
    });
    await flushReactEffects();

    expect(workerInstances).toHaveLength(2);
    expect(workerInstances[1].messages.find((message) => message.type === "connect")?.url)
      .toMatch(/^ws:\/\/terminal\/client-1\/window-2\?view_id=/);
  });

  it("rebuilds when a stale same-client session becomes unavailable after selection changes", async () => {
    installTerminalPaneDomMocks();

    act(() => {
      root?.render(
        <TerminalPane
          clientId="client-1"
          windowId="window-1"
          webSocketUrl={testWebSocketUrl}
        />
      );
    });
    await flushReactEffects();

    act(() => {
      root?.render(
        <TerminalPane
          clientId="client-1"
          windowId="window-2"
          webSocketUrl={testWebSocketUrl}
        />
      );
    });
    await flushReactEffects();

    expect(workerInstances).toHaveLength(1);

    act(() => {
      workerInstances[0].onmessage?.({
        data: {
          type: "control",
          data: JSON.stringify({
            type: "terminal_status",
            status: "unavailable",
            retry_after_ms: 5000,
          }),
        },
      } as MessageEvent);
    });
    await flushReactEffects();

    expect(workerInstances).toHaveLength(2);
    expect(workerInstances[1].messages.find((message) => message.type === "connect")?.url)
      .toMatch(/^ws:\/\/terminal\/client-1\/window-2\?view_id=/);
  });

  it("can switch windows without syncing app terminal selection", async () => {
    installTerminalPaneDomMocks();
    const onTerminalSelection = vi.fn();

    act(() => {
      root?.render(
        <TerminalPane
          clientId="client-1"
          windowId="window-1"
          webSocketUrl={testWebSocketUrl}
          selectionEnabled={false}
          terminalSwitchingEnabled={true}
          onTerminalSelection={onTerminalSelection}
        />
      );
    });
    await flushReactEffects();

    act(() => {
      root?.render(
        <TerminalPane
          clientId="client-1"
          windowId="window-2"
          webSocketUrl={testWebSocketUrl}
          selectionEnabled={false}
          terminalSwitchingEnabled={true}
          onTerminalSelection={onTerminalSelection}
        />
      );
    });

    expect(workerInstances).toHaveLength(1);
    expect(workerInstances[0].messages.filter((message) => message.type === "connect")).toHaveLength(1);
    expect(workerInstances[0].messages).toContainEqual({
      type: "json",
      data: JSON.stringify({ type: "select_window", window_id: "window-2" }),
    });
    expect(onTerminalSelection).not.toHaveBeenCalled();
  });
});
