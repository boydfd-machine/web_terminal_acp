import { agentClientOptions, agentLaunchForClient } from "../../agentLaunch";
import { agentLaunchFromProjectPreference } from "../../projectAgentPreference";
import type { AgentClient, AgentLaunchConfig, AgentLaunchKind, ProjectAgentPreference, ProjectTodo } from "../../types";

export function projectTodoDirectDispatchAgentLaunch(
  todo: ProjectTodo,
  agentClients: AgentClient[],
  projectPreference?: ProjectAgentPreference | null
): AgentLaunchConfig | null {
  const assignedAgent = todo.assigned_agent?.trim();
  if (!assignedAgent) {
    const preferredLaunch = agentLaunchFromProjectPreference(projectPreference, agentClients);
    if (preferredLaunch !== null) {
      return preferredLaunch;
    }
  }
  const launchAgent = assignedAgent && agentClients.some((agentClient) => agentClient.id === assignedAgent)
    ? assignedAgent
    : agentClientOptions(agentClients, "launch")[0]?.id;
  if (launchAgent === undefined) {
    return null;
  }
  return {
    ...agentLaunchForClient(launchAgent as AgentLaunchKind, agentClients),
    profile_id: todo.agent_profile_id
  };
}
