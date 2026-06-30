from importlib import import_module as _import_module

for _module_name in ("config_service", "config_items", "config_plugins"):
    _module = _import_module(f"{__package__}.{_module_name}")
    globals().update(
        {name: value for name, value in _module.__dict__.items() if not name.startswith("__")}
    )

import base64
from typing import Any

MCP_DISABLED_FILE = "mcp.disabled.json"
CLAUDE_DISABLED_MCP_KEY = "webTerminalDisabledMcpServers"


def _list_mcp(agent: AgentKind, root: Path) -> list[AgentConfigItem]:
    strategy = _agent_plugin(agent).native_config.mcp_strategy
    if strategy == "codex_toml":
        return _list_codex_mcp(root)
    if strategy == "claude_json":
        return _list_claude_mcp(root)
    return _list_json_mcp(root)


def _set_mcp_enabled(agent: AgentKind, root: Path, item_id: str, enabled: bool) -> None:
    strategy = _agent_plugin(agent).native_config.mcp_strategy
    if strategy == "codex_toml":
        _set_codex_mcp_enabled(root, item_id, enabled)
        return
    if strategy == "claude_json":
        _set_claude_mcp_enabled(root, item_id, enabled)
        return
    _set_json_mcp_enabled(root, item_id, enabled)


def _detach_mcp_window_config_items(agent: AgentKind, managed_root: Path) -> None:
    strategy = _agent_plugin(agent).native_config.mcp_strategy
    if strategy == "codex_toml":
        _detach_window_config_items(managed_root, ("config.toml", MCP_DISABLED_FILE))
    elif strategy == "claude_json":
        _detach_window_config_items(managed_root, (".claude.json",))
    else:
        _detach_window_config_items(managed_root, ("mcp.json", MCP_DISABLED_FILE))


def _copy_external_agent_state_items(
    agent: AgentKind,
    source_root: Path,
    managed_root: Path,
) -> None:
    if _agent_plugin(agent).native_config.mcp_strategy != "claude_json":
        return
    source = _claude_state_path(source_root)
    target = managed_root / ".claude.json"
    if not source.is_file() or target.exists() or target.is_symlink():
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target, follow_symlinks=True)


def _list_json_mcp(
    root: Path,
    *,
    origin: ConfigItemOrigin = "client",
) -> list[AgentConfigItem]:
    active_path = root / "mcp.json"
    disabled_path = root / MCP_DISABLED_FILE
    active = _mcp_servers(_read_json_file(active_path))
    disabled = _mcp_servers(_read_json_file(disabled_path))
    items = {
        item_id: AgentConfigItem(item_id, item_id, False, str(disabled_path), origin)
        for item_id in disabled
    }
    items.update(
        {
            item_id: AgentConfigItem(item_id, item_id, True, str(active_path), origin)
            for item_id in active
        }
    )
    return _sorted_mcp_items(items.values())


def _set_json_mcp_enabled(root: Path, item_id: str, enabled: bool) -> None:
    _validate_json_key_item_id(item_id)
    active_path = root / "mcp.json"
    disabled_path = root / MCP_DISABLED_FILE
    with _locked_config_writes(active_path, disabled_path):
        active_config = _read_json_file(active_path)
        disabled_config = _read_json_file(disabled_path)
        source_config = disabled_config if enabled else active_config
        target_config = active_config if enabled else disabled_config
        server = _remove_mcp_server(source_config, item_id)
        if server is None:
            if item_id in _mcp_servers(target_config):
                return
            raise ValueError(f"mcp server not found: {item_id}")
        _ensure_mcp_servers(target_config)[item_id] = server
        _write_json_file(active_path, active_config)
        _write_json_file(disabled_path, disabled_config)


def _list_codex_mcp(root: Path) -> list[AgentConfigItem]:
    config_path = root / "config.toml"
    disabled_path = root / MCP_DISABLED_FILE
    active = _read_codex_mcp_names(config_path)
    disabled = _mcp_servers(_read_json_file(disabled_path))
    items = {
        item_id: AgentConfigItem(item_id, item_id, False, str(disabled_path))
        for item_id in disabled
    }
    items.update(
        {
            item_id: AgentConfigItem(item_id, item_id, True, str(config_path))
            for item_id in active
        }
    )
    return _sorted_mcp_items(items.values())


