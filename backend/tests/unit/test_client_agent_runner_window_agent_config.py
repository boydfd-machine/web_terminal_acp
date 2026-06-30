# ruff: noqa: F403, F405
from tests.unit.test_client_agent_runner_support import *


@pytest.mark.asyncio
async def test_agent_config_get_uses_window_managed_home(monkeypatch: pytest.MonkeyPatch) -> None:
    writer = FakeWriter()
    captured: list[tuple[str, str]] = []

    def fail_list_agent_config(*args, **kwargs):
        raise AssertionError("window config must not read the global agent home")

    def fake_list_window_agent_config(agent: str, *, window_id: str, home=None):
        captured.append((agent, window_id))
        return AgentConfig(
            agent="codex",
            sections=[
                AgentConfigSection(
                    id="skills",
                    name="Skills",
                    items=[AgentConfigItem(id="docker", name="docker", enabled=False)],
                )
            ],
        )

    monkeypatch.setattr(
        "app.client_agent.runner.agent_config_service.list_agent_config",
        fail_list_agent_config,
    )
    monkeypatch.setattr(
        "app.client_agent.runner.agent_config_service.list_window_agent_config",
        fake_list_window_agent_config,
        raising=False,
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
            window_id=WINDOW_ID,
            request_id="request-1",
            payload={"agent": "codex"},
        ),
    )

    assert captured == [("codex", str(WINDOW_ID))]
    assert writer.messages[-1].payload["sections"][0]["items"][0]["enabled"] is False


@pytest.mark.asyncio
async def test_agent_config_get_includes_window_model_metadata(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    writer = FakeWriter()

    def fake_list_window_agent_config(agent: str, *, window_id: str, home=None):
        return AgentConfig(
            agent=agent,
            sections=[
                AgentConfigSection(
                    id="skills",
                    name="Skills",
                    items=[],
                )
            ],
        )

    def fake_window_agent_model_view(agent: str, *, window_id: str, home=None):
        assert agent == "claude_code"
        assert window_id == str(WINDOW_ID)
        return {
            "editable": False,
            "provider": "claude_code",
            "model": "claude-sonnet",
            "claude_reasoning_effort": "high",
        }

    monkeypatch.setattr(
        "app.client_agent.runner.agent_config_service.list_window_agent_config",
        fake_list_window_agent_config,
        raising=False,
    )
    monkeypatch.setattr(
        "app.client_agent.runner.agent_config_service.window_agent_model_view",
        fake_window_agent_model_view,
        raising=False,
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
            window_id=WINDOW_ID,
            request_id="request-1",
            payload={"agent": "claude_code"},
        ),
    )

    assert writer.messages[-1].payload["model"] == {
        "editable": False,
        "provider": "claude_code",
        "model": "claude-sonnet",
        "claude_reasoning_effort": "high",
    }


@pytest.mark.asyncio
async def test_agent_config_set_enabled_uses_window_managed_home(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    writer = FakeWriter()
    captured: list[tuple[str, str, str, bool, str]] = []

    def fail_set_agent_config_item_enabled(*args, **kwargs):
        raise AssertionError("window config must not write the global agent home")

    def fake_set_window_agent_config_item_enabled(
        agent: str,
        section_id: str,
        item_id: str,
        enabled: bool,
        *,
        window_id: str,
        home=None,
    ):
        captured.append((agent, section_id, item_id, enabled, window_id))
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

    monkeypatch.setattr(
        "app.client_agent.runner.agent_config_service.set_agent_config_item_enabled",
        fail_set_agent_config_item_enabled,
    )
    monkeypatch.setattr(
        "app.client_agent.runner.agent_config_service.set_window_agent_config_item_enabled",
        fake_set_window_agent_config_item_enabled,
        raising=False,
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
            type="agent_config_set_enabled",
            client_id=UUID("12345678-1234-5678-1234-567812345678"),
            window_id=WINDOW_ID,
            request_id="request-1",
            payload={
                "agent": "codex",
                "section_id": "skills",
                "item_id": "docker",
                "enabled": False,
            },
        ),
    )

    assert captured == [("codex", "skills", "docker", False, str(WINDOW_ID))]
    assert writer.messages[-1].payload["sections"][0]["items"][0]["enabled"] is False
