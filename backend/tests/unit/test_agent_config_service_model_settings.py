from tests.unit.test_agent_config_service_support import *


def _preset(
    preset_id: str = "main",
    *,
    provider: str = "openai_compatible",
    providers: list[str] | None = None,
    models: list[str] | None = None,
):
    return agent_config_service.SystemModelPreset(
        id=preset_id,
        name="Main",
        provider=provider,
        providers=[provider] if providers is None else providers,
        base_url="https://models.example.com/v1",
        api_key="secret-key",
        models=models or ["model-a", "model-b"],
    )


def _preset_with_model_limits(
    preset_id: str = "main",
    *,
    provider: str = "openai_compatible",
) -> agent_config_service.SystemModelPreset:
    return agent_config_service.SystemModelPreset(
        id=preset_id,
        name="Main",
        provider=provider,
        providers=[provider],
        base_url="https://models.example.com/v1",
        api_key="secret-key",
        models=["model-a", "model-b"],
        model_configs=[
            agent_config_service.SystemModelConfig(
                name="model-a",
                max_output_tokens=4096,
                context_window=128000,
                auto_compact_token_limit=96000,
            ),
            agent_config_service.SystemModelConfig(
                name="model-b",
                max_output_tokens=8192,
                context_window=258400,
                auto_compact_token_limit=200000,
            ),
        ],
    )


def _payload_with_preset(preset: agent_config_service.SystemModelPreset) -> dict[str, object]:
    payload, _preset_list = agent_config_service.upsert_system_model_preset_payload({}, preset)
    return payload


def test_system_model_presets_upsert_list_and_delete_payload() -> None:
    payload, created = agent_config_service.upsert_system_model_preset_payload({}, _preset())

    assert [preset.id for preset in created.presets] == ["main"]
    assert created.presets[0].provider == "openai_compatible"
    assert created.presets[0].providers == ["openai_compatible"]
    assert created.presets[0].models == ["model-a", "model-b"]
    assert payload["presets"]["main"]["models"] == ["model-a", "model-b"]

    payload, deleted = agent_config_service.delete_system_model_preset_payload(payload, "main")

    assert deleted.presets == []
    assert payload == {"presets": {}}


def test_system_model_presets_store_per_model_token_limits_payload() -> None:
    payload, created = agent_config_service.upsert_system_model_preset_payload(
        {},
        _preset_with_model_limits("limited-main"),
    )

    preset = created.presets[0]
    assert preset.models == ["model-a", "model-b"]
    assert preset.model_configs[1].name == "model-b"
    assert preset.model_configs[1].max_output_tokens == 8192
    assert preset.model_configs[1].context_window == 258400
    assert preset.model_configs[1].auto_compact_token_limit == 200000

    assert payload["presets"]["limited-main"]["model_configs"][1] == {
        "name": "model-b",
        "max_output_tokens": 8192,
        "context_window": 258400,
        "auto_compact_token_limit": 200000,
    }


def test_system_model_presets_accept_multiple_compatible_providers() -> None:
    payload = _payload_with_preset(
        _preset("dual-main", providers=["openai_compatible", "anthropic_compatible"]),
    )

    presets = agent_config_service.system_model_preset_list_from_payload(payload)
    assert presets.presets[0].providers == ["openai_compatible", "anthropic_compatible"]

    codex = agent_config_service.resolve_agent_model_selection_from_presets(
        "codex",
        agent_config_service.AgentModelSelection(preset_id="dual-main", model="model-b"),
        presets,
    )
    claude = agent_config_service.resolve_agent_model_selection_from_presets(
        "claude",
        agent_config_service.AgentModelSelection(
            preset_id="dual-main",
            claude=agent_config_service.ClaudeModelRouting(mode="all", model="model-a"),
        ),
        presets,
    )

    assert codex is not None
    assert codex.provider == "openai_compatible"
    assert claude is not None
    assert claude.provider == "anthropic_compatible"


def test_system_model_presets_read_legacy_single_provider_records(tmp_path: Path) -> None:
    path = tmp_path / ".web-terminal-acp" / "system-config" / "model-presets.json"
    path.parent.mkdir(parents=True)
    path.write_text(
        json.dumps({
            "presets": {
                "legacy": {
                    "name": "Legacy",
                    "provider": "anthropic_compatible",
                    "base_url": "https://models.example.com/v1",
                    "api_key": "secret-key",
                    "models": ["model-a"],
                }
            }
        }),
        encoding="utf-8",
    )

    presets = agent_config_service.list_system_model_presets(home=tmp_path)

    assert presets.presets[0].provider == "anthropic_compatible"
    assert presets.presets[0].providers == ["anthropic_compatible"]


