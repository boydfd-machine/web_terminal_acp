from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.contexts.agent_profiles.infrastructure.agent_config_store import (
    AgentModelSelection,
    ResolvedAgentModelSettings,
    SystemModelPresetList,
)
from app.contexts.terminal_artifacts.application import model_selection


@pytest.mark.asyncio
async def test_artifact_generation_model_selection_prefers_artifact_metadata(monkeypatch) -> None:
    artifact = SimpleNamespace(
        metadata_json={
            "artifact_model_selection": {
                "preset_id": "explicit-artifacts",
                "model": "model-explicit",
                "codex_model_reasoning_effort": "high",
            }
        }
    )
    source_window = SimpleNamespace(id=uuid4(), shell_command="codex", cwd="/workspace")
    captured: list[tuple[str, AgentModelSelection | None]] = []

    async def fake_preferences(session):
        return SimpleNamespace(
            artifact_model_selection_settings={
                "codex": {"preset_id": "system-artifacts", "model": "model-system"}
            }
        )

    async def fake_presets(session):
        return SystemModelPresetList(presets=[])

    def fake_resolve(agent, selection, presets):
        captured.append((agent, selection))
        return ResolvedAgentModelSettings(
            preset_id=selection.preset_id,
            provider="openai_compatible",
            base_url="https://models.example.com/v1",
            api_key="secret",
            model=selection.model or "fallback",
            codex_model_reasoning_effort=selection.codex_model_reasoning_effort,
        )

    monkeypatch.setattr(model_selection, "get_app_preferences", fake_preferences)
    monkeypatch.setattr(model_selection.system_config_service, "list_system_model_presets", fake_presets)
    monkeypatch.setattr(
        model_selection.agent_config_service,
        "resolve_agent_model_selection_from_presets",
        fake_resolve,
    )

    agent, settings = await model_selection.artifact_model_selection_for_generation(
        object(),
        source_window,
        artifact,
        source_agent_command="codex",
    )

    assert agent == "codex"
    assert settings is not None
    assert settings.preset_id == "explicit-artifacts"
    assert settings.model == "model-explicit"
    assert settings.codex_model_reasoning_effort == "high"
    assert captured[0][1].preset_id == "explicit-artifacts"


@pytest.mark.asyncio
async def test_artifact_generation_model_selection_uses_system_default(monkeypatch) -> None:
    artifact = SimpleNamespace(metadata_json={})
    source_window = SimpleNamespace(id=uuid4(), shell_command="codex", cwd="/workspace")

    async def fake_preferences(session):
        return SimpleNamespace(
            artifact_model_selection_settings={
                "codex": {
                    "preset_id": "system-artifacts",
                    "model": "model-system",
                    "codex_plan_mode_reasoning_effort": "xhigh",
                }
            }
        )

    async def fake_presets(session):
        return SystemModelPresetList(presets=[])

    def fake_resolve(agent, selection, presets):
        return ResolvedAgentModelSettings(
            preset_id=selection.preset_id,
            provider="openai_compatible",
            base_url="https://models.example.com/v1",
            api_key="secret",
            model=selection.model or "fallback",
            codex_plan_mode_reasoning_effort=selection.codex_plan_mode_reasoning_effort,
        )

    monkeypatch.setattr(model_selection, "get_app_preferences", fake_preferences)
    monkeypatch.setattr(model_selection.system_config_service, "list_system_model_presets", fake_presets)
    monkeypatch.setattr(
        model_selection.agent_config_service,
        "resolve_agent_model_selection_from_presets",
        fake_resolve,
    )

    agent, settings = await model_selection.artifact_model_selection_for_generation(
        object(),
        source_window,
        artifact,
        source_agent_command="codex",
    )

    assert agent == "codex"
    assert settings is not None
    assert settings.preset_id == "system-artifacts"
    assert settings.model == "model-system"
    assert settings.codex_plan_mode_reasoning_effort == "xhigh"
