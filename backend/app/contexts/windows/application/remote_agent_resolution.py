from __future__ import annotations

from app.contexts.windows.application.errors import WindowServiceError
from app.contexts.windows.domain.remote_agents import (
    AgentClientCapability,
    RemoteAgentCatalog,
    RemoteAgentResolutionError,
    local_provider_alias,
)
from app.platform.plugins.agent_plugins import get_agent_plugin_registry


def require_remote_agent_id(
    catalog: RemoteAgentCatalog,
    agent: str,
    capability: AgentClientCapability,
) -> str:
    result = catalog.resolve_agent_id(
        agent,
        capability,
        local_provider_id=_local_provider_id(agent),
    )
    if result.agent_id is not None:
        return result.agent_id
    raise _resolution_error(capability, result.error)


def _local_provider_id(agent: str) -> str | None:
    try:
        canonical = get_agent_plugin_registry().canonical_provider(local_provider_alias(agent))
        return get_agent_plugin_registry().by_provider(canonical).provider_id
    except ValueError:
        return None


def _resolution_error(
    capability: AgentClientCapability,
    error: RemoteAgentResolutionError | None,
) -> WindowServiceError:
    if error is RemoteAgentResolutionError.agent_required:
        return WindowServiceError(400, "agent is required")
    if error is RemoteAgentResolutionError.capability_unsupported:
        return WindowServiceError(400, f"agent client does not support {capability}")
    return WindowServiceError(404, "agent config unavailable for this terminal")
