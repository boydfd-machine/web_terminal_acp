from importlib import import_module as _import_module

for _module_name in (
    "config_service",
    "config_items",
    "config_plugins",
    "config_mcp",
    "config_managed_skills",
):
    _module = _import_module(f"{__package__}.{_module_name}")
    globals().update(
        {name: value for name, value in _module.__dict__.items() if not name.startswith("__")}
    )

import io
import stat
import zipfile
from pathlib import PurePosixPath

SYSTEM_CONFIG_ROOT = ".web-terminal-acp/system-config"
SYSTEM_SKILLS_DIR = "skills"
SYSTEM_DISABLED_SKILLS_DIR = "skills.disabled"
SYSTEM_MCP_FILE = "mcp.json"
SYSTEM_MCP_DISABLED_FILE = "mcp.disabled.json"
SYSTEM_DEFAULTS_FILE = "defaults.json"
MAX_SYSTEM_SKILL_UPLOAD_BYTES = 20 * 1024 * 1024
MAX_SYSTEM_SKILL_UNCOMPRESSED_BYTES = 50 * 1024 * 1024


def list_system_agent_config(*, home: Path | None = None) -> AgentConfig:
    from .config_system_plugins import _list_system_plugin_items

    root = _system_config_root(home or Path.home())
    user_home = home or Path.home()
    return AgentConfig(
        agent="system",
        sections=[
            AgentConfigSection(
                "skills",
                "System Skills",
                _system_items(
                    _list_system_builtin_skill_items(user_home, root),
                    _list_directory_items(root, SYSTEM_SKILLS_DIR, origin="system_config"),
                ),
            ),
            AgentConfigSection(
                "plugins",
                "System Plugins",
                _list_system_plugin_items(user_home, root),
            ),
            AgentConfigSection(
                "mcp",
                "System MCP Servers",
                _system_items(
                    _list_system_builtin_mcp_items(root),
                    _system_config_mcp_items(root),
                ),
            ),
        ],
    )


def set_system_agent_config_item_enabled(
    section_id: str,
    item_id: str,
    enabled: bool,
    *,
    home: Path | None = None,
) -> AgentConfig:
    user_home = home or Path.home()
    root = _system_config_root(user_home)
    from .config_system_plugins import _system_plugin_item_for_id

    if section_id == "skills" and _system_config_skill_root(root, item_id) is not None:
        _set_directory_item_enabled(root, SYSTEM_SKILLS_DIR, item_id, enabled)
    elif section_id == "plugins" and _system_plugin_item_for_id(
        item_id,
        home=user_home,
        root=root,
    ) is not None:
        _set_system_default_item_enabled(root, section_id, item_id, enabled)
    elif section_id == "mcp" and _system_config_mcp_server(root, item_id) is not None:
        _set_json_mcp_enabled(root, item_id, enabled)
    elif _system_builtin_item_for_id(section_id, item_id, home=user_home) is not None:
        _set_system_default_item_enabled(root, section_id, item_id, enabled)
    elif section_id == "skills":
        _set_directory_item_enabled(root, SYSTEM_SKILLS_DIR, item_id, enabled)
    elif section_id == "mcp":
        _set_json_mcp_enabled(root, item_id, enabled)
    else:
        raise ValueError(f"unsupported system config section: {section_id}")
    return list_system_agent_config(home=home)


def upsert_system_mcp_server(
    server_id: str,
    server: dict[str, Any],
    *,
    enabled: bool = True,
    home: Path | None = None,
) -> AgentConfig:
    _validate_system_mcp_id(server_id)
    user_home = home or Path.home()
    if not server:
        raise ValueError("mcp server config is required")
    root = _system_config_root(user_home)
    active_path = root / SYSTEM_MCP_FILE
    disabled_path = root / SYSTEM_MCP_DISABLED_FILE
    with _locked_config_writes(active_path, disabled_path):
        active = _read_json_file(active_path)
        disabled = _read_json_file(disabled_path)
        _ensure_mcp_servers(active).pop(server_id, None)
        _ensure_mcp_servers(disabled).pop(server_id, None)
        target = active if enabled else disabled
        _ensure_mcp_servers(target)[server_id] = server
        _write_json_file(active_path, active)
        _write_json_file(disabled_path, disabled)
    return list_system_agent_config(home=home)


