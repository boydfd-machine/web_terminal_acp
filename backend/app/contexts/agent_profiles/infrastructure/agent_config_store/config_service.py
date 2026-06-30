# ruff: noqa: F401,F821
"""Executed into agent_config_store's package globals."""

import contextlib
import json
import os
import re
import shutil
import tempfile
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from app.platform.plugins.agent_plugins import get_agent_plugin_registry
from app.platform.plugins.agent_plugins.shared_cache import link_shared_agent_cache_items
from app.platform.plugins.agent_plugins.types import AgentPlugin

AgentKind = str
SectionKind = Literal["skills", "plugins", "hooks", "mcp"]
ConfigItemOrigin = Literal["client", "system_builtin", "system_config"]
DISABLED_HOOKS_FILE = "hooks.disabled.json"
_CONFIG_WRITE_LOCKS: dict[str, threading.RLock] = {}
_CONFIG_WRITE_LOCKS_GUARD = threading.Lock()


@dataclass(frozen=True)
class AgentConfigItem:
    id: str
    name: str
    enabled: bool
    path: str | None = None
    origin: ConfigItemOrigin = "client"
    overridden: bool = False


@dataclass(frozen=True)
class AgentConfigSection:
    id: SectionKind
    name: str
    items: list[AgentConfigItem]


@dataclass(frozen=True)
class AgentConfig:
    agent: AgentKind
    sections: list[AgentConfigSection]


@dataclass(frozen=True)
class AgentConfigItemSelection:
    id: str
    enabled: bool


@dataclass(frozen=True)
class AgentConfigSectionSelection:
    id: SectionKind
    items: list[AgentConfigItemSelection]


@dataclass(frozen=True)
class AgentConfigSelection:
    agent: AgentKind
    sections: list[AgentConfigSectionSelection]


def list_agent_config(agent: str, *, home: Path | None = None) -> AgentConfig:
    agent_kind = _agent_kind(agent)
    root = _agent_root(agent_kind, home or Path.home())
    return AgentConfig(
        agent=agent_kind,
        sections=[
            AgentConfigSection(
                "skills",
                "Skills",
                _list_directory_items(root, _skills_directory(agent_kind)),
            ),
            AgentConfigSection("plugins", "Plugins", _list_plugins(agent_kind, root)),
            AgentConfigSection("hooks", "Hooks", _list_hooks(agent_kind, root)),
            AgentConfigSection("mcp", "MCP Servers", _list_mcp(agent_kind, root)),
        ],
    )


def set_agent_config_item_enabled(
    agent: str,
    section_id: str,
    item_id: str,
    enabled: bool,
    *,
    home: Path | None = None,
) -> AgentConfig:
    agent_kind = _agent_kind(agent)
    root = _agent_root(agent_kind, home or Path.home())
    if section_id == "skills":
        _set_directory_item_enabled(root, _skills_directory(agent_kind), item_id, enabled)
    elif section_id == "plugins":
        _set_plugin_enabled(agent_kind, root, item_id, enabled)
    elif section_id == "hooks":
        _set_hook_enabled(agent_kind, root, item_id, enabled)
    elif section_id == "mcp":
        _set_mcp_enabled(agent_kind, root, item_id, enabled)
    else:
        raise ValueError(f"unsupported config section: {section_id}")
    return list_agent_config(agent_kind, home=home)


def list_window_agent_config(
    agent: str,
    *,
    window_id: str,
    home: Path | None = None,
) -> AgentConfig:
    agent_kind = _agent_kind(agent)
    user_home = home or Path.home()
    managed_root = _ensure_window_agent_config_root(agent_kind, window_id, user_home)
    _merge_missing_system_skill_items(agent_kind, managed_root, user_home)
    return list_agent_config(agent_kind, home=_managed_home_root(managed_root))


def set_window_agent_config_item_enabled(
    agent: str,
    section_id: str,
    item_id: str,
    enabled: bool,
    *,
    window_id: str,
    home: Path | None = None,
) -> AgentConfig:
    agent_kind = _agent_kind(agent)
    user_home = home or Path.home()
    managed_root = _ensure_window_agent_config_root(agent_kind, window_id, user_home)
    _detach_window_config_section(agent_kind, managed_root, section_id)
    return set_agent_config_item_enabled(
        agent_kind,
        section_id,
        item_id,
        enabled,
        home=_managed_home_root(managed_root),
    )