def test_system_model_presets_reject_empty_provider_selection() -> None:
    with pytest.raises(ValueError, match="unsupported model provider"):
        agent_config_service.upsert_system_model_preset_payload(
            {},
            _preset("empty-provider", provider="", providers=[]),
        )


def test_resolve_agent_model_selection_validates_agent_provider_and_model() -> None:
    payload = _payload_with_preset(
        _preset("anthropic", provider="anthropic_compatible"),
    )
    presets = agent_config_service.system_model_preset_list_from_payload(payload)

    with pytest.raises(ValueError, match="OpenAI-compatible"):
        agent_config_service.resolve_agent_model_selection_from_presets(
            "codex",
            agent_config_service.AgentModelSelection(preset_id="anthropic", model="model-a"),
            presets,
        )

    with pytest.raises(ValueError, match="not available"):
        agent_config_service.resolve_agent_model_selection_from_presets(
            "claude",
            agent_config_service.AgentModelSelection(
                preset_id="anthropic",
                claude=agent_config_service.ClaudeModelRouting(mode="all", model="missing-model"),
            ),
            presets,
        )


def test_materialize_codex_model_settings_for_window(tmp_path: Path) -> None:
    codex_home = tmp_path / ".codex"
    codex_home.mkdir()
    (codex_home / "config.toml").write_text(
        '[mcp_servers.filesystem]\ncommand = "echo"\n',
        encoding="utf-8",
    )
    (codex_home / "auth.json").write_text(
        json.dumps({"OPENAI_API_KEY": "old-key", "refresh_token": "keep-me"}) + "\n",
        encoding="utf-8",
    )
    agent_config_service.upsert_system_model_preset(_preset_with_model_limits("openai-main"), home=tmp_path)
    settings = agent_config_service.resolve_agent_model_selection(
        "codex",
        agent_config_service.AgentModelSelection(preset_id="openai-main", model="model-b"),
        home=tmp_path,
    )

    agent_config_service.materialize_agent_model_settings_for_window(
        "codex",
        settings,
        window_id="window-1",
        home=tmp_path,
    )

    managed = tmp_path / ".web-terminal-acp" / "codex-homes" / "window-1"
    config = (managed / "config.toml").read_text(encoding="utf-8")
    auth = json.loads((managed / "auth.json").read_text(encoding="utf-8"))
    env_file = (managed / "model-env.sh").read_text(encoding="utf-8")
    assert 'model = "model-b"' in config
    assert 'model_provider = "web_terminal_openai_main"' in config
    assert "max_output_tokens = 8192" in config
    assert "model_context_window = 258400" in config
    assert "model_auto_compact_token_limit = 200000" in config
    assert "[model_providers.web_terminal_openai_main]" in config
    assert 'base_url = "https://models.example.com/v1"' in config
    assert 'env_key = "OPENAI_API_KEY"' in config
    assert "requires_openai_auth = true" in config
    assert '[mcp_servers.filesystem]' in config
    assert auth["OPENAI_API_KEY"] == "secret-key"
    assert auth["refresh_token"] == "keep-me"
    source_auth = json.loads((codex_home / "auth.json").read_text(encoding="utf-8"))
    assert source_auth["OPENAI_API_KEY"] == "old-key"
    assert "export OPENAI_API_KEY='secret-key'" in env_file