def delete_system_agent_config_item(
    section_id: str,
    item_id: str,
    *,
    home: Path | None = None,
) -> AgentConfig:
    user_home = home or Path.home()
    root = _system_config_root(user_home)
    from .config_system_plugins import _system_plugin_item_for_id

    if section_id == "plugins" and _system_plugin_item_for_id(
        item_id,
        home=user_home,
        root=root,
    ) is not None:
        raise ValueError(f"system plugin config item cannot be deleted; reset instead: {item_id}")
    if _system_builtin_item_for_id(section_id, item_id, home=user_home) is not None:
        raise ValueError(f"system built-in config item cannot be deleted; reset instead: {item_id}")
    if section_id == "skills":
        _delete_system_skill(root, item_id)
    elif section_id == "mcp":
        _delete_system_mcp(root, item_id)
    else:
        raise ValueError(f"unsupported system config section: {section_id}")
    return list_system_agent_config(home=home)


def install_system_skill_from_zip(
    skill_id: str,
    archive: bytes,
    *,
    enabled: bool = True,
    home: Path | None = None,
) -> AgentConfig:
    _validate_path_item_id(skill_id)
    user_home = home or Path.home()
    if len(archive) > MAX_SYSTEM_SKILL_UPLOAD_BYTES:
        raise ValueError("skill archive is too large")
    root = _system_config_root(user_home)
    root.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=f".{skill_id}.", dir=root) as temp_name:
        temp_root = Path(temp_name)
        payload_root = _extract_skill_zip(archive, temp_root)
        if not (payload_root / "SKILL.md").is_file():
            raise ValueError("skill archive must contain SKILL.md")
        target_base = root / (SYSTEM_SKILLS_DIR if enabled else SYSTEM_DISABLED_SKILLS_DIR)
        active = root / SYSTEM_SKILLS_DIR / skill_id
        disabled = root / SYSTEM_DISABLED_SKILLS_DIR / skill_id
        with _locked_config_writes(active, disabled, target_base):
            _remove_path(active)
            _remove_path(disabled)
            target_base.mkdir(parents=True, exist_ok=True)
            shutil.copytree(payload_root, target_base / skill_id, symlinks=False)
    return list_system_agent_config(home=home)


def reset_system_agent_config_item(
    section_id: str,
    item_id: str,
    *,
    home: Path | None = None,
) -> AgentConfig:
    user_home = home or Path.home()
    root = _system_config_root(user_home)
    if _system_builtin_item_for_id(section_id, item_id, home=user_home) is None:
        raise ValueError(f"system built-in config item not found: {item_id}")
    if section_id == "skills":
        _delete_system_skill(root, item_id, missing_ok=True)
    elif section_id == "mcp":
        _delete_system_mcp(root, item_id, missing_ok=True)
    else:
        raise ValueError(f"unsupported system config section: {section_id}")
    _remove_system_default_item_enabled(root, section_id, item_id)
    return list_system_agent_config(home=home)


def install_system_config_for_agent_window(
    agent: str,
    *,
    window_id: str,
    home: Path | None = None,
) -> None:
    agent_kind = _agent_kind(agent)
    user_home = home or Path.home()
    managed_root = _ensure_window_agent_config_root(agent_kind, window_id, user_home)
    install_system_config_for_materialized_agent_root(
        agent_kind,
        managed_root,
        home=user_home,
    )


def install_system_config_for_window(
    *,
    window_id: str,
    home: Path | None = None,
) -> None:
    for plugin in get_agent_plugin_registry().all():
        install_system_config_for_agent_window(
            plugin.agent_client_id,
            window_id=window_id,
            home=home,
        )


