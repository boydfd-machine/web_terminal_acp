export type AgentSession = {
  id: string;
  provider: "claude" | "codex" | string;
  source_id: string;
  source_path: string | null;
  project_path: string | null;
  virtual_window_id: string | null;
  title: string | null;
  tags: string[] | null;
  summary: string | null;
  created_at: string;
  updated_at: string;
};

export type AgentMessageType = "agent" | "subagent_call" | "subagent_result";

export type AgentEventProjection = {
  tone: string;
  label: string;
  body: string;
  body_format: "markdown" | "json";
  subtype: string | null;
  agent_message_type: AgentMessageType | null;
  subagent_id: string | null;
  subagent_tool_use_id: string | null;
  target_session_id: string | null;
  target_session_source_id: string | null;
};

export type AgentRecordEvent = {
  id: string;
  ai_session_id: string | null;
  source_type: string;
  source_id: string;
  kind: string;
  payload_json: Record<string, unknown>;
  projection: AgentEventProjection | null;
  created_at: string;
};

export type AgentRecord = {
  window_id: string;
  sessions: AgentSession[];
  events: AgentRecordEvent[];
  events_total: number;
  events_limit: number;
  events_offset: number;
  events_has_more: boolean;
};

export type AgentChatMessage = {
  id: string;
  ai_session_id: string | null;
  source_type: string;
  source_id: string;
  role: "user" | "agent";
  body: string;
  body_format: "markdown" | "json";
  agent_message_type: AgentMessageType | null;
  subagent_id: string | null;
  subagent_tool_use_id: string | null;
  target_session_id: string | null;
  target_session_source_id: string | null;
  created_at: string;
};

export type AgentChatRoleFilter = "all" | "user" | "agent" | "subagent_call" | "subagent_result";

export type AgentRecordDisplayMode = "chat" | "detail";

export type AgentChatRecord = {
  window_id: string;
  messages: AgentChatMessage[];
  messages_total: number;
  messages_total_exact?: boolean;
  messages_limit: number;
  messages_offset: number;
  messages_has_more: boolean;
};

export type SearchMatch = {
  field: string;
  start: number;
  end: number;
};

export type AgentRecordSearchResult = {
  message: AgentChatMessage;
  window_id: string;
  session_id: string | null;
  provider: string | null;
  matches: SearchMatch[];
};

export type AgentRecordSearchResponse = {
  query: string;
  results: AgentRecordSearchResult[];
  total: number;
  limit: number;
  offset: number;
  has_more: boolean;
  scope: "window" | "global";
};

export type AgentConfigItem = {
  id: string;
  name: string;
  enabled: boolean;
  path: string | null;
  origin?: "client" | "system_builtin" | "system_config";
  overridden?: boolean;
};

export type AgentConfigModel = {
  editable: boolean;
  provider?: string | null;
  preset_id?: string | null;
  preset_name?: string | null;
  model?: string | null;
  available_models: string[];
  codex_model_reasoning_effort?: CodexReasoningEffort | null;
  codex_plan_mode_reasoning_effort?: CodexReasoningEffort | null;
  claude_reasoning_effort?: ClaudeReasoningEffort | null;
  codex_reasoning_efforts: string[];
  claude_reasoning_efforts: string[];
};

export type AgentConfigSection = {
  id: "skills" | "plugins" | "hooks" | "mcp";
  name: string;
  items: AgentConfigItem[];
};

export type AgentConfig = {
  agent: string;
  sections: AgentConfigSection[];
  model?: AgentConfigModel | null;
};

export type AgentConfigModelUpdate = {
  model?: string | null;
  codex_model_reasoning_effort?: CodexReasoningEffort | null;
  codex_plan_mode_reasoning_effort?: CodexReasoningEffort | null;
  claude_reasoning_effort?: ClaudeReasoningEffort | null;
  clear_codex_model_reasoning_effort?: boolean;
  clear_codex_plan_mode_reasoning_effort?: boolean;
  clear_claude_reasoning_effort?: boolean;
};

export type SystemMcpServerInput = {
  id: string;
  server: Record<string, unknown>;
  enabled?: boolean;
};

export type SystemModelProvider = "openai_compatible" | "anthropic_compatible";

