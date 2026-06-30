from typing import Annotated, Literal

from pydantic import BaseModel, Field, StringConstraints

WindowTitle = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255)]
WindowText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=4096)]
WindowTitleTag = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=64)]
WindowStatusIn = Literal["ACTIVE", "ARCHIVED", "ERROR", "DISCONNECTED"]
AgentKindIn = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=64)]
AgentConfigSectionKindIn = Literal["skills", "plugins", "hooks", "mcp"]
ClientName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255)]
ClientStatusOut = Literal["ONLINE", "OFFLINE", "ERROR"]
ClientRuntimeOut = Literal["local", "remote"]
BootstrapHost = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255)]
BootstrapUsername = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255)]
BootstrapPrivateKey = Annotated[str, StringConstraints(min_length=1)]
BootstrapServerUrl = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2048)]
LoginSecret = Annotated[str, StringConstraints(min_length=1, max_length=4096)]
RefreshToken = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=8192)]
CaptchaId = Annotated[str, StringConstraints(strip_whitespace=True, min_length=16, max_length=256)]
CaptchaAnswer = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=32)]
RegistrationKey = Annotated[str, StringConstraints(strip_whitespace=True, min_length=16, max_length=512)]


class AgentConfigSelectionItemIn(BaseModel):
    id: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=512)]
    enabled: bool


class AgentConfigSelectionSectionIn(BaseModel):
    id: AgentConfigSectionKindIn
    items: list[AgentConfigSelectionItemIn] = Field(default_factory=list, max_length=500)


class AgentConfigSelectionIn(BaseModel):
    agent: AgentKindIn
    sections: list[AgentConfigSelectionSectionIn] = Field(default_factory=list, max_length=4)


class AgentClaudeModelRoutingIn(BaseModel):
    mode: Literal["all", "split"] = "all"
    model: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255)] | None = None
    opus_model: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255)] | None = None
    sonnet_model: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255)] | None = None
    haiku_model: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255)] | None = None


class AgentModelSelectionIn(BaseModel):
    preset_id: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=128)]
    model: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255)] | None = None
    claude: AgentClaudeModelRoutingIn | None = None
    codex_model_reasoning_effort: Literal["minimal", "low", "medium", "high", "xhigh"] | None = None
    codex_plan_mode_reasoning_effort: Literal["minimal", "low", "medium", "high", "xhigh"] | None = None
    claude_reasoning_effort: Literal["low", "medium", "high", "xhigh", "max", "auto"] | None = None


class AgentLaunchIn(BaseModel):
    agent: AgentKindIn
    command: WindowText | None = None
    config: AgentConfigSelectionIn | None = None
    model_selection: AgentModelSelectionIn | None = None
    template_id: str | None = None
    profile_id: str | None = None