def install_system_config_for_materialized_agent_root(
    agent: str,
    managed_root: Path,
    *,
    home: Path | None = None,
) -> None:
    agent_kind = _agent_kind(agent)
    user_home = home or Path.home()
    root = _system_config_root(user_home)
    source_root = _agent_root(agent_kind, user_home)
    _install_system_skills(agent_kind, root, managed_root, source_root, user_home=user_home)
    _install_system_plugins(agent_kind, root, managed_root)
    _install_system_mcp(agent_kind, root, managed_root)


def _system_config_root(home: Path) -> Path:
    return home / SYSTEM_CONFIG_ROOT


def _system_config_mcp_items(root: Path) -> list[AgentConfigItem]:
    return _list_json_mcp(root, origin="system_config")


def _system_config_skill_ids(root: Path) -> set[str]:
    ids: set[str] = set()
    for base in (root / SYSTEM_SKILLS_DIR, root / SYSTEM_DISABLED_SKILLS_DIR):
        if not base.is_dir():
            continue
        ids.update(path.name for path in base.iterdir() if path.is_dir())
    return ids


def _system_items(
    builtin_items: list[AgentConfigItem],
    managed_items: list[AgentConfigItem],
) -> list[AgentConfigItem]:
    builtin_by_id = {item.id: item for item in builtin_items}
    items: dict[str, AgentConfigItem] = dict(builtin_by_id)
    for item in managed_items:
        if item.id not in builtin_by_id:
            items[item.id] = item
            continue
        items[item.id] = AgentConfigItem(
            item.id,
            item.name,
            item.enabled,
            item.path,
            item.origin,
            True,
        )
    return sorted(
        items.values(),
        key=lambda item: (
            item.origin != "system_builtin",
            item.name.lower(),
            item.id.lower(),
        ),
    )


def _list_system_builtin_skill_items(home: Path, root: Path) -> list[AgentConfigItem]:
    items = {
        item.id: item
        for item in (
            *_builtin_system_skill_items(),
            *_agent_client_builtin_skill_items(home),
            *_managed_agent_skill_items(home),
        )
    }
    return sorted(
        _system_items_with_defaults("skills", items.values(), root),
        key=lambda item: (item.name.lower(), item.id.lower()),
    )


def _builtin_system_skill_items() -> list[AgentConfigItem]:
    from app.contexts.agent_profiles.infrastructure import builtin_system_skills

    return builtin_system_skills.builtin_system_skill_config_items(
        AgentConfigItem, _name_from_skill_text
    )


def _agent_client_builtin_skill_items(home: Path) -> list[AgentConfigItem]:
    items: dict[str, AgentConfigItem] = {}
    for plugin in get_agent_plugin_registry().all():
        root = home / plugin.storage.user_root
        for system_root in _system_skill_roots(root, plugin.storage.skills_directory):
            for path in sorted(child for child in system_root.iterdir() if child.is_dir()):
                marker = path / "SKILL.md"
                if not marker.is_file():
                    continue
                items[path.name] = AgentConfigItem(
                    path.name,
                    _name_from_skill(marker) or path.name,
                    True,
                    str(path),
                    "system_builtin",
                )
    return list(items.values())


def _system_skill_roots(root: Path, skills_directory: str) -> list[Path]:
    candidates = [
        root / skills_directory / ".system",
        root / skills_directory / skills_directory / ".system",
    ]
    roots: list[Path] = []
    seen: set[str] = set()
    for candidate in candidates:
        key = str(candidate.expanduser().resolve(strict=False))
        if key in seen or not candidate.is_dir():
            continue
        seen.add(key)
        roots.append(candidate)
    return roots


def _name_from_skill_text(content: str) -> str | None:
    for line in content.splitlines()[:20]:
        match = re.match(r"\s*name:\s*[\"']?([^\"']+)[\"']?\s*$", line)
        if match:
            return match.group(1).strip()
    return None


