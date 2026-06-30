from tests.integration.test_client_api_support import *

from app.services.client_update import ClientUpdateStartResult
from app.services.bootstrap.installer import BootstrapResult
from app.services.clients import listing_service as clients_listing_service

@pytest.mark.asyncio
async def test_list_clients_returns_local_client(db_client):
    response = await db_client.get("/api/clients")

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["name"] == "local"
    assert body[0]["status"] == "ONLINE"
    assert body[0]["runtime"] == "local"
    assert body[0]["version"] == __version__
    assert body[0]["last_update_at"] is not None
    assert "token_hash" not in body[0]

@pytest.mark.asyncio
async def test_list_clients_hot_cache_skips_repository(db_client, monkeypatch):
    first_response = await db_client.get("/api/clients")
    assert first_response.status_code == 200

    async def fail_list_clients(_session):
        raise AssertionError("hot clients cache should avoid the repository")

    monkeypatch.setattr(clients_listing_service, "list_clients", fail_list_clients)

    second_response = await db_client.get("/api/clients")

    assert second_response.status_code == 200
    assert second_response.json() == first_response.json()

@pytest.mark.asyncio
async def test_list_clients_expired_cache_serves_stale_response(db_client, monkeypatch):
    first_response = await db_client.get("/api/clients")
    assert first_response.status_code == 200
    refreshes = []

    async def fail_list_clients(_session):
        raise AssertionError("expired clients cache should return stale before refresh")

    monkeypatch.setattr(polling_response_cache, "_CACHE_TTL_SECONDS", -1.0)
    monkeypatch.setattr(clients_listing_service, "list_clients", fail_list_clients)
    monkeypatch.setattr(
        clients_listing_service.ClientListingService,
        "_refresh_clients_cache",
        lambda _service, cache_key: refreshes.append(cache_key),
    )

    second_response = await db_client.get("/api/clients")

    assert second_response.status_code == 200
    assert second_response.json() == first_response.json()
    assert refreshes

@pytest.mark.asyncio
async def test_get_client_returns_metadata(db_client):
    list_response = await db_client.get("/api/clients")
    client_id = list_response.json()[0]["id"]

    response = await db_client.get(f"/api/clients/{client_id}")

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == client_id
    assert body["name"] == "local"
    assert body["status"] == "ONLINE"
    assert body["runtime"] == "local"
    assert body["version"] == __version__
    assert body["last_update_at"] is not None
    assert body["connected_at"] is not None
    assert body["last_seen_at"] is not None

@pytest.mark.asyncio
async def test_patch_client_renames_client(db_client):
    list_response = await db_client.get("/api/clients")
    client_id = list_response.json()[0]["id"]

    response = await db_client.patch(f"/api/clients/{client_id}", json={"name": "Desk Mini"})

    assert response.status_code == 200
    assert response.json()["id"] == client_id
    assert response.json()["name"] == "Desk Mini"

    get_response = await db_client.get(f"/api/clients/{client_id}")
    assert get_response.json()["name"] == "Desk Mini"

@pytest.mark.asyncio
async def test_patch_client_invalidates_clients_hot_cache(db_client):
    list_response = await db_client.get("/api/clients")
    client_id = list_response.json()[0]["id"]

    response = await db_client.patch(f"/api/clients/{client_id}", json={"name": "Desk Mini"})
    assert response.status_code == 200

    list_after_patch = await db_client.get("/api/clients")

    assert list_after_patch.json()[0]["name"] == "Desk Mini"

@pytest.mark.asyncio
async def test_patch_client_rejects_duplicate_name(db_client):
    async with db_client.session_factory() as session:
        first, _first_token = await create_client(session, name="First", runtime=ClientRuntime.remote)
        second, _second_token = await create_client(session, name="Second", runtime=ClientRuntime.remote)
        await session.commit()

    response = await db_client.patch(f"/api/clients/{second.id}", json={"name": "First"})

    assert response.status_code == 409
    assert response.json()["detail"] == "client name already exists"

    get_first = await db_client.get(f"/api/clients/{first.id}")
    get_second = await db_client.get(f"/api/clients/{second.id}")
    assert get_first.json()["name"] == "First"
    assert get_second.json()["name"] == "Second"

@pytest.mark.asyncio
async def test_missing_client_returns_404(db_client):
    missing_id = "00000000-0000-0000-0000-000000000000"

    get_response = await db_client.get(f"/api/clients/{missing_id}")
    patch_response = await db_client.patch(f"/api/clients/{missing_id}", json={"name": "missing"})
    delete_response = await db_client.delete(f"/api/clients/{missing_id}")

    assert get_response.status_code == 404
    assert patch_response.status_code == 404
    assert delete_response.status_code == 404

