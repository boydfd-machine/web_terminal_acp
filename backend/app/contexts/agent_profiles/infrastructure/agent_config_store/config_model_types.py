from dataclasses import dataclass

SYSTEM_MODEL_PRESETS_FILE = "model-presets.json"
SYSTEM_MODEL_PRESETS_SETTING_KEY = "system_model_presets"
SYSTEM_MODEL_ENV_FILE = "model-env.sh"
MODEL_PROVIDER_TYPES = {"openai_compatible", "anthropic_compatible"}
CLAUDE_MODEL_TIERS = ("opus", "sonnet", "haiku")
CODEX_REASONING_EFFORTS = ("minimal", "low", "medium", "high", "xhigh")
CLAUDE_REASONING_EFFORTS = ("low", "medium", "high", "xhigh", "max", "auto")


@dataclass(frozen=True)
class SystemModelConfig:
    name: str
    max_output_tokens: int | None = None
    context_window: int | None = None
    auto_compact_token_limit: int | None = None
    codex_model_reasoning_effort: str | None = None
    codex_plan_mode_reasoning_effort: str | None = None
    claude_reasoning_effort: str | None = None


@dataclass(frozen=True)
class SystemModelPreset:
    id: str
    name: str
    provider: str
    base_url: str
    api_key: str
    models: list[str]
    providers: list[str] | None = None
    model_configs: list[SystemModelConfig] | None = None

    def __post_init__(self) -> None:
        providers = self.providers or [self.provider]
        object.__setattr__(self, "providers", list(providers))
        configs = self.model_configs or [SystemModelConfig(name=model) for model in self.models]
        object.__setattr__(self, "model_configs", list(configs))


@dataclass(frozen=True)
class SystemModelPresetList:
    presets: list[SystemModelPreset]


@dataclass(frozen=True)
class ClaudeModelRouting:
    mode: str = "all"
    model: str | None = None
    opus_model: str | None = None
    sonnet_model: str | None = None
    haiku_model: str | None = None


@dataclass(frozen=True)
class AgentModelSelection:
    preset_id: str
    model: str | None = None
    claude: ClaudeModelRouting | None = None
    codex_model_reasoning_effort: str | None = None
    codex_plan_mode_reasoning_effort: str | None = None
    claude_reasoning_effort: str | None = None


@dataclass(frozen=True)
class ResolvedAgentModelSettings:
    preset_id: str
    provider: str
    base_url: str
    api_key: str
    model: str
    max_output_tokens: int | None = None
    context_window: int | None = None
    auto_compact_token_limit: int | None = None
    claude: ClaudeModelRouting | None = None
    codex_model_reasoning_effort: str | None = None
    codex_plan_mode_reasoning_effort: str | None = None
    claude_reasoning_effort: str | None = None


__all__ = [name for name in globals() if not name.startswith("__")]
