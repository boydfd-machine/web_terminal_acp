import {
  agentClientOptions,
  agentDefaultCommand,
  agentLaunchForClient
} from "./agentLaunch";
import type { AgentClient, AgentLaunchConfig, AgentLaunchKind, ProjectAgentPreference } from "./types";

function launchableAgent(preference: ProjectAgentPreference, agentClients: AgentClient[]): AgentLaunchKind | null {
  const launchOptions = agentClientOptions(agentClients, "launch");
  const preferredAgent = preference.agent_client?.trim();
  if (preferredAgent && launchOptions.some((option) => option.id === preferredAgent)) {
    return preferredAgent as AgentLaunchKind;
  }
  return launchOptions[0]?.id ?? null;
}

export function hasProjectAgentPreference(preference: ProjectAgentPreference | null | undefined): boolean {
  return preference?.agent_profile_id != null
    || preference?.agent_client != null
    || preference?.agent_command != null
    || preference?.agent_model_selection != null;
}

export function agentLaunchFromProjectPreference(
  preference: ProjectAgentPreference | null | undefined,
  agentClients: AgentClient[]
): AgentLaunchConfig | null {
  if (!hasProjectAgentPreference(preference)) {
    return null;
  }
  const agent = launchableAgent(preference as ProjectAgentPreference, agentClients);
  if (agent === null) {
    return null;
  }
  const command = preference?.agent_command?.trim() || agentDefaultCommand(agent, agentClients);
  return {
    ...agentLaunchForClient(agent, agentClients),
    command,
    profile_id: preference?.agent_profile_id ?? null,
    ...(preference?.agent_model_selection != null ? { model_selection: preference.agent_model_selection } : {})
  };
}
