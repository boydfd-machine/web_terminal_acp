from importlib import import_module as _import_module

# ruff: noqa: F821

for _module_name in (
    "config_service",
    "config_items",
    "config_model_types",
    "config_model_payload",
):
    _module = _import_module(f"{__package__}.{_module_name}")
    globals().update(
        {name: value for name, value in _module.__dict__.items() if not name.startswith("__")}
    )


def _system_model_presets(home: Path) -> dict[str, SystemModelPreset]:
    return _system_model_presets_from_payload(
        _read_json_file(_system_config_root(home) / SYSTEM_MODEL_PRESETS_FILE)
    )


def _system_model_presets_from_payload(value: object) -> dict[str, SystemModelPreset]:
    if not isinstance(value, dict):
        return {}
    records = value.get("presets")
    if not isinstance(records, dict):
        return {}
    presets: dict[str, SystemModelPreset] = {}
    for preset_id, record in records.items():
        if not isinstance(preset_id, str) or not isinstance(record, dict):
            continue
        preset = _model_preset_from_record(preset_id, record)
        if preset is not None:
            presets[preset.id] = preset
    return presets


def _system_model_preset_list(presets: object) -> SystemModelPresetList:
    return SystemModelPresetList(
        presets=sorted(
            presets,
            key=lambda preset: (preset.name.lower(), preset.id.lower()),
        )
    )


def _system_model_preset_payload(presets: object) -> dict[str, object]:
    records: dict[str, object] = {}
    for preset in sorted(
        presets,
        key=lambda item: item.id.lower(),
    ):
        records[preset.id] = _model_preset_payload(preset)
    return {"presets": records}


def _ensure_model_preset_records(data: dict[str, Any]) -> dict[str, Any]:
    presets = data.setdefault("presets", {})
    if not isinstance(presets, dict):
        presets = {}
        data["presets"] = presets
    return presets


def _model_preset_from_record(preset_id: str, record: dict[str, Any]) -> SystemModelPreset | None:
    name = _string(record.get("name")) or preset_id
    legacy_provider = _string(record.get("provider"))
    providers = _model_providers(record.get("providers"), fallback=legacy_provider)
    base_url = _string(record.get("base_url"))
    api_key = record.get("api_key")
    model_configs = _model_configs(record.get("model_configs"), legacy_models=record.get("models"))
    models = [config.name for config in model_configs]
    if not providers or base_url is None or not models:
        return None
    return SystemModelPreset(
        id=preset_id,
        name=name,
        provider=_primary_model_provider(providers, legacy_provider),
        base_url=base_url,
        api_key=api_key if isinstance(api_key, str) else "",
        models=models,
        providers=providers,
        model_configs=model_configs,
    )


def _validate_model_preset(preset: SystemModelPreset) -> SystemModelPreset:
    _validate_json_key_item_id(preset.id)
    name = preset.name.strip() or preset.id
    providers = _model_providers(preset.providers, fallback=preset.provider)
    if not providers:
        raise ValueError(f"unsupported model provider: {preset.provider}")
    provider = _primary_model_provider(providers, preset.provider.strip())
    base_url = preset.base_url.strip()
    if not base_url:
        raise ValueError("model base_url is required")
    if len(base_url) > 2048:
        raise ValueError("model base_url is too long")
    model_configs = _model_configs(preset.model_configs, legacy_models=preset.models)
    models = [config.name for config in model_configs]
    if not models:
        raise ValueError("at least one model is required")
    return SystemModelPreset(
        id=preset.id.strip(),
        name=name[:120],
        provider=provider,
        base_url=base_url,
        api_key=preset.api_key,
        models=models,
        providers=providers,
        model_configs=model_configs,
    )


def _model_providers(value: object, *, fallback: str | None) -> list[str]:
    candidates = value if isinstance(value, list) else []
    providers: list[str] = []
    seen: set[str] = set()
    for item in [*candidates, fallback]:
        if not isinstance(item, str):
            continue
        clean = item.strip()
        if clean in MODEL_PROVIDER_TYPES and clean not in seen:
            seen.add(clean)
            providers.append(clean)
    return providers


def _primary_model_provider(providers: list[str], preferred: str | None) -> str:
    clean = preferred.strip() if isinstance(preferred, str) else ""
    return clean if clean in providers else providers[0]


