from dataclasses import dataclass
from importlib import import_module as _import_module

# ruff: noqa: F821

for _module_name in (
    "config_service",
    "config_items",
    "config_plugins",
    "config_mcp",
    "config_system",
    "config_model_types",
    "config_model_payload",
    "config_model_presets",
):
    _module = _import_module(f"{__package__}.{_module_name}")
    globals().update(
        {name: value for name, value in _module.__dict__.items() if not name.startswith("__")}
    )


def list_system_model_presets(*, home: Path | None = None) -> SystemModelPresetList:
    return _system_model_preset_list(_system_model_presets((home or Path.home())).values())


def system_model_preset_list_from_payload(value: object) -> SystemModelPresetList:
    return _system_model_preset_list(_system_model_presets_from_payload(value).values())


def legacy_system_model_preset_payload(*, home: Path | None = None) -> dict[str, object]:
    return _system_model_preset_payload(_system_model_presets(home or Path.home()).values())


def upsert_system_model_preset_payload(
    value: object,
    preset: SystemModelPreset,
) -> tuple[dict[str, object], SystemModelPresetList]:
    clean = _validate_model_preset(preset)
    presets = _system_model_presets_from_payload(value)
    presets[clean.id] = clean
    payload = _system_model_preset_payload(presets.values())
    return payload, system_model_preset_list_from_payload(payload)


def delete_system_model_preset_payload(
    value: object,
    preset_id: str,
) -> tuple[dict[str, object], SystemModelPresetList]:
    _validate_json_key_item_id(preset_id)
    presets = _system_model_presets_from_payload(value)
    if presets.pop(preset_id, None) is None:
        raise ValueError(f"model preset not found: {preset_id}")
    payload = _system_model_preset_payload(presets.values())
    return payload, system_model_preset_list_from_payload(payload)


def upsert_system_model_preset(
    preset: SystemModelPreset,
    *,
    home: Path | None = None,
) -> SystemModelPresetList:
    user_home = home or Path.home()
    clean = _validate_model_preset(preset)
    root = _system_config_root(user_home)
    path = root / SYSTEM_MODEL_PRESETS_FILE
    with _locked_config_writes(path):
        data = _read_json_file(path)
        records = _ensure_model_preset_records(data)
        records[clean.id] = _model_preset_payload(clean)
        _write_json_file(path, data)
    return list_system_model_presets(home=user_home)


def delete_system_model_preset(preset_id: str, *, home: Path | None = None) -> SystemModelPresetList:
    _validate_json_key_item_id(preset_id)
    user_home = home or Path.home()
    path = _system_config_root(user_home) / SYSTEM_MODEL_PRESETS_FILE
    with _locked_config_writes(path):
        data = _read_json_file(path)
        records = _ensure_model_preset_records(data)
        if records.pop(preset_id, None) is None:
            raise ValueError(f"model preset not found: {preset_id}")
        _write_json_file(path, data)
    return list_system_model_presets(home=user_home)


def resolve_agent_model_selection(
    agent: str,
    selection: AgentModelSelection | None,
    *,
    home: Path | None = None,
) -> ResolvedAgentModelSettings | None:
    return _resolve_agent_model_selection_from_presets(
        agent,
        selection,
        _system_model_presets(home or Path.home()),
    )


def resolve_agent_model_selection_from_presets(
    agent: str,
    selection: AgentModelSelection | None,
    preset_list: SystemModelPresetList,
) -> ResolvedAgentModelSettings | None:
    return _resolve_agent_model_selection_from_presets(
        agent,
        selection,
        {preset.id: preset for preset in preset_list.presets},
    )


def _resolve_agent_model_selection_from_presets(
    agent: str,
    selection: AgentModelSelection | None,
    presets: dict[str, SystemModelPreset],
) -> ResolvedAgentModelSettings | None:
    if selection is None:
        return None
    agent_kind = _agent_kind(agent)
    if agent_kind not in {"codex", "claude"}:
        raise ValueError("model settings are only supported for Codex and Claude Code")
    preset = presets.get(selection.preset_id)
    if preset is None:
        raise ValueError(f"model preset not found: {selection.preset_id}")
    provider = _provider_for_agent(agent_kind, preset)
    model = _selected_model_for_agent(agent_kind, preset, selection)
    model_config = _model_config_for_name(preset, model)
    return ResolvedAgentModelSettings(
        preset_id=preset.id,
        provider=provider,
        base_url=preset.base_url,
        api_key=preset.api_key,
        model=model,
        max_output_tokens=model_config.max_output_tokens,
        context_window=model_config.context_window,
        auto_compact_token_limit=model_config.auto_compact_token_limit,
        claude=_resolved_claude_routing(preset, selection) if agent_kind == "claude" else None,
        codex_model_reasoning_effort=_resolved_codex_reasoning_effort(
            selection.codex_model_reasoning_effort,
            model_config.codex_model_reasoning_effort,
        ),
        codex_plan_mode_reasoning_effort=_resolved_codex_reasoning_effort(
            selection.codex_plan_mode_reasoning_effort,
            model_config.codex_plan_mode_reasoning_effort,
        ),
        claude_reasoning_effort=_resolved_claude_reasoning_effort(
            selection.claude_reasoning_effort,
            model_config.claude_reasoning_effort,
        ),
    )


