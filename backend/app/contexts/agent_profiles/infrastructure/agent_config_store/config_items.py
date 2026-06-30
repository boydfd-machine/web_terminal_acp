from importlib import import_module as _import_module

_config_service = _import_module(f"{__package__}.config_service")
globals().update(
    {name: value for name, value in _config_service.__dict__.items() if not name.startswith("__")}
)

def _directory_plugin_manifest(path: Path) -> Path:
    for relative in (
        ".cursor-plugin/plugin.json",
        ".antigravity-plugin/plugin.json",
        ".gemini-plugin/plugin.json",
        ".claude-plugin/plugin.json",
        ".codex-plugin/plugin.json",
        "plugin.json",
    ):
        manifest = path / relative
        if manifest.is_file():
            return manifest
    return path / ".cursor-plugin" / "plugin.json"


def _set_plugin_enabled(agent: AgentKind, root: Path, item_id: str, enabled: bool) -> None:
    strategy = _agent_plugin(agent).native_config.plugin_strategy
    if strategy == "codex_toml":
        _write_codex_plugin_enabled(root / "config.toml", item_id, enabled)
        return
    if strategy == "claude_settings":
        _validate_json_key_item_id(item_id)
        settings_path = root / "settings.json"
        with _locked_config_writes(settings_path):
            settings = _read_json_file(settings_path)
            enabled_plugins = settings.setdefault("enabledPlugins", {})
            if not isinstance(enabled_plugins, dict):
                enabled_plugins = {}
                settings["enabledPlugins"] = enabled_plugins
            enabled_plugins[item_id] = enabled
            _write_json_file(settings_path, settings)
        return
    _set_cursor_plugin_enabled(root, item_id, enabled)


def _set_cursor_plugin_enabled(root: Path, item_id: str, enabled: bool) -> None:
    with _locked_config_writes(root / "plugins", root / "plugins.disabled"):
        try:
            _set_directory_item_enabled(root, "plugins", item_id, enabled)
            return
        except ValueError as exc:
            if not str(exc).startswith("config item not found:"):
                raise

        _validate_json_key_item_id(item_id)
        directory_name = _cursor_plugin_directory_for_manifest_name(root, item_id, enabled=enabled)
        if directory_name is None:
            raise ValueError(f"config item not found: {item_id}")
        _set_directory_item_enabled(root, "plugins", directory_name, enabled)


def _cursor_plugin_directory_for_manifest_name(
    root: Path,
    item_id: str,
    *,
    enabled: bool,
) -> str | None:
    source = root / ("plugins.disabled" if enabled else "plugins")
    if not source.exists():
        return None
    for path in sorted(child for child in source.iterdir() if child.is_dir()):
        data = _read_json_file(_directory_plugin_manifest(path))
        if _string(data.get("name")) == item_id:
            return path.name
    return None


def _list_hooks(agent: AgentKind, root: Path) -> list[AgentConfigItem]:
    settings_path = _hooks_config_path(agent, root)
    settings = _read_json_file(settings_path)
    active_hooks = _hooks_root(settings)
    disabled_hooks = _read_json_file(root / DISABLED_HOOKS_FILE)
    items = {item.id: item for item in _hook_items(disabled_hooks, enabled=False)}
    items.update({item.id: item for item in _hook_items(active_hooks, enabled=True)})
    return sorted(items.values(), key=lambda item: (item.name.lower(), item.id.lower(), item.enabled))


def _hook_items(hooks: dict[str, Any], *, enabled: bool) -> list[AgentConfigItem]:
    items: list[AgentConfigItem] = []
    for event_name, definitions in hooks.items():
        if not isinstance(event_name, str) or not isinstance(definitions, list):
            continue
        for entry_index, entry in enumerate(definitions):
            if not isinstance(entry, dict):
                continue
            nested_hooks = entry.get("hooks")
            if isinstance(nested_hooks, list):
                for hook_index, hook in enumerate(nested_hooks):
                    if not isinstance(hook, dict):
                        continue
                    command = _hook_command(hook, fallback=f"{entry_index}.{hook_index}")
                    item_id = f"{event_name}:{command}"
                    item_enabled = enabled and entry.get("enabled") is not False and hook.get("enabled") is not False
                    items.append(AgentConfigItem(item_id, event_name, item_enabled, command))
                continue
            command = _hook_command(entry, fallback=str(entry_index))
            item_id = f"{event_name}:{command}"
            item_enabled = enabled and entry.get("enabled") is not False
            items.append(AgentConfigItem(item_id, event_name, item_enabled, command))
    return items


