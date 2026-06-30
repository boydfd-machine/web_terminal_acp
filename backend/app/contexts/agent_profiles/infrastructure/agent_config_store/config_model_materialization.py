from importlib import import_module as _import_module

for _module_name in (
    "config_service",
    "config_items",
    "config_plugins",
    "config_mcp",
    "config_system",
    "config_model_settings",
):
    _module = _import_module(f"{__package__}.{_module_name}")
    globals().update(
        {name: value for name, value in _module.__dict__.items() if not name.startswith("__")}
    )


def _materialize_codex_model_settings(
    settings: ResolvedAgentModelSettings,
    *,
    window_id: str,
    home: Path | None,
) -> None:
    user_home = home or Path.home()
    managed_root = _ensure_window_agent_config_root("codex", window_id, user_home)
    _detach_window_config_items(managed_root, ("auth.json", "config.toml"))
    provider_id = _codex_provider_id(settings)
    config_path = managed_root / "config.toml"
    with _locked_config_writes(config_path):
        lines = _remove_codex_model_provider_blocks(_read_text_lines(config_path), provider_id)
        lines = _upsert_toml_assignment(lines, "model", settings.model)
        lines = _upsert_toml_assignment(lines, "model_provider", provider_id)
        lines = _upsert_optional_toml_int(lines, "max_output_tokens", settings.max_output_tokens)
        lines = _upsert_optional_toml_int(lines, "model_context_window", settings.context_window)
        lines = _upsert_optional_toml_int(
            lines,
            "model_auto_compact_token_limit",
            settings.auto_compact_token_limit,
        )
        lines = _upsert_optional_toml_string(
            lines, "model_reasoning_effort", settings.codex_model_reasoning_effort
        )
        lines = _upsert_optional_toml_string(
            lines, "plan_mode_reasoning_effort", settings.codex_plan_mode_reasoning_effort
        )
        _write_text_file_atomic(config_path, "\n".join(lines).rstrip() + "\n")
        _append_codex_model_provider_block(config_path, provider_id, settings)
    _write_codex_auth_file(managed_root, settings)
    _write_model_env_file(managed_root, {"OPENAI_API_KEY": settings.api_key})


def _materialize_claude_model_settings(
    settings: ResolvedAgentModelSettings,
    *,
    window_id: str,
    home: Path | None,
) -> None:
    user_home = home or Path.home()
    managed_root = _ensure_window_agent_config_root("claude", window_id, user_home)
    _detach_window_config_items(managed_root, ("settings.json",))
    settings_path = managed_root / "settings.json"
    routing = settings.claude or ClaudeModelRouting(mode="all", model=settings.model)
    base_url = _claude_code_base_url(settings.base_url)
    env = {
        "ANTHROPIC_BASE_URL": base_url,
        "CLAUDE_CODE_API_BASE_URL": base_url,
        "ANTHROPIC_API_KEY": settings.api_key,
    }
    if settings.max_output_tokens is not None:
        env["CLAUDE_CODE_MAX_OUTPUT_TOKENS"] = str(settings.max_output_tokens)
    if settings.auto_compact_token_limit is not None:
        env["CLAUDE_CODE_AUTO_COMPACT_WINDOW"] = str(settings.auto_compact_token_limit)
    if settings.claude_reasoning_effort is not None:
        env["CLAUDE_CODE_EFFORT_LEVEL"] = settings.claude_reasoning_effort
    if routing.mode == "split":
        env.update(
            {
                "ANTHROPIC_DEFAULT_OPUS_MODEL": routing.opus_model or settings.model,
                "ANTHROPIC_DEFAULT_SONNET_MODEL": routing.sonnet_model or settings.model,
                "ANTHROPIC_DEFAULT_HAIKU_MODEL": routing.haiku_model or settings.model,
            }
        )
    else:
        selected = routing.model or settings.model
        env.update(
            {
                "ANTHROPIC_DEFAULT_OPUS_MODEL": selected,
                "ANTHROPIC_DEFAULT_SONNET_MODEL": selected,
                "ANTHROPIC_DEFAULT_HAIKU_MODEL": selected,
            }
        )
    with _locked_config_writes(settings_path):
        data = _read_json_file(settings_path)
        settings_env = data.setdefault("env", {})
        if not isinstance(settings_env, dict):
            settings_env = {}
            data["env"] = settings_env
        settings_env.update(env)
        _write_json_file(settings_path, data)
    _write_model_env_file(managed_root, env)
    _inject_claude_custom_api_key_approval(settings.api_key, managed_root, user_home)


def _inject_claude_custom_api_key_approval(
    api_key: str,
    managed_root: Path,
    user_home: Path,
) -> None:
    last_20 = (api_key or "")[-20:]
    if not last_20:
        return
    for claude_json_path in (managed_root / ".claude.json", user_home / ".claude.json"):
        with contextlib.suppress(OSError):
            _add_approved_custom_api_key(claude_json_path, last_20)


