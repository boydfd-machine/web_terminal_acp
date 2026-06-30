from __future__ import annotations

import contextlib
import shutil
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

from app.contexts.agent_profiles.infrastructure import agent_config_store as agent_config
from app.contexts.agent_profiles.infrastructure import profile_config_store
from app.platform.plugins.agent_plugins import get_agent_plugin_registry
from app.contexts.agent_profiles.application.manifest_service import (
    AgentProfileManifest,
    now_iso,
    read_manifest,
    validate_profile_id,
    write_manifest,
)

COMMON_SKILLS_DIR = "skills"
COMMON_DISABLED_SKILLS_DIR = "skills.disabled"
COMMON_AGENT_MD = "AGENT.md"
_UNSET = object()


@dataclass(frozen=True)
class AgentProfile:
    id: str
    name: str
    description: str | None
    default_agent_client: agent_config.AgentKind
    agent_md: str
    created_at: str
    updated_at: str


def list_agent_profiles(*, home: Path | None = None) -> list[AgentProfile]:
    root = _profiles_root(home or Path.home())
    if not root.exists():
        return []
    profiles = []
    for child in sorted(root.iterdir(), key=lambda path: path.name):
        if not child.is_dir():
            continue
        with contextlib.suppress(ValueError, OSError):
            profiles.append(_profile_from_root(child))
    return sorted(profiles, key=lambda profile: (profile.name.lower(), profile.id))


def get_agent_profile(profile_id: str, *, home: Path | None = None) -> AgentProfile:
    return _profile_from_root(_profile_root(profile_id, home or Path.home()))


def create_agent_profile(
    *,
    name: str,
    description: str | None = None,
    default_agent_client: str = "codex",
    source_agent_client: str | None = None,
    home: Path | None = None,
) -> AgentProfile:
    user_home = home or Path.home()
    default_client = agent_config.normalize_agent_kind(default_agent_client)
    source_client = agent_config.normalize_agent_kind(source_agent_client or default_client)
    profile_id = uuid4().hex
    root = _profile_root(profile_id, user_home, must_exist=False)
    root.mkdir(parents=True)
    now = now_iso()
    _copy_initial_common_skills(source_client, root, user_home)
    _copy_initial_system_skills(source_client, root, user_home)
    _disable_initial_skills(root)
    _write_agent_md(root, _read_initial_agent_md(source_client, user_home))
    write_manifest(
        root,
        AgentProfileManifest.new(
            profile_id=profile_id,
            name=name,
            description=description,
            default_agent_client=default_client,
            client_configs=profile_config_store.initial_client_configs(user_home),
            now=now,
        ),
    )
    return _profile_from_root(root)


def update_agent_profile(
    profile_id: str,
    *,
    name: str | None = None,
    description: str | None | object = _UNSET,
    default_agent_client: str | None = None,
    agent_md: str | None | object = _UNSET,
    home: Path | None = None,
) -> AgentProfile:
    root = _profile_root(profile_id, home or Path.home())
    with agent_config._locked_config_writes(root / "profile.json", root / COMMON_AGENT_MD):
        manifest = read_manifest(root)
        if agent_md is not _UNSET:
            _write_agent_md(root, agent_md if isinstance(agent_md, str) else "")
        write_manifest(
            root,
            manifest.with_updates(
                name=name,
                description=description,
                description_set=description is not _UNSET,
                default_agent_client=default_agent_client,
                updated_at=now_iso(),
            ),
        )
    return _profile_from_root(root)


def delete_agent_profile(profile_id: str, *, home: Path | None = None) -> None:
    root = _profile_root(profile_id, home or Path.home())
    shutil.rmtree(root)


