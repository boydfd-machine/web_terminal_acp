from __future__ import annotations

from dataclasses import dataclass

UNSET = object()


@dataclass(frozen=True)
class AgentProfileUpdate:
    name: str | None = None
    description: str | None | object = UNSET
    default_agent_client: str | None = None
    agent_md: str | None | object = UNSET

    @classmethod
    def from_payload(cls, payload: object) -> "AgentProfileUpdate":
        fields = getattr(payload, "model_fields_set", set())
        return cls(
            name=getattr(payload, "name") if "name" in fields else None,
            description=getattr(payload, "description") if "description" in fields else UNSET,
            default_agent_client=(
                getattr(payload, "default_agent_client")
                if "default_agent_client" in fields
                else None
            ),
            agent_md=getattr(payload, "agent_md") if "agent_md" in fields else UNSET,
        )

    def remote_patch(self) -> dict[str, object]:
        patch: dict[str, object] = {}
        if self.name is not None:
            patch["name"] = self.name
        if self.description is not UNSET and self.description is not None:
            patch["description"] = self.description
        if self.default_agent_client is not None:
            patch["default_agent_client"] = self.default_agent_client
        if self.agent_md is not UNSET and self.agent_md is not None:
            patch["agent_md"] = self.agent_md
        return patch
