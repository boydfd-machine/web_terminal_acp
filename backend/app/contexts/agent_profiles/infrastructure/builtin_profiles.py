from __future__ import annotations

from pathlib import Path

from app.contexts.agent_profiles.infrastructure import agent_config_store as agent_config
from app.contexts.agent_profiles.infrastructure.builtin_profile_specs import (
    BUILTIN_DEVELOPER_PROFILE_ID,
    BUILTIN_PROFILE_SPECS,
)
from app.contexts.agent_profiles.infrastructure.profile_store import AgentProfile
from app.contexts.agent_profiles.application.manifest_service import now_iso
from app.platform.plugins.agent_plugins import get_agent_plugin_registry

_BUILTIN_CREATED_AT = "2026-06-05T00:00:00+00:00"
BUILTIN_PROFILE_CONFIG_ROOT = ".web-terminal-acp/builtin-profile-config"
_CONFIGURABLE_SECTIONS = {"skills", "plugins", "hooks", "mcp"}
_FOCUSED_BUILTIN_PROFILE_IDS = {BUILTIN_DEVELOPER_PROFILE_ID}


def is_builtin_profile_id(profile_id: str) -> bool:
    return profile_id in BUILTIN_PROFILE_SPECS


def builtin_agent_profiles() -> list[AgentProfile]:
    return [_builtin_profile(profile_id) for profile_id in BUILTIN_PROFILE_SPECS]


def builtin_developer_profile() -> AgentProfile:
    return _builtin_profile(BUILTIN_DEVELOPER_PROFILE_ID)


def _builtin_profile(profile_id: str) -> AgentProfile:
    name, description, agent_md, _skills = BUILTIN_PROFILE_SPECS[profile_id]
    return AgentProfile(
        id=profile_id,
        name=name,
        description=description,
        default_agent_client="codex",
        agent_md=agent_md,
        created_at=_BUILTIN_CREATED_AT,
        updated_at=_BUILTIN_CREATED_AT,
    )


def get_builtin_agent_profile(profile_id: str) -> AgentProfile | None:
    return _builtin_profile(profile_id) if is_builtin_profile_id(profile_id) else None


def materialize_builtin_profile_for_window(
    profile_id: str,
    agent: str,
    *,
    window_id: str,
    home: Path | None = None,
) -> agent_config.AgentConfig | None:
    if not is_builtin_profile_id(profile_id):
        return None
    user_home = home or Path.home()
    agent_kind = agent_config.normalize_agent_kind(agent)
    selection = build_builtin_profile_selection(profile_id, agent_kind, home=user_home)
    agent_config.apply_agent_config_selection(selection, window_id=window_id, home=user_home)
    managed_root = agent_config._managed_agent_root(agent_kind, window_id, user_home)
    _write_builtin_common_config(
        managed_root,
        agent_kind,
        skills=_builtin_profile_skills(profile_id),
        agent_md=_builtin_profile_agent_md(profile_id),
        selection=selection,
    )
    return agent_config.list_agent_config(
        agent_kind,
        home=agent_config._managed_home_root(managed_root),
    )


def builtin_profile_config(
    profile_id: str, agent: str, *, home: Path | None = None
) -> agent_config.AgentConfig | None:
    if not is_builtin_profile_id(profile_id):
        return None
    agent_kind = agent_config.normalize_agent_kind(agent)
    global_config = agent_config.list_agent_config(agent_kind, home=home)
    system_config = agent_config.list_system_agent_config(home=home)
    overrides = _builtin_config_overrides(profile_id, agent_kind, home=home)
    sections: list[agent_config.AgentConfigSection] = [
        _builtin_skill_section(profile_id, global_config, system_config, overrides),
    ]
    for section in global_config.sections:
        if section.id == "skills":
            continue
        source_section = _section_with_system_mcp(section, system_config)
        section_overrides = overrides.get(section.id, {})
        sections.append(
            _section_with_overrides(
                source_section,
                section_overrides,
                default_from_item=profile_id not in _FOCUSED_BUILTIN_PROFILE_IDS,
            )
        )
    return agent_config.AgentConfig(agent=agent_kind, sections=sections)


