from importlib import import_module as _import_module

for _module_name in (
    "config_service",
    "config_items",
    "config_plugins",
    "config_mcp",
    "config_system",
    "config_model_settings",
    "config_model_materialization",
    "config_model_metadata",
    "config_system_defaults",
):
    _module = _import_module(f"{__package__}.{_module_name}")
    globals().update(
        {name: value for name, value in _module.__dict__.items() if not name.startswith("__")}
    )

import json as _json
import sys as _sys

WEB_TERMINAL_MCP_SERVER_ID = "web-terminal-acp-mcp"
CODEX_BUILTIN_MCP_STARTUP_TIMEOUT_SEC = 120


def install_builtin_mcp_for_window(
    *,
    window_id: str,
    source_client_id: str,
    source_window_id: str,
    server_url: str,
    mcp_token: str | None = None,
    home: Path | None = None,
) -> None:
    for plugin in get_agent_plugin_registry().all():
        install_builtin_mcp_for_agent_window(
            plugin.agent_client_id,
            window_id=window_id,
            source_client_id=source_client_id,
            source_window_id=source_window_id,
            server_url=server_url,
            mcp_token=mcp_token,
            home=home,
        )


def install_builtin_mcp_for_agent_window(
    agent: str,
    *,
    window_id: str,
    source_client_id: str,
    source_window_id: str,
    server_url: str,
    mcp_token: str | None = None,
    home: Path | None = None,
) -> None:
    agent_kind = _agent_kind(agent)
    user_home = home or Path.home()
    managed_root = _ensure_window_agent_config_root(agent_kind, window_id, user_home)
    enabled = _managed_web_terminal_mcp_enabled(agent_kind, managed_root, user_home)
    _detach_mcp_window_config_items(agent_kind, managed_root)
    block = _builtin_mcp_server_block(
        source_client_id=source_client_id,
        source_window_id=source_window_id,
        server_url=server_url,
        mcp_token=mcp_token,
    )
    if not enabled:
        _write_mcp_block_for_agent(
            agent_kind,
            managed_root,
            WEB_TERMINAL_MCP_SERVER_ID,
            block,
            enabled=False,
        )
        return
    strategy = _agent_plugin(agent_kind).native_config.mcp_strategy
    if strategy == "codex_toml":
        _write_builtin_codex_mcp(managed_root / "config.toml", block)
    elif strategy == "claude_json":
        _write_builtin_json_mcp(_claude_state_path(managed_root), block, claude_state=True)
    else:
        _write_builtin_json_mcp(managed_root / "mcp.json", block)


def _managed_web_terminal_mcp_enabled(
    agent: AgentKind,
    managed_root: Path,
    user_home: Path,
) -> bool:
    try:
        config = list_agent_config(agent, home=_managed_home_root(managed_root))
    except ValueError:
        return True
    for section in config.sections:
        if section.id != "mcp":
            continue
        for item in section.items:
            if item.id in {WEB_TERMINAL_MCP_SERVER_ID, _claude_user_mcp_id(WEB_TERMINAL_MCP_SERVER_ID)}:
                return item.enabled
    item = _system_builtin_item_for_id("mcp", WEB_TERMINAL_MCP_SERVER_ID, home=user_home)
    return item.enabled if item is not None else True


def _builtin_mcp_server_block(
    *,
    source_client_id: str,
    source_window_id: str,
    server_url: str,
    mcp_token: str | None,
) -> dict[str, object]:
    env = {
        "PYTHONPATH": str(Path(__file__).resolve().parents[5]),
        "WEB_TERMINAL_CLIENT_ID": source_client_id,
        "WEB_TERMINAL_WINDOW_ID": source_window_id,
        "WEB_TERMINAL_SERVER_URL": server_url,
    }
    if mcp_token:
        env["WEB_TERMINAL_MCP_TOKEN"] = mcp_token
    return {
        "type": "stdio",
        "command": _sys.executable,
        "args": ["-m", "app.client_agent.web_terminal_acp_mcp"],
        "env": env,
    }


def _write_builtin_json_mcp(
    path: Path,
    block: dict[str, object],
    *,
    claude_state: bool = False,
) -> None:
    with _locked_config_writes(path):
        data = _read_json_file(path)
        _ensure_mcp_servers(data)[WEB_TERMINAL_MCP_SERVER_ID] = block
        if claude_state:
            disabled = _ensure_claude_disabled_mcp(data)
            disabled.pop(WEB_TERMINAL_MCP_SERVER_ID, None)
            disabled.pop(_claude_user_mcp_id(WEB_TERMINAL_MCP_SERVER_ID), None)
        _write_json_file(path, data)


def _write_builtin_codex_mcp(path: Path, block: dict[str, object]) -> None:
    with _locked_config_writes(path):
        output, _removed = _remove_codex_mcp_blocks(
            _read_text_lines(path),
            WEB_TERMINAL_MCP_SERVER_ID,
        )
        _write_text_file_atomic(path, "\n".join(output).rstrip() + "\n")
        _append_codex_mcp_block(path, _builtin_codex_mcp_lines(block))


def _builtin_codex_mcp_lines(block: dict[str, object]) -> list[str]:
    env = block.get("env")
    lines = [
        f'[mcp_servers."{WEB_TERMINAL_MCP_SERVER_ID}"]',
        f"command = {_toml_string(str(block['command']))}",
        f"args = {_toml_string_list(block.get('args'))}",
        f"startup_timeout_sec = {CODEX_BUILTIN_MCP_STARTUP_TIMEOUT_SEC}",
    ]
    if isinstance(env, dict) and env:
        lines.extend(["", f'[mcp_servers."{WEB_TERMINAL_MCP_SERVER_ID}".env]'])
        for key in sorted(env):
            value = env[key]
            if isinstance(key, str) and isinstance(value, str):
                lines.append(f"{key} = {_toml_string(value)}")
    return lines


def _toml_string(value: str) -> str:
    return _json.dumps(value)


def _toml_string_list(value: object) -> str:
    if not isinstance(value, list):
        return "[]"
    return "[" + ", ".join(_toml_string(str(item)) for item in value) + "]"
