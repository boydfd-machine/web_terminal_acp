import json
from pathlib import Path

from app.services import agent_config as agent_config_service


def _seed_preset(home: Path) -> None:
    agent_config_service.upsert_system_model_preset(
        agent_config_service.SystemModelPreset(
            id="main",
            name="Main",
            provider="openai_compatible",
            providers=["openai_compatible"],
            base_url="https://models.example.com/v1",
            api_key="secret-key",
            models=["model-a", "model-b"],
        ),
        home=home,
    )


def test_apply_window_agent_model_selection_persists_and_materializes(tmp_path: Path) -> None:
    _seed_preset(tmp_path)
    selection = agent_config_service.AgentModelSelection(
        preset_id="main", model="model-a", codex_model_reasoning_effort="high"
    )
    agent_config_service.apply_window_agent_model_selection(
        "codex", selection, window_id="win-1", home=tmp_path
    )
    loaded = agent_config_service.load_window_agent_model_selection(
        "codex", window_id="win-1", home=tmp_path
    )
    assert loaded == selection
    config_toml = (
        tmp_path / ".web-terminal-acp" / "codex-homes" / "win-1" / "config.toml"
    ).read_text()
    assert 'model = "model-a"' in config_toml
    assert 'model_reasoning_effort = "high"' in config_toml


def test_window_agent_model_view_returns_editable_when_selection_exists(tmp_path: Path) -> None:
    _seed_preset(tmp_path)
    agent_config_service.apply_window_agent_model_selection(
        "codex",
        agent_config_service.AgentModelSelection(
            preset_id="main", model="model-b", codex_model_reasoning_effort="low"
        ),
        window_id="win-1",
        home=tmp_path,
    )
    view = agent_config_service.window_agent_model_view(
        "codex", window_id="win-1", home=tmp_path
    )
    assert view is not None
    assert view["editable"] is True
    assert view["provider"] == "codex"
    assert view["preset_id"] == "main"
    assert view["preset_name"] == "Main"
    assert view["model"] == "model-b"
    assert view["available_models"] == ["model-a", "model-b"]
    assert view["codex_model_reasoning_effort"] == "low"
    assert view["codex_plan_mode_reasoning_effort"] is None
    assert "minimal" in view["codex_reasoning_efforts"]


def test_window_agent_model_view_falls_back_to_metadata_when_no_selection(tmp_path: Path) -> None:
    managed = tmp_path / ".web-terminal-acp" / "codex-homes" / "win-1"
    managed.mkdir(parents=True)
    (managed / "config.toml").write_text(
        'model = "legacy-model"\nmodel_reasoning_effort = "medium"\n'
    )
    view = agent_config_service.window_agent_model_view(
        "codex", window_id="win-1", home=tmp_path
    )
    assert view is not None
    assert view["editable"] is False
    assert view["model"] == "legacy-model"
    assert view["codex_model_reasoning_effort"] == "medium"
    assert view["available_models"] == []


def test_window_agent_model_view_returns_none_without_any_signal(tmp_path: Path) -> None:
    view = agent_config_service.window_agent_model_view(
        "codex", window_id="win-empty", home=tmp_path
    )
    assert view is None


def test_update_window_agent_model_merges_reasoning_effort(tmp_path: Path) -> None:
    _seed_preset(tmp_path)
    agent_config_service.apply_window_agent_model_selection(
        "codex",
        agent_config_service.AgentModelSelection(
            preset_id="main", model="model-a", codex_model_reasoning_effort="high"
        ),
        window_id="win-1",
        home=tmp_path,
    )
    agent_config_service.update_window_agent_model(
        "codex",
        agent_config_service.WindowAgentModelUpdate(codex_model_reasoning_effort="minimal"),
        window_id="win-1",
        home=tmp_path,
    )
    config_toml = (
        tmp_path / ".web-terminal-acp" / "codex-homes" / "win-1" / "config.toml"
    ).read_text()
    assert 'model_reasoning_effort = "minimal"' in config_toml
    selection = agent_config_service.load_window_agent_model_selection(
        "codex", window_id="win-1", home=tmp_path
    )
    assert selection.codex_model_reasoning_effort == "minimal"
    assert selection.model == "model-a"


def test_update_window_agent_model_switches_model(tmp_path: Path) -> None:
    _seed_preset(tmp_path)
    agent_config_service.apply_window_agent_model_selection(
        "codex",
        agent_config_service.AgentModelSelection(preset_id="main", model="model-a"),
        window_id="win-1",
        home=tmp_path,
    )
    agent_config_service.update_window_agent_model(
        "codex",
        agent_config_service.WindowAgentModelUpdate(model="model-b"),
        window_id="win-1",
        home=tmp_path,
    )
    config_toml = (
        tmp_path / ".web-terminal-acp" / "codex-homes" / "win-1" / "config.toml"
    ).read_text()
    assert 'model = "model-b"' in config_toml


def test_update_window_agent_model_clears_effort(tmp_path: Path) -> None:
    _seed_preset(tmp_path)
    agent_config_service.apply_window_agent_model_selection(
        "codex",
        agent_config_service.AgentModelSelection(
            preset_id="main", model="model-a", codex_model_reasoning_effort="high"
        ),
        window_id="win-1",
        home=tmp_path,
    )
    agent_config_service.update_window_agent_model(
        "codex",
        agent_config_service.WindowAgentModelUpdate(clear_codex_model_reasoning_effort=True),
        window_id="win-1",
        home=tmp_path,
    )
    selection = agent_config_service.load_window_agent_model_selection(
        "codex", window_id="win-1", home=tmp_path
    )
    assert selection.codex_model_reasoning_effort is None


def test_update_window_agent_model_raises_without_persisted_selection(tmp_path: Path) -> None:
    _seed_preset(tmp_path)
    try:
        agent_config_service.update_window_agent_model(
            "codex",
            agent_config_service.WindowAgentModelUpdate(codex_model_reasoning_effort="high"),
            window_id="lonely",
            home=tmp_path,
        )
    except ValueError as exc:
        assert "model preset" in str(exc) or "relaunch" in str(exc)
        return
    raise AssertionError("expected ValueError for missing persisted selection")