def test_materialize_codex_model_settings_removes_empty_auth_key(tmp_path: Path) -> None:
    codex_home = tmp_path / ".codex"
    codex_home.mkdir()
    (codex_home / "auth.json").write_text(
        json.dumps({"OPENAI_API_KEY": "old-key", "refresh_token": "keep-me"}) + "\n",
        encoding="utf-8",
    )
    agent_config_service.upsert_system_model_preset(
        agent_config_service.SystemModelPreset(
            id="openai-main",
            name="Main",
            provider="openai_compatible",
            providers=["openai_compatible"],
            base_url="https://models.example.com/v1",
            api_key="",
            models=["model-a"],
        ),
        home=tmp_path,
    )
    settings = agent_config_service.resolve_agent_model_selection(
        "codex",
        agent_config_service.AgentModelSelection(preset_id="openai-main", model="model-a"),
        home=tmp_path,
    )

    agent_config_service.materialize_agent_model_settings_for_window(
        "codex",
        settings,
        window_id="window-1",
        home=tmp_path,
    )

    managed = tmp_path / ".web-terminal-acp" / "codex-homes" / "window-1"
    auth = json.loads((managed / "auth.json").read_text(encoding="utf-8"))
    env_file = (managed / "model-env.sh").read_text(encoding="utf-8")
    assert "OPENAI_API_KEY" not in auth
    assert auth["refresh_token"] == "keep-me"
    assert "OPENAI_API_KEY" not in env_file
    source_auth = json.loads((codex_home / "auth.json").read_text(encoding="utf-8"))
    assert source_auth["OPENAI_API_KEY"] == "old-key"


def test_materialize_claude_split_model_settings_for_window(tmp_path: Path) -> None:
    claude_home = tmp_path / ".claude"
    claude_home.mkdir()
    (claude_home / "settings.json").write_text('{"permissions": {}}\n', encoding="utf-8")
    agent_config_service.upsert_system_model_preset(
        agent_config_service.SystemModelPreset(
            id="anthropic-main",
            name="Main",
            provider="anthropic_compatible",
            providers=["anthropic_compatible"],
            base_url="https://models.example.com/v1",
            api_key="secret-key",
            models=["opus-x", "sonnet-y", "haiku-z"],
            model_configs=[
                agent_config_service.SystemModelConfig(name="opus-x", max_output_tokens=4096),
                agent_config_service.SystemModelConfig(
                    name="sonnet-y",
                    max_output_tokens=8192,
                    context_window=200000,
                    auto_compact_token_limit=150000,
                ),
                agent_config_service.SystemModelConfig(name="haiku-z", max_output_tokens=2048),
            ],
        ),
        home=tmp_path,
    )
    settings = agent_config_service.resolve_agent_model_selection(
        "claude",
        agent_config_service.AgentModelSelection(
            preset_id="anthropic-main",
            claude=agent_config_service.ClaudeModelRouting(
                mode="split",
                opus_model="opus-x",
                sonnet_model="sonnet-y",
                haiku_model="haiku-z",
            ),
        ),
        home=tmp_path,
    )

    agent_config_service.materialize_agent_model_settings_for_window(
        "claude",
        settings,
        window_id="window-1",
        home=tmp_path,
    )

    managed = tmp_path / ".web-terminal-acp" / "claude-code-homes" / "window-1"
    settings_json = json.loads((managed / "settings.json").read_text(encoding="utf-8"))
    env = settings_json["env"]
    assert env["ANTHROPIC_BASE_URL"] == "https://models.example.com"
    assert env["CLAUDE_CODE_API_BASE_URL"] == "https://models.example.com"
    assert env["ANTHROPIC_API_KEY"] == "secret-key"
    assert env["ANTHROPIC_DEFAULT_OPUS_MODEL"] == "opus-x"
    assert env["ANTHROPIC_DEFAULT_SONNET_MODEL"] == "sonnet-y"
    assert env["ANTHROPIC_DEFAULT_HAIKU_MODEL"] == "haiku-z"
    assert env["CLAUDE_CODE_MAX_OUTPUT_TOKENS"] == "8192"
    assert env["CLAUDE_CODE_AUTO_COMPACT_WINDOW"] == "150000"
    env_file = (managed / "model-env.sh").read_text(encoding="utf-8")
    assert "export ANTHROPIC_API_KEY='secret-key'" in env_file
    assert "export ANTHROPIC_BASE_URL='https://models.example.com'" in env_file
    assert "export CLAUDE_CODE_MAX_OUTPUT_TOKENS='8192'" in env_file
    assert "export CLAUDE_CODE_AUTO_COMPACT_WINDOW='150000'" in env_file


def test_window_agent_model_metadata_reads_claude_settings_env(tmp_path: Path) -> None:
    managed = tmp_path / ".web-terminal-acp" / "claude-code-homes" / "window-1"
    managed.mkdir(parents=True)
    (managed / "settings.json").write_text(
        json.dumps({
            "env": {
                "ANTHROPIC_BASE_URL": "https://models.example.com",
                "ANTHROPIC_DEFAULT_SONNET_MODEL": "sonnet-y",
                "CLAUDE_CODE_AUTO_COMPACT_WINDOW": "150000",
            }
        }),
        encoding="utf-8",
    )

    metadata = agent_config_service.window_agent_model_metadata(
        "claude",
        window_id="window-1",
        home=tmp_path,
    )

    assert metadata == {
        "provider": "claude_code",
        "base_url": "https://models.example.com",
        "model": "sonnet-y",
        "auto_compact_token_limit": 150000,
    }


