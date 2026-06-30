import json
from uuid import UUID

import pytest

import app.contexts.clients.api.client_agent as client_agent_api
from app.contexts.terminal_runtime.domain.protocol import AgentMessage


@pytest.mark.asyncio
async def test_terminal_error_message_publishes_status_to_view_id(monkeypatch) -> None:
    client_id = UUID("12345678-1234-5678-1234-567812345678")
    window_id = UUID("87654321-4321-8765-4321-876543218765")
    view_id = UUID("11111111-2222-3333-4444-555555555555")
    statuses: list[tuple[UUID, UUID, dict[str, object]]] = []

    class FakeBroker:
        async def publish_status(self, published_client_id: UUID, target_id: UUID, message: str) -> None:
            statuses.append((published_client_id, target_id, json.loads(message)))

    monkeypatch.setattr(client_agent_api, "_terminal_broker", lambda websocket: FakeBroker())

    await client_agent_api._handle_terminal_error_message(
        object(),
        client_id,
        AgentMessage(
            type="terminal_error",
            client_id=client_id,
            window_id=window_id,
            payload={"message": "resize failed", "view_id": str(view_id)},
        ),
    )

    assert statuses == [
        (
            client_id,
            view_id,
            {"type": "terminal_status", "status": "error", "reason": "runtime_error"},
        )
    ]