def _resolved_codex_reasoning_effort(override: str | None, default: str | None) -> str | None:
    candidate = override if override is not None else default
    return candidate if candidate in CODEX_REASONING_EFFORTS else None


def _resolved_claude_reasoning_effort(override: str | None, default: str | None) -> str | None:
    candidate = override if override is not None else default
    return candidate if candidate in CLAUDE_REASONING_EFFORTS else None


def materialize_agent_model_settings_for_window(
    agent: str,
    settings: ResolvedAgentModelSettings | None,
    *,
    window_id: str,
    home: Path | None = None,
) -> None:
    if settings is None:
        return
    agent_kind = _agent_kind(agent)
    if agent_kind == "codex":
        _materialize_codex_model_settings(settings, window_id=window_id, home=home)
        return
    if agent_kind == "claude":
        _materialize_claude_model_settings(settings, window_id=window_id, home=home)
        return
    raise ValueError("model settings are only supported for Codex and Claude Code")


def resolved_agent_model_settings_payload(settings: ResolvedAgentModelSettings | None) -> dict[str, object] | None:
    if settings is None:
        return None
    payload: dict[str, object] = {
        "preset_id": settings.preset_id,
        "provider": settings.provider,
        "base_url": settings.base_url,
        "api_key": settings.api_key,
        "model": settings.model,
    }
    if settings.max_output_tokens is not None:
        payload["max_output_tokens"] = settings.max_output_tokens
    if settings.context_window is not None:
        payload["context_window"] = settings.context_window
    if settings.auto_compact_token_limit is not None:
        payload["auto_compact_token_limit"] = settings.auto_compact_token_limit
    if settings.claude is not None:
        payload["claude"] = _claude_routing_payload(settings.claude)
    if settings.codex_model_reasoning_effort is not None:
        payload["codex_model_reasoning_effort"] = settings.codex_model_reasoning_effort
    if settings.codex_plan_mode_reasoning_effort is not None:
        payload["codex_plan_mode_reasoning_effort"] = settings.codex_plan_mode_reasoning_effort
    if settings.claude_reasoning_effort is not None:
        payload["claude_reasoning_effort"] = settings.claude_reasoning_effort
    return payload


def safe_agent_model_settings_payload(settings: ResolvedAgentModelSettings | None) -> dict[str, object] | None:
    if settings is None:
        return None
    payload: dict[str, object] = {
        "preset_id": settings.preset_id,
        "provider": settings.provider,
        "model": settings.model,
    }
    if settings.max_output_tokens is not None:
        payload["max_output_tokens"] = settings.max_output_tokens
    if settings.context_window is not None:
        payload["context_window"] = settings.context_window
    if settings.auto_compact_token_limit is not None:
        payload["auto_compact_token_limit"] = settings.auto_compact_token_limit
    if settings.claude is not None:
        payload["claude"] = _claude_routing_payload(settings.claude)
    if settings.codex_model_reasoning_effort is not None:
        payload["codex_model_reasoning_effort"] = settings.codex_model_reasoning_effort
    if settings.codex_plan_mode_reasoning_effort is not None:
        payload["codex_plan_mode_reasoning_effort"] = settings.codex_plan_mode_reasoning_effort
    if settings.claude_reasoning_effort is not None:
        payload["claude_reasoning_effort"] = settings.claude_reasoning_effort
    return payload