def _set_hook_enabled(agent: AgentKind, root: Path, item_id: str, enabled: bool) -> None:
    settings_path = _hooks_config_path(agent, root)
    disabled_path = root / DISABLED_HOOKS_FILE
    event_name, separator, command = item_id.partition(":")
    if not separator:
        raise ValueError(f"invalid hook id: {item_id}")

    with _locked_config_writes(settings_path, disabled_path):
        settings = _read_json_file(settings_path)
        hooks = _ensure_hooks_root(settings)
        disabled_hooks = _read_json_file(disabled_path)

        if enabled:
            removed = _remove_hook_entry(disabled_hooks, event_name, command)
            if removed is not None:
                _set_hook_entry_enabled(removed, True)
                _append_hook_entry(hooks, event_name, removed)
                _write_json_file(settings_path, settings)
                _write_json_file(disabled_path, disabled_hooks)
                return
            active = _find_hook_entry(hooks, event_name, command)
            if active is not None:
                _set_hook_entry_enabled(active, True)
                _write_json_file(settings_path, settings)
                return
            raise ValueError(f"hook not found: {item_id}")

        removed = _remove_hook_entry(hooks, event_name, command)
        if removed is not None:
            _set_hook_entry_enabled(removed, False)
            _append_hook_entry(disabled_hooks, event_name, removed)
            _write_json_file(settings_path, settings)
            _write_json_file(disabled_path, disabled_hooks)
            return
        if _find_hook_entry(disabled_hooks, event_name, command) is not None:
            return
        raise ValueError(f"hook not found: {item_id}")


def _hooks_config_path(agent: AgentKind, root: Path) -> Path:
    return root / _hooks_config_name(agent)


def _hooks_root(settings: dict[str, Any]) -> dict[str, Any]:
    hooks = settings.get("hooks")
    if isinstance(hooks, dict):
        return hooks
    return {}


def _ensure_hooks_root(settings: dict[str, Any]) -> dict[str, Any]:
    hooks = settings.setdefault("hooks", {})
    if not isinstance(hooks, dict):
        hooks = {}
        settings["hooks"] = hooks
    return hooks


def _hook_command(definition: dict[str, Any], *, fallback: str) -> str:
    return _string(definition.get("command")) or _string(definition.get("prompt")) or fallback


def _find_hook_entry(hooks: dict[str, Any], event_name: str, command: str) -> dict[str, Any] | None:
    definitions = hooks.get(event_name)
    if not isinstance(definitions, list):
        return None
    for entry in definitions:
        if not isinstance(entry, dict):
            continue
        nested_hooks = entry.get("hooks")
        if isinstance(nested_hooks, list):
            for hook in nested_hooks:
                if isinstance(hook, dict) and _hook_command(hook, fallback="") == command:
                    return hook
            continue
        if _hook_command(entry, fallback="") == command:
            return entry
    return None


def _remove_hook_entry(hooks: dict[str, Any], event_name: str, command: str) -> dict[str, Any] | None:
    definitions = hooks.get(event_name)
    if not isinstance(definitions, list):
        return None
    for entry_index, entry in enumerate(definitions):
        if not isinstance(entry, dict):
            continue
        nested_hooks = entry.get("hooks")
        if isinstance(nested_hooks, list):
            for hook_index, hook in enumerate(nested_hooks):
                if not isinstance(hook, dict) or _hook_command(hook, fallback="") != command:
                    continue
                removed_hook = nested_hooks.pop(hook_index)
                removed_entry = {key: value for key, value in entry.items() if key != "hooks"}
                removed_entry["hooks"] = [removed_hook]
                if not nested_hooks:
                    definitions.pop(entry_index)
                _cleanup_hook_event(hooks, event_name)
                return removed_entry
            continue
        if _hook_command(entry, fallback="") == command:
            removed_entry = definitions.pop(entry_index)
            _cleanup_hook_event(hooks, event_name)
            return removed_entry
    return None


def _append_hook_entry(hooks: dict[str, Any], event_name: str, entry: dict[str, Any]) -> None:
    definitions = hooks.setdefault(event_name, [])
    if not isinstance(definitions, list):
        definitions = []
        hooks[event_name] = definitions
    definitions.append(entry)


def _cleanup_hook_event(hooks: dict[str, Any], event_name: str) -> None:
    definitions = hooks.get(event_name)
    if isinstance(definitions, list) and not definitions:
        hooks.pop(event_name, None)


def _set_hook_entry_enabled(entry: dict[str, Any], enabled: bool) -> None:
    nested_hooks = entry.get("hooks")
    if isinstance(nested_hooks, list):
        for hook in nested_hooks:
            if isinstance(hook, dict):
                _set_hook_entry_enabled(hook, enabled)
        if enabled:
            entry.pop("enabled", None)
        else:
            entry["enabled"] = False
        return
    if enabled:
        entry.pop("enabled", None)
    else:
        entry["enabled"] = False


