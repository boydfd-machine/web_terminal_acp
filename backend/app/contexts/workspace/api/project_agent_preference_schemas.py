from typing import Annotated, Any

from pydantic import BaseModel, StringConstraints

from app.platform.common_schemas import AgentModelSelectionIn

ProjectPreferenceAgentClient = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=64)]
ProjectPreferenceAgentCommand = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=4096)]
ProjectPreferenceAgentProfile = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=128)]


class ProjectAgentPreferenceIn(BaseModel):
    agent_profile_id: ProjectPreferenceAgentProfile | None = None
    agent_client: ProjectPreferenceAgentClient | None = None
    agent_command: ProjectPreferenceAgentCommand | None = None
    agent_model_selection: AgentModelSelectionIn | None = None


class ProjectAgentPreferenceOut(BaseModel):
    agent_profile_id: str | None = None
    agent_client: str | None = None
    agent_command: str | None = None
    agent_model_selection: dict[str, Any] | None = None
