from tests.integration.test_window_api_support import *


@pytest.mark.asyncio
async def test_get_window_agent_config_detects_local_agent_from_terminal_command(
    db_client,
    tmp_path,
    monkeypatch,
):
    monkeypatch.setattr(windows_router.agent_config_service.Path, "home", lambda: tmp_path)
    codex_home = tmp_path / ".codex"
    skill_dir = codex_home / "skills" / "docker"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text("---\nname: docker\n---\n", encoding="utf-8")
    (codex_home / "hooks.json").write_text(
        json.dumps(
            {
                "hooks": {
                    "UserPromptSubmit": [
                        {
                            "matcher": "",
                            "hooks": [
                                {
                                    "type": "command",
                                    "command": "hooks/preflight.sh",
                                }
                            ],
                        }
                    ]
                }
            }
        ),
        encoding="utf-8",
    )

    client_id = await get_local_client_id(db_client)
    window_response = await db_client.post(
        f"/api/clients/{client_id}/windows",
        json={"cwd": "/workspace/project", "shell_command": "/bin/bash"},
    )
    assert window_response.status_code == 200
    window_id = window_response.json()["id"]

    async with db_client.session_factory() as session:
        session.add(
            Event(
                client_id=UUID(client_id),
                virtual_window_id=UUID(window_id),
                source_type=EventSourceType.terminal,
                source_id="terminal",
                kind="terminal_input_command",
                payload_json={"command": "codex exec 'fix tests'"},
                fingerprint="agent-config-codex-command",
            )
        )
        await session.commit()

    response = await db_client.get(f"/api/clients/{client_id}/windows/{window_id}/agent-config")

    assert response.status_code == 200
    body = response.json()
    assert body["agent"] == "codex"
    skills = next(section for section in body["sections"] if section["id"] == "skills")
    assert next(item for item in skills["items"] if item["id"] == "docker")["enabled"] is True

    patch_response = await db_client.patch(
        f"/api/clients/{client_id}/windows/{window_id}/agent-config/hooks/UserPromptSubmit:hooks%2Fpreflight.sh",
        json={"enabled": False},
    )
    assert patch_response.status_code == 200
    updated_hooks = next(
        section for section in patch_response.json()["sections"] if section["id"] == "hooks"
    )
    assert updated_hooks["items"][0]["id"] == "UserPromptSubmit:hooks/preflight.sh"
    assert updated_hooks["items"][0]["enabled"] is False


@pytest.mark.asyncio
async def test_remote_window_agent_config_uses_client_agent_request(db_client):
    remote_client_id = await create_remote_client_id(db_client)
    connection = AgentConfigRemoteConnection()
    app.state.client_connections = FakeConnectionRegistry(connection)
    upload_response = await db_client.put(
        "/api/system-agent-config/skills/image-to-ppt",
        content=skill_zip_bytes("image-to-ppt", "---\nname: Image to PPT\n---\n"),
    )
    assert upload_response.status_code == 200
    create_response = await db_client.post(
        f"/api/clients/{remote_client_id}/windows",
        json={"cwd": "/workspace/project", "shell_command": "claude"},
    )
    assert create_response.status_code == 200
    window_id = create_response.json()["id"]
    await allow_remote_create_to_finish(connection)
    await wait_for_remote_window_ready(db_client, remote_client_id, window_id)

    get_response = await db_client.get(
        f"/api/clients/{remote_client_id}/windows/{window_id}/agent-config"
    )
    assert get_response.status_code == 200
    assert get_response.json()["agent"] == "claude"

    patch_response = await db_client.patch(
        f"/api/clients/{remote_client_id}/windows/{window_id}/agent-config/skills/review",
        json={"enabled": False},
    )
    assert patch_response.status_code == 200

    config_requests = [
        request for request in connection.requests if request.type.startswith("agent_config")
    ]
    assert [request.type for request in config_requests] == [
        "agent_config_get",
        "agent_config_set_enabled",
    ]
    get_payload = dict(config_requests[0].payload)
    system_config_files = get_payload.pop("system_config_files")
    assert get_payload == {"agent": "claude_code"}
    assert any(
        file["path"] == "skills/image-to-ppt/SKILL.md"
        for file in system_config_files["files"]
    )
    patch_payload = dict(config_requests[1].payload)
    assert patch_payload.pop("system_config_files")["version"] == 1
    assert patch_payload == {
        "agent": "claude_code",
        "section_id": "skills",
        "item_id": "review",
        "enabled": False,
    }