def _model_names(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    names: list[str] = []
    seen: set[str] = set()
    for item in value:
        if not isinstance(item, str):
            continue
        clean = item.strip()
        if not clean or clean in seen or len(clean) > 255:
            continue
        seen.add(clean)
        names.append(clean)
    return names[:100]


def _model_configs(value: object, *, legacy_models: object = None) -> list[SystemModelConfig]:
    source = value if isinstance(value, list) else []
    configs: list[SystemModelConfig] = []
    seen: set[str] = set()
    for item in source:
        config = _model_config_from_item(item)
        if config is None or config.name in seen:
            continue
        seen.add(config.name)
        configs.append(config)
        if len(configs) >= 100:
            return configs
    for model in _model_names(legacy_models):
        if model in seen:
            continue
        seen.add(model)
        configs.append(SystemModelConfig(name=model))
        if len(configs) >= 100:
            return configs
    return configs


def _model_config_from_item(value: object) -> SystemModelConfig | None:
    if isinstance(value, SystemModelConfig):
        return value
    if isinstance(value, str):
        name = value.strip()
        return SystemModelConfig(name=name) if name and len(name) <= 255 else None
    if not isinstance(value, dict):
        return None
    name = _string(value.get("name"))
    if name is None or len(name.strip()) > 255:
        return None
    return SystemModelConfig(
        name=name.strip(),
        max_output_tokens=_positive_int(value.get("max_output_tokens")),
        context_window=_positive_int(value.get("context_window")),
        auto_compact_token_limit=_positive_int(value.get("auto_compact_token_limit")),
        codex_model_reasoning_effort=_codex_reasoning_effort(
            value.get("codex_model_reasoning_effort")
        ),
        codex_plan_mode_reasoning_effort=_codex_reasoning_effort(
            value.get("codex_plan_mode_reasoning_effort")
        ),
        claude_reasoning_effort=_claude_reasoning_effort(
            value.get("claude_reasoning_effort")
        ),
    )


def _model_preset_payload(preset: SystemModelPreset) -> dict[str, object]:
    return {
        "name": preset.name,
        "provider": preset.provider,
        "providers": preset.providers or [preset.provider],
        "base_url": preset.base_url,
        "api_key": preset.api_key,
        "models": preset.models,
        "model_configs": [_model_config_payload(config) for config in (preset.model_configs or [])],
    }


def _model_config_payload(config: SystemModelConfig) -> dict[str, object]:
    payload: dict[str, object] = {"name": config.name}
    if config.max_output_tokens is not None:
        payload["max_output_tokens"] = config.max_output_tokens
    if config.context_window is not None:
        payload["context_window"] = config.context_window
    if config.auto_compact_token_limit is not None:
        payload["auto_compact_token_limit"] = config.auto_compact_token_limit
    if config.codex_model_reasoning_effort is not None:
        payload["codex_model_reasoning_effort"] = config.codex_model_reasoning_effort
    if config.codex_plan_mode_reasoning_effort is not None:
        payload["codex_plan_mode_reasoning_effort"] = config.codex_plan_mode_reasoning_effort
    if config.claude_reasoning_effort is not None:
        payload["claude_reasoning_effort"] = config.claude_reasoning_effort
    return payload


def _provider_for_agent(agent: str, preset: SystemModelPreset) -> str:
    provider = "openai_compatible" if agent == "codex" else "anthropic_compatible"
    if provider in (preset.providers or [preset.provider]):
        return provider
    if agent == "codex":
        raise ValueError("Codex model settings require an OpenAI-compatible preset")
    raise ValueError("Claude Code model settings require an Anthropic-compatible preset")


def _selected_model_for_agent(
    agent: str,
    preset: SystemModelPreset,
    selection: AgentModelSelection,
) -> str:
    if agent == "claude":
        routing = _resolved_claude_routing(preset, selection)
        if routing.mode == "split":
            return routing.sonnet_model or routing.opus_model or routing.haiku_model or preset.models[0]
        return routing.model or preset.models[0]
    model = selection.model.strip() if selection.model is not None else preset.models[0]
    if not model:
        raise ValueError("selected model is required")
    if model not in preset.models:
        raise ValueError(f"selected model is not available in preset: {model}")
    return model


def _resolved_claude_routing(
    preset: SystemModelPreset,
    selection: AgentModelSelection,
) -> ClaudeModelRouting:
    routing = selection.claude or ClaudeModelRouting(model=selection.model)
    mode = routing.mode if routing.mode in {"all", "split"} else "all"
    if mode == "split":
        opus = _model_or_default(preset, routing.opus_model)
        sonnet = _model_or_default(preset, routing.sonnet_model)
        haiku = _model_or_default(preset, routing.haiku_model)
        return ClaudeModelRouting(
            mode="split",
            opus_model=opus,
            sonnet_model=sonnet,
            haiku_model=haiku,
        )
    return ClaudeModelRouting(mode="all", model=_model_or_default(preset, routing.model))


def _model_or_default(preset: SystemModelPreset, model: str | None) -> str:
    clean = model.strip() if model is not None else preset.models[0]
    if not clean:
        clean = preset.models[0]
    if clean not in preset.models:
        raise ValueError(f"selected model is not available in preset: {clean}")
    return clean


def _model_config_for_name(preset: SystemModelPreset, model: str) -> SystemModelConfig:
    for config in preset.model_configs or []:
        if config.name == model:
            return config
    return SystemModelConfig(name=model)


__all__ = [name for name in globals() if not name.startswith("__")]
