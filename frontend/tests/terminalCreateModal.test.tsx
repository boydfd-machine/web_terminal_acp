import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, useState, type ReactNode } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { TerminalCreateModal, type TerminalCreateContext, type TerminalCreateSubmit } from "../src/components/TerminalCreateModal";

globalThis.IS_REACT_ACT_ENVIRONMENT = true;

let root: Root | null = null;
let container: HTMLDivElement | null = null;
let queryClient: QueryClient | null = null;

function renderTerminalCreateModal(options: {
  context?: TerminalCreateContext;
  children?: ReactNode;
  onClose?: () => void;
  onSubmit?: (payload: TerminalCreateSubmit) => void;
} = {}) {
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
        <TerminalCreateModal
          isOpen
          clientId="client-1"
          context={options.context ?? { title: "New terminal", description: "local" }}
          onClose={options.onClose ?? (() => {})}
          onSubmit={options.onSubmit ?? (() => {})}
        >
          {options.children}
        </TerminalCreateModal>
      </QueryClientProvider>
    );
  });
}

async function flushQueries() {
  await act(async () => {
    await Promise.resolve();
    await Promise.resolve();
  });
}

async function waitFor(assertion: () => void) {
  let lastError: unknown = null;
  for (let index = 0; index < 20; index += 1) {
    try {
      assertion();
      return;
    } catch (error) {
      lastError = error;
      await act(async () => {
        await new Promise((resolve) => setTimeout(resolve, 0));
      });
    }
  }
  throw lastError;
}

function setSelectValue(target: HTMLSelectElement, value: string): void {
  const setter = Object.getOwnPropertyDescriptor(HTMLSelectElement.prototype, "value")?.set;
  act(() => {
    setter?.call(target, value);
    target.dispatchEvent(new Event("change", { bubbles: true }));
  });
}

beforeEach(() => {
  vi.useFakeTimers();
  vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(JSON.stringify({
    agent_clients: [
      {
        id: "codex",
        provider_id: "codex",
        label: "Codex",
        aliases: [],
        default_command: "codex",
        command_names: ["codex"],
        capabilities: { launch: true, client_config: true }
      }
    ],
    profiles: []
  }), { status: 200, headers: { "Content-Type": "application/json" } }));
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
  window.localStorage.clear();
});

