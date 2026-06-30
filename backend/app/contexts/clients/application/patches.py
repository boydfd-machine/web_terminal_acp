from __future__ import annotations

from app.contexts.clients.domain import ClientPatch


def client_patch_from_payload(payload: object) -> ClientPatch:
    fields = getattr(payload, "model_fields_set", set())
    return ClientPatch(name=getattr(payload, "name") if "name" in fields else None)