def _set_codex_mcp_enabled(root: Path, item_id: str, enabled: bool) -> None:
    _validate_codex_plugin_id(item_id)
    config_path = root / "config.toml"
    disabled_path = root / MCP_DISABLED_FILE
    with _locked_config_writes(config_path, disabled_path):
        disabled = _read_json_file(disabled_path)
        disabled_servers = _ensure_mcp_servers(disabled)
        if enabled:
            block = disabled_servers.pop(item_id, None)
            if block is None:
                if item_id in _read_codex_mcp_names(config_path):
                    return
                raise ValueError(f"mcp server not found: {item_id}")
            _append_codex_mcp_block(config_path, _codex_disabled_block_lines(block))
            _write_json_file(disabled_path, disabled)
            return

        lines = _read_text_lines(config_path)
        output, removed = _remove_codex_mcp_blocks(lines, item_id)
        if not removed:
            if item_id in disabled_servers:
                return
            raise ValueError(f"mcp server not found: {item_id}")
        disabled_servers[item_id] = {"toml": removed}
        _write_text_file_atomic(config_path, "\n".join(output).rstrip() + "\n")
        _write_json_file(disabled_path, disabled)


def _list_claude_mcp(root: Path) -> list[AgentConfigItem]:
    state_path = _claude_state_path(root)
    state = _read_json_file(state_path)
    items: dict[str, AgentConfigItem] = {}
    for name in _mcp_servers(state):
        item_id = _claude_user_mcp_id(name)
        items[item_id] = AgentConfigItem(item_id, name, True, str(state_path))
    for project_key, project in _claude_projects(state).items():
        for name in _mcp_servers(project):
            item_id = _claude_project_mcp_id(project_key, name)
            items[item_id] = AgentConfigItem(
                item_id,
                f"{name} ({_claude_project_label(project_key)})",
                True,
                str(state_path),
            )
    for item_id, record in _claude_disabled_mcp(state).items():
        name = _string(record.get("label")) if isinstance(record, dict) else None
        items[item_id] = AgentConfigItem(item_id, name or item_id, False, str(state_path))
    return _sorted_mcp_items(items.values())


def _set_claude_mcp_enabled(root: Path, item_id: str, enabled: bool) -> None:
    _validate_json_key_item_id(item_id)
    state_path = _claude_state_path(root)
    with _locked_config_writes(state_path):
        state = _read_json_file(state_path)
        disabled = _ensure_claude_disabled_mcp(state)
        if enabled:
            record = disabled.pop(item_id, None)
            if record is None:
                if _claude_active_mcp_exists(state, item_id):
                    return
                raise ValueError(f"mcp server not found: {item_id}")
            _restore_claude_mcp(state, item_id, record)
            _write_json_file(state_path, state)
            return

        record = _remove_claude_mcp(state, item_id)
        if record is None:
            if item_id in disabled:
                return
            raise ValueError(f"mcp server not found: {item_id}")
        disabled[item_id] = record
        _write_json_file(state_path, state)


def _claude_state_path(root: Path) -> Path:
    local_state = root / ".claude.json"
    if local_state.exists() or root.name != ".claude":
        return local_state
    return root.parent / ".claude.json"


def _claude_projects(state: dict[str, Any]) -> dict[str, Any]:
    projects = state.get("projects")
    if not isinstance(projects, dict):
        return {}
    return {
        key: value
        for key, value in projects.items()
        if isinstance(key, str) and isinstance(value, dict)
    }


def _ensure_claude_projects(state: dict[str, Any]) -> dict[str, Any]:
    projects = state.setdefault("projects", {})
    if not isinstance(projects, dict):
        projects = {}
        state["projects"] = projects
    return projects


def _claude_disabled_mcp(state: dict[str, Any]) -> dict[str, Any]:
    disabled = state.get(CLAUDE_DISABLED_MCP_KEY)
    return disabled if isinstance(disabled, dict) else {}


def _ensure_claude_disabled_mcp(state: dict[str, Any]) -> dict[str, Any]:
    disabled = state.setdefault(CLAUDE_DISABLED_MCP_KEY, {})
    if not isinstance(disabled, dict):
        disabled = {}
        state[CLAUDE_DISABLED_MCP_KEY] = disabled
    return disabled


def _claude_active_mcp_exists(state: dict[str, Any], item_id: str) -> bool:
    scope, project_key, name = _parse_claude_mcp_id(item_id)
    if scope == "user":
        return name in _mcp_servers(state)
    project = _claude_projects(state).get(project_key or "")
    return isinstance(project, dict) and name in _mcp_servers(project)


def _remove_claude_mcp(state: dict[str, Any], item_id: str) -> dict[str, Any] | None:
    scope, project_key, name = _parse_claude_mcp_id(item_id)
    if scope == "user":
        server = _remove_mcp_server(state, name)
        if server is None:
            return None
        return {"scope": "user", "name": name, "label": name, "server": server}
    project = _claude_projects(state).get(project_key or "")
    if not isinstance(project, dict):
        return None
    server = _remove_mcp_server(project, name)
    if server is None:
        return None
    return {
        "scope": "project",
        "project": project_key,
        "name": name,
        "label": f"{name} ({_claude_project_label(project_key or '')})",
        "server": server,
    }