def _claude_preset_with_api_key(api_key: str) -> agent_config_service.SystemModelPreset:
    return agent_config_service.SystemModelPreset(
        id="anthropic-main",
        name="Main",
        provider="anthropic_compatible",
        providers=["anthropic_compatible"],
        base_url="https://models.example.com/v1",
        api_key=api_key,
        models=["sonnet-y"],
    )


def _materialize_claude_with_api_key(tmp_path: Path, api_key: str) -> Path:
    (tmp_path / ".claude").mkdir(exist_ok=True)
    agent_config_service.upsert_system_model_preset(
        _claude_preset_with_api_key(api_key),
        home=tmp_path,
    )
    settings = agent_config_service.resolve_agent_model_selection(
        "claude",
        agent_config_service.AgentModelSelection(
            preset_id="anthropic-main",
            claude=agent_config_service.ClaudeModelRouting(mode="all", model="sonnet-y"),
        ),
        home=tmp_path,
    )
    agent_config_service.materialize_agent_model_settings_for_window(
        "claude",
        settings,
        window_id="window-1",
        home=tmp_path,
    )
    return tmp_path / ".web-terminal-acp" / "claude-code-homes" / "window-1"


def test_materialize_claude_appends_custom_api_key_to_approved(tmp_path: Path) -> None:
    api_key = "test-ant-api-key-with-suffix-1dc7cd9152d33df8eb3d"
    global_state = tmp_path / ".claude.json"
    global_state.write_text(
        json.dumps(
            {
                "numStartups": 5,
                "customApiKeyResponses": {
                    "approved": ["preexisting00000000000000"],
                    "rejected": [],
                },
                "tipsHistory": {"warmup": 1},
            }
        ),
        encoding="utf-8",
    )

    managed = _materialize_claude_with_api_key(tmp_path, api_key)

    expected_suffix = api_key[-20:]
    assert expected_suffix == "1dc7cd9152d33df8eb3d"

    managed_state = json.loads((managed / ".claude.json").read_text(encoding="utf-8"))
    assert expected_suffix in managed_state["customApiKeyResponses"]["approved"]
    assert "preexisting00000000000000" in managed_state["customApiKeyResponses"]["approved"]
    assert managed_state["customApiKeyResponses"]["rejected"] == []
    assert managed_state["numStartups"] == 5
    assert managed_state["tipsHistory"] == {"warmup": 1}

    global_after = json.loads(global_state.read_text(encoding="utf-8"))
    assert expected_suffix in global_after["customApiKeyResponses"]["approved"]
    assert "preexisting00000000000000" in global_after["customApiKeyResponses"]["approved"]
    assert global_after["numStartups"] == 5
    assert global_after["tipsHistory"] == {"warmup": 1}


def test_materialize_claude_skips_custom_api_key_injection_when_api_key_empty(
    tmp_path: Path,
) -> None:
    global_state = tmp_path / ".claude.json"
    global_state.write_text(
        json.dumps({"customApiKeyResponses": {"approved": [], "rejected": []}}),
        encoding="utf-8",
    )

    managed = _materialize_claude_with_api_key(tmp_path, "")

    managed_state = json.loads((managed / ".claude.json").read_text(encoding="utf-8"))
    assert managed_state["customApiKeyResponses"]["approved"] == []
    global_after = json.loads(global_state.read_text(encoding="utf-8"))
    assert global_after["customApiKeyResponses"]["approved"] == []


def test_materialize_claude_custom_api_key_injection_is_idempotent(tmp_path: Path) -> None:
    api_key = "test-ant-api-key-with-suffix-1dc7cd9152d33df8eb3d"
    (tmp_path / ".claude.json").write_text(
        json.dumps({"customApiKeyResponses": {"approved": [], "rejected": []}}),
        encoding="utf-8",
    )

    _materialize_claude_with_api_key(tmp_path, api_key)
    managed = _materialize_claude_with_api_key(tmp_path, api_key)

    expected_suffix = api_key[-20:]
    managed_state = json.loads((managed / ".claude.json").read_text(encoding="utf-8"))
    assert managed_state["customApiKeyResponses"]["approved"].count(expected_suffix) == 1


