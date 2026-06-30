import { describe, expect, it } from "vitest";

import { agentLaunchFromProjectPreference } from "../src/projectAgentPreference";
import { projectTodoDirectDispatchAgentLaunch } from "../src/features/projectTodos/projectTodoDirectDispatch";
import type { AgentClient, ProjectAgentPreference, ProjectTodo } from "../src/types";

const agentClients: AgentClient[] = [
  {
    id: "codex",
    provider_id: "codex",
    label: "Codex",
    aliases: [],
    default_command: "codex",
    command_names: ["codex"],
    capabilities: { launch: true }
  },
  {
    id: "config_only",
    provider_id: "config_provider",
    label: "Config Only",
    aliases: [],
    default_command: "config-only",
    command_names: ["config-only"],
    capabilities: { launch: false }
  }
];

const preference: ProjectAgentPreference = {
  agent_profile_id: "builtin/developer",
  agent_client: "missing",
  agent_command: "codex --model gpt-5-codex",
  agent_model_selection: { preset_id: "openai-main", model: "gpt-5-codex" }
};

describe("project agent preferences", () => {
  it("turns a project preference into a launch config with launchable fallback", () => {
    expect(agentLaunchFromProjectPreference(preference, agentClients)).toEqual({
      agent: "codex",
      command: "codex --model gpt-5-codex",
      config: null,
      profile_id: "builtin/developer",
      model_selection: { preset_id: "openai-main", model: "gpt-5-codex" }
    });
  });

  it("uses project preference for direct todo dispatch when the todo is unassigned", () => {
    const todo = {
      assigned_agent: null,
      agent_profile_id: null
    } as ProjectTodo;

    expect(projectTodoDirectDispatchAgentLaunch(todo, agentClients, preference)).toEqual({
      agent: "codex",
      command: "codex --model gpt-5-codex",
      config: null,
      profile_id: "builtin/developer",
      model_selection: { preset_id: "openai-main", model: "gpt-5-codex" }
    });
  });

  it("keeps the todo assigned agent ahead of the project preference", () => {
    const todo = {
      assigned_agent: "codex",
      agent_profile_id: "todo/profile"
    } as ProjectTodo;

    expect(projectTodoDirectDispatchAgentLaunch(todo, agentClients, preference)).toMatchObject({
      agent: "codex",
      command: "codex",
      profile_id: "todo/profile"
    });
  });
});