def list_agent_profile_config(
    profile_id: str,
    agent: str,
    *,
    home: Path | None = None,
) -> agent_config.AgentConfig:
    user_home = home or Path.home()
    root = _profile_root(profile_id, user_home)
    agent_kind = agent_config.normalize_agent_kind(agent)
    profile_config = profile_config_store.client_config_selection(root, agent_kind)
    overrides = profile_config_store.selection_overrides(profile_config)
    global_config = agent_config.list_agent_config(agent_kind, home=user_home)
    system_config = agent_config.list_system_agent_config(home=user_home)
    system_plugin_defaults = agent_config._system_plugin_defaults_for_agent(
        system_config,
        agent_kind,
    )
    sections: list[agent_config.AgentConfigSection] = [
        _profile_skill_section(root, system_config, overrides.get("skills", {}))
    ]
    for section in global_config.sections:
        if section.id == "skills":
            continue
        section_overrides = overrides.get(section.id, {})
        items = list(section.items)
        if section.id == "mcp":
            system_mcp = next(
                (candidate for candidate in system_config.sections if candidate.id == "mcp"),
                None,
            )
            if system_mcp is not None:
                existing_ids = {item.id for item in items}
                items.extend(item for item in system_mcp.items if item.id not in existing_ids)
        sections.append(
            agent_config.AgentConfigSection(
                section.id,
                section.name,
                [
                    agent_config.AgentConfigItem(
                        item.id,
                        item.name,
                        section_overrides.get(
                            item.id,
                            _profile_config_default_enabled(
                                section.id,
                                item,
                                system_plugin_defaults,
                            ),
                        ),
                        item.path,
                        item.origin,
                    )
                    for item in items
                ],
            )
        )
    return agent_config.AgentConfig(agent=agent_kind, sections=sections)


def _profile_config_default_enabled(
    section_id: str,
    item: agent_config.AgentConfigItem,
    system_plugin_defaults: dict[str, bool],
) -> bool:
    if section_id == "mcp":
        return False
    if section_id == "plugins":
        return system_plugin_defaults.get(item.id, item.enabled)
    return item.enabled


def set_agent_profile_config_item_enabled(
    profile_id: str,
    agent: str,
    section_id: str,
    item_id: str,
    enabled: bool,
    *,
    home: Path | None = None,
) -> agent_config.AgentConfig:
    user_home = home or Path.home()
    root = _profile_root(profile_id, user_home)
    agent_kind = agent_config.normalize_agent_kind(agent)
    if section_id == "skills":
        if _profile_skill_root(root, item_id) is not None:
            agent_config._set_directory_item_enabled(root, COMMON_SKILLS_DIR, item_id, enabled)
        elif _system_skill_item(
            system_config=agent_config.list_system_agent_config(home=user_home),
            item_id=item_id,
        ) is not None:
            profile_config_store.set_client_config_override(root, agent_kind, section_id, item_id, enabled)
        else:
            agent_config._set_directory_item_enabled(root, COMMON_SKILLS_DIR, item_id, enabled)
        _touch_profile(root)
    elif section_id in {"plugins", "hooks", "mcp"}:
        profile_config_store.set_client_config_override(
            root,
            agent_kind,
            section_id,
            item_id,
            enabled,
        )
    else:
        raise ValueError(f"unsupported config section: {section_id}")
    return list_agent_profile_config(profile_id, agent_kind, home=user_home)


def build_agent_profile_selection(
    profile_id: str,
    agent: str,
    *,
    home: Path | None = None,
) -> agent_config.AgentConfigSelection:
    config = list_agent_profile_config(profile_id, agent, home=home)
    return agent_config.AgentConfigSelection(
        agent=config.agent,
        sections=[
            agent_config.AgentConfigSectionSelection(
                section.id,
                [
                    agent_config.AgentConfigItemSelection(item.id, item.enabled)
                    for item in section.items
                ],
            )
            for section in config.sections
        ],
    )


def materialize_agent_profile_for_window(
    profile_id: str,
    agent: str,
    *,
    window_id: str,
    home: Path | None = None,
) -> agent_config.AgentConfig:
    user_home = home or Path.home()
    root = _profile_root(profile_id, user_home)
    agent_kind = agent_config.normalize_agent_kind(agent)
    selection = build_agent_profile_selection(profile_id, agent_kind, home=user_home)
    agent_config.apply_agent_config_selection(
        selection,
        window_id=window_id,
        home=user_home,
    )
    managed_root = agent_config._managed_agent_root(agent_kind, window_id, user_home)
    _copy_profile_common_config(
        root,
        managed_root,
        agent_kind,
        system_config=agent_config.list_system_agent_config(home=user_home),
    )
    return agent_config.list_agent_config(
        agent_kind,
        home=agent_config._managed_home_root(managed_root),
    )