@pytest.mark.asyncio
async def test_remote_window_agent_config_model_update_uses_client_agent_request(db_client):
    remote_client_id = await create_remote_client_id(db_client)
    connection = AgentConfigRemoteConnection()
    app.state.client_connections = FakeConnectionRegistry(connection)
    create_response = await db_client.post(
        f"/api/clients/{remote_client_id}/windows",
        json={"cwd": "/workspace/project", "shell_command": "claude"},
    )
    assert create_response.status_code == 200
    window_id = create_response.json()["id"]
    await allow_remote_create_to_finish(connection)
    await wait_for_remote_window_ready(db_client, remote_client_id, window_id)

    patch_response = await db_client.patch(
        f"/api/clients/{remote_client_id}/windows/{window_id}/agent-config/model",
        json={"claude_reasoning_effort": "high"},
    )
    assert patch_response.status_code == 200
    body = patch_response.json()
    assert body["model"]["claude_reasoning_effort"] == "high"

    model_requests = [
        request for request in connection.requests if request.type == "agent_config_set_model"
    ]
    assert len(model_requests) == 1
    assert model_requests[0].payload["agent"] == "claude_code"
    assert model_requests[0].payload["claude_reasoning_effort"] == "high"


@pytest.mark.asyncio
async def test_remote_window_detail_uses_client_agent_model_metadata_for_token_limit(db_client):
    remote_client_id = await create_remote_client_id(db_client)
    connection = AgentConfigRemoteConnection()
    app.state.client_connections = FakeConnectionRegistry(connection)
    create_response = await db_client.post(
        f"/api/clients/{remote_client_id}/windows",
        json={"cwd": "/workspace/project", "shell_command": "claude"},
    )
    assert create_response.status_code == 200
    window_id = create_response.json()["id"]
    await allow_remote_create_to_finish(connection)
    await wait_for_remote_window_ready(db_client, remote_client_id, window_id)

    async with db_client.session_factory() as session:
        ai_session = AiSession(
            client_id=UUID(remote_client_id),
            provider="claude_code",
            source_id="claude-session-token-limit",
            virtual_window_id=UUID(window_id),
        )
        session.add(ai_session)
        await session.flush()
        session.add(
            Event(
                client_id=UUID(remote_client_id),
                virtual_window_id=UUID(window_id),
                ai_session_id=ai_session.id,
                source_type=EventSourceType.claude_jsonl,
                source_id="claude-session-token-limit",
                kind="assistant_message",
                payload_json={
                    "provider": "claude_code",
                    "message": {"usage": {"input_tokens": 112838, "output_tokens": 863}},
                },
                fingerprint="remote-window-detail-token-limit",
            )
        )
        await session.commit()

    detail_response = await db_client.get(f"/api/clients/{remote_client_id}/windows/{window_id}")

    assert detail_response.status_code == 200
    usage = detail_response.json()["agent_token_usage"]
    assert usage["total"]["total_tokens"] == 113701
    assert usage["context_window"] is None
    assert usage["auto_compact_token_limit"] == 230000
    config_requests = [
        request for request in connection.requests if request.type == "agent_config_get"
    ]
    assert config_requests[-1].window_id == UUID(window_id)
    detail_payload = dict(config_requests[-1].payload)
    assert detail_payload.pop("system_config_files")["version"] == 1
    assert detail_payload == {"agent": "claude_code"}


@pytest.mark.asyncio
async def test_remote_window_detail_reads_legacy_client_config_file_for_token_limit(db_client):
    remote_client_id = await create_remote_client_id(db_client)
    connection = LegacyAgentConfigRemoteConnection(
        settings_json=json.dumps({"env": {"CLAUDE_CODE_AUTO_COMPACT_WINDOW": "230000"}})
    )
    app.state.client_connections = FakeConnectionRegistry(connection)
    create_response = await db_client.post(
        f"/api/clients/{remote_client_id}/windows",
        json={"cwd": "/workspace/project", "shell_command": "claude"},
    )
    assert create_response.status_code == 200
    window_id = create_response.json()["id"]
    await allow_remote_create_to_finish(connection)
    window = await wait_for_remote_window_ready(db_client, remote_client_id, window_id)

    async with db_client.session_factory() as session:
        client = await session.get(Client, UUID(remote_client_id))
        assert client is not None
        client.install_path = "/home/test/.web-terminal-acp"
        session.add(
            Event(
                client_id=UUID(remote_client_id),
                virtual_window_id=window.id,
                source_type=EventSourceType.claude_jsonl,
                source_id="claude-session-legacy-token-limit",
                kind="assistant_message",
                payload_json={
                    "provider": "claude_code",
                    "message": {"usage": {"input_tokens": 112838, "output_tokens": 863}},
                },
                fingerprint="remote-window-detail-legacy-token-limit",
            )
        )
        await session.commit()

    detail_response = await db_client.get(f"/api/clients/{remote_client_id}/windows/{window_id}")

    assert detail_response.status_code == 200
    usage = detail_response.json()["agent_token_usage"]
    assert usage["auto_compact_token_limit"] == 230000
    file_requests = [request for request in connection.requests if request.type == "file_read"]
    assert file_requests[-1].payload["path"] == (
        f"/home/test/.web-terminal-acp/claude-code-homes/{window_id}/settings.json"
    )


