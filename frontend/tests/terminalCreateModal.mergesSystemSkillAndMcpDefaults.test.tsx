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
  setupQueryClient?: (client: QueryClient) => void;
} = {}) {
  container = document.createElement("div");
  document.body.appendChild(container);
  queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false }
    }
  });
  options.setupQueryClient?.(queryClient);
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
  it("merges system Skill and MCP defaults into editable direct launch config", async () => {
    vi.useRealTimers();
    const onSubmit = vi.fn();
    vi.mocked(globalThis.fetch).mockImplementation(async (input: RequestInfo | URL) => {
      const url = new URL(String(input));
      let body: unknown = { profiles: [] };
      if (url.pathname === "/api/clients/client-1/agent-clients") {
        body = {
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
        };
      } else if (url.pathname === "/api/clients/client-1/agent-config/codex") {
        body = {
          agent: "codex",
          sections: [
            {
              id: "skills",
              name: "Skills",
              items: [{ id: "docker", name: "Docker", enabled: true, path: null, origin: "client" }]
            },
            { id: "plugins", name: "Plugins", items: [] },
            { id: "hooks", name: "Hooks", items: [] },
            { id: "mcp", name: "MCP Servers", items: [] }
          ]
        };
      } else if (url.pathname === "/api/clients/client-1/system-agent-config") {
        body = {
          agent: "system",
          sections: [
            {
              id: "skills",
              name: "System Skills",
              items: [{ id: "review-helper", name: "Review Helper", enabled: true, path: null, origin: "system_config" }]
            },
            {
              id: "mcp",
              name: "System MCP Servers",
              items: [{
                id: "web-terminal-acp-mcp",
                name: "web-terminal-acp-mcp",
                enabled: true,
                path: null,
                origin: "system_builtin"
              }]
            }
          ]
        };
      } else if (url.pathname === "/api/system-agent-config/model-presets") {
        body = { presets: [] };
      }
      return new Response(JSON.stringify(body), { status: 200, headers: { "Content-Type": "application/json" } });
    });

    renderTerminalCreateModal({
      context: {
        title: "Dispatch todo",
        cwd: "/workspace/project",
        requireAgent: true,
        showConfigInitially: true,
        submitLabel: "Dispatch"
      },
      onSubmit
    });
    await flushQueries();

    await waitFor(() => {
      expect(container?.textContent).toContain("Docker");
      expect(container?.textContent).toContain("Review Helper");
      expect(container?.textContent).toContain("web-terminal-acp-mcp");
    });

    const systemRow = Array.from(container?.querySelectorAll(".agent-config-item") ?? [])
      .find((row) => row.textContent?.includes("Review Helper"));
    expect(systemRow).toBeInstanceOf(HTMLLIElement);
    const systemToggle = systemRow?.querySelector("input");
    expect(systemToggle).toBeInstanceOf(HTMLInputElement);
    expect((systemToggle as HTMLInputElement).disabled).toBe(false);
    act(() => {
      (systemToggle as HTMLInputElement).click();
    });

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
        config: {
          agent: "codex",
          sections: [
            {
              id: "skills",
              items: [
                { id: "docker", enabled: true },
                { id: "review-helper", enabled: false }
              ]
            },
            { id: "plugins", items: [] },
            { id: "hooks", items: [] },
            {
              id: "mcp",
              items: [{ id: "web-terminal-acp-mcp", enabled: true }]
            }
          ]
        },
        profile_id: null
      }
    });
  });

  it("shows disabled system skills as editable direct launch options", async () => {
    vi.useRealTimers();
    const onSubmit = vi.fn();
    vi.mocked(globalThis.fetch).mockImplementation(async (input: RequestInfo | URL) => {
      const url = new URL(String(input));
      let body: unknown = { profiles: [] };
      if (url.pathname === "/api/clients/client-1/agent-clients") {
        body = {
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
        };
      } else if (url.pathname === "/api/clients/client-1/agent-config/codex") {
        body = {
          agent: "codex",
          sections: [
            { id: "skills", name: "Skills", items: [] },
            { id: "plugins", name: "Plugins", items: [] },
            { id: "hooks", name: "Hooks", items: [] },
            { id: "mcp", name: "MCP Servers", items: [] }
          ]
        };
      } else if (url.pathname === "/api/clients/client-1/system-agent-config") {
        body = {
          agent: "system",
          sections: [
            {
              id: "skills",
              name: "System Skills",
              items: [{ id: "image-to-ppt", name: "Image to PPT", enabled: false, path: null, origin: "system_config" }]
            },
            { id: "mcp", name: "System MCP Servers", items: [] }
          ]
        };
      } else if (url.pathname === "/api/system-agent-config/model-presets") {
        body = { presets: [] };
      }
      return new Response(JSON.stringify(body), { status: 200, headers: { "Content-Type": "application/json" } });
    });

    renderTerminalCreateModal({
      context: {
        title: "Dispatch todo",
        cwd: "/workspace/project",
        requireAgent: true,
        showConfigInitially: true,
        submitLabel: "Dispatch"
      },
      onSubmit
    });
    await flushQueries();

    await waitFor(() => {
      expect(container?.textContent).toContain("Image to PPT");
    });

    const skillRow = Array.from(container?.querySelectorAll(".agent-config-item") ?? [])
      .find((row) => row.textContent?.includes("Image to PPT"));
    const skillToggle = skillRow?.querySelector("input");
    expect(skillToggle).toBeInstanceOf(HTMLInputElement);
    expect((skillToggle as HTMLInputElement).checked).toBe(false);
    expect((skillToggle as HTMLInputElement).disabled).toBe(false);
    act(() => {
      (skillToggle as HTMLInputElement).click();
    });

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
        config: {
          agent: "codex",
          sections: [
            { id: "skills", items: [{ id: "image-to-ppt", enabled: true }] },
            { id: "plugins", items: [] },
            { id: "hooks", items: [] },
            { id: "mcp", items: [] }
          ]
        },
        profile_id: null
      }
    });
  });

  it("refreshes cached system skills before showing direct launch config", async () => {
    vi.useRealTimers();
    const cachedSystemConfig = {
      agent: "system",
      sections: [
        {
          id: "skills",
          name: "System Skills",
          items: [{ id: "imagegen", name: "imagegen", enabled: true, path: null, origin: "system_builtin" }]
        },
        { id: "mcp", name: "System MCP Servers", items: [] }
      ]
    };
    const latestSystemConfig = {
      agent: "system",
      sections: [
        {
          id: "skills",
          name: "System Skills",
          items: [
            { id: "imagegen", name: "imagegen", enabled: true, path: null, origin: "system_builtin" },
            { id: "image-to-ppt", name: "image-to-ppt", enabled: false, path: null, origin: "system_config" }
          ]
        },
        { id: "mcp", name: "System MCP Servers", items: [] }
      ]
    };
    vi.mocked(globalThis.fetch).mockImplementation(async (input: RequestInfo | URL) => {
      const url = new URL(String(input));
      let body: unknown = { profiles: [] };
      if (url.pathname === "/api/clients/client-1/agent-clients") {
        body = {
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
        };
      } else if (url.pathname === "/api/clients/client-1/agent-config/codex") {
        body = {
          agent: "codex",
          sections: [
            { id: "skills", name: "Skills", items: [] },
            { id: "plugins", name: "Plugins", items: [] },
            { id: "hooks", name: "Hooks", items: [] },
            { id: "mcp", name: "MCP Servers", items: [] }
          ]
        };
      } else if (url.pathname === "/api/clients/client-1/system-agent-config") {
        body = latestSystemConfig;
      } else if (url.pathname === "/api/system-agent-config/model-presets") {
        body = { presets: [] };
      }
      return new Response(JSON.stringify(body), { status: 200, headers: { "Content-Type": "application/json" } });
    });

    renderTerminalCreateModal({
      context: {
        title: "New terminal",
        cwd: "/workspace/project",
        requireAgent: true,
        showConfigInitially: true
      },
      setupQueryClient: (client) => {
        client.setQueryData(["client-system-agent-config", "client-1"], cachedSystemConfig);
      }
    });
    await flushQueries();

    await waitFor(() => {
      expect(container?.textContent).toContain("image-to-ppt");
    });
    expect(globalThis.fetch).toHaveBeenCalledWith(
      expect.stringContaining("/api/clients/client-1/system-agent-config"),
      expect.anything()
    );
  });

  it("ignores stale cached system config without sections", async () => {
    vi.useRealTimers();
    vi.mocked(globalThis.fetch).mockImplementation(async (input: RequestInfo | URL) => {
      const url = new URL(String(input));
      let body: unknown = { profiles: [] };
      if (url.pathname === "/api/clients/client-1/agent-clients") {
        body = {
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
        };
      } else if (url.pathname === "/api/clients/client-1/agent-config/codex") {
        body = {
          agent: "codex",
          sections: [
            {
              id: "skills",
              name: "Skills",
              items: [{ id: "docker", name: "Docker", enabled: true, path: null, origin: "client" }]
            },
            { id: "plugins", name: "Plugins", items: [] },
            { id: "hooks", name: "Hooks", items: [] },
            { id: "mcp", name: "MCP Servers", items: [] }
          ]
        };
      } else if (url.pathname === "/api/clients/client-1/system-agent-config") {
        body = { agent: "system" };
      } else if (url.pathname === "/api/system-agent-config/model-presets") {
        body = { presets: [] };
      }
      return new Response(JSON.stringify(body), { status: 200, headers: { "Content-Type": "application/json" } });
    });

    renderTerminalCreateModal({
      context: {
        title: "Dispatch todo",
        cwd: "/workspace/project",
        requireAgent: true,
        showConfigInitially: true,
        submitLabel: "Dispatch"
      },
      setupQueryClient: (client) => {
        client.setQueryData(["client-system-agent-config", "client-1"], { agent: "system" });
      }
    });
    await flushQueries();

    await waitFor(() => {
      expect(container?.textContent).toContain("Docker");
    });
  });

  it("refreshes untouched system MCP defaults in direct launch config", async () => {
    vi.useRealTimers();
    const onSubmit = vi.fn();
    const enabledSystemConfig = {
      agent: "system",
      sections: [
        { id: "skills", name: "System Skills", items: [] },
        {
          id: "mcp",
          name: "System MCP Servers",
          items: [
            {
              id: "gpt-researcher",
              name: "gpt-researcher",
              enabled: true,
              path: null,
              origin: "system_builtin"
            },
            {
              id: "web-terminal-acp-mcp",
              name: "web-terminal-acp-mcp",
              enabled: true,
              path: null,
              origin: "system_builtin"
            }
          ]
        }
      ]
    };
    const disabledSystemConfig = {
      ...enabledSystemConfig,
      sections: enabledSystemConfig.sections.map((section) => section.id === "mcp"
        ? {
            ...section,
            items: section.items.map((item) => ({ ...item, enabled: false }))
          }
        : section)
    };
    vi.mocked(globalThis.fetch).mockImplementation(async (input: RequestInfo | URL) => {
      const url = new URL(String(input));
      let body: unknown = { profiles: [] };
      if (url.pathname === "/api/clients/client-1/agent-clients") {
        body = {
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
        };
      } else if (url.pathname === "/api/clients/client-1/agent-config/codex") {
        body = {
          agent: "codex",
          sections: [
            { id: "skills", name: "Skills", items: [] },
            { id: "plugins", name: "Plugins", items: [] },
            { id: "hooks", name: "Hooks", items: [] },
            { id: "mcp", name: "MCP Servers", items: [] }
          ]
        };
      } else if (url.pathname === "/api/clients/client-1/system-agent-config") {
        body = enabledSystemConfig;
      } else if (url.pathname === "/api/system-agent-config/model-presets") {
        body = { presets: [] };
      }
      return new Response(JSON.stringify(body), { status: 200, headers: { "Content-Type": "application/json" } });
    });

    renderTerminalCreateModal({
      context: {
        title: "Dispatch todo",
        cwd: "/workspace/project",
        requireAgent: true,
        showConfigInitially: true,
        submitLabel: "Dispatch"
      },
      onSubmit
    });
    await flushQueries();

    await waitFor(() => {
      expect(container?.textContent).toContain("gpt-researcher");
      expect(container?.textContent).toContain("web-terminal-acp-mcp");
    });

    act(() => {
      queryClient?.setQueryData(["client-system-agent-config", "client-1"], disabledSystemConfig);
    });

    await waitFor(() => {
      const rows = Array.from(container?.querySelectorAll(".agent-config-item") ?? []);
      const gptResearcher = rows.find((row) => row.textContent?.includes("gpt-researcher"));
      const webTerminalMcp = rows.find((row) => row.textContent?.includes("web-terminal-acp-mcp"));
      expect(gptResearcher?.querySelector("input")).toBeInstanceOf(HTMLInputElement);
      expect(webTerminalMcp?.querySelector("input")).toBeInstanceOf(HTMLInputElement);
      expect((gptResearcher?.querySelector("input") as HTMLInputElement).checked).toBe(false);
      expect((webTerminalMcp?.querySelector("input") as HTMLInputElement).checked).toBe(false);
    });

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
        config: {
          agent: "codex",
          sections: [
            { id: "skills", items: [] },
            { id: "plugins", items: [] },
            { id: "hooks", items: [] },
            {
              id: "mcp",
              items: [
                { id: "gpt-researcher", enabled: false },
                { id: "web-terminal-acp-mcp", enabled: false }
              ]
            }
          ]
        },
        profile_id: null
      }
    });
  });

  it("submits selected Codex model settings with agent launch", async () => {
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
    const presetSelect = container?.querySelector(".agent-model-picker select");
    expect(presetSelect).toBeInstanceOf(HTMLSelectElement);
    setSelectValue(presetSelect as HTMLSelectElement, "openai-main");
    await waitFor(() => {
      expect(container?.querySelectorAll(".agent-model-picker select").length).toBeGreaterThanOrEqual(2);
    });
    const modelSelect = Array.from(container?.querySelectorAll(".agent-model-picker select") ?? [])[1];
    expect(modelSelect).toBeInstanceOf(HTMLSelectElement);
    expect((modelSelect as HTMLSelectElement).value).toBe("model-a");
    setSelectValue(modelSelect as HTMLSelectElement, "model-b");

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
});
