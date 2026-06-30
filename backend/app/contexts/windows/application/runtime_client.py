from __future__ import annotations

from app.contexts.windows.domain.runtime_client import RuntimeClient
from app.models import Client


def runtime_client_from_model(client: Client) -> RuntimeClient:
    return RuntimeClient.from_values(client_id=client.id, runtime=client.runtime)