def normalize_agent_kind(agent: str) -> AgentKind:
    return _agent_kind(agent)


def apply_agent_config_selection(
    selection: AgentConfigSelection,
    *,
    window_id: str,
    home: Path | None = None,
    protect_system_config_skills: bool = False,
) -> AgentConfig:
    agent_kind = _agent_kind(selection.agent)
    if agent_kind != selection.agent:
        raise ValueError(f"selection agent mismatch: {selection.agent}")

    user_home = home or Path.home()
    source_root = _agent_root(agent_kind, user_home)
    managed_root = _managed_agent_root(agent_kind, window_id, user_home)
    _materialize_agent_config_root(agent_kind, source_root, managed_root, user_home)
    install_system_config_for_agent_window(agent_kind, window_id=window_id, home=user_home)
    protected_skill_ids = set()
    if protect_system_config_skills:
        protected_skill_ids = enabled_system_config_skill_ids(user_home)
    for section in selection.sections:
        for item in section.items:
            if section.id == "skills" and not item.enabled and item.id in protected_skill_ids:
                continue
            try:
                set_agent_config_item_enabled(
                    agent_kind,
                    section.id,
                    item.id,
                    item.enabled,
                    home=_managed_home_root(managed_root),
                )
            except ValueError:
                continue
    return list_agent_config(agent_kind, home=_managed_home_root(managed_root))


def _agent_kind(agent: str) -> AgentKind:
    return get_agent_plugin_registry().normalize_agent_id(agent)


def _agent_plugin(agent: AgentKind) -> AgentPlugin:
    return get_agent_plugin_registry().by_agent_id(agent)


def _lock_key(path: Path) -> str:
    return str(path.expanduser().resolve(strict=False))


def _config_write_lock(path: Path) -> threading.RLock:
    key = _lock_key(path)
    with _CONFIG_WRITE_LOCKS_GUARD:
        lock = _CONFIG_WRITE_LOCKS.get(key)
        if lock is None:
            lock = threading.RLock()
            _CONFIG_WRITE_LOCKS[key] = lock
        return lock


@contextlib.contextmanager
def _locked_config_writes(*paths: Path):
    locks: list[threading.RLock] = []
    seen: set[str] = set()
    for path in sorted(paths, key=_lock_key):
        key = _lock_key(path)
        if key in seen:
            continue
        seen.add(key)
        locks.append(_config_write_lock(path))
    for lock in locks:
        lock.acquire()
    try:
        yield
    finally:
        for lock in reversed(locks):
            lock.release()


def _agent_root(agent: AgentKind, home: Path) -> Path:
    return home / _agent_plugin(agent).storage.user_root


def _managed_agent_root(agent: AgentKind, window_id: str, home: Path) -> Path:
    return home / _agent_plugin(agent).storage.managed_root / window_id


def _managed_home_root(managed_root: Path) -> Path:
    return managed_root.parent / ".managed-home" / managed_root.name


def _ensure_window_agent_config_root(agent: AgentKind, window_id: str, home: Path) -> Path:
    managed_root = _managed_agent_root(agent, window_id, home)
    source_root = _agent_root(agent, home)
    _materialize_agent_config_root(agent, source_root, managed_root, home)
    return managed_root


def _materialize_agent_config_root(
    agent: AgentKind,
    source_root: Path,
    managed_root: Path,
    user_home: Path,
) -> None:
    managed_root.mkdir(parents=True, exist_ok=True)
    item_names = _agent_config_item_names(agent)
    for item_name in item_names:
        source = source_root / item_name
        target = managed_root / item_name
        if not source.exists():
            continue
        if source.is_dir():
            _copy_config_item_directory(agent, managed_root, item_name, source, target)
        elif not target.exists():
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target, follow_symlinks=True)

    _link_agent_history_items(agent, source_root, managed_root)
    _copy_external_agent_state_items(agent, source_root, managed_root)
    link_shared_agent_cache_items(agent, managed_root, home=user_home)

    home_root = _managed_home_root(managed_root)
    alias = _managed_home_alias_path(agent, home_root)
    alias.parent.mkdir(parents=True, exist_ok=True)
    if not alias.exists() and not alias.is_symlink():
        with contextlib.suppress(OSError):
            alias.symlink_to(managed_root)
    if not alias.exists() and not alias.is_symlink():
        _copy_config_directory(managed_root, alias)


