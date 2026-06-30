from importlib import import_module as _import_module

for _module_name in ("config_service", "config_items", "config_plugins", "config_system_defaults"):
    _module = _import_module(f"{__package__}.{_module_name}")
    globals().update(
        {name: value for name, value in _module.__dict__.items() if not name.startswith("__")}
    )


SYSTEM_PLUGIN_ID_SEPARATOR = ":"


def _system_plugin_item_id(agent: AgentKind, item_id: str) -> str:
    return f"{agent}{SYSTEM_PLUGIN_ID_SEPARATOR}{item_id}"


def _split_system_plugin_item_id(item_id: str) -> tuple[AgentKind, str]:
    agent_id, separator, native_id = item_id.partition(SYSTEM_PLUGIN_ID_SEPARATOR)
    if not separator or not agent_id or not native_id:
        raise ValueError(f"invalid system plugin id: {item_id}")
    agent_kind = _agent_kind(agent_id)
    if agent_kind != agent_id:
        raise ValueError(f"invalid system plugin id: {item_id}")
    _validate_native_plugin_item_id(agent_kind, native_id)
    return agent_kind, native_id


def _validate_system_plugin_item_id(item_id: str) -> None:
    _split_system_plugin_item_id(item_id)


def _validate_native_plugin_item_id(agent: AgentKind, item_id: str) -> None:
    strategy = _agent_plugin(agent).native_config.plugin_strategy
    if strategy == "codex_toml":
        _validate_codex_plugin_id(item_id)
    elif strategy == "claude_settings":
        _validate_json_key_item_id(item_id)
    else:
        _validate_path_item_id(item_id)


def _list_system_plugin_items(home: Path, root: Path) -> list[AgentConfigItem]:
    defaults = _system_default_overrides(root).get("plugins", {})
    items: list[AgentConfigItem] = []
    for plugin in get_agent_plugin_registry().all():
        agent = plugin.agent_client_id
        agent_root = _agent_root(agent, home)
        for item in _list_plugins(agent, agent_root):
            qualified_id = _system_plugin_item_id(agent, item.id)
            items.append(
                AgentConfigItem(
                    qualified_id,
                    f"{plugin.label} / {item.name}",
                    defaults.get(qualified_id, item.enabled),
                    item.path,
                    "client",
                    qualified_id in defaults,
                )
            )
    return sorted(items, key=lambda item: (item.name.lower(), item.id.lower()))


def _system_plugin_item_for_id(
    item_id: str,
    *,
    home: Path,
    root: Path,
) -> AgentConfigItem | None:
    try:
        agent, native_id = _split_system_plugin_item_id(item_id)
    except (KeyError, ValueError):
        return None
    plugin = _agent_plugin(agent)
    defaults = _system_default_overrides(root).get("plugins", {})
    for item in _list_plugins(agent, _agent_root(agent, home)):
        if item.id != native_id:
            continue
        return AgentConfigItem(
            item_id,
            f"{plugin.label} / {item.name}",
            defaults.get(item_id, item.enabled),
            item.path,
            "client",
            item_id in defaults,
        )
    return None


def _install_system_plugins(agent: AgentKind, root: Path, managed_root: Path) -> None:
    available_ids = {item.id for item in _list_plugins(agent, managed_root)}
    if not available_ids:
        return
    for item_id, enabled in sorted(_system_default_overrides(root).get("plugins", {}).items()):
        try:
            target_agent, native_id = _split_system_plugin_item_id(item_id)
        except (KeyError, ValueError):
            continue
        if target_agent != agent or native_id not in available_ids:
            continue
        try:
            _set_plugin_enabled(agent, managed_root, native_id, enabled)
        except ValueError:
            continue


def _system_plugin_defaults_for_agent(
    system_config: AgentConfig,
    agent: AgentKind,
) -> dict[str, bool]:
    defaults: dict[str, bool] = {}
    for section in system_config.sections:
        if section.id != "plugins":
            continue
        for item in section.items:
            try:
                target_agent, native_id = _split_system_plugin_item_id(item.id)
            except (KeyError, ValueError):
                continue
            if target_agent == agent:
                defaults[native_id] = item.enabled
    return defaults
