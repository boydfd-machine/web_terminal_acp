from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.contexts.windows.domain.clone_spec import CloneReservation, WindowCloneSource, WindowCloneSpec
from app.contexts.windows.domain.remote_agents import (
    RemoteAgentCatalog,
    RemoteAgentResolutionError,
)
from app.schemas import WindowCreateIn
from app.contexts.windows.application.errors import WindowServiceError
from app.contexts.windows.application.launch_plans import local_window_launch_plan, remote_window_launch_plan


def test_local_window_launch_plan_materializes_agent_config_selection() -> None:
    payload = WindowCreateIn.model_validate(
        {
            "cwd": "/workspace",
            "agent_launch": {
                "agent": "codex",
                "command": "codex exec",
                "config": {
                    "agent": "codex",
                    "sections": [
                        {"id": "skills", "items": [{"id": "docker", "enabled": False}]}
                    ],
                },
            },
        }
    )

    plan = local_window_launch_plan(payload, default_shell="/bin/zsh")

    assert plan.cwd == "/workspace"
    assert plan.shell_command == "codex exec"
    assert plan.agent_config_selection is not None
    assert plan.agent_config_selection.agent == "codex"
    assert plan.agent_profile is None
    assert plan.terminal_agent == "codex"


def test_remote_window_launch_plan_resolves_model_selection(monkeypatch: pytest.MonkeyPatch) -> None:
    resolved = SimpleNamespace(model="model-b")
    captured: list[tuple[str, str, str | None]] = []

    def fake_resolve(agent, selection, *, home=None):
        captured.append((agent, selection.preset_id, selection.model))
        return resolved

    monkeypatch.setattr(
        "app.contexts.windows.application.launch_plans.agent_config_service.resolve_agent_model_selection",
        fake_resolve,
    )
    monkeypatch.setattr(
        "app.contexts.windows.application.launch_plans.agent_config_service.resolved_agent_model_settings_payload",
        lambda settings: {"model": settings.model} if settings is not None else None,
    )
    payload = WindowCreateIn.model_validate(
        {
            "cwd": "/workspace",
            "agent_launch": {
                "agent": "codex",
                "command": "codex",
                "model_selection": {"preset_id": "openai-main", "model": "model-b"},
            },
        }
    )

    plan = remote_window_launch_plan(payload)

    assert captured == [("codex", "openai-main", "model-b")]
    assert plan.agent_model_agent == "codex"
    assert plan.agent_model_payload == {"model": "model-b"}


def test_local_window_launch_plan_rejects_mismatched_config_agent() -> None:
    payload = WindowCreateIn.model_validate(
        {
            "agent_launch": {
                "agent": "codex",
                "config": {"agent": "claude", "sections": []},
            },
        }
    )

    with pytest.raises(WindowServiceError) as exc_info:
        local_window_launch_plan(payload, default_shell="/bin/zsh")

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail == "agent launch config agent must match launch agent"


def test_remote_window_launch_plan_preserves_remote_only_agent_config() -> None:
    payload = WindowCreateIn.model_validate(
        {
            "cwd": "/workspace",
            "agent_launch": {
                "agent": "future_agent",
                "command": "future-agent",
                "config": {
                    "agent": "future_agent",
                    "sections": [
                        {"id": "skills", "items": [{"id": "review", "enabled": True}]}
                    ],
                },
            },
        }
    )

    plan = remote_window_launch_plan(payload)

    assert plan.shell_command == "future-agent"
    assert plan.agent_config_payload == {
        "agent": "future_agent",
        "sections": [
            {"id": "skills", "items": [{"id": "review", "enabled": True}]}
        ],
    }
    assert plan.runtime_terminal_agent is None


def test_remote_agent_catalog_supports_alias_and_capability_defaults() -> None:
    catalog = RemoteAgentCatalog.from_payload(
        {
            "agent_clients": [
                {
                    "id": "remote_claude",
                    "provider_id": "claude_code",
                    "aliases": ["claude"],
                    "default_command": "claude",
                    "command_names": ["claude"],
                }
            ]
        }
    )

    result = catalog.resolve_agent_id("claude", "launch", local_provider_id="claude_code")

    assert result.agent_id == "claude_code"
    assert result.error is None
    assert catalog.agent_from_command("env FOO=1 command claude --version") == "remote_claude"


def test_remote_agent_catalog_rejects_disabled_capability() -> None:
    catalog = RemoteAgentCatalog.from_payload(
        {
            "agent_clients": [
                {
                    "id": "restricted_agent",
                    "provider_id": "restricted_provider",
                    "default_command": "restricted-agent",
                    "capabilities": {"launch": False},
                }
            ]
        }
    )

    result = catalog.resolve_agent_id("restricted_agent", "launch")

    assert result.agent_id is None
    assert result.error is RemoteAgentResolutionError.capability_unsupported


def test_window_clone_spec_carries_local_agent_clone_metadata() -> None:
    source_id = uuid4()
    root_id = uuid4()
    source_window = WindowCloneSource(
        id=source_id,
        title="Agent",
        folder_id=uuid4(),
        cwd="/workspace",
        shell_command="codex",
        title_manually_overridden=True,
        folder_manually_overridden=True,
        root_window_id=root_id,
    )
    reservation = CloneReservation(
        cloned_agents=("codex",),
        session_ids={"codex": "new-session"},
        resume_commands={"codex": "codex resume new-session"},
    )
    payload = SimpleNamespace(mode="linked", prompt="continue", collect_paths=["src"])

    spec = WindowCloneSpec.local(source_window, payload, reservation, "codex resume new-session")

    assert spec.root_window_id == root_id
    assert spec.title == "Agent copy"
    assert spec.derived_context == {
        "source_window_id": str(source_id),
        "mode": "linked",
        "cloned_agents": ["codex"],
        "session_ids": {"codex": "new-session"},
        "resume_commands": {"codex": "codex resume new-session"},
        "reserved": {"prompt": "continue", "collect_paths": ["src"]},
    }
