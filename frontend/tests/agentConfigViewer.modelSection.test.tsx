import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { AgentConfigViewer } from "../src/components/AgentConfigViewer";
import { I18nProvider } from "../src/i18n";
import type { AgentConfig } from "../src/types";

globalThis.IS_REACT_ACT_ENVIRONMENT = true;

const apiMocks = vi.hoisted(() => ({
  updateAgentConfigModel: vi.fn()
}));

vi.mock("../src/api", () => ({
  ...apiMocks,
  fetchAgentConfig: vi.fn(),
  updateAgentConfigItem: vi.fn()
}));

let root: Root | null = null;
let container: HTMLDivElement | null = null;
let queryClient: QueryClient | null = null;

function renderWithConfig(config: AgentConfig | null, onUpdateModel?: (input: unknown) => void) {
  container = document.createElement("div");
  document.body.appendChild(container);
  root = createRoot(container);
  act(() => {
    root!.render(
      <QueryClientProvider client={queryClient!}>
        <I18nProvider>
          <AgentConfigViewer
            config={config}
            onToggleItem={() => undefined}
            onUpdateModel={onUpdateModel ?? apiMocks.updateAgentConfigModel}
          />
        </I18nProvider>
      </QueryClientProvider>
    );
  });
}

beforeEach(() => {
  queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  apiMocks.updateAgentConfigModel.mockReset();
});

afterEach(() => {
  act(() => {
    root?.unmount();
  });
  root = null;
  container?.remove();
  container = null;
});

function selectOption(select: HTMLSelectElement, value: string): void {
  const setter = Object.getOwnPropertyDescriptor(HTMLSelectElement.prototype, "value")?.set;
  act(() => {
    setter?.call(select, value);
    select.dispatchEvent(new Event("change", { bubbles: true }));
  });
}

function setInputValue(input: HTMLInputElement, value: string): void {
  const setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value")?.set;
  act(() => {
    setter?.call(input, value);
    input.dispatchEvent(new Event("input", { bubbles: true }));
  });
}

describe("AgentConfigViewer model section", () => {
  it("renders editable codex model and reasoning efforts", () => {
    renderWithConfig({
      agent: "codex",
      sections: [],
      model: {
        editable: true,
        provider: "codex",
        preset_id: "openai-main",
        preset_name: "OpenAI Main",
        model: "model-a",
        available_models: ["model-a", "model-b"],
        codex_model_reasoning_effort: "high",
        codex_plan_mode_reasoning_effort: "medium",
        claude_reasoning_effort: null,
        codex_reasoning_efforts: ["minimal", "low", "medium", "high", "xhigh"],
        claude_reasoning_efforts: ["low", "medium", "high"]
      }
    });
    const selects = container!.querySelectorAll("select.agent-config-select");
    expect(selects.length).toBe(3);
    expect((selects[0] as HTMLSelectElement).value).toBe("model-a");
    expect((selects[1] as HTMLSelectElement).value).toBe("high");
    expect((selects[2] as HTMLSelectElement).value).toBe("medium");
  });

  it("fires model update when reasoning effort changes", () => {
    const handler = vi.fn();
    renderWithConfig({
      agent: "codex",
      sections: [],
      model: {
        editable: true,
        provider: "codex",
        preset_id: "openai-main",
        preset_name: "OpenAI Main",
        model: "model-a",
        available_models: ["model-a", "model-b"],
        codex_model_reasoning_effort: "high",
        codex_plan_mode_reasoning_effort: null,
        claude_reasoning_effort: null,
        codex_reasoning_efforts: ["minimal", "low", "medium", "high", "xhigh"],
        claude_reasoning_efforts: ["low", "medium", "high"]
      }
    }, handler);
    const selects = container!.querySelectorAll("select.agent-config-select");
    selectOption(selects[1] as HTMLSelectElement, "low");
    expect(handler).toHaveBeenCalledWith({ codex_model_reasoning_effort: "low" });
  });

  it("clears reasoning effort when none option selected", () => {
    const handler = vi.fn();
    renderWithConfig({
      agent: "claude",
      sections: [],
      model: {
        editable: true,
        provider: "claude_code",
        preset_id: "anthropic-main",
        preset_name: "Anthropic Main",
        model: "claude-sonnet",
        available_models: ["claude-sonnet"],
        codex_model_reasoning_effort: null,
        codex_plan_mode_reasoning_effort: null,
        claude_reasoning_effort: "high",
        codex_reasoning_efforts: ["minimal", "low", "medium", "high"],
        claude_reasoning_efforts: ["low", "medium", "high", "xhigh"]
      }
    }, handler);
    const selects = container!.querySelectorAll("select.agent-config-select");
    expect(selects.length).toBe(2);
    selectOption(selects[1] as HTMLSelectElement, "__none__");
    expect(handler).toHaveBeenCalledWith({ clear_claude_reasoning_effort: true });
  });

  it("renders read-only values when not editable", () => {
    renderWithConfig({
      agent: "codex",
      sections: [],
      model: {
        editable: false,
        provider: "codex",
        model: "legacy-model",
        available_models: [],
        codex_model_reasoning_effort: "medium",
        codex_plan_mode_reasoning_effort: null,
        claude_reasoning_effort: null,
        codex_reasoning_efforts: ["minimal", "low", "medium", "high"],
        claude_reasoning_efforts: ["low", "medium", "high"]
      }
    });
    const values = container!.querySelectorAll(".agent-config-value");
    expect(values.length).toBeGreaterThanOrEqual(2);
    expect(values[0].textContent).toBe("legacy-model");
    expect(values[1].textContent).toBe("medium");
    expect(container!.querySelector("select")).toBeNull();
  });

  it("omits model section when not present", () => {
    renderWithConfig({ agent: "codex", sections: [], model: null });
    expect(container!.querySelector(".agent-config-model")).toBeNull();
  });

  it("filters config section items by name and id", () => {
    renderWithConfig({
      agent: "codex",
      sections: [
        {
          id: "skills",
          name: "Skills",
          items: [
            { id: "docker", name: "Docker", enabled: true, path: null },
            { id: "deep-research", name: "Deep Research", enabled: false, path: "/skills/deep-research" }
          ]
        },
        {
          id: "mcp",
          name: "MCP Servers",
          items: [{ id: "filesystem", name: "Filesystem", enabled: true, path: null }]
        }
      ],
      model: null
    });

    const searchInputs = container!.querySelectorAll<HTMLInputElement>('input[type="search"]');
    expect(searchInputs.length).toBe(2);
    setInputValue(searchInputs[0], "research");

    expect(container?.textContent).toContain("Deep Research");
    expect(container?.textContent).not.toContain("Docker");
    expect(container?.textContent).toContain("Filesystem");

    setInputValue(searchInputs[0], "missing");
    expect(container?.textContent).toContain("No matching items.");
  });
});
