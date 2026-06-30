import { act } from "react";
import { describe, expect, it, vi } from "vitest";

import {
  container,
  jsonResponse,
  renderSettingsModal,
  setInputFiles,
  waitFor
} from "./settingsModalHarness";

function buttonByAriaLabel(label: string): HTMLButtonElement | null {
  const button = container?.querySelector(`button[aria-label="${label}"]`);
  return button instanceof HTMLButtonElement ? button : null;
}

function inputByAriaLabel(label: string): HTMLInputElement | null {
  const input = container?.querySelector(`input[aria-label="${label}"]`);
  return input instanceof HTMLInputElement ? input : null;
}

function stubObjectUrls() {
  const createObjectURL = vi.fn(() => "blob:settings-export");
  const revokeObjectURL = vi.fn();
  Object.defineProperty(URL, "createObjectURL", { configurable: true, value: createObjectURL });
  Object.defineProperty(URL, "revokeObjectURL", { configurable: true, value: revokeObjectURL });
  return { createObjectURL, revokeObjectURL };
}

describe("Settings import/export", () => {
  it("exports and imports agent profiles including built-in profiles", async () => {
    const { createObjectURL } = stubObjectUrls();
    const bundle = {
      kind: "web-terminal-agent-profile",
      version: 1,
      profile: {
        id: "builtin/developer",
        name: "Developer",
        description: null,
        default_agent_client: "codex",
        agent_md: "Developer prompt",
        created_at: "2026-06-05T00:00:00Z",
        updated_at: "2026-06-05T00:00:00Z"
      },
      files: { version: 1, files: [] }
    };
    let importedBody: unknown = null;
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
        return jsonResponse({ profiles: [bundle.profile] });
      }
      if (url.pathname === "/api/clients/client-1/agent-profile-config" && init?.method === undefined) {
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
      if (url.pathname === "/api/clients/client-1/agent-profiles/export" && init?.method === undefined) {
        expect(url.searchParams.get("profile_id")).toBe("builtin/developer");
        return jsonResponse(bundle);
      }
      if (url.pathname === "/api/clients/client-1/agent-profiles/import" && init?.method === "POST") {
        importedBody = JSON.parse(String(init.body));
        return jsonResponse({
          ...bundle.profile,
          id: "imported-developer",
          created_at: "2026-06-28T00:00:00Z",
          updated_at: "2026-06-28T00:00:00Z"
        });
      }
      throw new Error(`unexpected request: ${url.pathname}`);
    });
    globalThis.fetch = fetchMock as never;

    renderSettingsModal({ initialView: "agents" });

    await waitFor(() => {
      expect(container?.textContent).toContain("Developer");
    });
    const exportButton = buttonByAriaLabel("下载 Developer");
    expect(exportButton).toBeInstanceOf(HTMLButtonElement);
    await act(async () => {
      exportButton?.click();
    });
    expect(createObjectURL).toHaveBeenCalled();

    const importInput = inputByAriaLabel("导入 Agent");
    expect(importInput).toBeInstanceOf(HTMLInputElement);
    const file = new File([JSON.stringify(bundle)], "developer.json", { type: "application/json" });
    await act(async () => {
      setInputFiles(importInput as HTMLInputElement, [file]);
    });

    await waitFor(() => {
      expect(importedBody).toEqual(bundle);
    });
  });

  it("exports and imports model presets", async () => {
    const { createObjectURL } = stubObjectUrls();
    const preset = {
      id: "subapi",
      name: "subapi",
      provider: "openai_compatible",
      providers: ["openai_compatible"],
      base_url: "https://api.example.test/v1",
      api_key: "secret",
      models: ["gpt-4.1"],
      model_configs: [{ name: "gpt-4.1" }]
    };
    const bundle = { kind: "web-terminal-model-preset", version: 1, preset };
    let importedBody: unknown = null;
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = new URL(String(input));
      if (url.pathname === "/api/clients/client-1/agent-clients" && init?.method === undefined) {
        return jsonResponse({ agent_clients: [] });
      }
      if (url.pathname === "/api/system-agent-config/model-presets" && init?.method === undefined) {
        return jsonResponse({ presets: [preset] });
      }
      if (url.pathname === "/api/system-agent-config/model-presets/subapi/export" && init?.method === undefined) {
        return jsonResponse(bundle);
      }
      if (url.pathname === "/api/system-agent-config/model-presets/import" && init?.method === "POST") {
        importedBody = JSON.parse(String(init.body));
        return jsonResponse({ presets: [preset] });
      }
      throw new Error(`unexpected request: ${url.pathname}`);
    });
    globalThis.fetch = fetchMock as never;

    renderSettingsModal({ initialView: "system-models" });

    await waitFor(() => {
      expect(container?.textContent).toContain("subapi");
    });
    const presetRow = Array.from(container?.querySelectorAll(".system-model-preset-list .system-config-item-content") ?? [])
      .find((button) => button.textContent?.includes("subapi"));
    expect(presetRow).toBeInstanceOf(HTMLButtonElement);
    act(() => {
      (presetRow as HTMLButtonElement).click();
    });

    const exportButton = buttonByAriaLabel("下载 subapi");
    expect(exportButton).toBeInstanceOf(HTMLButtonElement);
    await act(async () => {
      exportButton?.click();
    });
    expect(createObjectURL).toHaveBeenCalled();

    const importInput = inputByAriaLabel("导入模型配置");
    expect(importInput).toBeInstanceOf(HTMLInputElement);
    const file = new File([JSON.stringify(bundle)], "subapi.json", { type: "application/json" });
    await act(async () => {
      setInputFiles(importInput as HTMLInputElement, [file]);
    });

    await waitFor(() => {
      expect(importedBody).toEqual(bundle);
    });
  });

  it("shows export controls for built-in system skills", async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = new URL(String(input));
      if (url.pathname === "/api/system-agent-config" && init?.method === undefined) {
        return jsonResponse({
          agent: "system",
          sections: [
            {
              id: "skills",
              name: "System Skills",
              items: [{
                id: "builtin-skill",
                name: "Built-in Skill",
                enabled: true,
                path: null,
                origin: "system_builtin"
              }]
            },
            { id: "mcp", name: "System MCP Servers", items: [] }
          ]
        });
      }
      throw new Error(`unexpected request: ${url.pathname}`);
    });
    globalThis.fetch = fetchMock as never;

    renderSettingsModal({ initialView: "system-skills" });

    await waitFor(() => {
      expect(container?.textContent).toContain("Built-in Skill");
    });
    expect(buttonByAriaLabel("下载 Built-in Skill")).toBeInstanceOf(HTMLButtonElement);
  });
});
