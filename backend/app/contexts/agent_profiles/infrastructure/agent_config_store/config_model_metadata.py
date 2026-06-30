from importlib import import_module as _import_module

for _module_name in (
    "config_service",
    "config_items",
    "config_plugins",
    "config_mcp",
    "config_system",
    "config_model_settings",
    "config_model_materialization",
):
    _module = _import_module(f"{__package__}.{_module_name}")
    globals().update(
        {name: value for name, value in _module.__dict__.items() if not name.startswith("__")}
    )


def window_agent_model_metadata(
    agent: str,
    *,
    window_id: str,
    home: Path | None = None,
) -> dict[str, object] | None:
    agent_kind = _agent_kind(agent)
    managed_root = _managed_agent_root(agent_kind, window_id, home or Path.home())
    if agent_kind == "claude":
        return _claude_window_model_metadata(managed_root)
    if agent_kind == "codex":
        return _codex_window_model_metadata(managed_root)
    return None


def _claude_window_model_metadata(managed_root: Path) -> dict[str, object] | None:
    env = _claude_settings_env(managed_root / "settings.json")
    env.update(_model_env_file_exports(managed_root / SYSTEM_MODEL_ENV_FILE))
    metadata: dict[str, object] = {"provider": "claude_code"}
    _set_metadata_text(metadata, "base_url", env.get("ANTHROPIC_BASE_URL") or env.get("CLAUDE_CODE_API_BASE_URL"))
    _set_metadata_text(
        metadata,
        "model",
        env.get("ANTHROPIC_DEFAULT_SONNET_MODEL")
        or env.get("ANTHROPIC_DEFAULT_OPUS_MODEL")
        or env.get("ANTHROPIC_DEFAULT_HAIKU_MODEL"),
    )
    _set_metadata_int(metadata, "max_output_tokens", env.get("CLAUDE_CODE_MAX_OUTPUT_TOKENS"))
    _set_metadata_int(metadata, "auto_compact_token_limit", env.get("CLAUDE_CODE_AUTO_COMPACT_WINDOW"))
    _set_metadata_text(metadata, "reasoning_effort", env.get("CLAUDE_CODE_EFFORT_LEVEL"))
    return metadata if len(metadata) > 1 else None


def _codex_window_model_metadata(managed_root: Path) -> dict[str, object] | None:
    config = _toml_scalar_assignments(managed_root / "config.toml")
    metadata: dict[str, object] = {"provider": "codex"}
    _set_metadata_text(metadata, "model", config.get("model"))
    _set_metadata_int(metadata, "max_output_tokens", config.get("max_output_tokens"))
    _set_metadata_int(metadata, "context_window", config.get("model_context_window"))
    _set_metadata_int(metadata, "auto_compact_token_limit", config.get("model_auto_compact_token_limit"))
    _set_metadata_text(metadata, "model_reasoning_effort", config.get("model_reasoning_effort"))
    _set_metadata_text(metadata, "plan_mode_reasoning_effort", config.get("plan_mode_reasoning_effort"))
    return metadata if len(metadata) > 1 else None


def _claude_settings_env(path: Path) -> dict[str, str]:
    data = _read_json_file(path)
    env = data.get("env")
    if not isinstance(env, dict):
        return {}
    return {key: value for key, value in env.items() if isinstance(key, str) and isinstance(value, str)}


def _model_env_file_exports(path: Path) -> dict[str, str]:
    result: dict[str, str] = {}
    if not path.is_file():
        return result
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return result
    for line in lines:
        key, value = _export_assignment(line)
        if key is not None and value is not None:
            result[key] = value
    return result


def _export_assignment(line: str) -> tuple[str | None, str | None]:
    match = re.match(r"\s*export\s+([A-Za-z_][A-Za-z0-9_]*)=(.*)\s*$", line)
    if match is None:
        return None, None
    raw = match.group(2).strip()
    if len(raw) >= 2 and raw[0] == raw[-1] and raw[0] in {"'", '"'}:
        raw = raw[1:-1]
    return match.group(1), raw


def _toml_scalar_assignments(path: Path) -> dict[str, str]:
    result: dict[str, str] = {}
    if not path.is_file():
        return result
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return result
    for line in lines:
        if line.lstrip().startswith("["):
            break
        key, value = _toml_assignment(line)
        if key is not None and value is not None:
            result[key] = value
    return result


def _toml_assignment(line: str) -> tuple[str | None, str | None]:
    match = re.match(r"\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*?)\s*(?:#.*)?$", line)
    if match is None:
        return None, None
    raw = match.group(2).strip()
    if len(raw) >= 2 and raw[0] == raw[-1] and raw[0] in {"'", '"'}:
        raw = raw[1:-1]
    return match.group(1), raw


def _set_metadata_text(metadata: dict[str, object], key: str, value: object) -> None:
    if isinstance(value, str) and value.strip():
        metadata[key] = value.strip()


def _set_metadata_int(metadata: dict[str, object], key: str, value: object) -> None:
    parsed = _positive_int(value)
    if parsed is not None:
        metadata[key] = parsed
