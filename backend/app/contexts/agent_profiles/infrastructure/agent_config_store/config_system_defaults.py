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
):
    _module = _import_module(f"{__package__}.{_module_name}")
    globals().update(
        {name: value for name, value in _module.__dict__.items() if not name.startswith("__")}
    )


def _system_items_with_defaults(
    section_id: str,
    items,
    root: Path,
) -> list[AgentConfigItem]:
    overrides = _system_default_overrides(root).get(section_id, {})
    return [
        AgentConfigItem(
            item.id,
            item.name,
            overrides.get(item.id, item.enabled),
            item.path,
            item.origin,
            item.overridden,
        )
        for item in items
    ]


def _system_default_overrides(root: Path) -> dict[str, dict[str, bool]]:
    data = _read_json_file(root / SYSTEM_DEFAULTS_FILE)
    overrides: dict[str, dict[str, bool]] = {}
    sections = data.get("sections")
    if not isinstance(sections, list):
        return overrides
    for section in sections:
        if not isinstance(section, dict):
            continue
        section_id = section.get("id")
        if section_id not in {"skills", "plugins", "mcp"}:
            continue
        section_overrides = overrides.setdefault(section_id, {})
        items = section.get("items")
        if not isinstance(items, list):
            continue
        for item in items:
            if not isinstance(item, dict):
                continue
            item_id = item.get("id")
            enabled = item.get("enabled")
            if isinstance(item_id, str) and item_id and isinstance(enabled, bool):
                section_overrides[item_id] = enabled
    return overrides


def _set_system_default_item_enabled(
    root: Path,
    section_id: str,
    item_id: str,
    enabled: bool,
) -> None:
    _validate_system_default_item_id(section_id, item_id)
    path = root / SYSTEM_DEFAULTS_FILE
    with _locked_config_writes(path):
        data = _read_json_file(path)
        sections = data.setdefault("sections", [])
        if not isinstance(sections, list):
            sections = []
            data["sections"] = sections
        section = next(
            (
                candidate
                for candidate in sections
                if isinstance(candidate, dict) and candidate.get("id") == section_id
            ),
            None,
        )
        if section is None:
            section = {"id": section_id, "items": []}
            sections.append(section)
        items = section.setdefault("items", [])
        if not isinstance(items, list):
            items = []
            section["items"] = items
        item = next(
            (
                candidate
                for candidate in items
                if isinstance(candidate, dict) and candidate.get("id") == item_id
            ),
            None,
        )
        if item is None:
            items.append({"id": item_id, "enabled": enabled})
        else:
            item["enabled"] = enabled
        _write_json_file(path, data)


def _remove_system_default_item_enabled(root: Path, section_id: str, item_id: str) -> None:
    _validate_system_default_item_id(section_id, item_id)
    path = root / SYSTEM_DEFAULTS_FILE
    with _locked_config_writes(path):
        data = _read_json_file(path)
        sections = data.get("sections")
        if not isinstance(sections, list):
            return
        for section in list(sections):
            if not isinstance(section, dict) or section.get("id") != section_id:
                continue
            items = section.get("items")
            if not isinstance(items, list):
                continue
            section["items"] = [
                item for item in items
                if not (isinstance(item, dict) and item.get("id") == item_id)
            ]
            if not section["items"]:
                sections.remove(section)
            _write_json_file(path, data)
            return


def _validate_system_default_item_id(section_id: str, item_id: str) -> None:
    if section_id == "skills":
        _validate_path_item_id(item_id)
    elif section_id == "plugins":
        from app.contexts.agent_profiles.infrastructure.agent_config_store.config_system_plugins import (
            _validate_system_plugin_item_id,
        )

        _validate_system_plugin_item_id(item_id)
    elif section_id == "mcp":
        _validate_system_mcp_id(item_id)
    else:
        raise ValueError(f"unsupported system config section: {section_id}")
