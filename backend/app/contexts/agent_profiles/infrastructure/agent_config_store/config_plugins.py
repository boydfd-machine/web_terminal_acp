from importlib import import_module as _import_module

for _module_name in ("config_service", "config_items"):
    _module = _import_module(f"{__package__}.{_module_name}")
    globals().update(
        {name: value for name, value in _module.__dict__.items() if not name.startswith("__")}
    )


def _list_plugins(agent: AgentKind, root: Path) -> list[AgentConfigItem]:
    strategy = _agent_plugin(agent).native_config.plugin_strategy
    if strategy == "codex_toml":
        return _list_codex_plugins(root)
    if strategy == "claude_settings":
        return _list_claude_plugins(root)
    return _list_directory_plugins(root)


def _list_codex_plugins(root: Path) -> list[AgentConfigItem]:
    enabled = _read_codex_plugin_enabled(root / "config.toml")
    items: list[AgentConfigItem] = []
    pattern = "plugins/cache/*/*/*/.codex-plugin/plugin.json"
    for manifest in sorted(root.glob(pattern)):
        marketplace = manifest.parents[3].name
        plugin_name = manifest.parents[2].name
        plugin_id = f"{plugin_name}@{marketplace}"
        data = _read_json_file(manifest)
        label = (
            _deep_string(data, "interface", "displayName")
            or _string(data.get("name"))
            or plugin_name
        )
        items.append(
            AgentConfigItem(
                plugin_id,
                label,
                enabled.get(plugin_id, True),
                str(manifest.parent.parent),
            )
        )
    return sorted(items, key=lambda item: item.name.lower())


def _list_claude_plugins(root: Path) -> list[AgentConfigItem]:
    installed = _read_json_file(root / "plugins" / "installed_plugins.json").get("plugins", {})
    enabled = _read_json_file(root / "settings.json").get("enabledPlugins", {})
    if not isinstance(installed, dict):
        return []
    return [
        AgentConfigItem(plugin_id, plugin_id, bool(enabled.get(plugin_id, True)))
        for plugin_id in sorted(key for key in installed if isinstance(key, str))
    ]


def _list_directory_plugins(root: Path) -> list[AgentConfigItem]:
    items: dict[str, AgentConfigItem] = {}
    for enabled, base in ((False, root / "plugins.disabled"), (True, root / "plugins")):
        if not base.exists():
            continue
        for path in sorted(child for child in base.iterdir() if child.is_dir()):
            manifest = _directory_plugin_manifest(path)
            if not manifest.is_file():
                continue
            data = _read_json_file(manifest)
            plugin_id = path.name
            label = (
                _string(data.get("displayName"))
                or _deep_string(data, "interface", "displayName")
                or _string(data.get("title"))
                or _string(data.get("name"))
                or path.name
            )
            items[plugin_id] = AgentConfigItem(plugin_id, label, enabled, str(path))
    return sorted(items.values(), key=lambda item: item.name.lower())