export type CodexReasoningEffort = "minimal" | "low" | "medium" | "high" | "xhigh";
export type ClaudeReasoningEffort = "low" | "medium" | "high" | "xhigh" | "max" | "auto";

export type SystemModelConfig = {
  name: string;
  max_output_tokens?: number | null;
  context_window?: number | null;
  auto_compact_token_limit?: number | null;
  codex_model_reasoning_effort?: CodexReasoningEffort | null;
  codex_plan_mode_reasoning_effort?: CodexReasoningEffort | null;
  claude_reasoning_effort?: ClaudeReasoningEffort | null;
};

export type SystemModelPreset = {
  id: string;
  name: string;
  provider: SystemModelProvider;
  providers: SystemModelProvider[];
  base_url: string;
  api_key: string;
  models: string[];
  model_configs?: SystemModelConfig[];
};

export type SystemModelPresetList = {
  presets: SystemModelPreset[];
};

export type SystemModelPresetInput = {
  name: string;
  provider?: SystemModelProvider;
  providers: SystemModelProvider[];
  base_url: string;
  api_key?: string;
  models: string[];
  model_configs?: SystemModelConfig[];
};

export type SystemModelPresetExportBundle = {
  kind: "web-terminal-model-preset";
  version: number;
  preset: SystemModelPreset;
};

export type SystemSkillEntry = {
  path: string;
  kind: "directory" | "file";
  size: number | null;
};

export type SystemSkillFile = {
  path: string;
  content: string | null;
  size: number;
  editable: boolean;
};

export type SystemSkillDetail = {
  id: string;
  name: string;
  enabled: boolean;
  path: string | null;
  origin: "system_builtin" | "system_config";
  editable: boolean;
  overridden: boolean;
  entries: SystemSkillEntry[];
  files: SystemSkillFile[];
};

export type SystemMcpTool = {
  name: string;
  description: string | null;
  input_schema: Record<string, unknown>;
};

export type SystemMcpDetail = {
  id: string;
  name: string;
  enabled: boolean;
  path: string | null;
  origin: "system_builtin" | "system_config";
  editable: boolean;
  overridden: boolean;
  server: Record<string, unknown>;
  tools: SystemMcpTool[];
};

export type AgentLaunchKind = AgentConfig["agent"];

export type AgentClient = {
  id: string;
  provider_id: string;
  label: string;
  aliases: string[];
  default_command: string;
  command_names: string[];
  capabilities?: {
    launch?: boolean;
    client_config?: boolean;
    window_config?: boolean;
    profile_config?: boolean;
    agent_records?: boolean;
    runtime_tags?: boolean;
    work_presence?: boolean;
  };
};

export type AgentClientList = {
  agent_clients: AgentClient[];
};

export type AgentProfile = {
  id: string;
  name: string;
  description: string | null;
  default_agent_client: AgentLaunchKind;
  agent_md: string;
  created_at: string;
  updated_at: string;
};

export type AgentProfileList = {
  profiles: AgentProfile[];
};

export type AgentProfileExportBundle = {
  kind: "web-terminal-agent-profile";
  version: number;
  origin?: string;
  profile: AgentProfile;
  files: Record<string, unknown>;
};

export type AgentConfigSelectionItem = {
  id: string;
  enabled: boolean;
};

export type AgentConfigSelectionSection = {
  id: AgentConfigSection["id"];
  items: AgentConfigSelectionItem[];
};

export type AgentConfigSelection = {
  agent: AgentLaunchKind;
  sections: AgentConfigSelectionSection[];
};

export type ClaudeModelRouting = {
  mode: "all" | "split";
  model?: string | null;
  opus_model?: string | null;
  sonnet_model?: string | null;
  haiku_model?: string | null;
};

export type AgentModelSelection = {
  preset_id: string;
  model?: string | null;
  claude?: ClaudeModelRouting | null;
  codex_model_reasoning_effort?: CodexReasoningEffort | null;
  codex_plan_mode_reasoning_effort?: CodexReasoningEffort | null;
  claude_reasoning_effort?: ClaudeReasoningEffort | null;
};

export type AgentLaunchConfig = {
  agent: AgentLaunchKind;
  command?: string | null;
  config?: AgentConfigSelection | null;
  model_selection?: AgentModelSelection | null;
  template_id?: string | null;
  profile_id?: string | null;
};