def test_materialize_claude_removes_custom_api_key_from_rejected_when_approving(
    tmp_path: Path,
) -> None:
    api_key = "test-ant-api-key-with-suffix-1dc7cd9152d33df8eb3d"
    expected_suffix = api_key[-20:]
    (tmp_path / ".claude.json").write_text(
        json.dumps(
            {
                "customApiKeyResponses": {
                    "approved": [],
                    "rejected": [expected_suffix],
                }
            }
        ),
        encoding="utf-8",
    )

    managed = _materialize_claude_with_api_key(tmp_path, api_key)

    managed_state = json.loads((managed / ".claude.json").read_text(encoding="utf-8"))
    assert expected_suffix in managed_state["customApiKeyResponses"]["approved"]
    assert expected_suffix not in managed_state["customApiKeyResponses"]["rejected"]


def test_materialize_claude_injects_into_missing_custom_api_key_responses(
    tmp_path: Path,
) -> None:
    api_key = "test-ant-api-key-with-suffix-1dc7cd9152d33df8eb3d"
    (tmp_path / ".claude.json").write_text(
        json.dumps({"numStartups": 1}),
        encoding="utf-8",
    )

    managed = _materialize_claude_with_api_key(tmp_path, api_key)

    expected_suffix = api_key[-20:]
    managed_state = json.loads((managed / ".claude.json").read_text(encoding="utf-8"))
    assert managed_state["customApiKeyResponses"] == {
        "approved": [expected_suffix],
        "rejected": [],
    }
    assert managed_state["numStartups"] == 1


def _preset_with_reasoning_effort(
    preset_id: str = "effort-main",
    *,
    provider: str = "openai_compatible",
    providers: list[str] | None = None,
) -> agent_config_service.SystemModelPreset:
    provider_list = [provider] if providers is None else providers
    return agent_config_service.SystemModelPreset(
        id=preset_id,
        name="Effort",
        provider=provider_list[0],
        providers=provider_list,
        base_url="https://models.example.com/v1",
        api_key="secret-key",
        models=["model-a"],
        model_configs=[
            agent_config_service.SystemModelConfig(
                name="model-a",
                codex_model_reasoning_effort="high",
                codex_plan_mode_reasoning_effort="medium",
                claude_reasoning_effort="max",
            ),
        ],
    )


def test_system_model_presets_persist_per_model_reasoning_effort() -> None:
    payload, created = agent_config_service.upsert_system_model_preset_payload(
        {},
        _preset_with_reasoning_effort(),
    )

    config = created.presets[0].model_configs[0]
    assert config.codex_model_reasoning_effort == "high"
    assert config.codex_plan_mode_reasoning_effort == "medium"
    assert config.claude_reasoning_effort == "max"

    assert payload["presets"]["effort-main"]["model_configs"][0] == {
        "name": "model-a",
        "codex_model_reasoning_effort": "high",
        "codex_plan_mode_reasoning_effort": "medium",
        "claude_reasoning_effort": "max",
    }


def test_system_model_presets_drop_unknown_reasoning_effort_values() -> None:
    payload = {
        "presets": {
            "effort-main": {
                "name": "Effort",
                "provider": "openai_compatible",
                "providers": ["openai_compatible"],
                "base_url": "https://models.example.com/v1",
                "api_key": "secret-key",
                "model_configs": [
                    {
                        "name": "model-a",
                        "codex_model_reasoning_effort": "absurd",
                        "claude_reasoning_effort": "nope",
                    }
                ],
            }
        }
    }

    presets = agent_config_service.system_model_preset_list_from_payload(payload)
    config = presets.presets[0].model_configs[0]
    assert config.codex_model_reasoning_effort is None
    assert config.claude_reasoning_effort is None


def test_resolve_codex_reasoning_effort_uses_model_config_default() -> None:
    presets = agent_config_service.system_model_preset_list_from_payload(
        _payload_with_preset(_preset_with_reasoning_effort())
    )
    resolved = agent_config_service.resolve_agent_model_selection_from_presets(
        "codex",
        agent_config_service.AgentModelSelection(preset_id="effort-main", model="model-a"),
        presets,
    )

    assert resolved is not None
    assert resolved.codex_model_reasoning_effort == "high"
    assert resolved.codex_plan_mode_reasoning_effort == "medium"
    assert resolved.claude_reasoning_effort == "max"


