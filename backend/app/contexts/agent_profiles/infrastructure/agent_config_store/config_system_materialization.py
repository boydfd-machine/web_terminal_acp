from importlib import import_module as _import_module

for _module_name in (
    "config_service",
    "config_items",
    "config_plugins",
    "config_mcp",
    "config_system",
    "config_managed_skills",
    "config_model_settings",
    "config_model_materialization",
    "config_model_metadata",
    "config_system_defaults",
    "config_system_plugins",
    "config_builtin_mcp",
    "config_system_detail",
):
    _module = _import_module(f"{__package__}.{_module_name}")
    globals().update(
        {name: value for name, value in _module.__dict__.items() if not name.startswith("__")}
    )


def _install_system_skills(
    agent: AgentKind,
    root: Path,
    managed_root: Path,
    source_root: Path,
    *,
    user_home: Path,
    include_managed_agent_skills: bool = True,
    target_skills_dir: str | None = None,
) -> None:
    source_skills_dir = _skills_directory(agent)
    skills_dir = target_skills_dir or source_skills_dir
    default_overrides = _system_default_overrides(root).get("skills", {})
    overridden_skill_ids = _system_config_skill_ids(root)

    _merge_system_skill_tree(
        root / SYSTEM_SKILLS_DIR,
        managed_root / skills_dir,
        managed_root / f"{skills_dir}.disabled",
    )
    _merge_system_skill_tree(
        root / SYSTEM_DISABLED_SKILLS_DIR,
        managed_root / f"{skills_dir}.disabled",
        managed_root / skills_dir,
    )
    _install_agent_client_builtin_system_skills(
        source_root,
        source_skills_dir,
        managed_root,
        skills_dir,
        default_overrides,
    )
    if include_managed_agent_skills:
        _install_managed_agent_skills(
            agent,
            user_home=user_home,
            managed_root=managed_root,
            target_skills_dir=skills_dir,
            default_overrides=default_overrides,
        )
    from app.contexts.agent_profiles.infrastructure import builtin_system_skills

    builtin_system_skills.materialize_builtin_system_skills(
        managed_root,
        skills_dir,
        _write_text_file_atomic,
        enabled_by_id=default_overrides,
        preserve_ids=overridden_skill_ids,
    )


def _merge_system_skill_tree(source: Path, target: Path, counterpart: Path) -> None:
    if not source.is_dir():
        return
    target.mkdir(parents=True, exist_ok=True)
    for child in sorted(source.iterdir(), key=lambda candidate: candidate.name):
        destination = target / child.name
        counterpart_destination = counterpart / child.name
        if counterpart_destination.exists() or counterpart_destination.is_symlink():
            _remove_path(counterpart_destination)
        if destination.exists() or destination.is_symlink():
            _remove_path(destination)
        _link_or_copy_config_child(child, destination)


def _install_agent_client_builtin_system_skills(
    source_root: Path,
    source_skills_dir: str,
    managed_root: Path,
    target_skills_dir: str,
    default_overrides: dict[str, bool],
) -> None:
    for system_root in _system_skill_roots(source_root, source_skills_dir):
        for child in sorted(candidate for candidate in system_root.iterdir() if candidate.is_dir()):
            marker = child / "SKILL.md"
            if not marker.is_file():
                continue
            active_system = managed_root / target_skills_dir / ".system" / child.name
            active_direct = managed_root / target_skills_dir / child.name
            disabled = managed_root / f"{target_skills_dir}.disabled" / child.name
            if default_overrides.get(child.name, True):
                if active_direct.exists() or disabled.exists():
                    continue
                if active_system.exists():
                    continue
                _link_config_directory(child, active_direct)
                continue
            if active_system.parent.is_symlink():
                _replace_symlink_with_copy(active_system.parent)
            _remove_path(active_system)
            _remove_path(active_direct)
            if not disabled.exists():
                _link_config_directory(child, disabled)


def _install_managed_agent_skills(
    agent: AgentKind,
    *,
    user_home: Path,
    managed_root: Path,
    target_skills_dir: str,
    default_overrides: dict[str, bool],
) -> None:
    plugin = _agent_plugin(agent)
    for child in _managed_agent_skill_roots(
        user_home,
        plugin.storage.managed_root,
        plugin.storage.skills_directory,
        exclude_managed_root=managed_root,
    ):
        active = managed_root / target_skills_dir / child.name
        disabled = managed_root / f"{target_skills_dir}.disabled" / child.name
        if default_overrides.get(child.name, True):
            if active.exists() or disabled.exists():
                continue
            _link_config_directory(child, active)
            continue
        _remove_path(active)
        if not disabled.exists():
            _link_config_directory(child, disabled)


def _install_system_mcp(agent: AgentKind, root: Path, managed_root: Path) -> None:
    servers: list[tuple[str, dict[str, Any], bool]] = []
    for server_id, server in _mcp_servers(_read_json_file(root / SYSTEM_MCP_FILE)).items():
        if isinstance(server, dict):
            servers.append((server_id, server, True))
    for server_id, server in _mcp_servers(_read_json_file(root / SYSTEM_MCP_DISABLED_FILE)).items():
        if isinstance(server, dict):
            servers.append((server_id, server, False))
    for item in _list_system_builtin_mcp_items(root):
        block = _builtin_system_mcp_server_block(item.id)
        if block:
            servers.append((item.id, block, item.enabled))
    if not servers:
        return
    _detach_mcp_window_config_items(agent, managed_root)
    for server_id, server, enabled in sorted(servers, key=lambda item: item[0]):
        _write_mcp_block_for_agent(agent, managed_root, server_id, server, enabled=enabled)