@pytest.mark.asyncio
async def test_delete_remote_client_removes_client_graph_and_invalidates_cache(db_client):
    async with db_client.session_factory() as session:
        remote_client, _token = await create_client(session, name="Remote", runtime=ClientRuntime.remote)
        folder = await get_or_create_folder_by_path(session, remote_client.id, "/project")
        window = await create_window(
            session,
            remote_client.id,
            cwd="/project",
            shell_command="/bin/bash",
        )
        window.folder_id = folder.id
        summary_job = SummaryJob(virtual_window_id=window.id)
        session.add(summary_job)
        terminal_recent = TerminalRecentUsage(
            client_id=remote_client.id,
            window_id=window.id,
            title=window.title,
        )
        session.add(terminal_recent)
        notification_state = TerminalNotificationState(
            client_id=remote_client.id,
            window_id=window.id,
        )
        session.add(notification_state)
        ai_session = AiSession(
            client_id=remote_client.id,
            provider="codex",
            source_id="session-1",
            virtual_window_id=window.id,
        )
        session.add(ai_session)
        await session.flush()
        event = Event(
            client_id=remote_client.id,
            source_type=EventSourceType.codex_trace,
            source_id="trace-1",
            kind="agent_message",
            virtual_window_id=window.id,
            ai_session_id=ai_session.id,
            payload_json={},
            fingerprint="trace-1",
        )
        project_summary = ProjectSummary(client_id=remote_client.id, project_path="/project")
        session.add_all([event, project_summary])
        await session.commit()
        remote_client_id = remote_client.id
        window_id = window.id
        folder_id = folder.id
        ai_session_id = ai_session.id

    cached_clients = await db_client.get("/api/clients")
    assert cached_clients.status_code == 200
    assert any(client["id"] == str(remote_client_id) for client in cached_clients.json())

    response = await db_client.delete(f"/api/clients/{remote_client_id}")

    assert response.status_code == 204
    assert (await db_client.get(f"/api/clients/{remote_client_id}")).status_code == 404
    list_after_delete = await db_client.get("/api/clients")
    assert all(client["id"] != str(remote_client_id) for client in list_after_delete.json())

    async with db_client.session_factory() as session:
        assert await session.get(Client, remote_client_id) is None
        assert await session.get(Folder, folder_id) is None
        assert await session.get(VirtualWindow, window_id) is None
        assert await session.get(AiSession, ai_session_id) is None
        assert (await session.scalars(select(Event).where(Event.client_id == remote_client_id))).first() is None
        assert (
            await session.scalars(
                select(TerminalRecentUsage).where(TerminalRecentUsage.client_id == remote_client_id)
            )
        ).first() is None
        assert (
            await session.scalars(
                select(TerminalNotificationState).where(
                    TerminalNotificationState.client_id == remote_client_id
                )
            )
        ).first() is None
        assert (
            await session.scalars(
                select(ProjectSummary).where(ProjectSummary.client_id == remote_client_id)
            )
        ).first() is None

@pytest.mark.asyncio
async def test_delete_remote_client_closes_active_connection(db_client):
    async with db_client.session_factory() as session:
        remote_client, _token = await create_client(session, name="Remote", runtime=ClientRuntime.remote)
        await session.commit()

    connection = FakeClientConnection()
    registry = FakeClientConnectionRegistry(connection)
    app.state.client_connections = registry

    response = await db_client.delete(f"/api/clients/{remote_client.id}")

    assert response.status_code == 204
    assert connection.closed is True
    assert registry.unregistered == [(remote_client.id, connection)]

@pytest.mark.asyncio
async def test_delete_local_client_is_rejected(db_client):
    list_response = await db_client.get("/api/clients")
    local_client_id = list_response.json()[0]["id"]

    response = await db_client.delete(f"/api/clients/{local_client_id}")

    assert response.status_code == 400
    assert response.json()["detail"] == "local client deletion unsupported"

@pytest.mark.asyncio
async def test_bootstrap_client_route_returns_runner_result(db_client):
    client_id = uuid4()

    async def fake_runner(_session, payload):
        assert payload.private_key == BOOTSTRAP_PAYLOAD["private_key"]
        return BootstrapResult(
            client_id=client_id,
            name=payload.name,
            status="OFFLINE",
            reused=False,
        )

    app.dependency_overrides[clients_router.get_bootstrap_runner] = lambda: fake_runner

    response = await db_client.post("/api/clients/bootstrap", json=BOOTSTRAP_PAYLOAD)

    assert response.status_code == 200
    assert response.json() == {
        "client_id": str(client_id),
        "name": "Remote Dev",
        "status": "OFFLINE",
        "reused": False,
    }

@pytest.mark.asyncio
async def test_update_client_route_returns_started_result(db_client):
    async with db_client.session_factory() as session:
        remote_client, _token = await create_client(session, name="Remote", runtime=ClientRuntime.remote)
        await session.commit()

    async def fake_runner(client_id, _registry):
        return ClientUpdateStartResult(
            client_id=client_id,
            job_id="job-1",
            method="agent_message",
        )

    app.dependency_overrides[clients_router.get_update_runner] = lambda: fake_runner

    response = await db_client.post(f"/api/clients/{remote_client.id}/update")

    assert response.status_code == 202
    assert response.json() == {
        "client_id": str(remote_client.id),
        "job_id": "job-1",
        "status": "STARTED",
        "method": "agent_message",
    }

