from __future__ import annotations

from app.contexts.agent_profiles.api.schemas import AgentConfigOut
from app.contexts.agent_profiles.application import config_selection as agent_config_service


def agent_config_out(payload: object, *, model: object = None) -> AgentConfigOut:
    if isinstance(payload, agent_config_service.AgentConfig):
        payload = {
            "agent": payload.agent,
            "sections": [
                {
                    "id": section.id,
                    "name": section.name,
                    "items": [
                        {
                            "id": item.id,
                            "name": item.name,
                            "enabled": item.enabled,
                            "path": item.path,
                            "origin": item.origin,
                            "overridden": item.overridden,
                        }
                        for item in section.items
                    ],
                }
                for section in payload.sections
            ],
        }
    if model is not None and isinstance(payload, dict):
        payload = {**payload, "model": model}
    return AgentConfigOut.model_validate(payload)
