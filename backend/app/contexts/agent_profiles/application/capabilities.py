from __future__ import annotations

from typing import Literal

from app.platform.plugins.agent_plugins import get_agent_plugin_registry

AgentClientCapability = Literal["launch", "client_config", "window_config", "profile_config"]

_PROVIDER_ALIASES = {"claude": "claude_code", "cursor": "cursor_cli", "agent": "cursor_cli"}


class AgentClientCapabilityError(Exception):
    def __init__(self, status_code: int, detail: str) -> None:
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


def canonical_provider(provider: str) -> str:
    return get_agent_plugin_registry().canonical_provider(_PROVIDER_ALIASES.get(provider, provider))


def require_local_agent_capability(agent: str, capability: AgentClientCapability) -> str:
    try:
        plugin = get_agent_plugin_registry().by_agent_id(agent)
    except ValueError as exc:
        raise AgentClientCapabilityError(400, str(exc)) from exc
    if not getattr(plugin.capabilities, capability):
        raise AgentClientCapabilityError(400, f"agent client does not support {capability}")
    return plugin.agent_client_id


def require_supported_agent_capability(
    provider: str | None,
    capability: AgentClientCapability,
) -> str:
    if provider is not None:
        try:
            plugin = get_agent_plugin_registry().by_provider(provider)
        except ValueError:
            pass
        else:
            if getattr(plugin.capabilities, capability):
                return plugin.agent_client_id
            raise AgentClientCapabilityError(400, f"agent client does not support {capability}")
    raise AgentClientCapabilityError(404, "agent config unavailable for this terminal")


def require_supported_provider(provider: str | None) -> str:
    if provider is not None:
        try:
            return get_agent_plugin_registry().by_provider(provider).provider_id
        except ValueError:
            pass
    raise AgentClientCapabilityError(404, "agent config unavailable for this terminal")