def _restore_claude_mcp(state: dict[str, Any], item_id: str, record: Any) -> None:
    if not isinstance(record, dict):
        raise ValueError(f"invalid disabled mcp server: {item_id}")
    scope = _string(record.get("scope"))
    name = _string(record.get("name"))
    server = record.get("server")
    if name is None or not isinstance(server, dict):
        raise ValueError(f"invalid disabled mcp server: {item_id}")
    if scope == "user":
        _ensure_mcp_servers(state)[name] = server
        return
    if scope == "project":
        project_key = _string(record.get("project"))
        if project_key is None:
            raise ValueError(f"invalid disabled mcp server: {item_id}")
        project = _ensure_claude_projects(state).setdefault(project_key, {})
        if not isinstance(project, dict):
            project = {}
            _ensure_claude_projects(state)[project_key] = project
        _ensure_mcp_servers(project)[name] = server
        return
    raise ValueError(f"invalid disabled mcp server: {item_id}")


def _parse_claude_mcp_id(item_id: str) -> tuple[str, str | None, str]:
    if item_id and not item_id.startswith("user:") and not item_id.startswith("project:"):
        return "user", None, item_id
    if item_id.startswith("user:") and item_id[5:]:
        return "user", None, item_id[5:]
    if item_id.startswith("project:"):
        rest = item_id[8:]
        encoded_project, separator, name = rest.partition(":")
        if separator and encoded_project and name:
            return "project", _decode_mcp_id_part(encoded_project), name
    raise ValueError(f"invalid mcp server id: {item_id}")


def _claude_user_mcp_id(name: str) -> str:
    return f"user:{name}"


def _claude_project_mcp_id(project_key: str, name: str) -> str:
    return f"project:{_encode_mcp_id_part(project_key)}:{name}"


def _claude_project_label(project_key: str) -> str:
    return Path(project_key).name or project_key


def _encode_mcp_id_part(value: str) -> str:
    return base64.urlsafe_b64encode(value.encode("utf-8")).decode("ascii").rstrip("=")


def _decode_mcp_id_part(value: str) -> str:
    try:
        padding = "=" * (-len(value) % 4)
        return base64.urlsafe_b64decode((value + padding).encode("ascii")).decode("utf-8")
    except (ValueError, UnicodeDecodeError) as exc:
        raise ValueError(f"invalid mcp server id: {value}") from exc


def _read_codex_mcp_names(path: Path) -> set[str]:
    return {
        name
        for line in _read_text_lines(path)
        for name in [_codex_mcp_header(line)]
        if name is not None
    }


def _remove_codex_mcp_blocks(lines: list[str], item_id: str) -> tuple[list[str], list[str]]:
    output: list[str] = []
    removed: list[str] = []
    in_target = False
    for line in lines:
        server_id = _codex_mcp_header(line)
        if server_id is not None:
            in_target = server_id == item_id
        elif _is_toml_table_header(line):
            in_target = False
        if in_target:
            removed.append(line)
        else:
            output.append(line)
    return output, removed


def _append_codex_mcp_block(path: Path, lines: list[str]) -> None:
    if not lines:
        raise ValueError("invalid disabled mcp server")
    content = path.read_text(encoding="utf-8") if path.is_file() else ""
    next_content = content.rstrip()
    if next_content:
        next_content += "\n\n"
    next_content += "\n".join(lines).rstrip() + "\n"
    _write_text_file_atomic(path, next_content)


def _codex_disabled_block_lines(value: Any) -> list[str]:
    if not isinstance(value, dict):
        return []
    lines = value.get("toml")
    if not isinstance(lines, list):
        return []
    return [line for line in lines if isinstance(line, str)]


def _codex_mcp_header(line: str) -> str | None:
    match = re.match(
        r'\s*\[mcp_servers\.(?:"([^"]+)"|([^.\]\s]+))(?:\.[^\]]+)?\]\s*(?:#.*)?$',
        line,
    )
    if match is None:
        return None
    return match.group(1) or match.group(2)


def _read_text_lines(path: Path) -> list[str]:
    try:
        return path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []


def _mcp_servers(data: dict[str, Any]) -> dict[str, Any]:
    servers = data.get("mcpServers")
    if not isinstance(servers, dict):
        return {}
    return {key: value for key, value in servers.items() if isinstance(key, str) and key}


def _ensure_mcp_servers(data: dict[str, Any]) -> dict[str, Any]:
    servers = data.setdefault("mcpServers", {})
    if not isinstance(servers, dict):
        servers = {}
        data["mcpServers"] = servers
    return servers


def _remove_mcp_server(data: dict[str, Any], item_id: str) -> Any | None:
    return _ensure_mcp_servers(data).pop(item_id, None)


def _sorted_mcp_items(items) -> list[AgentConfigItem]:
    return sorted(items, key=lambda item: (item.name.lower(), item.id.lower(), item.enabled))
