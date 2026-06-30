from __future__ import annotations

import posixpath
import re
import shlex
from dataclasses import dataclass
from enum import Enum
from typing import Literal

AgentClientCapability = Literal["launch", "client_config", "window_config", "profile_config"]

_CAPABILITY_DEFAULTS: dict[AgentClientCapability, bool] = {
    "launch": True,
    "client_config": True,
    "window_config": True,
    "profile_config": True,
}
_PROVIDER_ALIASES = {"claude": "claude_code", "cursor": "cursor_cli", "agent": "cursor_cli"}
_COMMAND_SEGMENT_PATTERN = re.compile(r"&&|\|\||[;|]")
_ENV_ASSIGNMENT_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=.*$")
_COMMAND_WRAPPERS = {"command", "env", "sudo"}


class RemoteAgentResolutionError(Enum):
    agent_required = "agent_required"
    config_unavailable = "config_unavailable"
    capability_unsupported = "capability_unsupported"


@dataclass(frozen=True)
class RemoteAgentResolution:
    agent_id: str | None = None
    error: RemoteAgentResolutionError | None = None

    @property
    def ok(self) -> bool:
        return self.error is None and self.agent_id is not None


@dataclass(frozen=True)
class RemoteAgentDescriptor:
    payload: dict[str, object]

    @property
    def agent_id(self) -> str | None:
        value = self.payload.get("id")
        return value.strip() if isinstance(value, str) and value.strip() else None

    @property
    def aliases(self) -> tuple[str, ...]:
        candidates: list[str] = []
        for key in ("id", "provider_id", "default_command"):
            value = self.payload.get(key)
            if isinstance(value, str) and value.strip():
                candidates.append(value.strip())
        for key in ("aliases", "command_names"):
            values = self.payload.get(key)
            if isinstance(values, list):
                candidates.extend(
                    value.strip() for value in values if isinstance(value, str) and value.strip()
                )
        return tuple(candidates)

    def supports(self, capability: AgentClientCapability) -> bool:
        capabilities = self.payload.get("capabilities")
        if not isinstance(capabilities, dict):
            return _CAPABILITY_DEFAULTS[capability]
        value = capabilities.get(capability)
        return value if isinstance(value, bool) else _CAPABILITY_DEFAULTS[capability]


@dataclass(frozen=True)
class RemoteAgentCatalog:
    descriptors: tuple[RemoteAgentDescriptor, ...]

    @classmethod
    def from_payload(cls, payload: dict[str, object]) -> "RemoteAgentCatalog":
        agents = payload.get("agent_clients")
        if not isinstance(agents, list):
            agents = []
        return cls(
            tuple(
                RemoteAgentDescriptor(descriptor)
                for descriptor in agents
                if isinstance(descriptor, dict)
            )
        )

    def resolve_agent_id(
        self,
        agent: str,
        capability: AgentClientCapability,
        *,
        local_provider_id: str | None = None,
    ) -> RemoteAgentResolution:
        clean_agent = agent.strip()
        if not clean_agent:
            return RemoteAgentResolution(error=RemoteAgentResolutionError.agent_required)
        descriptor = self._descriptor_for_agent(clean_agent)
        if descriptor is None and local_provider_id is not None:
            descriptor = self._descriptor_for_agent(local_provider_id)
        if descriptor is None:
            return RemoteAgentResolution(error=RemoteAgentResolutionError.config_unavailable)
        if not descriptor.supports(capability):
            return RemoteAgentResolution(error=RemoteAgentResolutionError.capability_unsupported)
        if local_provider_id is not None and self._descriptor_for_agent(local_provider_id) is descriptor:
            return RemoteAgentResolution(agent_id=local_provider_id)
        agent_id = descriptor.agent_id
        if agent_id is None:
            return RemoteAgentResolution(error=RemoteAgentResolutionError.config_unavailable)
        return RemoteAgentResolution(agent_id=agent_id)

    def agent_from_command(self, command: str | None) -> str | None:
        if not command:
            return None
        command_agents = self._command_agent_map()
        for segment in _COMMAND_SEGMENT_PATTERN.split(command):
            tokens = _command_tokens(segment)
            while tokens:
                token = tokens.pop(0)
                if _ENV_ASSIGNMENT_PATTERN.match(token) or token in _COMMAND_WRAPPERS:
                    continue
                agent = command_agents.get(posixpath.basename(token).lower())
                if agent is not None:
                    return agent
                break
        return None

    def _descriptor_for_agent(self, agent: str) -> RemoteAgentDescriptor | None:
        clean_agent = agent.strip().lower()
        if not clean_agent:
            return None
        for descriptor in self.descriptors:
            if any(candidate.lower() == clean_agent for candidate in descriptor.aliases):
                return descriptor
        return None

    def _command_agent_map(self) -> dict[str, str]:
        result: dict[str, str] = {}
        for descriptor in self.descriptors:
            agent_id = descriptor.agent_id
            if agent_id is None:
                continue
            for candidate in descriptor.aliases:
                result[posixpath.basename(candidate).lower()] = agent_id
        return result

def local_provider_alias(agent: str) -> str:
    return _PROVIDER_ALIASES.get(agent, agent)


def _command_tokens(segment: str) -> list[str]:
    try:
        return shlex.split(segment.strip())
    except ValueError:
        return segment.strip().split()
