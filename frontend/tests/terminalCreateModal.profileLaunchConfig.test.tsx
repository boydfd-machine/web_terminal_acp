import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  TerminalCreateModal,
  type TerminalCreateContext,
  type TerminalCreateSubmit
} from "../src/components/TerminalCreateModal";

globalThis.IS_REACT_ACT_ENVIRONMENT = true;

let root: Root | null = null;
let container: HTMLDivElement | null = null;
let queryClient: QueryClient | null = null;

function renderProfileLaunchConfigModal(
  onSubmit: (payload: TerminalCreateSubmit) => void,
  contextOverrides: Partial<TerminalCreateContext> = {}
) {
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
          context={{
            title: "Dispatch todo",
            cwd: "/workspace/project",
            initialAgent: "codex",
            initialAgentProfileId: "builtin/developer",
            requireAgent: true,
            showConfigInitially: true,
            submitLabel: "Dispatch",
            ...contextOverrides
          }}
          onClose={() => {}}
          onSubmit={onSubmit}
        />
      </QueryClientProvider>
    );
  });
}

function setSelectValue(target: HTMLSelectElement, value: string): void {
  const setter = Object.getOwnPropertyDescriptor(HTMLSelectElement.prototype, "value")?.set;
  act(() => {
    setter?.call(target, value);
    target.dispatchEvent(new Event("change", { bubbles: true }));
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

beforeEach(() => {
  vi.useRealTimers();
  vi.spyOn(globalThis, "fetch").mockImplementation(async (input: RequestInfo | URL) => {
    const url = new URL(String(input));
    if (url.pathname === "/api/clients/client-1/agent-clients") {
      return jsonResponse({
        agent_clients: [{
          id: "codex",
          provider_id: "codex",
          label: "Codex",
          aliases: [],
          default_command: "codex",
          command_names: ["codex"],
          capabilities: { launch: true, client_config: true, profile_config: false }
        }]
      });
    }
    if (url.pathname === "/api/clients/client-1/agent-profiles") {
      return jsonResponse({
        profiles: [{
          id: "builtin/developer",
          name: "Built-in Developer",
          description: null,
          default_agent_client: "codex",
          agent_md: "",
          created_at: "2026-06-13T00:00:00Z",
          updated_at: "2026-06-13T00:00:00Z"
        }]
      });
    }
    if (url.pathname === "/api/clients/client-1/agent-config/codex") {
      return jsonResponse({
        agent: "codex",
        sections: [
          { id: "skills", name: "Skills", items: [] },
          { id: "plugins", name: "Plugins", items: [] },
          { id: "hooks", name: "Hooks", items: [] },
          { id: "mcp", name: "MCP Servers", items: [] }
        ]
      });
    }
    if (url.pathname === "/api/clients/client-1/agent-profile-config") {
      expect(url.searchParams.get("profile_id")).toBe("builtin/developer");
      expect(url.searchParams.get("agent")).toBe("codex");
      return jsonResponse({
        agent: "codex",
        sections: [
          {
            id: "skills",
            name: "Skills",
            items: [{ id: "profile-skill", name: "Profile Skill", enabled: true, path: null, origin: "client" }]
          },
          {
            id: "plugins",
            name: "Plugins",
            items: [{ id: "superpowers", name: "Superpowers", enabled: true, path: null, origin: "client" }]
          },
          { id: "hooks", name: "Hooks", items: [] },
          {
            id: "mcp",
            name: "MCP Servers",
            items: [{ id: "profile-mcp", name: "Profile MCP", enabled: false, path: null, origin: "client" }]
          }
        ]
      });
    }
    if (url.pathname === "/api/system-agent-config/model-presets") {
      return jsonResponse({ presets: [] });
    }
    throw new Error(`unexpected request: ${url.pathname}`);
  });
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
  vi.restoreAllMocks();
});

describe("TerminalCreateModal profile launch config", () => {
  it("allows launch-only skill, MCP, and plugin overrides from an initial profile", async () => {
    const onSubmit = vi.fn();
    renderProfileLaunchConfigModal(onSubmit);

    await waitFor(() => {
      expect(container?.textContent).toContain("Profile Skill");
      expect(container?.textContent).toContain("Superpowers");
      expect(container?.textContent).toContain("Profile MCP");
    });

    const skillRow = Array.from(container?.querySelectorAll(".agent-config-item") ?? [])
      .find((row) => row.textContent?.includes("Profile Skill"));
    expect(skillRow).toBeInstanceOf(HTMLLIElement);
    const skillToggle = skillRow?.querySelector("input");
    expect(skillToggle).toBeInstanceOf(HTMLInputElement);
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
            { id: "skills", items: [{ id: "profile-skill", enabled: false }] },
            { id: "plugins", items: [{ id: "superpowers", enabled: true }] },
            { id: "hooks", items: [] },
            { id: "mcp", items: [{ id: "profile-mcp", enabled: false }] }
          ]
        },
        profile_id: "builtin/developer"
      }
    });
  });

  it("allows launch-only skill, MCP, and plugin overrides after selecting a profile", async () => {
    const onSubmit = vi.fn();
    renderProfileLaunchConfigModal(onSubmit, {
      initialAgentProfileId: null,
      showConfigInitially: false
    });

    await waitFor(() => {
      expect(container?.textContent).toContain("Built-in Developer");
    });

    const profileSelect = container?.querySelector(".terminal-create-body .settings-field select");
    expect(profileSelect).toBeInstanceOf(HTMLSelectElement);
    setSelectValue(profileSelect as HTMLSelectElement, "builtin/developer");

    const configButton = container?.querySelector(".terminal-create-config-row");
    expect(configButton).toBeInstanceOf(HTMLButtonElement);
    act(() => {
      (configButton as HTMLButtonElement).click();
    });

    await waitFor(() => {
      expect(container?.textContent).toContain("Profile Skill");
    });

    const skillRow = Array.from(container?.querySelectorAll(".agent-config-item") ?? [])
      .find((row) => row.textContent?.includes("Profile Skill"));
    const skillToggle = skillRow?.querySelector("input");
    expect(skillToggle).toBeInstanceOf(HTMLInputElement);
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

    expect(onSubmit).toHaveBeenCalledWith(expect.objectContaining({
      agent_launch: expect.objectContaining({
        config: expect.objectContaining({
          sections: expect.arrayContaining([
            { id: "skills", items: [{ id: "profile-skill", enabled: false }] }
          ])
        }),
        profile_id: "builtin/developer"
      })
    }));
  });
});

function jsonResponse(body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status: 200,
    headers: { "Content-Type": "application/json" }
  });
}