def _list_system_builtin_mcp_items(root: Path) -> list[AgentConfigItem]:
    return []


def _system_builtin_item_for_id(
    section_id: str,
    item_id: str,
    *,
    home: Path,
) -> AgentConfigItem | None:
    return next(
        (item for item in _system_builtin_items_for_section(section_id, home) if item.id == item_id),
        None,
    )


def _system_builtin_items_for_section(section_id: str, home: Path) -> list[AgentConfigItem]:
    root = _system_config_root(home)
    if section_id == "skills":
        return _list_system_builtin_skill_items(home, root)
    if section_id == "plugins":
        from .config_system_plugins import _list_system_plugin_items

        return _list_system_plugin_items(home, root)
    if section_id == "mcp":
        return _list_system_builtin_mcp_items(root)
    return []


def _validate_system_mcp_id(server_id: str) -> None:
    _validate_json_key_item_id(server_id)
    _validate_codex_plugin_id(server_id)


def _delete_system_skill(root: Path, skill_id: str, *, missing_ok: bool = False) -> None:
    _validate_path_item_id(skill_id)
    paths = (root / SYSTEM_SKILLS_DIR / skill_id, root / SYSTEM_DISABLED_SKILLS_DIR / skill_id)
    removed = False
    with _locked_config_writes(*paths):
        for path in paths:
            if path.exists() or path.is_symlink():
                _remove_path(path)
                removed = True
    if not removed and not missing_ok:
        raise ValueError(f"system skill not found: {skill_id}")


def _delete_system_mcp(root: Path, server_id: str, *, missing_ok: bool = False) -> None:
    _validate_system_mcp_id(server_id)
    active_path = root / SYSTEM_MCP_FILE
    disabled_path = root / SYSTEM_MCP_DISABLED_FILE
    with _locked_config_writes(active_path, disabled_path):
        active = _read_json_file(active_path)
        disabled = _read_json_file(disabled_path)
        removed = _remove_mcp_server(active, server_id) is not None
        removed = _remove_mcp_server(disabled, server_id) is not None or removed
        if not removed and not missing_ok:
            raise ValueError(f"system mcp server not found: {server_id}")
        _write_json_file(active_path, active)
        _write_json_file(disabled_path, disabled)


def _extract_skill_zip(archive: bytes, temp_root: Path) -> Path:
    try:
        with zipfile.ZipFile(io.BytesIO(archive)) as zip_file:
            infos = [info for info in zip_file.infolist() if not info.is_dir()]
            total_size = sum(max(info.file_size, 0) for info in infos)
            if total_size > MAX_SYSTEM_SKILL_UNCOMPRESSED_BYTES:
                raise ValueError("skill archive contents are too large")
            roots: set[str] = set()
            for info in infos:
                relative_path = _safe_zip_member_path(info)
                if relative_path is None:
                    continue
                parts = relative_path.parts
                if parts:
                    roots.add(parts[0])
                target = temp_root / relative_path
                target.parent.mkdir(parents=True, exist_ok=True)
                with zip_file.open(info) as source, target.open("wb") as target_file:
                    shutil.copyfileobj(source, target_file)
    except zipfile.BadZipFile as exc:
        raise ValueError("skill upload must be a zip archive") from exc

    if (temp_root / "SKILL.md").is_file():
        return temp_root
    candidates = [
        temp_root / root_name
        for root_name in sorted(roots)
        if (temp_root / root_name / "SKILL.md").is_file()
    ]
    if len(candidates) == 1:
        return candidates[0]
    return temp_root


def _safe_zip_member_path(info: zipfile.ZipInfo) -> PurePosixPath | None:
    mode = info.external_attr >> 16
    if stat.S_ISLNK(mode):
        return None
    path = PurePosixPath(info.filename)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        raise ValueError(f"invalid archive path: {info.filename}")
    return path


def _remove_path(path: Path) -> None:
    if path.is_dir() and not path.is_symlink():
        shutil.rmtree(path)
    else:
        path.unlink(missing_ok=True)
