# ruff: noqa: F403, F405
from tests.unit.test_client_agent_runner_support import *


@pytest.mark.asyncio
async def test_terminal_select_window_can_explicitly_recreate_missing_tmux_window_before_latest_resume() -> (
    None
):
    calls: list[str] = []
    terminal = FakeTerminal(calls)
    supervisor = FakeIdleSupervisor(calls)
    supervisor.resumable_session = True
    writer = FakeWriter()
    runtime = FakeRuntime(window_exists=False)

    await handle_message_for_test(
        writer,
        FakeBulkWriter(),
        object(),
        runtime,
        terminal,
        supervisor,
        FakeAgentToolWatcher(calls),
        {},
        {},
        AgentMessage(
            type="terminal_select_window",
            client_id=UUID("12345678-1234-5678-1234-567812345678"),
            window_id=WINDOW_ID,
            request_id="request-1",
            payload={
                "remote_session_id": "pool",
                "remote_window_id": "@7",
                "view_id": str(VIEW_ID),
                "cwd": "/workspace/project",
                "shell_command": "/bin/bash",
                "allow_missing_window_recreate": True,
            },
        ),
    )

    assert runtime.recreated == [WINDOW_ID]
    assert calls == [
        "unregister_window",
        "register_window",
        "register_window_supervisor",
        "attach_view",
        "resume_window",
        "select_window",
    ]
    assert supervisor.resume_calls == [(WINDOW_ID, True)]
    assert writer.messages[-1].payload["remote_window_id"] == "@9"


@pytest.mark.asyncio
async def test_terminal_select_window_can_explicitly_recreate_with_default_shell_when_resume_is_available() -> (
    None
):
    calls: list[str] = []
    terminal = FakeTerminal(calls)
    supervisor = FakeIdleSupervisor(calls)
    supervisor.resumable_session = True
    writer = FakeWriter()
    runtime = FakeRuntime(window_exists=False)

    await handle_message_for_test(
        writer,
        FakeBulkWriter(),
        object(),
        runtime,
        terminal,
        supervisor,
        FakeAgentToolWatcher(calls),
        {},
        {},
        AgentMessage(
            type="terminal_select_window",
            client_id=UUID("12345678-1234-5678-1234-567812345678"),
            window_id=WINDOW_ID,
            request_id="request-1",
            payload={
                "remote_session_id": "pool",
                "remote_window_id": "@7",
                "view_id": str(VIEW_ID),
                "cwd": "/workspace/project",
                "shell_command": "codex",
                "allow_missing_window_recreate": True,
            },
        ),
    )

    assert runtime.recreate_shell_commands == [None]
    assert supervisor.resume_calls == [(WINDOW_ID, True)]
    assert writer.messages[-1].payload["shell_command"] == "codex"


@pytest.mark.asyncio
async def test_agent_config_get_returns_serialized_config(monkeypatch: pytest.MonkeyPatch) -> None:
    writer = FakeWriter()

    def fake_list_agent_config(agent: str):
        assert agent == "codex"
        return AgentConfig(
            agent="codex",
            sections=[
                AgentConfigSection(
                    id="skills",
                    name="Skills",
                    items=[AgentConfigItem(id="docker", name="docker", enabled=True)],
                ),
                AgentConfigSection(id="plugins", name="Plugins", items=[]),
                AgentConfigSection(id="hooks", name="Hooks", items=[]),
            ],
        )

    monkeypatch.setattr(
        "app.client_agent.runner.agent_config_service.list_agent_config",
        fake_list_agent_config,
    )

    await handle_message_for_test(
        writer,
        FakeBulkWriter(),
        object(),
        FakeRuntime(),
        FakeTerminal([]),
        FakeIdleSupervisor([]),
        FakeAgentToolWatcher([]),
        {},
        {},
        AgentMessage(
            type="agent_config_get",
            client_id=UUID("12345678-1234-5678-1234-567812345678"),
            request_id="request-1",
            payload={"agent": "codex"},
        ),
    )

    assert writer.messages[-1].type == "agent_config_result"
    assert writer.messages[-1].payload["agent"] == "codex"
    assert writer.messages[-1].payload["sections"][0]["items"][0]["id"] == "docker"


