from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.models import ClientRuntime
from app.schemas import AgentProfileCreateIn
from app.services.agent_profiles_api import AgentProfileApiError, AgentProfileApiService
from app.services.runtime.protocol import AgentMessage


class FakeSession:
    async def commit(self) -> None:
        return None


class FakeRegistry:
    def __init__(self, connection) -> None:
        self.connection = connection

    def get(self, _client_id):
        return self.connection


class AgentProfileConnection:
    def __init__(self, agent_capabilities: dict[str, bool] | None = None) -> None:
        self.requests: list[AgentMessage] = []
        self.agent_capabilities = agent_capabilities or {}

    async def request(self, message: AgentMessage, *, timeout: float) -> AgentMessage:
        self.requests.append(message)
        if message.type == "agent_clients_list":
            return AgentMessage(
                type="agent_client_result",
                client_id=message.client_id,
                request_id=message.request_id,
                payload={
                    "agent_clients": [
                        {
                            "id": "remote_codex",
                            "provider_id": "codex",
                            "label": "Remote Codex",
                            "aliases": ["codex"],
                            "default_command": "codex",
                            "command_names": ["codex"],
                            "capabilities": self.agent_capabilities,
                        }
                    ]
                },
            )
        if message.type == "agent_profile_create":
            return AgentMessage(
                type="agent_profile_result",
                client_id=message.client_id,
                request_id=message.request_id,
                payload={
                    "id": "builder",
                    "name": message.payload["name"],
                    "description": None,
                    "default_agent_client": "codex",
                    "agent_md": "",
                    "created_at": "2026-06-04T00:00:00+00:00",
                    "updated_at": "2026-06-04T00:00:00+00:00",
                },
            )
        raise AssertionError(f"unexpected request: {message.type}")


@pytest.mark.asyncio
async def test_remote_create_profile_checks_capabilities_before_create(monkeypatch) -> None:
    client_id = uuid4()
    connection = AgentProfileConnection()

    async def fake_get_client(_session, requested_client_id):
        assert requested_client_id == client_id
        return SimpleNamespace(id=client_id, runtime=ClientRuntime.remote)

    monkeypatch.setattr("app.services.agent_profiles_api.get_client", fake_get_client)
    service = AgentProfileApiService(
        session=FakeSession(),
        registry=FakeRegistry(connection),
    )
    monkeypatch.setattr(
        "app.contexts.agent_profiles.application.api_service.system_config_service.system_agent_config_files_payload",
        AsyncMock(return_value={"version": 1, "files": []}),
    )

    profile = await service.create_profile(
        AgentProfileCreateIn(name="Remote Builder", default_agent_client="codex"),
        client_id=client_id,
    )

    assert profile.id == "builder"
    assert [request.type for request in connection.requests] == [
        "agent_clients_list",
        "agent_profile_create",
    ]
    assert connection.requests[1].payload["name"] == "Remote Builder"
    assert connection.requests[1].payload["system_config_files"] == {"version": 1, "files": []}


@pytest.mark.asyncio
async def test_remote_create_profile_rejects_agent_without_profile_config(
    monkeypatch,
) -> None:
    client_id = uuid4()
    connection = AgentProfileConnection({"launch": True, "profile_config": False})

    async def fake_get_client(_session, _client_id):
        return SimpleNamespace(id=client_id, runtime=ClientRuntime.remote)

    monkeypatch.setattr("app.services.agent_profiles_api.get_client", fake_get_client)
    service = AgentProfileApiService(
        session=FakeSession(),
        registry=FakeRegistry(connection),
    )

    with pytest.raises(AgentProfileApiError) as exc_info:
        await service.create_profile(
            AgentProfileCreateIn(name="Remote Builder", default_agent_client="codex"),
            client_id=client_id,
        )

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail == "agent client does not support profile_config"
    assert [request.type for request in connection.requests] == ["agent_clients_list"]

