import { act } from "react";
import { describe, expect, it, vi } from "vitest";

import { downloadSystemSkill } from "../src/api";
import {
  container,
  jsonResponse,
  renderSettingsModal,
  setInputFiles,
  setValue as setFormValue,
  waitFor
} from "./settingsModalHarness";

function setPressedButtonValue(target: HTMLButtonElement, pressed: boolean): void {
  if (target.getAttribute("aria-pressed") === String(pressed)) {
    return;
  }
  act(() => {
    target.click();
  });
}

function buttonByAriaLabel(label: string): HTMLButtonElement | null {
  const button = container?.querySelector(`button[aria-label="${label}"]`);
  return button instanceof HTMLButtonElement ? button : null;
}

async function readBlobText(blob: Blob): Promise<string> {
  if (typeof blob.text === "function") {
    return blob.text();
  }
  return await new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.addEventListener("load", () => resolve(String(reader.result ?? "")));
    reader.addEventListener("error", () => reject(reader.error));
    reader.readAsText(blob);
  });
}

describe("System agent config settings", () => {
  it("opens system MCP detail with tools and server JSON", async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = new URL(String(input));
      if (url.pathname === "/api/system-agent-config" && init?.method === undefined) {
        return jsonResponse({
          agent: "system",
          sections: [
            { id: "skills", name: "System Skills", items: [] },
            {
              id: "mcp",
              name: "System MCP Servers",
              items: [{ id: "web-terminal-acp-mcp", name: "web-terminal-acp-mcp", enabled: true, path: null, origin: "system_builtin" }]
            }
          ]
        });
      }
      if (url.pathname === "/api/system-agent-config/mcp/web-terminal-acp-mcp/detail") {
        return jsonResponse({
          id: "web-terminal-acp-mcp",
          name: "web-terminal-acp-mcp",
          enabled: true,
          path: null,
          origin: "system_builtin",
          editable: true,
          overridden: false,
          server: { type: "stdio", command: "python" },
          tools: [
            {
              name: "send_input",
              description: "Send terminal input to a window.",
              input_schema: {
                type: "object",
                required: ["target_client_id"],
                properties: {
                  target_client_id: { type: "string", description: "Target client ID." },
                  input: { type: "string", description: "Terminal input." },
                  tags: { type: "array", items: { type: "string" }, description: "Optional labels." }
                }
              }
            }
          ]
        });
      }
      throw new Error(`unexpected request: ${url.pathname}`);
    });
    globalThis.fetch = fetchMock as never;

    renderSettingsModal();
    const mcpTab = Array.from(container?.querySelectorAll(".settings-tabs button") ?? [])
      .find((button) => button.textContent?.includes("系统 MCP"));
    act(() => {
      (mcpTab as HTMLButtonElement).click();
    });

    await waitFor(() => {
      expect(container?.textContent).toContain("web-terminal-acp-mcp");
    });
    const rowButton = container?.querySelector(".system-config-item-content");
    expect(rowButton).toBeInstanceOf(HTMLButtonElement);
    await act(async () => {
      (rowButton as HTMLButtonElement).click();
    });

    await waitFor(() => {
      expect(container?.textContent).toContain("send_input");
      expect(container?.textContent).toContain("Editable");
      expect(container?.textContent).toContain("工具描述");
      expect(container?.textContent).toContain("target_client_id");
      expect(container?.textContent).toContain("必填");
      expect(container?.textContent).toContain("array<string>");
    });
    const jsonModeButton = Array.from(container?.querySelectorAll(".workspace-mode-toggle button") ?? [])
      .find((button) => button.textContent?.includes("JSON"));
    expect(jsonModeButton).toBeInstanceOf(HTMLButtonElement);
    act(() => {
      (jsonModeButton as HTMLButtonElement).click();
    });

    await waitFor(() => {
      expect(container?.textContent).toContain("\"command\": \"python\"");
      expect(container?.textContent).toContain("\"target_client_id\"");
    });
  });

  it("uploads a system skill from the redesigned uploader", async () => {
    const archive = new File(["zip-bytes"], "review-helper.zip", { type: "application/zip" });
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = new URL(String(input));
      if (url.pathname === "/api/system-agent-config" && init?.method === undefined) {
        return jsonResponse({
          agent: "system",
          sections: [
            { id: "skills", name: "System Skills", items: [] },
            { id: "mcp", name: "System MCP Servers", items: [] }
          ]
        });
      }
      if (url.pathname === "/api/system-agent-config/skills/review-helper") {
        expect(init?.method).toBe("PUT");
        expect(url.searchParams.get("enabled")).toBe("true");
        expect(init?.body).toBe(archive);
        return jsonResponse({
          agent: "system",
          sections: [
            {
              id: "skills",
              name: "System Skills",
              items: [{ id: "review-helper", name: "review-helper", enabled: true, path: null }]
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
      expect(container?.querySelector(".system-config-upload input")).toBeInstanceOf(HTMLInputElement);
    });
    const fileInput = container?.querySelector(".system-config-upload input");
    act(() => {
      setInputFiles(fileInput as HTMLInputElement, [archive]);
    });
    await waitFor(() => {
      expect(container?.querySelector(".system-config-upload-copy strong")?.textContent).toBe("review-helper.zip");
    });
    const uploadButton = Array.from(container?.querySelectorAll(".system-config-editor button") ?? [])
      .find((button) => button.textContent?.includes("上传 Skill"));
    expect(uploadButton).toBeInstanceOf(HTMLButtonElement);
    await act(async () => {
      (uploadButton as HTMLButtonElement).click();
    });

    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining("/api/system-agent-config/skills/review-helper?enabled=true"),
      expect.objectContaining({ method: "PUT", body: archive })
    );
  });

  it("downloads system skills with bearer auth", async () => {
    window.localStorage.setItem("web-terminal-acp:auth-token", "token-1");
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response("zip-bytes"));

    const archive = await downloadSystemSkill("review-helper");

    expect(await readBlobText(archive)).toBe("zip-bytes");
    const [input, init] = fetchMock.mock.calls[0];
    expect(new URL(String(input)).pathname).toBe("/api/system-agent-config/skills/review-helper/download");
    expect(new Headers(init?.headers).get("Authorization")).toBe("Bearer token-1");
  });

  it("saves system model presets from Settings", async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = new URL(String(input));
      if (url.pathname === "/api/clients/client-1/agent-clients" && init?.method === undefined) {
        return jsonResponse({ agent_clients: [] });
      }
      if (url.pathname === "/api/system-agent-config/model-presets" && init?.method === undefined) {
        return jsonResponse({ presets: [] });
      }
      if (url.pathname === "/api/system-agent-config/model-presets/openai-main") {
        expect(init?.method).toBe("PUT");
        expect(JSON.parse(String(init?.body))).toEqual({
          name: "OpenAI Main",
          providers: ["openai_compatible", "anthropic_compatible"],
          base_url: "https://models.example.com/v1",
          api_key: "secret-key",
          models: ["model-a", "model-b"],
          model_configs: [
            {
              name: "model-a",
              max_output_tokens: 8192,
              context_window: 258400,
              auto_compact_token_limit: 200000
            },
            { name: "model-b" }
          ]
        });
        return jsonResponse({
          presets: [
            {
              id: "openai-main",
              name: "OpenAI Main",
              provider: "openai_compatible",
              providers: ["openai_compatible", "anthropic_compatible"],
              base_url: "https://models.example.com/v1",
              api_key: "secret-key",
              models: ["model-a", "model-b"],
              model_configs: [
                {
                  name: "model-a",
                  max_output_tokens: 8192,
                  context_window: 258400,
                  auto_compact_token_limit: 200000
                },
                { name: "model-b" }
              ]
            }
          ]
        });
      }
      throw new Error(`unexpected request: ${url.pathname}`);
    });
    globalThis.fetch = fetchMock as never;

    renderSettingsModal();
    const modelTab = Array.from(container?.querySelectorAll(".settings-tabs button") ?? [])
      .find((button) => button.textContent?.includes("模型"));
    expect(modelTab).toBeInstanceOf(HTMLButtonElement);
    act(() => {
      (modelTab as HTMLButtonElement).click();
    });

    await waitFor(() => {
      expect(container?.querySelector(".system-model-form")).not.toBeNull();
    });
    const idInput = container?.querySelector('.system-model-form input[placeholder="openai-main"]');
    const nameInput = container?.querySelector('.system-model-form input[placeholder="OpenAI main"]');
    const openaiProviderButton = container?.querySelector('.system-model-provider-options button[aria-label="OpenAI-compatible"]');
    const anthropicProviderButton = container?.querySelector('.system-model-provider-options button[aria-label="Anthropic-compatible"]');
    const baseUrlInput = container?.querySelector('.system-model-form input[placeholder="https://api.example.com/v1"]');
    const apiKeyInput = container?.querySelector('.system-model-form input[type="password"]');
    const modelNameInputs = container?.querySelectorAll(".system-model-config-row input[placeholder='gpt-4.1']");
    const firstRowInputs = container?.querySelectorAll(".system-model-config-row:first-of-type input");
    expect(idInput).toBeInstanceOf(HTMLInputElement);
    expect(nameInput).toBeInstanceOf(HTMLInputElement);
    expect(openaiProviderButton).toBeInstanceOf(HTMLButtonElement);
    expect(anthropicProviderButton).toBeInstanceOf(HTMLButtonElement);
    expect(baseUrlInput).toBeInstanceOf(HTMLInputElement);
    expect(apiKeyInput).toBeInstanceOf(HTMLInputElement);
    expect(modelNameInputs?.length).toBe(1);
    expect(firstRowInputs?.length).toBe(4);
    act(() => {
      setFormValue(idInput as HTMLInputElement, "openai-main");
      setFormValue(nameInput as HTMLInputElement, "OpenAI Main");
      setFormValue(baseUrlInput as HTMLInputElement, "https://models.example.com/v1");
      setFormValue(apiKeyInput as HTMLInputElement, "secret-key");
      setFormValue(firstRowInputs?.[0] as HTMLInputElement, "model-a");
      setFormValue(firstRowInputs?.[1] as HTMLInputElement, "258400");
      setFormValue(firstRowInputs?.[2] as HTMLInputElement, "200000");
      setFormValue(firstRowInputs?.[3] as HTMLInputElement, "8192");
    });
    const addButton = buttonByAriaLabel("添加模型");
    expect(addButton).toBeInstanceOf(HTMLButtonElement);
    act(() => {
      addButton?.click();
    });
    const nextModelNameInputs = container?.querySelectorAll(".system-model-config-row input[placeholder='gpt-4.1']");
    expect(nextModelNameInputs?.length).toBe(2);
    act(() => {
      setFormValue(nextModelNameInputs?.[1] as HTMLInputElement, "model-b");
    });
    setPressedButtonValue(anthropicProviderButton as HTMLButtonElement, true);
    const saveButton = container?.querySelector('.system-model-actions button[aria-label="保存模型配置"]');
    expect(saveButton).toBeInstanceOf(HTMLButtonElement);
    await act(async () => {
      (saveButton as HTMLButtonElement).click();
    });

    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining("/api/system-agent-config/model-presets/openai-main"),
      expect.objectContaining({ method: "PUT" })
    );
    await waitFor(() => {
      expect(container?.textContent).toContain("OpenAI Main");
      expect(container?.textContent).toContain("2 个模型");
    });
  });
});