def build_builtin_profile_selection(
    profile_id: str,
    agent: str,
    *,
    home: Path | None = None,
) -> agent_config.AgentConfigSelection:
    config = builtin_profile_config(profile_id, agent, home=home)
    if config is None:
        raise ValueError(f"built-in agent profile not found: {profile_id}")
    return agent_config.AgentConfigSelection(
        agent=config.agent,
        sections=[
            agent_config.AgentConfigSectionSelection(
                section.id,
                [agent_config.AgentConfigItemSelection(item.id, item.enabled) for item in section.items],
            )
            for section in config.sections
        ],
    )


def set_builtin_profile_config_item_enabled(
    profile_id: str,
    agent: str,
    section_id: str,
    item_id: str,
    enabled: bool,
    *,
    home: Path | None = None,
) -> agent_config.AgentConfig:
    if not is_builtin_profile_id(profile_id):
        raise ValueError(f"built-in agent profile not found: {profile_id}")
    agent_kind = agent_config.normalize_agent_kind(agent)
    config = builtin_profile_config(profile_id, agent_kind, home=home)
    if config is None:
        raise ValueError(f"built-in agent profile not found: {profile_id}")
    section = next((candidate for candidate in config.sections if candidate.id == section_id), None)
    if section is None or section.id not in _CONFIGURABLE_SECTIONS:
        raise ValueError(f"unsupported config section: {section_id}")
    if not any(item.id == item_id for item in section.items):
        raise ValueError(f"config item not found: {item_id}")
    _set_builtin_config_override(profile_id, agent_kind, section.id, item_id, enabled, home=home)
    updated = builtin_profile_config(profile_id, agent_kind, home=home)
    if updated is None:
        raise ValueError(f"built-in agent profile not found: {profile_id}")
    return updated


def _write_builtin_common_config(
    managed_root: Path,
    agent: agent_config.AgentKind,
    *,
    skills: tuple[tuple[str, str], ...],
    agent_md: str,
    selection: agent_config.AgentConfigSelection,
) -> None:
    skills_dir_name = agent_config._skills_directory(agent)
    for skill_id, skill_md in skills:
        enabled = _selection_item_enabled(selection, "skills", skill_id, default=True)
        _write_builtin_skill_config(managed_root, skills_dir_name, skill_id, skill_md, enabled=enabled)

    targets = (
        get_agent_plugin_registry()
        .by_agent_id(agent)
        .native_config.profile_agent_md_targets
    )
    for target_name in targets:
        target = managed_root / target_name
        agent_config._write_text_file_atomic(target, agent_md)


def _write_builtin_skill_config(
    managed_root: Path,
    skills_dir_name: str,
    skill_id: str,
    skill_md: str,
    *,
    enabled: bool,
) -> None:
    active = managed_root / skills_dir_name / skill_id
    disabled = managed_root / f"{skills_dir_name}.disabled" / skill_id
    target = active if enabled else disabled
    counterpart = disabled if enabled else active
    with agent_config._locked_config_writes(active, disabled):
        if counterpart.exists() or counterpart.is_symlink():
            agent_config._remove_path(counterpart)
        target.mkdir(parents=True, exist_ok=True)
        agent_config._write_text_file_atomic(target / "SKILL.md", skill_md)


def _builtin_skill_section(
    profile_id: str,
    global_config: agent_config.AgentConfig,
    system_config: agent_config.AgentConfig,
    overrides: dict[str, dict[str, bool]],
) -> agent_config.AgentConfigSection:
    skill_overrides = overrides.get("skills", {})
    builtin_skills = _builtin_profile_skills(profile_id)
    builtin_skill_ids = {skill_id for skill_id, _content in builtin_skills}
    items = [
        agent_config.AgentConfigItem(
            skill_id,
            skill_id,
            skill_overrides.get(skill_id, True),
            None,
        )
        for skill_id, _content in builtin_skills
    ]
    if profile_id in _FOCUSED_BUILTIN_PROFILE_IDS:
        global_skills = next(
            (section for section in global_config.sections if section.id == "skills"),
            None,
        )
        if global_skills is not None:
            items.extend(
                agent_config.AgentConfigItem(
                    item.id,
                    item.name,
                    skill_overrides.get(item.id, False),
                    item.path,
                )
                for item in global_skills.items
                if item.id not in builtin_skill_ids
            )
    existing_ids = {item.id for item in items}
    system_skills = next(
        (section for section in system_config.sections if section.id == "skills"),
        None,
    )
    if system_skills is not None:
        items.extend(
            agent_config.AgentConfigItem(
                item.id,
                item.name,
                skill_overrides.get(item.id, item.enabled),
                item.path,
                item.origin,
                item.overridden,
            )
            for item in system_skills.items
            if item.id not in existing_ids
        )
    return agent_config.AgentConfigSection("skills", "Skills", items)


