from typing import Annotated, Literal

from pydantic import BaseModel, Field, StringConstraints, model_validator

AgentKindIn = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=64)]
SystemModelProviderIn = Literal["openai_compatible", "anthropic_compatible"]
CodexReasoningEffort = Literal["minimal", "low", "medium", "high", "xhigh"]
ClaudeReasoningEffort = Literal["low", "medium", "high", "xhigh", "max", "auto"]


class AgentConfigItemOut(BaseModel):
    id: str
    name: str
    enabled: bool
    path: str | None = None
    origin: Literal["client", "system_builtin", "system_config"] = "client"
    overridden: bool = False


class AgentConfigSectionOut(BaseModel):
    id: Literal["skills", "plugins", "hooks", "mcp"]
    name: str
    items: list[AgentConfigItemOut] = Field(default_factory=list)


class AgentConfigModelOut(BaseModel):
    editable: bool = False
    provider: str | None = None
    preset_id: str | None = None
    preset_name: str | None = None
    model: str | None = None
    available_models: list[str] = Field(default_factory=list)
    codex_model_reasoning_effort: CodexReasoningEffort | None = None
    codex_plan_mode_reasoning_effort: CodexReasoningEffort | None = None
    claude_reasoning_effort: ClaudeReasoningEffort | None = None
    codex_reasoning_efforts: list[str] = Field(default_factory=list)
    claude_reasoning_efforts: list[str] = Field(default_factory=list)


class AgentConfigModelUpdateIn(BaseModel):
    model: str | None = None
    codex_model_reasoning_effort: CodexReasoningEffort | None = None
    codex_plan_mode_reasoning_effort: CodexReasoningEffort | None = None
    claude_reasoning_effort: ClaudeReasoningEffort | None = None
    clear_codex_model_reasoning_effort: bool = False
    clear_codex_plan_mode_reasoning_effort: bool = False
    clear_claude_reasoning_effort: bool = False


class AgentConfigOut(BaseModel):
    agent: AgentKindIn
    sections: list[AgentConfigSectionOut] = Field(default_factory=list)
    model: AgentConfigModelOut | None = None


class AgentConfigToggleIn(BaseModel):
    enabled: bool


class SystemMcpServerUpsertIn(BaseModel):
    id: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=128)]
    server: dict = Field(default_factory=dict)
    enabled: bool = True


class SystemModelConfigIn(BaseModel):
    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255)]
    max_output_tokens: int | None = Field(default=None, ge=1)
    context_window: int | None = Field(default=None, ge=1)
    auto_compact_token_limit: int | None = Field(default=None, ge=1)
    codex_model_reasoning_effort: CodexReasoningEffort | None = None
    codex_plan_mode_reasoning_effort: CodexReasoningEffort | None = None
    claude_reasoning_effort: ClaudeReasoningEffort | None = None


class SystemModelConfigOut(SystemModelConfigIn):
    pass


class SystemModelPresetOut(BaseModel):
    id: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=128)]
    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]
    provider: SystemModelProviderIn
    providers: list[SystemModelProviderIn] = Field(default_factory=list, min_length=1, max_length=2)
    base_url: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2048)]
    api_key: str = ""
    models: list[Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255)]] = Field(
        default_factory=list,
        max_length=100,
    )
    model_configs: list[SystemModelConfigOut] = Field(default_factory=list, max_length=100)


class SystemModelPresetListOut(BaseModel):
    presets: list[SystemModelPresetOut] = Field(default_factory=list)


class SystemModelPresetUpsertIn(BaseModel):
    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]
    provider: SystemModelProviderIn | None = None
    providers: list[SystemModelProviderIn] = Field(default_factory=list, max_length=2)
    base_url: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2048)]
    api_key: str = ""
    models: list[Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255)]] = Field(
        default_factory=list,
        max_length=100,
    )
    model_configs: list[SystemModelConfigIn] = Field(default_factory=list, max_length=100)

    @model_validator(mode="after")
    def validate_provider_selection(self) -> "SystemModelPresetUpsertIn":
        if self.provider is None and not self.providers:
            raise ValueError("at least one model provider is required")
        if not self.models and not self.model_configs:
            raise ValueError("at least one model is required")
        return self


class SystemSkillEntryOut(BaseModel):
    path: str
    kind: Literal["directory", "file"]
    size: int | None = None


class SystemSkillFileOut(BaseModel):
    path: str
    content: str | None = None
    size: int
    editable: bool


class SystemSkillDetailOut(BaseModel):
    id: str
    name: str
    enabled: bool
    path: str | None = None
    origin: Literal["system_builtin", "system_config"]
    editable: bool
    overridden: bool = False
    entries: list[SystemSkillEntryOut] = Field(default_factory=list)
    files: list[SystemSkillFileOut] = Field(default_factory=list)


class SystemSkillFileUpdateIn(BaseModel):
    path: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=512)]
    content: Annotated[str, StringConstraints(max_length=1048576)]


class SystemMcpToolOut(BaseModel):
    name: str
    description: str | None = None
    input_schema: dict = Field(default_factory=dict)


class SystemMcpDetailOut(BaseModel):
    id: str
    name: str
    enabled: bool
    path: str | None = None
    origin: Literal["system_builtin", "system_config"]
    editable: bool
    overridden: bool = False
    server: dict = Field(default_factory=dict)
    tools: list[SystemMcpToolOut] = Field(default_factory=list)


class AgentClientOut(BaseModel):
    id: str
    provider_id: str
    label: str
    aliases: list[str] = Field(default_factory=list)
    default_command: str
    command_names: list[str] = Field(default_factory=list)
    capabilities: dict[str, bool] = Field(default_factory=dict)


class AgentClientListOut(BaseModel):
    agent_clients: list[AgentClientOut] = Field(default_factory=list)


class CursorOfficialModelOut(BaseModel):
    id: str
    label: str


class CursorOfficialModelListOut(BaseModel):
    models: list[CursorOfficialModelOut] = Field(default_factory=list)


class AgentProfileOut(BaseModel):
    id: str
    name: str
    description: str | None = None
    default_agent_client: AgentKindIn
    agent_md: str = ""
    created_at: str
    updated_at: str


class AgentProfileListOut(BaseModel):
    profiles: list[AgentProfileOut] = Field(default_factory=list)


class AgentProfileCreateIn(BaseModel):
    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]
    description: Annotated[str, StringConstraints(max_length=500)] | None = None
    default_agent_client: AgentKindIn = "codex"
    source_agent_client: AgentKindIn | None = None


class AgentProfileUpdateIn(BaseModel):
    name: Annotated[
        str,
        StringConstraints(strip_whitespace=True, min_length=1, max_length=120),
    ] | None = None
    description: Annotated[str, StringConstraints(max_length=500)] | None = None
    default_agent_client: AgentKindIn | None = None
    agent_md: Annotated[str, StringConstraints(max_length=65536)] | None = None