def _merge_missing_system_skill_items(
    agent: AgentKind,
    managed_root: Path,
    user_home: Path,
) -> None:
    system_root = _system_config_root(user_home)
    skills_dir = _skills_directory(agent)
    _merge_missing_system_skill_tree(
        system_root / SYSTEM_SKILLS_DIR,
        managed_root / skills_dir,
        managed_root / f"{skills_dir}.disabled",
    )
    _merge_missing_system_skill_tree(
        system_root / SYSTEM_DISABLED_SKILLS_DIR,
        managed_root / f"{skills_dir}.disabled",
        managed_root / skills_dir,
    )


def _merge_missing_system_skill_tree(source: Path, target: Path, counterpart: Path) -> None:
    if not source.is_dir():
        return
    for child in sorted(source.iterdir(), key=lambda candidate: candidate.name):
        if not child.is_dir() or not (child / "SKILL.md").is_file():
            continue
        destination = target / child.name
        counterpart_destination = counterpart / child.name
        if destination.exists() or destination.is_symlink():
            continue
        if counterpart_destination.exists() or counterpart_destination.is_symlink():
            continue
        _link_or_copy_config_child(child, destination)


def _copy_config_item_directory(
    agent: AgentKind,
    managed_root: Path,
    item_name: str,
    source: Path,
    target: Path,
) -> None:
    counterpart = _managed_config_directory_counterpart(agent, item_name)
    if target.is_symlink():
        if counterpart is None:
            return
        target.unlink(missing_ok=True)
    if target.exists() and not target.is_dir():
        return
    if counterpart is None:
        _copy_config_directory(source, target)
        return

    target.mkdir(parents=True, exist_ok=True)
    counterpart_root = managed_root / counterpart
    for child in sorted(source.iterdir(), key=lambda candidate: candidate.name):
        if child.is_symlink() and not child.exists():
            continue
        child_target = target / child.name
        if child_target.exists() or (counterpart_root / child.name).exists():
            continue
        if child.is_dir():
            _link_config_directory(child, child_target)
        else:
            shutil.copy2(child, child_target, follow_symlinks=True)


def _copy_config_directory(source: Path, target: Path) -> None:
    shutil.copytree(source, target, symlinks=True, dirs_exist_ok=True)


def _link_or_copy_config_child(source: Path, target: Path) -> None:
    if source.is_dir():
        _link_config_directory(source, target)
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target, follow_symlinks=True)


def _link_config_directory(source: Path, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    with contextlib.suppress(OSError):
        target.symlink_to(source, target_is_directory=True)
    if not target.exists() and not target.is_symlink():
        _copy_config_directory(source, target)


def _managed_home_alias_path(agent: AgentKind, home_root: Path) -> Path:
    plugin_alias = _agent_plugin(agent).storage.managed_home_alias
    if not plugin_alias:
        return home_root / _agent_root(agent, Path()).name
    alias_path = Path(plugin_alias)
    if alias_path.is_absolute() or ".." in alias_path.parts:
        raise ValueError(f"invalid managed home alias: {plugin_alias}")
    return home_root / alias_path


def _managed_config_directory_counterpart(agent: AgentKind, item_name: str) -> str | None:
    skills = _skills_directory(agent)
    counterparts = {
        skills: f"{skills}.disabled",
        f"{skills}.disabled": skills,
        "plugins": "plugins.disabled",
        "plugins.disabled": "plugins",
    }
    return counterparts.get(item_name)


def _detach_window_config_section(agent: AgentKind, managed_root: Path, section_id: str) -> None:
    if section_id == "skills":
        _detach_window_config_items(
            managed_root,
            (_skills_directory(agent), f"{_skills_directory(agent)}.disabled"),
        )
        return
    if section_id == "plugins":
        plugin = _agent_plugin(agent)
        if plugin.native_config.plugin_strategy == "codex_toml":
            _detach_window_config_items(managed_root, ("config.toml",))
        elif plugin.native_config.plugin_strategy == "claude_settings":
            _detach_window_config_items(managed_root, ("settings.json",))
        else:
            _detach_window_config_items(managed_root, ("plugins", "plugins.disabled"))
        return
    if section_id == "hooks":
        _detach_window_config_items(managed_root, (_hooks_config_name(agent), DISABLED_HOOKS_FILE))
        return
    if section_id == "mcp":
        _detach_mcp_window_config_items(agent, managed_root)


def _hooks_config_name(agent: AgentKind) -> str:
    return _agent_plugin(agent).native_config.hooks_config_name


def _detach_window_config_items(managed_root: Path, item_names: tuple[str, ...]) -> None:
    for item_name in item_names:
        path = managed_root / item_name
        if path.is_symlink():
            _replace_symlink_with_copy(path)


def _replace_symlink_with_copy(path: Path) -> None:
    try:
        source = path.resolve(strict=True)
    except FileNotFoundError:
        path.unlink(missing_ok=True)
        return
    path.unlink()
    if source.is_dir():
        _copy_config_directory(source, path)
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, path, follow_symlinks=True)