describe("TerminalCreateModal", () => {
  it("takes focus from a focused terminal textarea and closes before terminal Escape handling", () => {
    const terminalTextarea = document.createElement("textarea");
    terminalTextarea.className = "xterm-helper-textarea";
    const terminalEscapeHandler = vi.fn((event: KeyboardEvent) => {
      event.preventDefault();
      event.stopPropagation();
    });
    terminalTextarea.addEventListener("keydown", terminalEscapeHandler);
    document.body.appendChild(terminalTextarea);
    terminalTextarea.focus();

    const onClose = vi.fn();
    renderTerminalCreateModal({ onClose });

    act(() => {
      vi.advanceTimersByTime(16);
    });

    expect(document.activeElement).toBe(container?.querySelector(".terminal-create-modal"));

    act(() => {
      terminalTextarea.dispatchEvent(new KeyboardEvent("keydown", {
        bubbles: true,
        cancelable: true,
        key: "Escape"
      }));
    });

    expect(onClose).toHaveBeenCalledTimes(1);
    expect(terminalEscapeHandler).not.toHaveBeenCalled();
  });

  it("requires an agent and submits agent launch payload for todo dispatch", () => {
    const onSubmit = vi.fn();
    renderTerminalCreateModal({
      context: {
        title: "Dispatch todo",
        description: "Fix the failing flow",
        cwd: "/workspace/project",
        requireAgent: true,
        submitLabel: "Dispatch"
      },
      onSubmit
    });

    const agentTabs = Array.from(container?.querySelectorAll(".terminal-create-agent-tabs button") ?? []);
    expect(agentTabs.map((button) => button.textContent)).not.toContain("No Agent");
    expect(agentTabs[0]?.textContent).toBe("Codex");

    const dispatchButton = Array.from(container?.querySelectorAll(".terminal-create-actions button") ?? []).find(
      (button) => button.textContent === "Dispatch"
    );
    expect(dispatchButton).toBeInstanceOf(HTMLButtonElement);

    act(() => {
      (dispatchButton as HTMLButtonElement).click();
    });

    expect(onSubmit).toHaveBeenCalledWith({
      cwd: "/workspace/project",
      folder_path: null,
      agent_launch: {
        agent: "codex",
        command: "codex",
        config: null,
        profile_id: null
      }
    });
  });

  it("applies saved default model settings for direct agent launches", async () => {
    vi.useRealTimers();
    const onSubmit = vi.fn();
    window.localStorage.setItem("web-terminal-acp:agent-model-selections", JSON.stringify({
      codex: { preset_id: "openai-main", model: "model-b" }
    }));
    vi.mocked(globalThis.fetch).mockImplementation(async (input: RequestInfo | URL) => {
      const url = new URL(String(input));
      if (url.pathname === "/api/clients/client-1/agent-clients") {
        return new Response(JSON.stringify({
          agent_clients: [
            {
              id: "codex",
              provider_id: "codex",
              label: "Codex",
              aliases: [],
              default_command: "codex",
              command_names: ["codex"],
              capabilities: { launch: true, client_config: true }
            }
          ]
        }), { status: 200, headers: { "Content-Type": "application/json" } });
      }
      if (url.pathname === "/api/clients/client-1/agent-profiles") {
        return new Response(JSON.stringify({ profiles: [] }), { status: 200, headers: { "Content-Type": "application/json" } });
      }
      if (url.pathname === "/api/system-agent-config/model-presets") {
        return new Response(JSON.stringify({
          presets: [
            {
              id: "openai-main",
              name: "OpenAI Main",
              provider: "openai_compatible",
              base_url: "https://models.example.com/v1",
              api_key: "secret-key",
              models: ["model-a", "model-b"]
            }
          ]
        }), { status: 200, headers: { "Content-Type": "application/json" } });
      }
      throw new Error(`unexpected request: ${url.pathname}`);
    });

    renderTerminalCreateModal({
      context: {
        title: "Dispatch todo",
        cwd: "/workspace/project",
        requireAgent: true,
        submitLabel: "Dispatch"
      },
      onSubmit
    });
    await waitFor(() => {
      expect(container?.textContent).toContain("OpenAI Main");
    });
    const modelSelect = Array.from(container?.querySelectorAll(".agent-model-picker select") ?? [])[1];
    expect(modelSelect).toBeInstanceOf(HTMLSelectElement);
    expect((modelSelect as HTMLSelectElement).value).toBe("model-b");

    const dispatchButton = Array.from(container?.querySelectorAll(".terminal-create-actions button") ?? [])
      .find((button) => button.textContent === "Dispatch");
    expect(dispatchButton).toBeInstanceOf(HTMLButtonElement);
    act(() => {
      (dispatchButton as HTMLButtonElement).click();
    });

    expect(onSubmit).toHaveBeenCalledWith({
      cwd: "/workspace/project",
      folder_path: null,
      agent_launch: {
        agent: "codex",
        command: "codex",
        config: null,
        model_selection: {
          preset_id: "openai-main",
          model: "model-b"
        },
        profile_id: null
      }
    });
  });

  it("uses initial project preference command and model selection", async () => {
    vi.useRealTimers();
    const onSubmit = vi.fn();
    vi.mocked(globalThis.fetch).mockImplementation(async (input: RequestInfo | URL) => {
      const url = new URL(String(input));
      if (url.pathname === "/api/clients/client-1/agent-clients") {
        return new Response(JSON.stringify({
          agent_clients: [
            {
              id: "codex",
              provider_id: "codex",
              label: "Codex",
              aliases: [],
              default_command: "codex",
              command_names: ["codex"],
              capabilities: { launch: true, client_config: true }
            }
          ]
        }), { status: 200, headers: { "Content-Type": "application/json" } });
      }
      if (url.pathname === "/api/clients/client-1/agent-profiles") {
        return new Response(JSON.stringify({ profiles: [] }), { status: 200, headers: { "Content-Type": "application/json" } });
      }
      if (url.pathname === "/api/system-agent-config/model-presets") {
        return new Response(JSON.stringify({
          presets: [
            {
              id: "openai-main",
              name: "OpenAI Main",
              provider: "openai_compatible",
              base_url: "https://models.example.com/v1",
              api_key: "secret-key",
              models: ["gpt-5-codex"]
            }
          ]
        }), { status: 200, headers: { "Content-Type": "application/json" } });
      }
      throw new Error(`unexpected request: ${url.pathname}`);
    });

    renderTerminalCreateModal({
      context: {
        title: "Project terminal",
        cwd: "/workspace/project",
        initialAgent: "codex",
        initialAgentCommand: "codex --model gpt-5-codex",
        initialAgentModelSelection: { preset_id: "openai-main", model: "gpt-5-codex" },
        requireAgent: true,
        submitLabel: "Create"
      },
      onSubmit
    });
    await waitFor(() => {
      expect(container?.textContent).toContain("OpenAI Main");
    });
    const createButton = Array.from(container?.querySelectorAll(".terminal-create-actions button") ?? [])
      .find((button) => button.textContent === "Create");
    expect(createButton).toBeInstanceOf(HTMLButtonElement);
    act(() => {
      (createButton as HTMLButtonElement).click();
    });

    expect(onSubmit).toHaveBeenCalledWith({
      cwd: "/workspace/project",
      folder_path: null,
      agent_launch: {
        agent: "codex",
        command: "codex --model gpt-5-codex",
        config: null,
        model_selection: { preset_id: "openai-main", model: "gpt-5-codex" },
        profile_id: null
      }
    });
  });

  it("keeps dispatch actions outside the scrollable modal body", () => {
    renderTerminalCreateModal({
      context: {
        title: "Dispatch todo",
        description: "Fix the failing flow",
        cwd: "/workspace/project",
        requireAgent: true,
        submitLabel: "Dispatch"
      },
      children: <div className="dispatch-options-fixture">Dispatch options</div>
    });

    const body = container?.querySelector(".terminal-create-body");
    const actions = container?.querySelector(".terminal-create-actions");
    const dispatchOptions = container?.querySelector(".dispatch-options-fixture");
    expect(body).toBeInstanceOf(HTMLDivElement);
    expect(actions).toBeInstanceOf(HTMLDivElement);
    expect(dispatchOptions).toBeInstanceOf(HTMLDivElement);
    expect(body?.contains(dispatchOptions as Element)).toBe(true);
    expect(body?.contains(actions as Element)).toBe(false);
    expect(actions?.parentElement).toBe(container?.querySelector(".terminal-create-modal"));
  });

  it("keeps the selected agent when dispatch modal children rerender", async () => {
    vi.useRealTimers();
    const onSubmit = vi.fn();
    vi.mocked(globalThis.fetch).mockResolvedValue(new Response(JSON.stringify({
      agent_clients: [
        {
          id: "codex",
          provider_id: "codex",
          label: "Codex",
          aliases: [],
          default_command: "codex",
          command_names: ["codex"],
          capabilities: { launch: true, client_config: true }
        },
        {
          id: "claude",
          provider_id: "claude_code",
          label: "Claude Code",
          aliases: ["claude_code"],
          default_command: "claude",
          command_names: ["claude"],
          capabilities: { launch: true, client_config: true }
        }
      ],
      profiles: []
    }), { status: 200, headers: { "Content-Type": "application/json" } }));

    function DispatchWrapper() {
      const [compose, setCompose] = useState(false);
      return (
        <TerminalCreateModal
          isOpen
          clientId="client-1"
          context={{
            title: "Dispatch todo",
            description: "Fix the failing flow",
            cwd: "/workspace/project",
            requireAgent: true,
            submitLabel: "Dispatch"
          }}
          onClose={() => {}}
          onSubmit={onSubmit}
        >
          <button type="button" onClick={() => setCompose((current) => !current)}>
            {compose ? "Submit" : "Compose"}
          </button>
        </TerminalCreateModal>
      );
    }

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
          <DispatchWrapper />
        </QueryClientProvider>
      );
    });

    await act(async () => {
      await Promise.resolve();
      await Promise.resolve();
    });

    const claudeTab = Array.from(container.querySelectorAll(".terminal-create-agent-tabs button")).find(
      (button) => button.textContent === "Claude Code"
    );
    expect(claudeTab).toBeInstanceOf(HTMLButtonElement);
    act(() => {
      (claudeTab as HTMLButtonElement).click();
    });

    const composeButton = Array.from(container.querySelectorAll("button")).find(
      (button) => button.textContent === "Compose"
    );
    expect(composeButton).toBeInstanceOf(HTMLButtonElement);
    act(() => {
      (composeButton as HTMLButtonElement).click();
    });

    expect((claudeTab as HTMLButtonElement).className).toBe("active");

    const dispatchButton = Array.from(container.querySelectorAll(".terminal-create-actions button")).find(
      (button) => button.textContent === "Dispatch"
    );
    expect(dispatchButton).toBeInstanceOf(HTMLButtonElement);
    act(() => {
      (dispatchButton as HTMLButtonElement).click();
    });

    expect(onSubmit).toHaveBeenCalledWith({
      cwd: "/workspace/project",
      folder_path: null,
      agent_launch: {
        agent: "claude",
        command: "claude",
        config: null,
        profile_id: null
      }
    });
  });

});
