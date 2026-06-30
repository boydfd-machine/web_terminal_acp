from importlib import import_module as _import_module

for _module_name in ("config_service",):
    _module = _import_module(f"{__package__}.{_module_name}")
    globals().update(
        {name: value for name, value in _module.__dict__.items() if not name.startswith("__")}
    )

MAX_MANAGED_SKILL_HOME_SCAN = 64


def _managed_agent_skill_items(home: Path) -> list[AgentConfigItem]:
    items: dict[str, AgentConfigItem] = {}
    for plugin in get_agent_plugin_registry().all():
        for skill_root in _managed_agent_skill_roots(
            home,
            plugin.storage.managed_root,
            plugin.storage.skills_directory,
        ):
            marker = skill_root / "SKILL.md"
            items[skill_root.name] = AgentConfigItem(
                skill_root.name,
                _name_from_skill(marker) or skill_root.name,
                True,
                str(skill_root),
                "system_builtin",
            )
    return sorted(items.values(), key=lambda item: (item.name.lower(), item.id.lower()))


def _managed_agent_skill_roots(
    home: Path,
    managed_root_name: str,
    skills_directory: str,
    *,
    exclude_managed_root: Path | None = None,
) -> list[Path]:
    root = home / managed_root_name
    if not root.is_dir():
        return []
    excluded = _resolved_path_key(exclude_managed_root) if exclude_managed_root is not None else None
    roots: list[Path] = []
    seen: set[str] = set()
    seen_ids: set[str] = set()
    for managed_home in _recent_managed_homes(root):
        if excluded is not None and _resolved_path_key(managed_home) == excluded:
            continue
        skills_root = managed_home / skills_directory
        if not skills_root.is_dir() or skills_root.is_symlink():
            continue
        for skill_root in sorted(path for path in skills_root.iterdir() if path.is_dir()):
            if skill_root.name.startswith(".") or not _is_packaged_managed_skill(skill_root):
                continue
            if skill_root.name in seen_ids:
                continue
            key = _resolved_path_key(skill_root)
            if key in seen:
                continue
            seen.add(key)
            seen_ids.add(skill_root.name)
            roots.append(skill_root)
    return roots


def _resolved_path_key(path: Path) -> str:
    return str(path.expanduser().resolve(strict=False))


def _recent_managed_homes(root: Path) -> list[Path]:
    homes = [
        path
        for path in root.iterdir()
        if path.is_dir() and path.name != ".managed-home"
    ]
    return sorted(homes, key=_path_mtime, reverse=True)[:MAX_MANAGED_SKILL_HOME_SCAN]


def _path_mtime(path: Path) -> float:
    try:
        return path.stat().st_mtime
    except OSError:
        return 0.0


def _is_packaged_managed_skill(skill_root: Path) -> bool:
    if not (skill_root / "SKILL.md").is_file():
        return False
    agents = skill_root / "agents"
    return agents.is_dir() and any(path.is_file() for path in agents.iterdir())