def _link_agent_history_items(agent: AgentKind, source_root: Path, managed_root: Path) -> None:
    for item_name in _agent_history_item_names(agent):
        _link_existing_item(source_root / item_name, managed_root / item_name)


def _link_existing_item(source: Path, target: Path) -> None:
    if not source.exists() or target.exists() or target.is_symlink():
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    with contextlib.suppress(OSError):
        target.symlink_to(source)


def _agent_config_item_names(agent: AgentKind) -> tuple[str, ...]:
    return _agent_plugin(agent).storage.config_item_names


def _agent_history_item_names(agent: AgentKind) -> tuple[str, ...]:
    return _agent_plugin(agent).storage.history_item_names


def _skills_directory(agent: AgentKind) -> str:
    return _agent_plugin(agent).storage.skills_directory


def _list_directory_items(
    root: Path,
    section: str,
    *,
    origin: ConfigItemOrigin = "client",
) -> list[AgentConfigItem]:
    items: dict[str, AgentConfigItem] = {}
    for enabled, base in ((False, root / f"{section}.disabled"), (True, root / section)):
        if not base.exists():
            continue
        for path in sorted(child for child in base.iterdir() if child.is_dir()):
            marker = path / "SKILL.md"
            if section in {"skills", "skills-cursor"} and not marker.exists():
                continue
            items[path.name] = AgentConfigItem(
                id=path.name,
                name=_name_from_skill(marker) or path.name,
                enabled=enabled,
                path=str(path),
                origin=origin,
            )
    return sorted(items.values(), key=lambda item: item.name.lower())


def _set_directory_item_enabled(root: Path, section: str, item_id: str, enabled: bool) -> None:
    _validate_path_item_id(item_id)
    active = root / section / item_id
    disabled = root / f"{section}.disabled" / item_id
    source = disabled if enabled else active
    target = active if enabled else disabled
    with _locked_config_writes(active.parent, disabled.parent, active, disabled):
        if not source.exists():
            if target.exists():
                return
            raise ValueError(f"config item not found: {item_id}")
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            raise ValueError(f"config item already exists at target: {item_id}")
        shutil.move(str(source), str(target))


def _name_from_skill(path: Path) -> str | None:
    if not path.is_file():
        return None
    try:
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines()[:20]:
            match = re.match(r"\s*name:\s*[\"']?([^\"']+)[\"']?\s*$", line)
            if match:
                return match.group(1).strip()
    except OSError:
        return None
    return None


for _module_name in (
    "config_items",
    "config_plugins",
    "config_mcp",
    "config_system",
    "config_model_settings",
    "config_model_materialization",
    "config_model_metadata",
    "config_system_defaults",
    "config_system_queries",
    "config_builtin_mcp",
    "config_system_detail",
    "config_system_materialization",
):
    from importlib import import_module as _import_module

    _module = _import_module(f"{__package__}.{_module_name}")
    globals().update(
        {name: value for name, value in _module.__dict__.items() if not name.startswith("__")}
    )

__all__ = [name for name in globals() if not name.startswith("__")]