def _write_mcp_block_for_agent(
    agent: AgentKind,
    managed_root: Path,
    server_id: str,
    block: dict[str, Any],
    *,
    enabled: bool,
) -> None:
    strategy = _agent_plugin(agent).native_config.mcp_strategy
    if enabled:
        if strategy == "codex_toml":
            _write_system_codex_mcp(managed_root / "config.toml", server_id, block)
            _remove_json_mcp_server(managed_root / MCP_DISABLED_FILE, server_id)
        elif strategy == "claude_json":
            _write_system_json_mcp(
                _claude_state_path(managed_root),
                server_id,
                block,
                claude_state=True,
            )
        else:
            _write_system_json_mcp(managed_root / "mcp.json", server_id, block)
            _remove_json_mcp_server(managed_root / MCP_DISABLED_FILE, server_id)
        return

    if strategy == "codex_toml":
        _remove_codex_mcp_server(managed_root / "config.toml", server_id)
        _write_disabled_codex_mcp(managed_root / MCP_DISABLED_FILE, server_id, block)
    elif strategy == "claude_json":
        _write_disabled_claude_mcp(_claude_state_path(managed_root), server_id, block)
    else:
        _remove_json_mcp_server(managed_root / "mcp.json", server_id)
        _write_disabled_json_mcp(managed_root / MCP_DISABLED_FILE, server_id, block)


def _remove_codex_mcp_server(path: Path, server_id: str) -> None:
    with _locked_config_writes(path):
        output, removed = _remove_codex_mcp_blocks(_read_text_lines(path), server_id)
        if removed:
            _write_text_file_atomic(path, "\n".join(output).rstrip() + "\n")


def _remove_json_mcp_server(path: Path, server_id: str) -> None:
    with _locked_config_writes(path):
        data = _read_json_file(path)
        if _remove_mcp_server(data, server_id) is not None:
            _write_json_file(path, data)


def _write_disabled_json_mcp(path: Path, server_id: str, block: dict[str, Any]) -> None:
    with _locked_config_writes(path):
        data = _read_json_file(path)
        _ensure_mcp_servers(data)[server_id] = block
        _write_json_file(path, data)


def _write_disabled_codex_mcp(path: Path, server_id: str, block: dict[str, Any]) -> None:
    with _locked_config_writes(path):
        data = _read_json_file(path)
        _ensure_mcp_servers(data)[server_id] = {"toml": _system_codex_mcp_lines(server_id, block)}
        _write_json_file(path, data)


def _write_disabled_claude_mcp(path: Path, server_id: str, block: dict[str, Any]) -> None:
    with _locked_config_writes(path):
        data = _read_json_file(path)
        _remove_mcp_server(data, server_id)
        disabled = _ensure_claude_disabled_mcp(data)
        disabled[_claude_user_mcp_id(server_id)] = {
            "scope": "user",
            "name": server_id,
            "label": server_id,
            "server": block,
        }
        _write_json_file(path, data)


def _write_system_json_mcp(
    path: Path,
    server_id: str,
    block: dict[str, Any],
    *,
    claude_state: bool = False,
) -> None:
    with _locked_config_writes(path):
        data = _read_json_file(path)
        _ensure_mcp_servers(data)[server_id] = block
        if claude_state:
            disabled = _ensure_claude_disabled_mcp(data)
            disabled.pop(server_id, None)
            disabled.pop(_claude_user_mcp_id(server_id), None)
        _write_json_file(path, data)


def _write_system_codex_mcp(path: Path, server_id: str, block: dict[str, Any]) -> None:
    with _locked_config_writes(path):
        output, _removed = _remove_codex_mcp_blocks(_read_text_lines(path), server_id)
        _write_text_file_atomic(path, "\n".join(output).rstrip() + "\n")
        _append_codex_mcp_block(path, _system_codex_mcp_lines(server_id, block))


def _system_codex_mcp_lines(server_id: str, block: dict[str, Any]) -> list[str]:
    lines = [f'[mcp_servers."{server_id}"]']
    for key in sorted(block):
        if key == "env":
            continue
        value = block[key]
        rendered = _toml_value(value)
        if rendered is not None:
            lines.append(f"{key} = {rendered}")
    env = block.get("env")
    if isinstance(env, dict) and env:
        lines.extend(["", f'[mcp_servers."{server_id}".env]'])
        for key in sorted(env):
            value = env[key]
            if isinstance(key, str) and isinstance(value, str):
                lines.append(f"{key} = {_toml_string(value)}")
    return lines


def _toml_value(value: object) -> str | None:
    if isinstance(value, str):
        return _toml_string(value)
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return str(value)
    if isinstance(value, list) and all(isinstance(item, str) for item in value):
        return _toml_string_list(value)
    return None
