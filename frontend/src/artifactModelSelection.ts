import { DEFAULT_AGENT_CLIENTS } from "./agentLaunch";
import {
  readArtifactModelSelectionSettings,
  type AgentModelSelectionSettings
} from "./userPreferences";
import type {
  AgentClient,
  AgentLaunchKind,
  AgentModelSelection,
  ProjectAgentPreference,
  ProjectTodo,
  ProjectTodoListItem,
  ProjectTodoType,
  VirtualWindow
} from "./types";

export function artifactModelAgentSupportsSelection(agent: string | null | undefined): agent is AgentLaunchKind {
  return agent === "codex" || agent === "claude";
}

export function artifactModelDefaultSelection(
  agent: AgentLaunchKind | null,
  settings: AgentModelSelectionSettings = readArtifactModelSelectionSettings()
): AgentModelSelection | null {
  return agent === null ? null : settings[agent] ?? null;
}

export function artifactModelAgentFromWindow(
  window: Pick<VirtualWindow, "derived_context" | "runtime_tags" | "shell_command">,
  agentClients: AgentClient[] = DEFAULT_AGENT_CLIENTS
): AgentLaunchKind | null {
  const context = isRecord(window.derived_context) ? window.derived_context : {};
  const sourceCommand = context.source_agent_command;
  const commandAgent = artifactModelAgentFromCommand(
    typeof sourceCommand === "string" ? sourceCommand : window.shell_command,
    agentClients
  );
  if (commandAgent !== null) {
    return commandAgent;
  }

  for (const tag of window.runtime_tags ?? []) {
    const agent = artifactModelAgentFromToken(tag, agentClients);
    if (agent !== null) {
      return agent;
    }
  }
  return null;
}

export function artifactModelAgentFromTodo(
  todo: Pick<ProjectTodo | ProjectTodoListItem, "assigned_agent" | "todo_type"> | null,
  projectPreference: ProjectAgentPreference | null | undefined,
  agentClients: AgentClient[] = DEFAULT_AGENT_CLIENTS
): AgentLaunchKind | null {
  return artifactModelAgentFromToken(todo?.assigned_agent, agentClients)
    ?? artifactModelAgentFromToken(todo?.todo_type.agent, agentClients)
    ?? artifactModelAgentFromToken(projectPreference?.agent_client, agentClients);
}

export function artifactModelAgentFromTodoType(
  todoType: Pick<ProjectTodoType, "agent"> | null,
  projectPreference: ProjectAgentPreference | null | undefined,
  agentClients: AgentClient[] = DEFAULT_AGENT_CLIENTS
): AgentLaunchKind | null {
  return artifactModelAgentFromToken(todoType?.agent, agentClients)
    ?? artifactModelAgentFromToken(projectPreference?.agent_client, agentClients);
}

function artifactModelAgentFromCommand(
  command: string | null | undefined,
  agentClients: AgentClient[]
): AgentLaunchKind | null {
  if (typeof command !== "string" || command.trim().length === 0) {
    return null;
  }
  for (const token of command.trim().split(/\s+/)) {
    const agent = artifactModelAgentFromToken(token, agentClients);
    if (agent !== null) {
      return agent;
    }
  }
  return null;
}

function artifactModelAgentFromToken(
  token: string | null | undefined,
  agentClients: AgentClient[]
): AgentLaunchKind | null {
  if (typeof token !== "string" || token.trim().length === 0) {
    return null;
  }
  const normalized = token.trim();
  const basename = normalized.split(/[\\/]/).pop() ?? normalized;
  for (const agentClient of agentClients) {
    const names = new Set([
      agentClient.id,
      agentClient.provider_id,
      agentClient.default_command,
      ...agentClient.aliases,
      ...agentClient.command_names
    ]);
    if (names.has(normalized) || names.has(basename)) {
      return artifactModelAgentSupportsSelection(agentClient.id)
        ? agentClient.id as AgentLaunchKind
        : null;
    }
  }
  return null;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}
