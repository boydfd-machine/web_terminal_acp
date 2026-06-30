from uuid import uuid4

import pytest

from app.schemas import BootstrapClientIn
from app.services.bootstrap.installer import BootstrapDependencyError, BootstrapResult
from app.services.clients.api_service import ClientApiService
from app.services.clients.errors import ClientApiError


class FakeSession:
    def __init__(self) -> None:
        self.committed = False

    async def commit(self) -> None:
        self.committed = True


@pytest.mark.asyncio
async def test_bootstrap_service_maps_dependency_error_and_redacts_secret():
    async def failing_runner(_session, _payload):
        raise BootstrapDependencyError(
            "missing tmux PRIVATE-KEY ssh-passphrase plain-client-token"
        )

    payload = BootstrapClientIn(
        name="Remote Dev",
        host="dev.example.com",
        port=22,
        username="alice",
        private_key="PRIVATE-KEY",
        passphrase="ssh-passphrase",
        server_url="https://control.example.com",
    )
    session = FakeSession()
    service = ClientApiService(session)

    with pytest.raises(ClientApiError) as exc_info:
        await service.bootstrap_remote_client(payload, runner=failing_runner)

    assert exc_info.value.status_code == 400
    assert "missing tmux" in exc_info.value.detail
    assert "PRIVATE-KEY" not in exc_info.value.detail
    assert "ssh-passphrase" not in exc_info.value.detail
    assert "plain-client-token" not in exc_info.value.detail
    assert session.committed is False


@pytest.mark.asyncio
async def test_bootstrap_service_commits_then_returns_runner_result():
    client_id = uuid4()

    async def runner(_session, payload):
        return BootstrapResult(
            client_id=client_id,
            name=payload.name,
            status="OFFLINE",
            reused=False,
        )

    payload = BootstrapClientIn(
        name="Remote Dev",
        host="dev.example.com",
        port=22,
        username="alice",
        private_key="PRIVATE-KEY",
        passphrase=None,
        server_url="https://control.example.com",
    )
    session = FakeSession()
    service = ClientApiService(session)

    result = await service.bootstrap_remote_client(payload, runner=runner)

    assert session.committed is True
    assert result.client_id == client_id
    assert result.name == "Remote Dev"
    assert result.status == "OFFLINE"
    assert result.reused is False