def test_resolve_codex_reasoning_effort_override_takes_precedence() -> None:
    presets = agent_config_service.system_model_preset_list_from_payload(
        _payload_with_preset(_preset_with_reasoning_effort())
    )
    resolved = agent_config_service.resolve_agent_model_selection_from_presets(
        "codex",
        agent_config_service.AgentModelSelection(
            preset_id="effort-main",
            model="model-a",
            codex_model_reasoning_effort="xhigh",
            codex_plan_mode_reasoning_effort="minimal",
        ),
        presets,
    )

    assert resolved is not None
    assert resolved.codex_model_reasoning_effort == "xhigh"
    assert resolved.codex_plan_mode_reasoning_effort == "minimal"


def test_resolve_claude_reasoning_effort_override() -> None:
    presets = agent_config_service.system_model_preset_list_from_payload(
        _payload_with_preset(
            _preset_with_reasoning_effort("anthropic-effort", provider="anthropic_compatible")
        )
    )
    resolved = agent_config_service.resolve_agent_model_selection_from_presets(
        "claude",
        agent_config_service.AgentModelSelection(
            preset_id="anthropic-effort",
            claude=agent_config_service.ClaudeModelRouting(mode="all", model="model-a"),
            claude_reasoning_effort="auto",
        ),
        presets,
    )

    assert resolved is not None
    assert resolved.claude_reasoning_effort == "auto"


def test_resolved_agent_model_settings_payload_round_trips_reasoning_effort() -> None:
    settings = agent_config_service.ResolvedAgentModelSettings(
        preset_id="effort-main",
        provider="openai_compatible",
        base_url="https://models.example.com/v1",
        api_key="secret-key",
        model="model-a",
        codex_model_reasoning_effort="high",
        codex_plan_mode_reasoning_effort="medium",
        claude_reasoning_effort="max",
    )

    payload = agent_config_service.resolved_agent_model_settings_payload(settings)
    assert payload is not None
    assert payload["codex_model_reasoning_effort"] == "high"
    assert payload["codex_plan_mode_reasoning_effort"] == "medium"
    assert payload["claude_reasoning_effort"] == "max"

    safe = agent_config_service.safe_agent_model_settings_payload(settings)
    assert safe is not None
    assert safe["codex_model_reasoning_effort"] == "high"

    restored = agent_config_service.resolved_agent_model_settings_from_payload(payload)
    assert restored is not None
    assert restored.codex_model_reasoning_effort == "high"
    assert restored.codex_plan_mode_reasoning_effort == "medium"
    assert restored.claude_reasoning_effort == "max"


def test_agent_model_selection_payload_round_trips_reasoning_effort() -> None:
    selection = agent_config_service.AgentModelSelection(
        preset_id="effort-main",
        model="model-a",
        codex_model_reasoning_effort="high",
        claude_reasoning_effort="max",
    )

    restored = agent_config_service.agent_model_selection_from_payload(
        {
            "preset_id": "effort-main",
            "model": "model-a",
            "codex_model_reasoning_effort": "high",
            "claude_reasoning_effort": "max",
        }
    )

    assert restored is not None
    assert restored.codex_model_reasoning_effort == "high"
    assert restored.claude_reasoning_effort == "max"


def test_materialize_codex_reasoning_effort_writes_config_keys(tmp_path: Path) -> None:
    (tmp_path / ".codex").mkdir(exist_ok=True)
    agent_config_service.upsert_system_model_preset(
        _preset_with_reasoning_effort("openai-effort"),
        home=tmp_path,
    )
    settings = agent_config_service.resolve_agent_model_selection(
        "codex",
        agent_config_service.AgentModelSelection(
            preset_id="openai-effort",
            model="model-a",
            codex_plan_mode_reasoning_effort="xhigh",
        ),
        home=tmp_path,
    )

    agent_config_service.materialize_agent_model_settings_for_window(
        "codex",
        settings,
        window_id="window-1",
        home=tmp_path,
    )

    config = (
        tmp_path / ".web-terminal-acp" / "codex-homes" / "window-1" / "config.toml"
    ).read_text(encoding="utf-8")
    assert 'model_reasoning_effort = "high"' in config
    assert 'plan_mode_reasoning_effort = "xhigh"' in config


