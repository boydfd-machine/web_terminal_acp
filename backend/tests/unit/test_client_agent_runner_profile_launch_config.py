from tests.unit.test_client_agent_runner_support import *  # noqa: F403


@pytest.mark.asyncio
async def test_create_window_applies_agent_config_after_profile_materialization(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []
    materialized: list[tuple[str, str, str]] = []
    applied: list[tuple[str, str, bool]] = []

    def fake_materialize(profile_id, agent, *, window_id, home=None):
        materialized.append((profile_id, agent, window_id))
        calls.append("materialize_profile")
        return AgentConfig(agent=agent, sections=[])

    def fake_apply(selection, *, window_id, home=None, protect_system_config_skills=False):
        applied.append((selection.agent, window_id, protect_system_config_skills))
        calls.append("apply_config")
        return AgentConfig(agent=selection.agent, sections=[])

    monkeypatch.setattr(
        "app.client_agent.runner.agent_profile_service.materialize_agent_profile_for_window",
        fake_materialize,
    )
    monkeypatch.setattr(
        "app.client_agent.runner.agent_config_service.apply_agent_config_selection",
        fake_apply,
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
                "agent_profile_id": "builder",
                "agent_profile_agent": "codex",
                "agent_config_selection": {
                    "agent": "codex",
                    "sections": [
                        {"id": "skills", "items": [{"id": "docker", "enabled": False}]}
                    ],
                },
            },
        ),
    )

    assert calls[:3] == ["materialize_profile", "apply_config", "create_window"]
    assert materialized == [("builder", "codex", str(WINDOW_ID))]
    assert applied == [("codex", str(WINDOW_ID), True)]