def _add_approved_custom_api_key(claude_json_path: Path, key_suffix: str) -> None:
    if not claude_json_path.is_file():
        return
    with _locked_config_writes(claude_json_path):
        data = _read_json_file(claude_json_path)
        responses = data.get("customApiKeyResponses")
        if not isinstance(responses, dict):
            responses = {}
            data["customApiKeyResponses"] = responses
        approved = responses.get("approved")
        if not isinstance(approved, list):
            approved = []
            responses["approved"] = approved
        rejected = responses.get("rejected")
        if not isinstance(rejected, list):
            rejected = []
            responses["rejected"] = rejected
        if key_suffix in rejected:
            rejected.remove(key_suffix)
        if key_suffix in approved:
            return
        approved.append(key_suffix)
        _write_json_file(claude_json_path, data)


def _codex_provider_id(settings: ResolvedAgentModelSettings) -> str:
    base = settings.preset_id.strip().replace(".", "_").replace("-", "_")
    clean = "".join(character if character.isalnum() or character == "_" else "_" for character in base)
    return f"web_terminal_{clean or 'model'}"


def _append_codex_model_provider_block(
    path: Path,
    provider_id: str,
    settings: ResolvedAgentModelSettings,
) -> None:
    lines = [
        "",
        f"[model_providers.{provider_id}]",
        f"name = {_toml_string(provider_id)}",
        f"base_url = {_toml_string(settings.base_url)}",
        'wire_api = "responses"',
        'env_key = "OPENAI_API_KEY"',
        "requires_openai_auth = false" if not settings.api_key else "requires_openai_auth = true",
    ]
    _append_text_lines(path, lines)


def _write_codex_auth_file(managed_root: Path, settings: ResolvedAgentModelSettings) -> None:
    path = managed_root / "auth.json"
    with _locked_config_writes(path):
        data = _read_json_file(path)
        if settings.api_key:
            data["OPENAI_API_KEY"] = settings.api_key
        else:
            data.pop("OPENAI_API_KEY", None)
        _write_json_file(path, data)
    with contextlib.suppress(OSError):
        path.chmod(0o600)


def _claude_code_base_url(base_url: str) -> str:
    clean = base_url.rstrip("/")
    return clean[:-3] if clean.endswith("/v1") else clean


def _append_text_lines(path: Path, lines: list[str]) -> None:
    existing = path.read_text(encoding="utf-8") if path.is_file() else ""
    separator = "" if not existing or existing.endswith("\n") else "\n"
    _write_text_file_atomic(path, existing.rstrip() + separator + "\n".join(lines).rstrip() + "\n")


def _remove_codex_model_provider_blocks(lines: list[str], provider_id: str) -> list[str]:
    output: list[str] = []
    skip = False
    for line in lines:
        if _codex_model_provider_header(line) == provider_id:
            skip = True
            continue
        if skip and _is_toml_table_header(line):
            skip = False
        if skip:
            continue
        output.append(line)
    return output


def _codex_model_provider_header(line: str) -> str | None:
    match = re.match(r"\s*\[model_providers\.([A-Za-z0-9_]+)\]\s*(?:#.*)?$", line)
    return match.group(1) if match else None


def _upsert_toml_assignment(lines: list[str], key: str, value: str) -> list[str]:
    pattern = re.compile(rf"\s*{re.escape(key)}\s*=")
    output: list[str] = []
    updated = False
    inserted = False
    for line in lines:
        if not inserted and _is_toml_table_header(line):
            if not updated:
                output.append(f"{key} = {_toml_string(value)}")
                updated = True
            inserted = True
        if not inserted and pattern.match(line):
            if not updated:
                output.append(f"{key} = {_toml_string(value)}")
                updated = True
            continue
        output.append(line)
    if not updated:
        output.append(f"{key} = {_toml_string(value)}")
    return output


def _upsert_optional_toml_int(lines: list[str], key: str, value: int | None) -> list[str]:
    if value is None:
        return _remove_toml_assignment(lines, key)
    return _upsert_toml_raw_assignment(lines, key, str(value))


def _upsert_optional_toml_string(lines: list[str], key: str, value: str | None) -> list[str]:
    if value is None:
        return _remove_toml_assignment(lines, key)
    return _upsert_toml_assignment(lines, key, value)


def _remove_toml_assignment(lines: list[str], key: str) -> list[str]:
    pattern = re.compile(rf"\s*{re.escape(key)}\s*=")
    return [line for line in lines if not pattern.match(line)]


def _upsert_toml_raw_assignment(lines: list[str], key: str, value: str) -> list[str]:
    pattern = re.compile(rf"\s*{re.escape(key)}\s*=")
    output: list[str] = []
    updated = False
    inserted = False
    for line in lines:
        if not inserted and _is_toml_table_header(line):
            if not updated:
                output.append(f"{key} = {value}")
                updated = True
            inserted = True
        if not inserted and pattern.match(line):
            if not updated:
                output.append(f"{key} = {value}")
                updated = True
            continue
        output.append(line)
    if not updated:
        output.append(f"{key} = {value}")
    return output


def _write_model_env_file(managed_root: Path, values: dict[str, str]) -> None:
    lines = [
        "# Generated by Web Terminal ACP. Do not commit this file.",
        *[
            f"export {key}={_shell_env_value(value)}"
            for key, value in sorted(values.items())
            if value != ""
        ],
    ]
    path = managed_root / SYSTEM_MODEL_ENV_FILE
    _write_text_file_atomic(path, "\n".join(lines).rstrip() + "\n")
    with contextlib.suppress(OSError):
        path.chmod(0o600)


def _shell_env_value(value: str) -> str:
    return "'" + value.replace("'", "'\\''") + "'"