@pytest.mark.asyncio
async def test_system_agent_config_get_returns_serialized_config(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    writer = FakeWriter()

    def fake_list_system_agent_config():
        return AgentConfig(
            agent="system",
            sections=[
                AgentConfigSection(
                    id="skills",
                    name="System Skills",
                    items=[
                        AgentConfigItem(
                            id="review-helper",
                            name="Review Helper",
                            enabled=True,
                            origin="system_config",
                        )
                    ],
                ),
                AgentConfigSection(
                    id="mcp",
                    name="System MCP Servers",
                    items=[
                        AgentConfigItem(
                            id="web-terminal-acp-mcp",
                            name="web-terminal-acp-mcp",
                            enabled=True,
                            origin="system_builtin",
                        )
                    ],
                ),
            ],
        )

    monkeypatch.setattr(
        "app.client_agent.runner.agent_config_service.list_system_agent_config",
        fake_list_system_agent_config,
    )

    await handle_message_for_test(
        writer,
        FakeBulkWriter(),
        object(),
        FakeRuntime(),
        FakeTerminal([]),
        FakeIdleSupervisor([]),
        FakeAgentToolWatcher([]),
        {},
        {},
        AgentMessage(
            type="system_agent_config_get",
            client_id=UUID("12345678-1234-5678-1234-567812345678"),
            request_id="request-1",
            payload={},
        ),
    )

    assert writer.messages[-1].type == "agent_config_result"
    assert writer.messages[-1].payload["agent"] == "system"
    skills = writer.messages[-1].payload["sections"][0]
    assert skills["items"][0]["id"] == "review-helper"
    assert skills["items"][0]["origin"] == "system_config"


@pytest.mark.asyncio
async def test_agent_clients_list_returns_serialized_descriptors() -> None:
    writer = FakeWriter()

    await handle_message_for_test(
        writer,
        FakeBulkWriter(),
        object(),
        FakeRuntime(),
        FakeTerminal([]),
        FakeIdleSupervisor([]),
        FakeAgentToolWatcher([]),
        {},
        {},
        AgentMessage(
            type="agent_clients_list",
            client_id=UUID("12345678-1234-5678-1234-567812345678"),
            request_id="request-1",
            payload={},
        ),
    )

    assert writer.messages[-1].type == "agent_client_result"
    clients = {client["id"]: client for client in writer.messages[-1].payload["agent_clients"]}
    assert clients["codex"]["provider_id"] == "codex"
    assert clients["codex"]["capabilities"]["agent_records"] is True
    assert clients["cursor"]["command_names"] == ["agent", "cursor", "cursor-agent"]


@pytest.mark.asyncio
async def test_agent_profile_list_returns_serialized_profiles(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    writer = FakeWriter()

    def fake_list_agent_profiles():
        return [
            AgentProfile(
                id="builder",
                name="Builder",
                description=None,
                default_agent_client="codex",
                agent_md="Rules",
                created_at="2026-01-01T00:00:00+00:00",
                updated_at="2026-01-01T00:00:00+00:00",
            )
        ]

    monkeypatch.setattr(
        "app.client_agent.runner.agent_profile_service.list_agent_profiles",
        fake_list_agent_profiles,
    )

    await handle_message_for_test(
        writer,
        FakeBulkWriter(),
        object(),
        FakeRuntime(),
        FakeTerminal([]),
        FakeIdleSupervisor([]),
        FakeAgentToolWatcher([]),
        {},
        {},
        AgentMessage(
            type="agent_profile_list",
            client_id=UUID("12345678-1234-5678-1234-567812345678"),
            request_id="request-1",
            payload={},
        ),
    )

    assert writer.messages[-1].type == "agent_profile_result"
    assert writer.messages[-1].payload["profiles"][0]["id"] == "builder"


@pytest.mark.asyncio
async def test_builtin_agent_profile_config_set_enabled_uses_builtin_store(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    writer = FakeWriter()
    captured: list[tuple[str, str, str, str, bool]] = []

    def fake_set_builtin_profile_config_item_enabled(
        profile_id: str,
        agent: str,
        section_id: str,
        item_id: str,
        enabled: bool,
    ):
        captured.append((profile_id, agent, section_id, item_id, enabled))
        return AgentConfig(
            agent="codex",
            sections=[
                AgentConfigSection(
                    id="skills",
                    name="Skills",
                    items=[AgentConfigItem(id=item_id, name=item_id, enabled=enabled)],
                )
            ],
        )

    def fail_set_agent_profile_config_item_enabled(*args, **kwargs):
        raise AssertionError("built-in profile config must not use editable profile store")

    monkeypatch.setattr(
        "app.client_agent.runner.builtin_profiles.set_builtin_profile_config_item_enabled",
        fake_set_builtin_profile_config_item_enabled,
    )
    monkeypatch.setattr(
        "app.client_agent.runner.agent_profile_service.set_agent_profile_config_item_enabled",
        fail_set_agent_profile_config_item_enabled,
    )

    await handle_message_for_test(
        writer,
        FakeBulkWriter(),
        object(),
        FakeRuntime(),
        FakeTerminal([]),
        FakeIdleSupervisor([]),
        FakeAgentToolWatcher([]),
        {},
        {},
        AgentMessage(
            type="agent_profile_config_set_enabled",
            client_id=UUID("12345678-1234-5678-1234-567812345678"),
            request_id="request-1",
            payload={
                "profile_id": "builtin/developer",
                "agent": "codex",
                "section_id": "skills",
                "item_id": "docker",
                "enabled": True,
            },
        ),
    )

    assert captured == [("builtin/developer", "codex", "skills", "docker", True)]
    assert writer.messages[-1].type == "agent_config_result"
    assert writer.messages[-1].payload["sections"][0]["items"][0]["enabled"] is True