def test_materialize_codex_reasoning_effort_absent_when_unset(tmp_path: Path) -> None:
    (tmp_path / ".codex").mkdir(exist_ok=True)
    agent_config_service.upsert_system_model_preset(
        agent_config_service.SystemModelPreset(
            id="openai-plain",
            name="Plain",
            provider="openai_compatible",
            providers=["openai_compatible"],
            base_url="https://models.example.com/v1",
            api_key="secret-key",
            models=["model-a"],
        ),
        home=tmp_path,
    )
    settings = agent_config_service.resolve_agent_model_selection(
        "codex",
        agent_config_service.AgentModelSelection(preset_id="openai-plain", model="model-a"),
        home=tmp_path,
    )

    agent_config_service.materialize_agent_model_settings_for_window(
        "codex",
        settings,
        window_id="window-1",
        home=tmp_path,
    )

    config = (
        tmp_path / ".web-terminal-acp" / "codex-homes" / "window-1" / "config.toml"
    ).read_text(encoding="utf-8")
    assert "model_reasoning_effort" not in config
    assert "plan_mode_reasoning_effort" not in config


def test_materialize_claude_reasoning_effort_sets_env(tmp_path: Path) -> None:
    (tmp_path / ".claude").mkdir(exist_ok=True)
    agent_config_service.upsert_system_model_preset(
        _preset_with_reasoning_effort("anthropic-effort", provider="anthropic_compatible"),
        home=tmp_path,
    )
    settings = agent_config_service.resolve_agent_model_selection(
        "claude",
        agent_config_service.AgentModelSelection(
            preset_id="anthropic-effort",
            claude=agent_config_service.ClaudeModelRouting(mode="all", model="model-a"),
            claude_reasoning_effort="low",
        ),
        home=tmp_path,
    )

    agent_config_service.materialize_agent_model_settings_for_window(
        "claude",
        settings,
        window_id="window-1",
        home=tmp_path,
    )

    managed = tmp_path / ".web-terminal-acp" / "claude-code-homes" / "window-1"
    settings_json = json.loads((managed / "settings.json").read_text(encoding="utf-8"))
    assert settings_json["env"]["CLAUDE_CODE_EFFORT_LEVEL"] == "low"
    env_file = (managed / "model-env.sh").read_text(encoding="utf-8")
    assert "export CLAUDE_CODE_EFFORT_LEVEL='low'" in env_file


def test_codex_window_model_metadata_reads_reasoning_effort(tmp_path: Path) -> None:
    (tmp_path / ".codex").mkdir(exist_ok=True)
    agent_config_service.upsert_system_model_preset(
        _preset_with_reasoning_effort("openai-effort"),
        home=tmp_path,
    )
    settings = agent_config_service.resolve_agent_model_selection(
        "codex",
        agent_config_service.AgentModelSelection(preset_id="openai-effort", model="model-a"),
        home=tmp_path,
    )
    agent_config_service.materialize_agent_model_settings_for_window(
        "codex",
        settings,
        window_id="window-1",
        home=tmp_path,
    )

    metadata = agent_config_service.window_agent_model_metadata(
        "codex",
        window_id="window-1",
        home=tmp_path,
    )
    assert metadata is not None
    assert metadata["model_reasoning_effort"] == "high"
    assert metadata["plan_mode_reasoning_effort"] == "medium"


def test_claude_window_model_metadata_reads_reasoning_effort(tmp_path: Path) -> None:
    (tmp_path / ".claude").mkdir(exist_ok=True)
    agent_config_service.upsert_system_model_preset(
        _preset_with_reasoning_effort("anthropic-effort", provider="anthropic_compatible"),
        home=tmp_path,
    )
    settings = agent_config_service.resolve_agent_model_selection(
        "claude",
        agent_config_service.AgentModelSelection(
            preset_id="anthropic-effort",
            claude=agent_config_service.ClaudeModelRouting(mode="all", model="model-a"),
        ),
        home=tmp_path,
    )
    agent_config_service.materialize_agent_model_settings_for_window(
        "claude",
        settings,
        window_id="window-1",
        home=tmp_path,
    )

    metadata = agent_config_service.window_agent_model_metadata(
        "claude",
        window_id="window-1",
        home=tmp_path,
    )
    assert metadata is not None
    assert metadata["reasoning_effort"] == "max"
