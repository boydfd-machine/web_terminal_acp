import { act } from "react";
import { describe, expect, it, vi } from "vitest";

import {
  container,
  jsonResponse,
  renderSettingsModal,
  setValue as setFormValue,
  waitFor
} from "./settingsModalHarness";

describe("System agent config settings", () => {
  it("separates agent prompt, MCP, Skill, and creation settings into profile tabs", async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = new URL(String(input));
      if (url.pathname === "/api/clients/client-1/agent-clients" && init?.method === undefined) {
        return jsonResponse({
          agent_clients: [{
            id: "codex",
            provider_id: "codex",
            label: "Codex",
            aliases: [],
            default_command: "codex",
            command_names: ["codex"],
            capabilities: { launch: true, profile_config: true }
          }]
        });
      }
      if (url.pathname === "/api/clients/client-1/agent-profiles" && init?.method === undefined) {
        return jsonResponse({
          profiles: [{
            id: "review-agent",
            name: "Review Agent",
            description: "Code review",
            default_agent_client: "codex",
            agent_md: "Review carefully.",
            created_at: "2026-06-08T00:00:00Z",
            updated_at: "2026-06-08T00:00:00Z"
          }]
        });
      }
      if (url.pathname === "/api/clients/client-1/agent-profiles/review-agent/agent-config/codex" && init?.method === undefined) {
        return jsonResponse({
          agent: "codex",
          sections: [
            { id: "skills", name: "Skills", items: [{ id: "docker", name: "docker", enabled: true, path: null }] },
            { id: "plugins", name: "Plugins", items: [] },
            { id: "hooks", name: "Hooks", items: [] },
            { id: "mcp", name: "MCP Servers", items: [{ id: "filesystem", name: "filesystem", enabled: true, path: null }] }
          ]
        });
      }
      throw new Error(`unexpected request: ${url.pathname}`);
    });
    globalThis.fetch = fetchMock as never;

    renderSettingsModal({ initialView: "agents" });

    await waitFor(() => {
      expect(container?.textContent).toContain("Review Agent");
      expect(container?.textContent).toContain("AGENT.md");
    });
    const profileRow = container?.querySelector(".agent-profile-row");
    expect(profileRow?.textContent).toContain("Review Agent");
    expect(profileRow?.textContent).toContain("Codex");
    expect(profileRow?.textContent).not.toContain("Code review");
    expect(container?.textContent).toContain("Review carefully.");
    expect(container?.textContent).not.toContain("filesystem");
    expect(container?.textContent).not.toContain("docker");

    const mcpTab = Array.from(container?.querySelectorAll(".agent-profile-tabs button") ?? [])
      .find((button) => button.textContent === "MCP");
    expect(mcpTab).toBeInstanceOf(HTMLButtonElement);
    act(() => {
      (mcpTab as HTMLButtonElement).click();
    });
    await waitFor(() => {
      expect(container?.textContent).toContain("filesystem");
    });
    expect(container?.textContent).not.toContain("docker");
    expect(container?.textContent).not.toContain("AGENT.md");

    const skillTab = Array.from(container?.querySelectorAll(".agent-profile-tabs button") ?? [])
      .find((button) => button.textContent === "Skill");
    expect(skillTab).toBeInstanceOf(HTMLButtonElement);
    act(() => {
      (skillTab as HTMLButtonElement).click();
    });
    await waitFor(() => {
      expect(container?.textContent).toContain("docker");
    });
    expect(container?.textContent).not.toContain("filesystem");

    const createTab = Array.from(container?.querySelectorAll(".agent-profile-tabs button") ?? [])
      .find((button) => button.textContent === "新增 Agent");
    expect(createTab).toBeInstanceOf(HTMLButtonElement);
    act(() => {
      (createTab as HTMLButtonElement).click();
    });
    await waitFor(() => {
      expect(container?.querySelector('input[placeholder="例如：Review Agent"]')).toBeInstanceOf(HTMLInputElement);
    });
    expect(container?.textContent).not.toContain("Review carefully.");
  });

  it("uses an icon create action and resets profile basics when selecting another agent", async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = new URL(String(input));
      if (url.pathname === "/api/clients/client-1/agent-clients" && init?.method === undefined) {
        return jsonResponse({
          agent_clients: [{
            id: "codex",
            provider_id: "codex",
            label: "Codex",
            aliases: [],
            default_command: "codex",
            command_names: ["codex"],
            capabilities: { launch: true, profile_config: true }
          }]
        });
      }
      if (url.pathname === "/api/clients/client-1/agent-profiles" && init?.method === undefined) {
        return jsonResponse({
          profiles: [
            {
              id: "general-cn",
              name: "通用问答的招商智慧的策略领域专家",
              description: "Chinese title should remain readable",
              default_agent_client: "codex",
              agent_md: "General prompt.",
              created_at: "2026-06-08T00:00:00Z",
              updated_at: "2026-06-08T00:00:00Z"
            },
            {
              id: "developer",
              name: "开发经理",
              description: "Builds plans",
              default_agent_client: "codex",
              agent_md: "Developer prompt.",
              created_at: "2026-06-08T00:00:00Z",
              updated_at: "2026-06-08T00:00:00Z"
            }
          ]
        });
      }
      if (url.pathname.endsWith("/agent-config/codex") && init?.method === undefined) {
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
      throw new Error(`unexpected request: ${url.pathname}`);
    });
    globalThis.fetch = fetchMock as never;

    renderSettingsModal({ initialView: "agents" });

    await waitFor(() => {
      expect(container?.textContent).toContain("通用问答的招商智慧的策略领域专家");
    });
    const createButton = container?.querySelector(".agent-profile-create-button");
    expect(createButton).toBeInstanceOf(HTMLButtonElement);
    expect(createButton?.getAttribute("aria-label")).toBe("创建 agent");
    expect(createButton?.textContent?.trim()).toBe("");
    expect(container?.querySelector(".agent-profile-detail > .system-config-detail-header strong")).toBeNull();

    const nameInput = container?.querySelector(".settings-agent-command-grid input");
    expect(nameInput).toBeInstanceOf(HTMLInputElement);
    expect((nameInput as HTMLInputElement).value).toBe("通用问答的招商智慧的策略领域专家");
    act(() => {
      setFormValue(nameInput as HTMLInputElement, "未保存的本地输入");
    });

    const developerRow = Array.from(container?.querySelectorAll(".agent-profile-row") ?? [])
      .find((button) => button.textContent?.includes("开发经理"));
    expect(developerRow).toBeInstanceOf(HTMLButtonElement);
    act(() => {
      (developerRow as HTMLButtonElement).click();
    });

    await waitFor(() => {
      const currentNameInput = container?.querySelector(".settings-agent-command-grid input");
      expect(currentNameInput).toBeInstanceOf(HTMLInputElement);
      expect((currentNameInput as HTMLInputElement).value).toBe("开发经理");
    });
  });

  it("lists and toggles system skills from Settings", async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = new URL(String(input));
      if (url.pathname === "/api/system-agent-config" && init?.method === undefined) {
        return jsonResponse({
          agent: "system",
          sections: [
            {
              id: "skills",
              name: "System Skills",
              items: [{ id: "review-helper", name: "Review Helper", enabled: true, path: null }]
            },
            { id: "mcp", name: "System MCP Servers", items: [] }
          ]
        });
      }
      if (url.pathname === "/api/system-agent-config/skills/review-helper") {
        expect(init?.method).toBe("PATCH");
        expect(init?.body).toBe(JSON.stringify({ enabled: false }));
        return jsonResponse({
          agent: "system",
          sections: [
            {
              id: "skills",
              name: "System Skills",
              items: [{ id: "review-helper", name: "Review Helper", enabled: false, path: null }]
            },
            { id: "mcp", name: "System MCP Servers", items: [] }
          ]
        });
      }
      throw new Error(`unexpected request: ${url.pathname}`);
    });
    globalThis.fetch = fetchMock as never;

    renderSettingsModal();
    const skillTab = Array.from(container?.querySelectorAll(".settings-tabs button") ?? [])
      .find((button) => button.textContent?.includes("系统 Skill"));
    expect(skillTab).toBeInstanceOf(HTMLButtonElement);
    act(() => {
      (skillTab as HTMLButtonElement).click();
    });

    await waitFor(() => {
      expect(container?.textContent).toContain("Review Helper");
    });
    const toggle = container?.querySelector('input[aria-label="禁用 Review Helper"]');
    expect(toggle).toBeInstanceOf(HTMLInputElement);
    await act(async () => {
      (toggle as HTMLInputElement).click();
    });

    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining("/api/system-agent-config/skills/review-helper"),
      expect.objectContaining({ method: "PATCH" })
    );
  });

  it("lists and toggles system plugins from Settings", async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = new URL(String(input));
      if (url.pathname === "/api/system-agent-config" && init?.method === undefined) {
        return jsonResponse({
          agent: "system",
          sections: [
            { id: "skills", name: "System Skills", items: [] },
            {
              id: "plugins",
              name: "System Plugins",
              items: [{
                id: "codex:superpowers@openai-curated",
                name: "Codex / Superpowers",
                enabled: true,
                path: "/home/user/.codex/plugins/cache/openai-curated/superpowers",
                origin: "client"
              }]
            },
            { id: "mcp", name: "System MCP Servers", items: [] }
          ]
        });
      }
      if (url.pathname === "/api/system-agent-config/plugins/codex%3Asuperpowers%40openai-curated") {
        expect(init?.method).toBe("PATCH");
        expect(init?.body).toBe(JSON.stringify({ enabled: false }));
        return jsonResponse({
          agent: "system",
          sections: [
            { id: "skills", name: "System Skills", items: [] },
            {
              id: "plugins",
              name: "System Plugins",
              items: [{
                id: "codex:superpowers@openai-curated",
                name: "Codex / Superpowers",
                enabled: false,
                path: "/home/user/.codex/plugins/cache/openai-curated/superpowers",
                origin: "client"
              }]
            },
            { id: "mcp", name: "System MCP Servers", items: [] }
          ]
        });
      }
      throw new Error(`unexpected request: ${url.pathname}`);
    });
    globalThis.fetch = fetchMock as never;

    renderSettingsModal({ initialView: "system-plugins" });

    await waitFor(() => {
      expect(container?.textContent).toContain("Codex / Superpowers");
    });
    const toggle = container?.querySelector('input[aria-label="禁用 Codex / Superpowers"]');
    expect(toggle).toBeInstanceOf(HTMLInputElement);
    await act(async () => {
      (toggle as HTMLInputElement).click();
    });

    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining("/api/system-agent-config/plugins/codex%3Asuperpowers%40openai-curated"),
      expect.objectContaining({ method: "PATCH" })
    );
  });

  it("shows profile plugin config in its own Agent tab", async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = new URL(String(input));
      if (url.pathname === "/api/clients/client-1/agent-clients" && init?.method === undefined) {
        return jsonResponse({
          agent_clients: [{
            id: "codex",
            provider_id: "codex",
            label: "Codex",
            aliases: [],
            default_command: "codex",
            command_names: ["codex"],
            capabilities: { launch: true, profile_config: true }
          }]
        });
      }
      if (url.pathname === "/api/clients/client-1/agent-profiles" && init?.method === undefined) {
        return jsonResponse({
          profiles: [{
            id: "review-agent",
            name: "Review Agent",
            description: "Code review",
            default_agent_client: "codex",
            agent_md: "Review carefully.",
            created_at: "2026-06-08T00:00:00Z",
            updated_at: "2026-06-08T00:00:00Z"
          }]
        });
      }
      if (url.pathname === "/api/clients/client-1/agent-profiles/review-agent/agent-config/codex" && init?.method === undefined) {
        return jsonResponse({
          agent: "codex",
          sections: [
            { id: "skills", name: "Skills", items: [] },
            {
              id: "plugins",
              name: "Plugins",
              items: [{ id: "superpowers@openai-curated", name: "Superpowers", enabled: true, path: null }]
            },
            { id: "hooks", name: "Hooks", items: [] },
            { id: "mcp", name: "MCP Servers", items: [] }
          ]
        });
      }
      if (
        url.pathname
        === "/api/clients/client-1/agent-profiles/review-agent/agent-config/codex/plugins/superpowers%40openai-curated"
      ) {
        expect(init?.method).toBe("PATCH");
        expect(init?.body).toBe(JSON.stringify({ enabled: false }));
        return jsonResponse({
          agent: "codex",
          sections: [
            { id: "skills", name: "Skills", items: [] },
            {
              id: "plugins",
              name: "Plugins",
              items: [{ id: "superpowers@openai-curated", name: "Superpowers", enabled: false, path: null }]
            },
            { id: "hooks", name: "Hooks", items: [] },
            { id: "mcp", name: "MCP Servers", items: [] }
          ]
        });
      }
      throw new Error(`unexpected request: ${url.pathname}`);
    });
    globalThis.fetch = fetchMock as never;

    renderSettingsModal({ initialView: "agents" });

    await waitFor(() => {
      expect(container?.textContent).toContain("Review Agent");
    });
    expect(container?.textContent).not.toContain("Superpowers");
    const pluginTab = Array.from(container?.querySelectorAll(".agent-profile-tabs button") ?? [])
      .find((button) => button.textContent === "Plugin");
    expect(pluginTab).toBeInstanceOf(HTMLButtonElement);
    act(() => {
      (pluginTab as HTMLButtonElement).click();
    });

    await waitFor(() => {
      expect(container?.textContent).toContain("Superpowers");
    });
    const toggle = container?.querySelector('input[aria-label="禁用 Superpowers"]');
    expect(toggle).toBeInstanceOf(HTMLInputElement);
    await act(async () => {
      (toggle as HTMLInputElement).click();
    });

    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining("/agent-config/codex/plugins/superpowers%40openai-curated"),
      expect.objectContaining({ method: "PATCH" })
    );
  });

});
