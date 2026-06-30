from __future__ import annotations

from app.contexts.clients.api.schemas import ClientOut
from app.models import Client


def client_out(client: Client) -> ClientOut:
    return ClientOut(
        id=client.id,
        name=client.name,
        status=client.status.value,
        hostname=client.hostname,
        install_path=client.install_path,
        version=client.version,
        last_update_at=client.last_update_at,
        runtime=client.runtime.value,
        last_seen_at=client.last_seen_at,
        connected_at=client.connected_at,
        created_at=client.created_at,
        updated_at=client.updated_at,
    )