def _profiles_root(home: Path) -> Path:
    return home / ".web-terminal-acp" / "agents"


def _profile_root(profile_id: str, home: Path, *, must_exist: bool = True) -> Path:
    validate_profile_id(profile_id)
    root = _profiles_root(home) / profile_id
    if must_exist and not root.is_dir():
        raise ValueError(f"agent profile not found: {profile_id}")
    return root


def _profile_from_root(root: Path) -> AgentProfile:
    manifest = read_manifest(root)
    return AgentProfile(
        id=manifest.id,
        name=manifest.name,
        description=manifest.description,
        default_agent_client=manifest.default_agent_client,
        agent_md=_read_agent_md(root),
        created_at=manifest.created_at,
        updated_at=manifest.updated_at,
    )


def _touch_profile(root: Path) -> None:
    with agent_config._locked_config_writes(root / "profile.json"):
        manifest = read_manifest(root)
        write_manifest(root, manifest.with_updates(updated_at=now_iso()))


def _read_agent_md(root: Path) -> str:
    path = root / COMMON_AGENT_MD
    if not path.is_file():
        return ""
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return ""


def _write_agent_md(root: Path, content: str) -> None:
    root.mkdir(parents=True, exist_ok=True)
    agent_config._write_text_file_atomic(root / COMMON_AGENT_MD, content)


def _copy_initial_common_skills(
    source_agent: agent_config.AgentKind, root: Path, home: Path
) -> None:
    source_root = agent_config._agent_root(source_agent, home)
    source_skills = source_root / agent_config._skills_directory(source_agent)
    disabled_skills = source_root / f"{agent_config._skills_directory(source_agent)}.disabled"
    (root / COMMON_SKILLS_DIR).mkdir(parents=True, exist_ok=True)
    if source_skills.exists():
        shutil.copytree(source_skills, root / COMMON_SKILLS_DIR, symlinks=True, dirs_exist_ok=True)
    (root / COMMON_DISABLED_SKILLS_DIR).mkdir(parents=True, exist_ok=True)
    if disabled_skills.exists():
        shutil.copytree(
            disabled_skills,
            root / COMMON_DISABLED_SKILLS_DIR,
            symlinks=True,
            dirs_exist_ok=True,
        )


def _copy_initial_system_skills(
    source_agent: agent_config.AgentKind, root: Path, home: Path
) -> None:
    source_root = agent_config._agent_root(source_agent, home)
    system_root = agent_config._system_config_root(home)
    agent_config._install_system_skills(
        source_agent,
        system_root,
        root,
        source_root,
        user_home=home,
        include_managed_agent_skills=False,
        target_skills_dir=COMMON_SKILLS_DIR,
    )


def _disable_initial_skills(root: Path) -> None:
    active = root / COMMON_SKILLS_DIR
    disabled = root / COMMON_DISABLED_SKILLS_DIR
    active.mkdir(parents=True, exist_ok=True)
    disabled.mkdir(parents=True, exist_ok=True)
    for child in sorted(active.iterdir(), key=lambda candidate: candidate.name):
        target = disabled / child.name
        if target.exists() or target.is_symlink():
            agent_config._remove_path(target)
        shutil.move(str(child), str(target))


def _read_initial_agent_md(source_agent: agent_config.AgentKind, home: Path) -> str:
    source_root = agent_config._agent_root(source_agent, home)
    candidates = (
        get_agent_plugin_registry()
        .by_agent_id(source_agent)
        .native_config.initial_agent_md_candidates
    )
    for candidate in candidates:
        path = source_root / candidate
        if path.is_file():
            try:
                return path.read_text(encoding="utf-8")
            except OSError:
                return ""
    return ""