def _builtin_profile_skills(profile_id: str) -> tuple[tuple[str, str], ...]:
    return BUILTIN_PROFILE_SPECS[profile_id][3]


def _builtin_profile_agent_md(profile_id: str) -> str:
    return BUILTIN_PROFILE_SPECS[profile_id][2]


def _section_with_overrides(
    section: agent_config.AgentConfigSection,
    overrides: dict[str, bool],
    *,
    default_from_item: bool,
) -> agent_config.AgentConfigSection:
    return agent_config.AgentConfigSection(
        section.id,
        section.name,
        [
            agent_config.AgentConfigItem(
                item.id,
                item.name,
                overrides.get(item.id, item.enabled if default_from_item else False),
                item.path,
                item.origin,
            )
            for item in section.items
        ],
    )


def _section_with_system_mcp(
    section: agent_config.AgentConfigSection,
    system_config: agent_config.AgentConfig,
) -> agent_config.AgentConfigSection:
    if section.id != "mcp":
        return section
    system_mcp = next((section for section in system_config.sections if section.id == "mcp"), None)
    if system_mcp is None:
        return section
    existing_ids = {item.id for item in section.items}
    items = [*section.items, *(item for item in system_mcp.items if item.id not in existing_ids)]
    return agent_config.AgentConfigSection(section.id, section.name, items)


def _selection_item_enabled(
    selection: agent_config.AgentConfigSelection,
    section_id: str,
    item_id: str,
    *,
    default: bool,
) -> bool:
    return next(
        (item.enabled for section in selection.sections if section.id == section_id for item in section.items if item.id == item_id),
        default,
    )


def _builtin_config_overrides(
    profile_id: str,
    agent: agent_config.AgentKind,
    *,
    home: Path | None,
) -> dict[str, dict[str, bool]]:
    data = agent_config._read_json_file(_builtin_config_path(profile_id, agent, home=home))
    overrides: dict[str, dict[str, bool]] = {}
    sections = data.get("sections")
    if not isinstance(sections, list):
        return overrides
    for section in sections:
        if not isinstance(section, dict):
            continue
        section_id = section.get("id")
        if section_id not in _CONFIGURABLE_SECTIONS:
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


def _set_builtin_config_override(
    profile_id: str,
    agent: agent_config.AgentKind,
    section_id: str,
    item_id: str,
    enabled: bool,
    *,
    home: Path | None,
) -> None:
    path = _builtin_config_path(profile_id, agent, home=home)
    with agent_config._locked_config_writes(path):
        data = agent_config._read_json_file(path)
        sections = data.setdefault("sections", [])
        if not isinstance(sections, list):
            sections = []
            data["sections"] = sections
        section = next((s for s in sections if isinstance(s, dict) and s.get("id") == section_id), None)
        if section is None:
            section = {"id": section_id, "items": []}
            sections.append(section)
        items = section.setdefault("items", [])
        if not isinstance(items, list):
            items = []
            section["items"] = items
        item = next(
            (candidate for candidate in items if isinstance(candidate, dict) and candidate.get("id") == item_id),
            None,
        )
        if item is None:
            items.append({"id": item_id, "enabled": enabled})
        else:
            item["enabled"] = enabled
        data["updated_at"] = now_iso()
        agent_config._write_json_file(path, data)


def _builtin_config_path(profile_id: str, agent: agent_config.AgentKind, *, home: Path | None) -> Path:
    return (home or Path.home()) / BUILTIN_PROFILE_CONFIG_ROOT / profile_id / f"{agent}.json"
