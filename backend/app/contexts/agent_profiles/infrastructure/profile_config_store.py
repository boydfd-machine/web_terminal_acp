from __future__ import annotations

from pathlib import Path
from typing import Any

from app.contexts.agent_profiles.application.manifest_service import (
    AgentProfileManifest,
    now_iso,
    read_manifest,
    write_manifest,
)
from app.contexts.agent_profiles.infrastructure import agent_config_store as agent_config
from app.platform.plugins.agent_plugins import get_agent_plugin_registry


def initial_client_configs(home: Path) -> dict[str, Any]:
    configs: dict[str, Any] = {}
    system_config = agent_config.list_system_agent_config(home=home)
    system_mcp = next(
        (section for section in system_config.sections if section.id == "mcp"),
        None,
    )
    for agent in _agent_clients():
        try:
            config = agent_config.list_agent_config(agent, home=home)
        except ValueError:
            continue
        configs[agent] = {
            "sections": [
                {
                    "id": section.id,
                    "items": [
                        {
                            "id": item.id,
                            "enabled": False if section.id == "mcp" else item.enabled,
                        }
                        for item in _initial_section_items(section, system_mcp)
                        if section.id not in {"skills", "plugins"}
                    ],
                }
                for section in config.sections
                if section.id not in {"skills", "plugins"}
            ]
        }
    return configs


def client_config_selection(root: Path, agent: agent_config.AgentKind) -> dict[str, Any]:
    manifest = read_manifest(root).to_dict()
    configs = manifest.setdefault("client_configs", {})
    if not isinstance(configs, dict):
        configs = {}
        manifest["client_configs"] = configs
    config = configs.setdefault(agent, {"sections": []})
    if not isinstance(config, dict):
        config = {"sections": []}
        configs[agent] = config
    return config


def selection_overrides(client_config: dict[str, Any]) -> dict[str, dict[str, bool]]:
    overrides: dict[str, dict[str, bool]] = {}
    sections = client_config.get("sections")
    if not isinstance(sections, list):
        return overrides
    for section in sections:
        if not isinstance(section, dict):
            continue
        section_id = section.get("id")
        if section_id not in {"skills", "plugins", "hooks", "mcp"}:
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


def set_client_config_override(
    root: Path,
    agent: agent_config.AgentKind,
    section_id: str,
    item_id: str,
    enabled: bool,
) -> None:
    _validate_config_item(agent, section_id, item_id)
    with agent_config._locked_config_writes(root / "profile.json"):
        manifest = read_manifest(root).to_dict()
        configs = manifest.setdefault("client_configs", {})
        if not isinstance(configs, dict):
            configs = {}
            manifest["client_configs"] = configs
        client_config = configs.setdefault(agent, {"sections": []})
        if not isinstance(client_config, dict):
            client_config = {"sections": []}
            configs[agent] = client_config
        sections = client_config.setdefault("sections", [])
        if not isinstance(sections, list):
            sections = []
            client_config["sections"] = sections
        section = _profile_config_section(sections, section_id)
        items = section.setdefault("items", [])
        if not isinstance(items, list):
            items = []
            section["items"] = items
        item = _profile_config_item(items, item_id)
        if item is None:
            items.append({"id": item_id, "enabled": enabled})
        else:
            item["enabled"] = enabled
        manifest["updated_at"] = now_iso()
        write_manifest(root, AgentProfileManifest.from_dict(root.name, manifest))


def _agent_clients() -> tuple[agent_config.AgentKind, ...]:
    return tuple(plugin.agent_client_id for plugin in get_agent_plugin_registry().all())


def _initial_section_items(
    section: agent_config.AgentConfigSection,
    system_mcp: agent_config.AgentConfigSection | None,
) -> list[agent_config.AgentConfigItem]:
    items = list(section.items)
    if section.id != "mcp" or system_mcp is None:
        return items
    existing_ids = {item.id for item in items}
    items.extend(item for item in system_mcp.items if item.id not in existing_ids)
    return items


def _validate_config_item(
    agent: agent_config.AgentKind,
    section_id: str,
    item_id: str,
) -> None:
    if section_id == "skills":
        agent_config._validate_path_item_id(item_id)
    elif section_id == "plugins":
        strategy = get_agent_plugin_registry().by_agent_id(agent).native_config.plugin_strategy
        if strategy == "codex_toml":
            agent_config._validate_codex_plugin_id(item_id)
        elif strategy == "claude_settings":
            agent_config._validate_json_key_item_id(item_id)
        else:
            agent_config._validate_path_item_id(item_id)
    elif section_id == "hooks":
        agent_config._validate_json_key_item_id(item_id)
    elif section_id == "mcp":
        strategy = get_agent_plugin_registry().by_agent_id(agent).native_config.mcp_strategy
        if strategy == "codex_toml":
            agent_config._validate_codex_plugin_id(item_id)
        else:
            agent_config._validate_json_key_item_id(item_id)


def _profile_config_section(
    sections: list[Any],
    section_id: str,
) -> dict[str, Any]:
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
    return section


def _profile_config_item(
    items: list[Any],
    item_id: str,
) -> dict[str, Any] | None:
    return next(
        (
            candidate
            for candidate in items
            if isinstance(candidate, dict) and candidate.get("id") == item_id
        ),
        None,
    )