@pytest.mark.asyncio
async def test_client_agent_config_endpoint_uses_remote_agent_config_request(db_client):
    remote_client_id = await create_remote_client_id(db_client)
    connection = AgentConfigRemoteConnection()
    app.state.client_connections = FakeConnectionRegistry(connection)

    response = await db_client.get(f"/api/clients/{remote_client_id}/agent-config/claude")

    assert response.status_code == 200
    assert response.json()["agent"] == "claude"
    assert [request.type for request in connection.requests[:2]] == [
        "agent_clients_list",
        "agent_config_get",
    ]
    assert connection.requests[1].window_id is None
    request_payload = dict(connection.requests[1].payload)
    assert request_payload.pop("system_config_files")["version"] == 1
    assert request_payload == {"agent": "claude_code"}


@pytest.mark.asyncio
async def test_client_system_agent_config_endpoint_reads_local_system_config(
    db_client,
    tmp_path,
    monkeypatch,
):
    monkeypatch.setattr(
        windows_router.system_config_service.agent_config_store.Path,
        "home",
        lambda: tmp_path,
    )
    skill_dir = tmp_path / ".web-terminal-acp" / "system-config" / "skills" / "review-helper"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text("---\nname: Review Helper\n---\n", encoding="utf-8")
    client_id = await get_local_client_id(db_client)

    response = await db_client.get(f"/api/clients/{client_id}/system-agent-config")

    assert response.status_code == 200
    body = response.json()
    assert body["agent"] == "system"
    skills = next(section for section in body["sections"] if section["id"] == "skills")
    skill_items = {item["id"]: item for item in skills["items"]}
    assert skill_items["review-helper"]["name"] == "Review Helper"
    assert skill_items["review-helper"]["origin"] == "system_config"


@pytest.mark.asyncio
async def test_client_system_agent_config_endpoint_uses_remote_system_config_request(db_client):
    remote_client_id = await create_remote_client_id(db_client)
    connection = AgentConfigRemoteConnection()
    app.state.client_connections = FakeConnectionRegistry(connection)
    upload_response = await db_client.put(
        "/api/system-agent-config/skills/image-to-ppt",
        content=skill_zip_bytes("image-to-ppt", "---\nname: Image to PPT\n---\n"),
    )
    assert upload_response.status_code == 200

    response = await db_client.get(f"/api/clients/{remote_client_id}/system-agent-config")

    assert response.status_code == 200
    body = response.json()
    assert body["agent"] == "system"
    skills = next(section for section in body["sections"] if section["id"] == "skills")
    skill_items = {item["id"]: item for item in skills["items"]}
    assert skill_items["image-to-ppt"]["name"] == "Image to PPT"
    assert skill_items["image-to-ppt"]["origin"] == "system_config"
    assert connection.requests == []


@pytest.mark.asyncio
async def test_client_agent_config_rejects_client_config_disabled_descriptor(db_client):
    remote_client_id = await create_remote_client_id(db_client)
    connection = CapabilityRemoteConnection({"client_config": False})
    app.state.client_connections = FakeConnectionRegistry(connection)

    response = await db_client.get(f"/api/clients/{remote_client_id}/agent-config/restricted_agent")

    assert response.status_code == 400
    assert response.json()["detail"] == "agent client does not support client_config"
    assert [request.type for request in connection.requests] == ["agent_clients_list"]


@pytest.mark.asyncio
async def test_remote_agent_config_endpoints_allow_remote_only_agent_descriptor(db_client):
    remote_client_id = await create_remote_client_id(db_client)
    connection = FutureAgentRemoteConnection()
    app.state.client_connections = FakeConnectionRegistry(connection)

    create_response = await db_client.post(
        f"/api/clients/{remote_client_id}/windows",
        json={
            "cwd": "/workspace/project",
            "agent_launch": {"agent": "future_agent", "command": "future-agent"},
        },
    )
    assert create_response.status_code == 200
    window_id = create_response.json()["id"]
    await allow_remote_create_to_finish(connection)
    await wait_for_remote_window_ready(db_client, remote_client_id, window_id)

    client_response = await db_client.get(
        f"/api/clients/{remote_client_id}/agent-config/future_agent"
    )
    assert client_response.status_code == 200
    assert client_response.json()["agent"] == "future_agent"

    window_response = await db_client.get(
        f"/api/clients/{remote_client_id}/windows/{window_id}/agent-config"
    )
    assert window_response.status_code == 200
    assert window_response.json()["agent"] == "future_agent"

    config_requests = [
        request for request in connection.requests if request.type == "agent_config_get"
    ]
    assert [request.payload["agent"] for request in config_requests] == [
        "future_agent",
        "future_agent",
    ]
