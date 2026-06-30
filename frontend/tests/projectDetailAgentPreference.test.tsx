import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ProjectDetail } from "../src/components/ProjectDetail";
import type { Project } from "../src/types";

globalThis.IS_REACT_ACT_ENVIRONMENT = true;

const apiMocks = vi.hoisted(() => ({
  fetchAgentClients: vi.fn(),
  fetchAgentProfiles: vi.fn(),
  fetchProject: vi.fn(),
  fetchSystemModelPresets: vi.fn(),
  updateProjectAgentPreference: vi.fn()
}));

vi.mock("../src/api", () => apiMocks);

let root: Root | null = null;
let container: HTMLDivElement | null = null;
let queryClient: QueryClient | null = null;

const project: Project = {
  client_id: "client-1",
  path: "/workspace/project",
  display_name: "Project",
  summary_status: null,
  summary_updated_at: null,
  window_count: 0,
  agent_preference: {
    agent_profile_id: "builtin/developer",
    agent_client: "codex",
    agent_command: "codex",
    agent_model_selection: { preset_id: "openai-main", model: "gpt-5-codex" }
  }
};

function setInputValue(target: HTMLInputElement, value: string): void {
  const setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value")?.set;
  act(() => {
    setter?.call(target, value);
    target.dispatchEvent(new Event("input", { bubbles: true }));
  });
}

async function flush(): Promise<void> {
  await act(async () => {
    await Promise.resolve();
    await Promise.resolve();
  });
}

beforeEach(() => {
  apiMocks.fetchAgentClients.mockResolvedValue({
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
  apiMocks.fetchAgentProfiles.mockResolvedValue({
    profiles: [{
      id: "builtin/developer",
      name: "Developer",
      description: null,
      default_agent_client: "codex",
      agent_md: "",
      created_at: "2026-06-12T00:00:00Z",
      updated_at: "2026-06-12T00:00:00Z"
    }]
  });
  apiMocks.fetchSystemModelPresets.mockResolvedValue({
    presets: [{
      id: "openai-main",
      name: "OpenAI Main",
      provider: "openai_compatible",
      base_url: "https://models.example.com/v1",
      api_key: "secret-key",
      models: ["gpt-5-codex"]
    }]
  });
  apiMocks.updateProjectAgentPreference.mockResolvedValue({
    agent_profile_id: "builtin/developer",
    agent_client: "codex",
    agent_command: "codex --model gpt-5-codex",
    agent_model_selection: { preset_id: "openai-main", model: "gpt-5-codex" }
  });
});

afterEach(() => {
  act(() => {
    root?.unmount();
  });
  container?.remove();
  queryClient?.clear();
  root = null;
  container = null;
  queryClient = null;
  vi.clearAllMocks();
});

describe("ProjectDetail agent preference settings", () => {
  it("saves the project default profile, agent CLI, command, and model", async () => {
    container = document.createElement("div");
    document.body.appendChild(container);
    queryClient = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
    root = createRoot(container);
    act(() => {
      root?.render(
        <QueryClientProvider client={queryClient as QueryClient}>
          <ProjectDetail
            clientId="client-1"
            projectPath="/workspace/project"
            project={project}
            projects={[project]}
            timeRange="30d"
            onSelectWindow={() => {}}
          />
        </QueryClientProvider>
      );
    });
    await flush();

    const commandInput = container.querySelector('input[aria-label="Agent command"]');
    expect(commandInput).toBeInstanceOf(HTMLInputElement);
    setInputValue(commandInput as HTMLInputElement, "codex --model gpt-5-codex");
    const saveButton = Array.from(container.querySelectorAll("button")).find((button) => button.textContent === "Save");
    expect(saveButton).toBeInstanceOf(HTMLButtonElement);
    act(() => {
      (saveButton as HTMLButtonElement).click();
    });
    await flush();

    expect(apiMocks.updateProjectAgentPreference).toHaveBeenCalledWith("client-1", "/workspace/project", {
      agent_profile_id: "builtin/developer",
      agent_client: "codex",
      agent_command: "codex --model gpt-5-codex",
      agent_model_selection: { preset_id: "openai-main", model: "gpt-5-codex" }
    });
  });
});