def _copy_profile_common_config(
    root: Path,
    managed_root: Path,
    agent: agent_config.AgentKind,
    *,
    system_config: agent_config.AgentConfig,
) -> None:
    skills_dir = agent_config._skills_directory(agent)
    system_enabled_skill_ids = _system_enabled_skill_ids(system_config)
    _prune_profile_skill_trees(
        managed_root / skills_dir,
        managed_root / f"{skills_dir}.disabled",
        keep_ids=_profile_skill_ids(root) | {item.id for item in _system_skill_items(system_config)},
    )
    _merge_profile_skill_tree(
        root / COMMON_SKILLS_DIR,
        managed_root / skills_dir,
        managed_root / f"{skills_dir}.disabled",
    )
    _merge_profile_skill_tree(
        root / COMMON_DISABLED_SKILLS_DIR,
        managed_root / f"{skills_dir}.disabled",
        managed_root / skills_dir,
        skip_ids=system_enabled_skill_ids,
    )
    agent_md = root / COMMON_AGENT_MD
    if not agent_md.is_file():
        return
    targets = (
        get_agent_plugin_registry()
        .by_agent_id(agent)
        .native_config.profile_agent_md_targets
    )
    for target_name in targets:
        target = managed_root / target_name
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists() or target.is_symlink():
            if target.is_dir() and not target.is_symlink():
                shutil.rmtree(target)
            else:
                target.unlink()
        shutil.copy2(agent_md, target, follow_symlinks=True)


def _profile_skill_section(
    root: Path,
    system_config: agent_config.AgentConfig,
    skill_overrides: dict[str, bool],
) -> agent_config.AgentConfigSection:
    system_enabled_skill_ids = _system_enabled_skill_ids(system_config)
    profile_items = agent_config._list_directory_items(root, COMMON_SKILLS_DIR)
    items = [
        agent_config.AgentConfigItem(
            item.id,
            item.name,
            skill_overrides.get(
                item.id,
                True if item.id in system_enabled_skill_ids else item.enabled,
            ),
            item.path,
            item.origin,
        )
        for item in profile_items
    ]
    existing_ids = {item.id for item in items}
    for item in _system_skill_items(system_config):
        if item.id in existing_ids:
            continue
        items.append(
            agent_config.AgentConfigItem(
                item.id,
                item.name,
                skill_overrides.get(item.id, item.enabled),
                item.path,
                item.origin,
                item.overridden,
            )
        )
    return agent_config.AgentConfigSection(
        "skills",
        "Skills",
        sorted(items, key=lambda item: item.name.lower()),
    )


def _system_enabled_skill_ids(system_config: agent_config.AgentConfig) -> set[str]:
    return {
        item.id
        for item in _system_skill_items(system_config)
        if item.enabled and item.origin == "system_config"
    }


def _system_skill_items(system_config: agent_config.AgentConfig) -> list[agent_config.AgentConfigItem]:
    return next((section.items for section in system_config.sections if section.id == "skills"), [])


def _system_skill_item(
    *,
    system_config: agent_config.AgentConfig,
    item_id: str,
) -> agent_config.AgentConfigItem | None:
    return next((item for item in _system_skill_items(system_config) if item.id == item_id), None)


def _profile_skill_root(root: Path, item_id: str) -> Path | None:
    agent_config._validate_path_item_id(item_id)
    for base in (root / COMMON_SKILLS_DIR, root / COMMON_DISABLED_SKILLS_DIR):
        candidate = base / item_id
        if candidate.is_dir():
            return candidate
    return None


def _profile_skill_ids(root: Path) -> set[str]:
    return {
        child.name
        for base in (root / COMMON_SKILLS_DIR, root / COMMON_DISABLED_SKILLS_DIR)
        if base.exists()
        for child in base.iterdir()
        if child.is_dir()
    }


def _prune_profile_skill_trees(active: Path, disabled: Path, *, keep_ids: set[str]) -> None:
    for base in (active, disabled):
        base.mkdir(parents=True, exist_ok=True)
        for child in list(base.iterdir()):
            if child.name not in keep_ids:
                agent_config._remove_path(child)


def _merge_profile_skill_tree(
    source: Path,
    target: Path,
    counterpart: Path,
    *,
    skip_ids: set[str] | None = None,
) -> None:
    target.mkdir(parents=True, exist_ok=True)
    if not source.exists():
        return
    skip = skip_ids or set()
    for child in sorted(source.iterdir(), key=lambda candidate: candidate.name):
        if child.name in skip:
            continue
        destination = target / child.name
        counterpart_destination = counterpart / child.name
        if counterpart_destination.exists() or counterpart_destination.is_symlink():
            agent_config._remove_path(counterpart_destination)
        if destination.exists() or destination.is_symlink():
            agent_config._remove_path(destination)
        agent_config._link_or_copy_config_child(child, destination)
