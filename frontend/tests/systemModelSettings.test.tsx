import { act } from "react";
import { describe, expect, it, vi } from "vitest";

import {
  container,
  jsonResponse,
  renderSettingsModal,
  waitFor
} from "./settingsModalHarness";

function buttonByAriaLabel(label: string): HTMLButtonElement | null {
  const button = container?.querySelector(`button[aria-label="${label}"]`);
  return button instanceof HTMLButtonElement ? button : null;
}

function selectByLabelSpan(text: string): HTMLSelectElement | null {
  const labels = Array.from(container?.querySelectorAll(".system-model-effort-field") ?? []);
  const match = labels.find((label) => label.textContent?.includes(text));
  const select = match?.querySelector("select");
  return select instanceof HTMLSelectElement ? select : null;
}

function changeSelect(select: HTMLSelectElement, value: string): void {
  act(() => {
    select.value = value;
    select.dispatchEvent(new Event("change", { bubbles: true }));
  });
}

describe("System model settings", () => {
  it("separates model presets from CLI launch settings inside the model page", async () => {
    let lastModelPresetBody: unknown = null;
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = new URL(String(input));
      if (url.pathname === "/api/system-agent-config/model-presets" && init?.method === undefined) {
        return jsonResponse({
          presets: [{
            id: "subapi",
            name: "subapi",
            provider: "openai_compatible",
            providers: ["openai_compatible", "anthropic_compatible"],
            base_url: "https://api.example.test/v1",
            api_key: "secret",
            models: ["gpt-4.1"],
            model_configs: [{ name: "gpt-4.1" }]
          }]
        });
      }
      if (url.pathname === "/api/clients/client-1/agent-clients" && init?.method === undefined) {
        return jsonResponse({
          agent_clients: [{
            id: "codex",
            provider_id: "codex",
            label: "Codex",
            aliases: [],
            default_command: "codex",
            command_names: ["codex"],
            capabilities: { launch: true }
          }]
        });
      }
      if (url.pathname === "/api/system-agent-config/model-presets/subapi" && init?.method === "PUT") {
        lastModelPresetBody = JSON.parse(String(init.body));
        return jsonResponse({
          presets: [{
            id: "subapi",
            name: "subapi",
            provider: "openai_compatible",
            ...(lastModelPresetBody as object)
          }]
        });
      }
      throw new Error(`unexpected request: ${url.pathname}`);
    });
    globalThis.fetch = fetchMock as never;

    renderSettingsModal({ initialView: "system-models" });

    await waitFor(() => {
      expect(container?.textContent).toContain("subapi");
      expect(container?.querySelector(".system-model-inner-tabs")).toBeInstanceOf(HTMLElement);
    });
    expect(container?.textContent).toContain("Base URL");
    expect(container?.textContent).not.toContain("Agent CLI 启动与默认模型");

    const cliTab = Array.from(container?.querySelectorAll(".system-model-inner-tabs button") ?? [])
      .find((button) => button.textContent === "CLI 启动");
    expect(cliTab).toBeInstanceOf(HTMLButtonElement);
    act(() => {
      (cliTab as HTMLButtonElement).click();
    });
    await waitFor(() => {
      expect(container?.textContent).toContain("Agent CLI 启动与默认模型");
      expect(container?.textContent).toContain("Codex 启动命令");
    });
    expect(container?.textContent).not.toContain("Base URL");

    const modelTab = Array.from(container?.querySelectorAll(".system-model-inner-tabs button") ?? [])
      .find((button) => button.textContent === "模型配置");
    expect(modelTab).toBeInstanceOf(HTMLButtonElement);
    act(() => {
      (modelTab as HTMLButtonElement).click();
    });
    const subapiPreset = Array.from(container?.querySelectorAll(".system-model-preset-list .system-config-item-content") ?? [])
      .find((button) => button.textContent?.includes("subapi"));
    expect(subapiPreset).toBeInstanceOf(HTMLButtonElement);
    act(() => {
      (subapiPreset as HTMLButtonElement).click();
    });
    const anthropicButton = buttonByAriaLabel("Anthropic-compatible");
    expect(anthropicButton).toBeInstanceOf(HTMLButtonElement);
    act(() => {
      (anthropicButton as HTMLButtonElement).click();
    });
    const savePresetButton = buttonByAriaLabel("保存模型配置");
    expect(savePresetButton).toBeInstanceOf(HTMLButtonElement);
    await act(async () => {
      (savePresetButton as HTMLButtonElement).click();
    });

    expect(lastModelPresetBody).toMatchObject({
      name: "subapi",
      providers: ["openai_compatible"],
      base_url: "https://api.example.test/v1",
      models: ["gpt-4.1"],
      model_configs: [{ name: "gpt-4.1" }]
    });
  });

  it("persists per-model reasoning effort overrides when saving a preset", async () => {
    let lastModelPresetBody: unknown = null;
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = new URL(String(input));
      if (url.pathname === "/api/system-agent-config/model-presets" && init?.method === undefined) {
        return jsonResponse({
          presets: [{
            id: "dual",
            name: "dual",
            provider: "openai_compatible",
            providers: ["openai_compatible", "anthropic_compatible"],
            base_url: "https://api.example.test/v1",
            api_key: "secret",
            models: ["gpt-4.1"],
            model_configs: [{ name: "gpt-4.1" }]
          }]
        });
      }
      if (url.pathname === "/api/clients/client-1/agent-clients" && init?.method === undefined) {
        return jsonResponse({ agent_clients: [] });
      }
      if (url.pathname === "/api/system-agent-config/model-presets/dual" && init?.method === "PUT") {
        lastModelPresetBody = JSON.parse(String(init.body));
        return jsonResponse({
          presets: [{
            id: "dual",
            name: "dual",
            provider: "openai_compatible",
            ...(lastModelPresetBody as object)
          }]
        });
      }
      throw new Error(`unexpected request: ${url.pathname}`);
    });
    globalThis.fetch = fetchMock as never;

    renderSettingsModal({ initialView: "system-models" });

    await waitFor(() => {
      expect(container?.textContent).toContain("dual");
    });

    const dualPreset = Array.from(container?.querySelectorAll(".system-model-preset-list .system-config-item-content") ?? [])
      .find((button) => button.textContent?.includes("dual"));
    expect(dualPreset).toBeInstanceOf(HTMLButtonElement);
    act(() => {
      (dualPreset as HTMLButtonElement).click();
    });

    await waitFor(() => {
      expect(selectByLabelSpan("Codex 执行思考强度")).toBeInstanceOf(HTMLSelectElement);
    });
    changeSelect(selectByLabelSpan("Codex 执行思考强度") as HTMLSelectElement, "high");
    changeSelect(selectByLabelSpan("Codex 计划思考强度") as HTMLSelectElement, "medium");
    changeSelect(selectByLabelSpan("Claude 思考强度") as HTMLSelectElement, "max");

    const savePresetButton = buttonByAriaLabel("保存模型配置");
    expect(savePresetButton).toBeInstanceOf(HTMLButtonElement);
    await act(async () => {
      (savePresetButton as HTMLButtonElement).click();
    });

    expect(lastModelPresetBody).toMatchObject({
      model_configs: [{
        name: "gpt-4.1",
        codex_model_reasoning_effort: "high",
        codex_plan_mode_reasoning_effort: "medium",
        claude_reasoning_effort: "max"
      }]
    });
  });
});
