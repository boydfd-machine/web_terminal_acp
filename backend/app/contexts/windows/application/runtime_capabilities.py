from __future__ import annotations

from app.contexts.windows.domain.remote_agents import AgentClientCapability, RemoteAgentCatalog
from app.contexts.windows.api.schemas import WindowCreateIn
from app.contexts.terminal_runtime.application.runtime_provider import RemoteRuntime
from app.contexts.windows.application.launch_plans import launch_agent_profile_id
from app.contexts.windows.application.remote_agent_resolution import require_remote_agent_id


async def require_remote_agent_capability(
    remote_runtime: RemoteRuntime,
    agent: str,
    capability: AgentClientCapability,
) -> str:
    return require_remote_agent_id(
        RemoteAgentCatalog.from_payload(await remote_runtime.list_agent_clients()),
        agent,
        capability,
    )


async def require_remote_launch_capabilities(
    payload: WindowCreateIn,
    remote_runtime: RemoteRuntime,
) -> None:
    launch = payload.agent_launch
    if launch is None:
        return
    catalog = RemoteAgentCatalog.from_payload(await remote_runtime.list_agent_clients())
    require_remote_agent_id(catalog, launch.agent, "launch")
    if launch.config is not None:
        require_remote_agent_id(catalog, launch.config.agent, "client_config")
    if launch_agent_profile_id(payload) is not None:
        require_remote_agent_id(catalog, launch.agent, "profile_config")
