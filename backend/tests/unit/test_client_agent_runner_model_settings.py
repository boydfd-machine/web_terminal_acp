from tests.unit.test_client_agent_runner_support import *


@pytest.mark.asyncio
async def test_create_window_materializes_agent_model_settings_before_runtime_create(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []
    materialized: list[tuple[str, str, str]] = []

    def fake_materialize(agent, settings, *, window_id, home=None):
        calls.append("materialize_model")
        materialized.append((agent, settings.model, window_id))

    monkeypatch.setattr(
        "app.client_agent.runner.agent_config_service.materialize_agent_model_settings_for_window",
        fake_materialize,
    )

    await handle_message_for_test(
        FakeWriter(),
        FakeBulkWriter(),
        object(),
        FakeRuntime(calls),
        FakeTerminal(calls),
        FakeIdleSupervisor(calls),
        FakeAgentToolWatcher(calls),
        {},
        {},
        AgentMessage(
            type="create_window",
            client_id=UUID("12345678-1234-5678-1234-567812345678"),
            window_id=WINDOW_ID,
            request_id="request-1",
            payload={
                "cwd": "/workspace/project",
                "shell_command": "codex",
                "agent_model_agent": "codex",
                "agent_model_settings": {
                    "preset_id": "openai-main",
                    "provider": "openai_compatible",
                    "base_url": "https://models.example.com/v1",
                    "api_key": "secret-key",
                    "model": "model-a",
                },
            },
        ),
    )

    assert calls[:2] == ["materialize_model", "create_window"]
    assert materialized == [("codex", "model-a", str(WINDOW_ID))]