@pytest.mark.asyncio
async def test_update_package_requires_client_token(db_client):
    async with db_client.session_factory() as session:
        remote_client, token = await create_client(session, name="Remote", runtime=ClientRuntime.remote)
        await session.commit()

    rejected = await db_client.get(f"/api/clients/{remote_client.id}/update/package")
    accepted = await db_client.get(
        f"/api/clients/{remote_client.id}/update/package?job_id=job-1",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert rejected.status_code == 401
    assert accepted.status_code == 200
    assert accepted.json()["job_id"] == "job-1"
    assert "client_agent/updater.py" in accepted.json()["files"]

@pytest.mark.asyncio
async def test_update_complete_records_completion_time_after_client_callback(db_client):
    async with db_client.session_factory() as session:
        remote_client, token = await create_client(session, name="Remote", runtime=ClientRuntime.remote)
        await session.commit()

    rejected = await db_client.post(
        f"/api/clients/{remote_client.id}/update/complete",
        json={"job_id": "job-1"},
    )
    accepted = await db_client.post(
        f"/api/clients/{remote_client.id}/update/complete",
        json={"job_id": "job-1"},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert rejected.status_code == 401
    assert accepted.status_code == 200
    assert accepted.json()["job_id"] == "job-1"

    response = await db_client.get(f"/api/clients/{remote_client.id}")
    assert response.json()["last_update_at"] is not None

@pytest.mark.asyncio
async def test_bootstrap_client_route_maps_dependency_error_to_400_and_redacts(db_client):
    async def fake_runner(_session, _payload):
        raise BootstrapDependencyError(
            "missing tmux "
            + BOOTSTRAP_PAYLOAD["private_key"]
            + " ssh-passphrase plain-client-token"
        )

    app.dependency_overrides[clients_router.get_bootstrap_runner] = lambda: fake_runner

    response = await db_client.post("/api/clients/bootstrap", json=BOOTSTRAP_PAYLOAD)

    assert response.status_code == 400
    detail = response.json()["detail"]
    assert "missing tmux" in detail
    assert BOOTSTRAP_PAYLOAD["private_key"] not in detail
    assert BOOTSTRAP_PAYLOAD["passphrase"] not in detail
    assert "plain-client-token" not in detail

@pytest.mark.asyncio
async def test_bootstrap_client_route_dependency_error_traceback_drops_secret_cause():
    async def fake_runner(_session, _payload):
        try:
            raise ValueError(
                "dependency cause "
                + BOOTSTRAP_PAYLOAD["private_key"]
                + " ssh-passphrase plain-client-token"
            )
        except ValueError as exc:
            raise BootstrapDependencyError("missing tmux plain-client-token") from exc

    session = CommitRecorder()
    payload = BootstrapClientIn(**BOOTSTRAP_PAYLOAD)

    with pytest.raises(HTTPException) as exc_info:
        await clients_router.bootstrap_remote_client(payload, session=session, runner=fake_runner)

    formatted = _formatted_exception(exc_info.value)
    assert exc_info.value.status_code == 400
    assert session.committed is False
    assert BOOTSTRAP_PAYLOAD["private_key"] not in formatted
    assert BOOTSTRAP_PAYLOAD["passphrase"] not in formatted
    assert "plain-client-token" not in formatted

@pytest.mark.asyncio
async def test_bootstrap_client_route_maps_connection_error_to_502_and_redacts(db_client):
    async def fake_runner(_session, _payload):
        raise BootstrapConnectionError(
            "auth failed " + BOOTSTRAP_PAYLOAD["private_key"] + " ssh-passphrase"
        )

    app.dependency_overrides[clients_router.get_bootstrap_runner] = lambda: fake_runner

    response = await db_client.post("/api/clients/bootstrap", json=BOOTSTRAP_PAYLOAD)

    assert response.status_code == 502
    detail = response.json()["detail"]
    assert "auth failed" in detail
    assert BOOTSTRAP_PAYLOAD["private_key"] not in detail
    assert BOOTSTRAP_PAYLOAD["passphrase"] not in detail

@pytest.mark.asyncio
async def test_bootstrap_client_route_connection_error_traceback_drops_secret_cause():
    async def fake_runner(_session, _payload):
        try:
            raise RuntimeError(
                "connection cause "
                + BOOTSTRAP_PAYLOAD["private_key"]
                + " ssh-passphrase plain-client-token"
            )
        except RuntimeError as exc:
            raise BootstrapConnectionError("auth failed plain-client-token") from exc

    session = CommitRecorder()
    payload = BootstrapClientIn(**BOOTSTRAP_PAYLOAD)

    with pytest.raises(HTTPException) as exc_info:
        await clients_router.bootstrap_remote_client(payload, session=session, runner=fake_runner)

    formatted = _formatted_exception(exc_info.value)
    assert exc_info.value.status_code == 502
    assert session.committed is False
    assert BOOTSTRAP_PAYLOAD["private_key"] not in formatted
    assert BOOTSTRAP_PAYLOAD["passphrase"] not in formatted
    assert "plain-client-token" not in formatted