def resolved_agent_model_settings_from_payload(value: object) -> ResolvedAgentModelSettings | None:
    if not isinstance(value, dict):
        return None
    preset_id = _string(value.get("preset_id"))
    provider = _string(value.get("provider"))
    base_url = _string(value.get("base_url"))
    model = _string(value.get("model"))
    if preset_id is None or provider is None or base_url is None or model is None:
        return None
    api_key = value.get("api_key")
    claude = _claude_routing_from_payload(value.get("claude"))
    return ResolvedAgentModelSettings(
        preset_id=preset_id,
        provider=provider,
        base_url=base_url,
        api_key=api_key if isinstance(api_key, str) else "",
        model=model,
        max_output_tokens=_positive_int(value.get("max_output_tokens")),
        context_window=_positive_int(value.get("context_window")),
        auto_compact_token_limit=_positive_int(value.get("auto_compact_token_limit")),
        claude=claude,
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


WINDOW_MODEL_SELECTION_FILE = "model-selection.json"


def save_window_agent_model_selection(
    agent: str,
    selection: AgentModelSelection,
    *,
    window_id: str,
    home: Path | None = None,
) -> None:
    agent_kind = _agent_kind(agent)
    if agent_kind not in {"codex", "claude"}:
        raise ValueError("model settings are only supported for Codex and Claude Code")
    user_home = home or Path.home()
    managed_root = _managed_agent_root(agent_kind, window_id, user_home)
    managed_root.mkdir(parents=True, exist_ok=True)
    path = managed_root / WINDOW_MODEL_SELECTION_FILE
    _write_json_file(path, _agent_model_selection_payload(selection))


def load_window_agent_model_selection(
    agent: str,
    *,
    window_id: str,
    home: Path | None = None,
) -> AgentModelSelection | None:
    agent_kind = _agent_kind(agent)
    if agent_kind not in {"codex", "claude"}:
        return None
    user_home = home or Path.home()
    path = _managed_agent_root(agent_kind, window_id, user_home) / WINDOW_MODEL_SELECTION_FILE
    if not path.is_file():
        return None
    return agent_model_selection_from_payload(_read_json_file(path))


def _agent_model_selection_payload(selection: AgentModelSelection) -> dict[str, object]:
    payload: dict[str, object] = {"preset_id": selection.preset_id}
    if selection.model is not None:
        payload["model"] = selection.model
    if selection.claude is not None:
        payload["claude"] = _claude_routing_payload(selection.claude)
    if selection.codex_model_reasoning_effort is not None:
        payload["codex_model_reasoning_effort"] = selection.codex_model_reasoning_effort
    if selection.codex_plan_mode_reasoning_effort is not None:
        payload["codex_plan_mode_reasoning_effort"] = selection.codex_plan_mode_reasoning_effort
    if selection.claude_reasoning_effort is not None:
        payload["claude_reasoning_effort"] = selection.claude_reasoning_effort
    return payload


def apply_window_agent_model_selection(
    agent: str,
    selection: AgentModelSelection | None,
    *,
    window_id: str,
    home: Path | None = None,
) -> None:
    if selection is not None:
        save_window_agent_model_selection(agent, selection, window_id=window_id, home=home)
    settings = resolve_agent_model_selection(agent, selection, home=home)
    materialize_agent_model_settings_for_window(agent, settings, window_id=window_id, home=home)


@dataclass(frozen=True)
class WindowAgentModelUpdate:
    model: str | None = None
    codex_model_reasoning_effort: str | None = None
    codex_plan_mode_reasoning_effort: str | None = None
    claude_reasoning_effort: str | None = None
    clear_codex_model_reasoning_effort: bool = False
    clear_codex_plan_mode_reasoning_effort: bool = False
    clear_claude_reasoning_effort: bool = False


def window_agent_model_view(
    agent: str,
    *,
    window_id: str,
    home: Path | None = None,
    preset_list: SystemModelPresetList | None = None,
) -> dict[str, object] | None:
    agent_kind = _agent_kind(agent)
    if agent_kind not in {"codex", "claude"}:
        return None
    provider = "codex" if agent_kind == "codex" else "claude_code"
    base: dict[str, object] = {
        "editable": False,
        "provider": provider,
        "preset_id": None,
        "preset_name": None,
        "model": None,
        "available_models": [],
        "codex_model_reasoning_effort": None,
        "codex_plan_mode_reasoning_effort": None,
        "claude_reasoning_effort": None,
        "codex_reasoning_efforts": list(CODEX_REASONING_EFFORTS),
        "claude_reasoning_efforts": list(CLAUDE_REASONING_EFFORTS),
    }
    selection = load_window_agent_model_selection(agent, window_id=window_id, home=home)
    if selection is None:
        metadata = window_agent_model_metadata(agent, window_id=window_id, home=home)
        if metadata is None:
            return None
        return _window_model_view_from_metadata(base, metadata)
    presets = preset_list if preset_list is not None else list_system_model_presets(home=home)
    preset = next((p for p in presets.presets if p.id == selection.preset_id), None)
    if preset is None:
        metadata = window_agent_model_metadata(agent, window_id=window_id, home=home)
        return _window_model_view_from_metadata(base, metadata) if metadata is not None else base
    try:
        if preset_list is not None:
            settings = resolve_agent_model_selection_from_presets(agent, selection, preset_list)
        else:
            settings = resolve_agent_model_selection(agent, selection, home=home)
    except ValueError:
        settings = None
    available_models = (
        [c.name for c in preset.model_configs] if preset.model_configs else list(preset.models)
    )
    fallback_model = selection.model or (available_models[0] if available_models else None)
    view: dict[str, object] = {
        **base,
        "editable": True,
        "preset_id": preset.id,
        "preset_name": preset.name,
        "model": settings.model if settings is not None else fallback_model,
        "available_models": available_models,
    }
    if settings is not None:
        if agent_kind == "codex":
            view["codex_model_reasoning_effort"] = settings.codex_model_reasoning_effort
            view["codex_plan_mode_reasoning_effort"] = settings.codex_plan_mode_reasoning_effort
        else:
            view["claude_reasoning_effort"] = settings.claude_reasoning_effort
    return view


def _window_model_view_from_metadata(
    base: dict[str, object],
    metadata: dict[str, object],
) -> dict[str, object]:
    view: dict[str, object] = {**base, "editable": False}
    if "provider" in metadata:
        view["provider"] = metadata["provider"]
    if "model" in metadata:
        view["model"] = metadata["model"]
    if "reasoning_effort" in metadata:
        view["claude_reasoning_effort"] = metadata["reasoning_effort"]
    if "model_reasoning_effort" in metadata:
        view["codex_model_reasoning_effort"] = metadata["model_reasoning_effort"]
    if "plan_mode_reasoning_effort" in metadata:
        view["codex_plan_mode_reasoning_effort"] = metadata["plan_mode_reasoning_effort"]
    return view


def update_window_agent_model(
    agent: str,
    update: WindowAgentModelUpdate,
    *,
    window_id: str,
    home: Path | None = None,
    preset_list: SystemModelPresetList | None = None,
) -> AgentConfig:
    agent_kind = _agent_kind(agent)
    if agent_kind not in {"codex", "claude"}:
        raise ValueError("model settings are only supported for Codex and Claude Code")
    selection = load_window_agent_model_selection(agent, window_id=window_id, home=home)
    if selection is None:
        raise ValueError(
            "no persisted model selection for this window; relaunch with a model preset to enable live model adjustment"
        )
    merged = _merge_window_agent_model_selection(selection, update, agent_kind=agent_kind)
    if preset_list is not None:
        settings = resolve_agent_model_selection_from_presets(agent, merged, preset_list)
    else:
        settings = resolve_agent_model_selection(agent, merged, home=home)
    save_window_agent_model_selection(agent, merged, window_id=window_id, home=home)
    materialize_agent_model_settings_for_window(agent, settings, window_id=window_id, home=home)
    return list_window_agent_config(agent, window_id=window_id, home=home)


def _merge_window_agent_model_selection(
    selection: AgentModelSelection,
    update: WindowAgentModelUpdate,
    *,
    agent_kind: str,
) -> AgentModelSelection:
    model = update.model if update.model is not None else selection.model
    if agent_kind == "codex":
        codex_model_effort = _merged_effort(
            update.codex_model_reasoning_effort,
            update.clear_codex_model_reasoning_effort,
            selection.codex_model_reasoning_effort,
        )
        codex_plan_effort = _merged_effort(
            update.codex_plan_mode_reasoning_effort,
            update.clear_codex_plan_mode_reasoning_effort,
            selection.codex_plan_mode_reasoning_effort,
        )
        return AgentModelSelection(
            preset_id=selection.preset_id,
            model=model,
            claude=selection.claude,
            codex_model_reasoning_effort=codex_model_effort,
            codex_plan_mode_reasoning_effort=codex_plan_effort,
            claude_reasoning_effort=None,
        )
    claude_effort = _merged_effort(
        update.claude_reasoning_effort,
        update.clear_claude_reasoning_effort,
        selection.claude_reasoning_effort,
    )
    return AgentModelSelection(
        preset_id=selection.preset_id,
        model=model,
        claude=selection.claude,
        codex_model_reasoning_effort=None,
        codex_plan_mode_reasoning_effort=None,
        claude_reasoning_effort=claude_effort,
    )


def _merged_effort(
    incoming: str | None,
    clear: bool,
    current: str | None,
) -> str | None:
    if clear:
        return None
    if incoming is not None:
        return incoming
    return current


def agent_model_selection_from_payload(value: object) -> AgentModelSelection | None:
    if not isinstance(value, dict):
        return None
    preset_id = _string(value.get("preset_id"))
    if preset_id is None:
        return None
    return AgentModelSelection(
        preset_id=preset_id,
        model=_string(value.get("model")),
        claude=_claude_routing_from_payload(value.get("claude")),
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