def _read_json_file(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def _write_json_file(path: Path, data: dict[str, Any]) -> None:
    with _locked_config_writes(path):
        _write_text_file_atomic(path, json.dumps(data, indent=2, ensure_ascii=False) + "\n")


def _write_text_file_atomic(path: Path, content: str) -> None:
    write_path = path
    if path.is_symlink():
        with contextlib.suppress(OSError):
            write_path = path.resolve(strict=True)
    write_path.parent.mkdir(parents=True, exist_ok=True)
    existing_mode: int | None = None
    with contextlib.suppress(OSError):
        existing_mode = write_path.stat().st_mode & 0o777
    fd, temp_name = tempfile.mkstemp(
        prefix=f".{write_path.name}.",
        suffix=".tmp",
        dir=write_path.parent,
        text=True,
    )
    temp_path = Path(temp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            if existing_mode is not None:
                os.fchmod(handle.fileno(), existing_mode)
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_path, write_path)
    except BaseException:
        with contextlib.suppress(OSError):
            temp_path.unlink()
        raise


def _string(value: object) -> str | None:
    return value if isinstance(value, str) and value.strip() else None


def _deep_string(data: object, *keys: str) -> str | None:
    value = data
    for key in keys:
        if not isinstance(value, dict):
            return None
        value = value.get(key)
    return _string(value)


def _codex_plugin_header(line: str) -> str | None:
    header = re.match(r'\s*\[plugins\."([^"]+)"\]\s*(?:#.*)?$', line)
    return header.group(1) if header else None


def _is_toml_table_header(line: str) -> bool:
    return re.match(r"\s*\[\[?[^\[\]]+\]?\]\s*(?:#.*)?$", line) is not None


def _read_codex_plugin_enabled(path: Path) -> dict[str, bool]:
    if not path.is_file():
        return {}
    values: dict[str, bool] = {}
    current_plugin: str | None = None
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return {}
    for line in lines:
        plugin_id = _codex_plugin_header(line)
        if plugin_id is not None:
            current_plugin = plugin_id
            continue
        if _is_toml_table_header(line):
            current_plugin = None
        if current_plugin is None:
            continue
        enabled = re.match(r"\s*enabled\s*=\s*(true|false)\s*(?:#.*)?$", line, re.IGNORECASE)
        if enabled:
            values[current_plugin] = enabled.group(1).lower() == "true"
    return values


def _write_codex_plugin_enabled(path: Path, item_id: str, enabled: bool) -> None:
    _validate_codex_plugin_id(item_id)
    value = "true" if enabled else "false"
    with _locked_config_writes(path):
        if not path.exists():
            _write_text_file_atomic(path, f'[plugins."{item_id}"]\nenabled = {value}\n')
            return

        lines = path.read_text(encoding="utf-8").splitlines()
        output: list[str] = []
        in_target = False
        target_seen = False
        enabled_written = False
        for line in lines:
            plugin_id = _codex_plugin_header(line)
            if plugin_id is not None or _is_toml_table_header(line):
                if in_target and not enabled_written:
                    output.append(f"enabled = {value}")
                    enabled_written = True
                in_target = plugin_id == item_id
                if in_target:
                    target_seen = True
                output.append(line)
                continue
            if in_target and re.match(r"\s*enabled\s*=", line):
                output.append(f"enabled = {value}")
                enabled_written = True
                continue
            output.append(line)
        if in_target and not enabled_written:
            output.append(f"enabled = {value}")
        if not target_seen:
            if output and output[-1].strip():
                output.append("")
            output.extend([f'[plugins."{item_id}"]', f"enabled = {value}"])
        _write_text_file_atomic(path, "\n".join(output) + "\n")


def _validate_path_item_id(item_id: str) -> None:
    if (
        not item_id
        or item_id in {".", ".."}
        or "/" in item_id
        or "\\" in item_id
        or any(ord(character) < 32 for character in item_id)
    ):
        raise ValueError(f"invalid config item id: {item_id}")


def _validate_codex_plugin_id(item_id: str) -> None:
    if (
        not item_id
        or "\\" in item_id
        or '"' in item_id
        or any(ord(character) < 32 for character in item_id)
    ):
        raise ValueError(f"invalid config item id: {item_id}")


def _validate_json_key_item_id(item_id: str) -> None:
    if not item_id or any(ord(character) < 32 for character in item_id):
        raise ValueError(f"invalid config item id: {item_id}")
