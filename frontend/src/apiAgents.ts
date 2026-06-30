import type {
  AgentChatRecord,
  AgentChatRoleFilter,
  AgentClientList,
  AgentConfig,
  AgentConfigModelUpdate,
  AgentProfile,
  AgentProfileExportBundle,
  AgentProfileList,
  AgentRecord,
  SystemModelPresetExportBundle,
  SystemModelPresetInput,
  SystemModelPresetList,
  SystemMcpDetail,
  SystemMcpServerInput,
  SystemSkillDetail
} from "./types";
import { apiUrl, authHeaders, fetchApi, pathSegment, request, requestVoid, throwApiError } from "./apiCore";

export function fetchAgentRecordChat(
  clientId: string,
  windowId: string,
  limit = 30,
  offset = 0,
  role: AgentChatRoleFilter = "all",
  sessionId: string | null = null,
  order: "earliest" | "latest" = "earliest"
): Promise<AgentChatRecord> {
  const params = new URLSearchParams({
    messages_limit: String(limit),
    messages_offset: String(offset)
  });
  if (order !== "earliest") {
    params.set("messages_order", order);
  }
  if (role !== "all") {
    params.set("role", role);
  }
  if (sessionId !== null) {
    params.set("session_id", sessionId);
  }
  return request<AgentChatRecord>(
    `/api/clients/${pathSegment(clientId)}/windows/${pathSegment(windowId)}/agent-record/chat?${params.toString()}`
  );
}

export function fetchAgentRecordDetail(
  clientId: string,
  windowId: string,
  limit = 100,
  offset = 0,
  sessionId: string | null = null
): Promise<AgentRecord> {
  const params = new URLSearchParams({
    events_limit: String(limit),
    events_offset: String(offset)
  });
  if (sessionId !== null) {
    params.set("session_id", sessionId);
  }
  return request<AgentRecord>(
    `/api/clients/${pathSegment(clientId)}/windows/${pathSegment(windowId)}/agent-record/detail?${params.toString()}`
  );
}

export function fetchAgentConfig(clientId: string, windowId: string): Promise<AgentConfig> {
  return request<AgentConfig>(
    `/api/clients/${pathSegment(clientId)}/windows/${pathSegment(windowId)}/agent-config`
  );
}

export function fetchAgentClients(clientId: string): Promise<AgentClientList> {
  return request<AgentClientList>(`/api/clients/${pathSegment(clientId)}/agent-clients`);
}

export function fetchCursorOfficialModels(clientId: string): Promise<{ models: Array<{ id: string; label: string }> }> {
  return request<{ models: Array<{ id: string; label: string }> }>(
    `/api/clients/${pathSegment(clientId)}/agent-clients/cursor/official-models`
  );
}

export function fetchClientAgentConfig(clientId: string, agent: AgentConfig["agent"]): Promise<AgentConfig> {
  return request<AgentConfig>(
    `/api/clients/${pathSegment(clientId)}/agent-config/${pathSegment(agent)}`
  );
}

export function fetchClientSystemAgentConfig(clientId: string): Promise<AgentConfig> {
  return request<AgentConfig>(
    `/api/clients/${pathSegment(clientId)}/system-agent-config`
  );
}

export function fetchAgentProfiles(clientId: string): Promise<AgentProfileList> {
  return request<AgentProfileList>(`/api/clients/${pathSegment(clientId)}/agent-profiles`);
}

export function exportAgentProfile(
  clientId: string,
  profileId: string
): Promise<AgentProfileExportBundle> {
  const params = new URLSearchParams({ profile_id: profileId });
  return request<AgentProfileExportBundle>(
    `/api/clients/${pathSegment(clientId)}/agent-profiles/export?${params.toString()}`
  );
}

export function importAgentProfile(
  clientId: string,
  payload: unknown
): Promise<AgentProfile> {
  return request<AgentProfile>(`/api/clients/${pathSegment(clientId)}/agent-profiles/import`, {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

export function createAgentProfile(
  clientId: string,
  input: {
    name: string;
    description?: string | null;
    default_agent_client: AgentConfig["agent"];
    source_agent_client?: AgentConfig["agent"] | null;
  }
): Promise<AgentProfile> {
  return request<AgentProfile>(`/api/clients/${pathSegment(clientId)}/agent-profiles`, {
    method: "POST",
    body: JSON.stringify(input)
  });
}

export function updateAgentProfile(
  clientId: string,
  profileId: string,
  input: Partial<Pick<AgentProfile, "name" | "description" | "default_agent_client" | "agent_md">>
): Promise<AgentProfile> {
  if (profileId.includes("/")) {
    const params = new URLSearchParams({ profile_id: profileId });
    return request<AgentProfile>(
      `/api/clients/${pathSegment(clientId)}/agent-profiles/detail?${params.toString()}`,
      {
        method: "PATCH",
        body: JSON.stringify(input)
      }
    );
  }
  return request<AgentProfile>(
    `/api/clients/${pathSegment(clientId)}/agent-profiles/${pathSegment(profileId)}`,
    {
      method: "PATCH",
      body: JSON.stringify(input)
    }
  );
}

export async function deleteAgentProfile(clientId: string, profileId: string): Promise<void> {
  if (profileId.includes("/")) {
    const params = new URLSearchParams({ profile_id: profileId });
    await requestVoid(
      `/api/clients/${pathSegment(clientId)}/agent-profiles/detail?${params.toString()}`,
      { method: "DELETE" }
    );
    return;
  }
  await requestVoid(
    `/api/clients/${pathSegment(clientId)}/agent-profiles/${pathSegment(profileId)}`,
    { method: "DELETE" }
  );
}

export function fetchAgentProfileConfig(
  clientId: string,
  profileId: string,
  agent: AgentConfig["agent"]
): Promise<AgentConfig> {
  if (profileId.includes("/")) {
    const params = new URLSearchParams({ profile_id: profileId, agent });
    return request<AgentConfig>(
      `/api/clients/${pathSegment(clientId)}/agent-profile-config?${params.toString()}`
    );
  }
  return request<AgentConfig>(
    `/api/clients/${pathSegment(clientId)}/agent-profiles/${pathSegment(profileId)}/agent-config/${pathSegment(agent)}`
  );
}

export function updateAgentProfileConfigItem(
  clientId: string,
  profileId: string,
  agent: AgentConfig["agent"],
  sectionId: string,
  itemId: string,
  enabled: boolean
): Promise<AgentConfig> {
  if (profileId.includes("/")) {
    const params = new URLSearchParams({ profile_id: profileId });
    return request<AgentConfig>(
      `/api/clients/${pathSegment(clientId)}/agent-profile-config/${pathSegment(agent)}/${pathSegment(sectionId)}/${pathSegment(itemId)}?${params.toString()}`,
      {
        method: "PATCH",
        body: JSON.stringify({ enabled })
      }
    );
  }
  return request<AgentConfig>(
    `/api/clients/${pathSegment(clientId)}/agent-profiles/${pathSegment(profileId)}/agent-config/${pathSegment(agent)}/${pathSegment(sectionId)}/${pathSegment(itemId)}`,
    {
      method: "PATCH",
      body: JSON.stringify({ enabled })
    }
  );
}

export function updateAgentConfigItem(
  clientId: string,
  windowId: string,
  sectionId: string,
  itemId: string,
  enabled: boolean
): Promise<AgentConfig> {
  return request<AgentConfig>(
    `/api/clients/${pathSegment(clientId)}/windows/${pathSegment(windowId)}/agent-config/${pathSegment(sectionId)}/${pathSegment(itemId)}`,
    {
      method: "PATCH",
      body: JSON.stringify({ enabled })
    }
  );
}

export function updateAgentConfigModel(
  clientId: string,
  windowId: string,
  input: AgentConfigModelUpdate
): Promise<AgentConfig> {
  return request<AgentConfig>(
    `/api/clients/${pathSegment(clientId)}/windows/${pathSegment(windowId)}/agent-config/model`,
    {
      method: "PATCH",
      body: JSON.stringify(input)
    }
  );
}

export function fetchSystemAgentConfig(): Promise<AgentConfig> {
  return request<AgentConfig>("/api/system-agent-config");
}

export function fetchSystemModelPresets(): Promise<SystemModelPresetList> {
  return request<SystemModelPresetList>("/api/system-agent-config/model-presets");
}

export function exportSystemModelPreset(presetId: string): Promise<SystemModelPresetExportBundle> {
  return request<SystemModelPresetExportBundle>(
    `/api/system-agent-config/model-presets/${pathSegment(presetId)}/export`
  );
}

export function importSystemModelPreset(payload: unknown): Promise<SystemModelPresetList> {
  return request<SystemModelPresetList>("/api/system-agent-config/model-presets/import", {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

export function upsertSystemModelPreset(
  presetId: string,
  input: SystemModelPresetInput
): Promise<SystemModelPresetList> {
  return request<SystemModelPresetList>(
    `/api/system-agent-config/model-presets/${pathSegment(presetId)}`,
    {
      method: "PUT",
      body: JSON.stringify({
        name: input.name,
        providers: input.providers,
        base_url: input.base_url,
        api_key: input.api_key ?? "",
        models: input.models,
        model_configs: input.model_configs ?? []
      })
    }
  );
}

export function deleteSystemModelPreset(presetId: string): Promise<SystemModelPresetList> {
  return request<SystemModelPresetList>(
    `/api/system-agent-config/model-presets/${pathSegment(presetId)}`,
    { method: "DELETE" }
  );
}

export function fetchSystemSkillDetail(skillId: string): Promise<SystemSkillDetail> {
  return request<SystemSkillDetail>(`/api/system-agent-config/skills/${pathSegment(skillId)}/detail`);
}

export function updateSystemSkillFile(
  skillId: string,
  path: string,
  content: string
): Promise<SystemSkillDetail> {
  return request<SystemSkillDetail>(`/api/system-agent-config/skills/${pathSegment(skillId)}/files`, {
    method: "PATCH",
    body: JSON.stringify({ path, content })
  });
}

export function fetchSystemMcpDetail(serverId: string): Promise<SystemMcpDetail> {
  return request<SystemMcpDetail>(`/api/system-agent-config/mcp/${pathSegment(serverId)}/detail`);
}

export function updateSystemAgentConfigItem(
  sectionId: string,
  itemId: string,
  enabled: boolean
): Promise<AgentConfig> {
  return request<AgentConfig>(
    `/api/system-agent-config/${pathSegment(sectionId)}/${pathSegment(itemId)}`,
    {
      method: "PATCH",
      body: JSON.stringify({ enabled })
    }
  );
}

export function deleteSystemAgentConfigItem(sectionId: string, itemId: string): Promise<AgentConfig> {
  return request<AgentConfig>(
    `/api/system-agent-config/${pathSegment(sectionId)}/${pathSegment(itemId)}`,
    { method: "DELETE" }
  );
}

export function resetSystemAgentConfigItem(sectionId: string, itemId: string): Promise<AgentConfig> {
  return request<AgentConfig>(
    `/api/system-agent-config/${pathSegment(sectionId)}/${pathSegment(itemId)}/reset`,
    { method: "POST" }
  );
}

export function upsertSystemMcpServer(input: SystemMcpServerInput): Promise<AgentConfig> {
  return request<AgentConfig>("/api/system-agent-config/mcp", {
    method: "PUT",
    body: JSON.stringify({
      id: input.id,
      server: input.server,
      enabled: input.enabled ?? true
    })
  });
}

export async function uploadSystemSkill(skillId: string, archive: Blob, enabled = true): Promise<AgentConfig> {
  const url = new URL(apiUrl(`/api/system-agent-config/skills/${pathSegment(skillId)}`));
  url.searchParams.set("enabled", enabled ? "true" : "false");
  const response = await fetchApi(url.toString(), {
    method: "PUT",
    headers: authHeaders(),
    body: archive
  });
  if (!response.ok) {
    await throwApiError(response);
  }
  return response.json() as Promise<AgentConfig>;
}

export async function downloadSystemSkill(skillId: string): Promise<Blob> {
  const response = await fetchApi(apiUrl(`/api/system-agent-config/skills/${pathSegment(skillId)}/download`), {
    headers: authHeaders()
  });
  if (!response.ok) {
    await throwApiError(response);
  }
  return response.blob();
}
