from importlib import import_module as _import_module

for _module_name in (
    "config_service",
    "config_items",
    "config_plugins",
    "config_mcp",
    "config_system",
    "config_managed_skills",
    "config_model_settings",
    "config_model_materialization",
    "config_model_metadata",
    "config_system_defaults",
    "config_builtin_mcp",
):
    _module = _import_module(f"{__package__}.{_module_name}")
    globals().update(
        {name: value for name, value in _module.__dict__.items() if not name.startswith("__")}
    )

from pathlib import PurePosixPath

MAX_SYSTEM_SKILL_DETAIL_FILE_BYTES = 1024 * 1024


@dataclass(frozen=True)
class SystemSkillEntry:
    path: str
    kind: Literal["directory", "file"]
    size: int | None = None


@dataclass(frozen=True)
class SystemSkillFile:
    path: str
    content: str | None
    size: int
    editable: bool


@dataclass(frozen=True)
class SystemSkillDetail:
    id: str
    name: str
    enabled: bool
    path: str | None
    origin: Literal["system_builtin", "system_config"]
    editable: bool
    overridden: bool
    entries: list[SystemSkillEntry]
    files: list[SystemSkillFile]


@dataclass(frozen=True)
class SystemMcpTool:
    name: str
    description: str | None
    input_schema: dict[str, Any]


@dataclass(frozen=True)
class SystemMcpDetail:
    id: str
    name: str
    enabled: bool
    path: str | None
    origin: Literal["system_builtin", "system_config"]
    editable: bool
    overridden: bool
    server: dict[str, Any]
    tools: list[SystemMcpTool]


def system_skill_detail(skill_id: str, *, home: Path | None = None) -> SystemSkillDetail:
    _validate_path_item_id(skill_id)
    user_home = home or Path.home()
    item = _system_item_for_id("skills", skill_id, home=user_home)
    if item is None:
        raise ValueError(f"system skill not found: {skill_id}")
    if item.origin == "system_config":
        skill_root = _system_config_skill_root(_system_config_root(user_home), skill_id)
        if skill_root is None:
            raise ValueError(f"system skill not found: {skill_id}")
        return _skill_directory_detail(item, skill_root, editable=True)
    profile_detail = _builtin_profile_skill_detail(item)
    if profile_detail is not None:
        return profile_detail
    system_detail = _builtin_system_skill_detail(item)
    if system_detail is not None:
        return system_detail
    if item.path is not None:
        return _skill_directory_detail(item, Path(item.path), editable=False)
    raise ValueError(f"system skill content not available: {skill_id}")


def update_system_skill_file(
    skill_id: str,
    relative_path: str,
    content: str,
    *,
    home: Path | None = None,
) -> SystemSkillDetail:
    _validate_path_item_id(skill_id)
    user_home = home or Path.home()
    root = _system_config_root(user_home)
    skill_root = _system_config_skill_root(root, skill_id)
    if skill_root is None and _system_builtin_item_for_id("skills", skill_id, home=user_home) is not None:
        _materialize_system_builtin_skill_override(skill_id, root, user_home)
        skill_root = _system_config_skill_root(root, skill_id)
    if skill_root is None:
        raise ValueError(f"system skill not found: {skill_id}")
    target = _system_skill_file_path(skill_root, relative_path)
    if not target.is_file():
        raise ValueError(f"system skill file not found: {relative_path}")
    _write_text_file_atomic(target, content)
    return system_skill_detail(skill_id, home=user_home)


def system_mcp_detail(server_id: str, *, home: Path | None = None) -> SystemMcpDetail:
    _validate_system_mcp_id(server_id)
    user_home = home or Path.home()
    item = _system_item_for_id("mcp", server_id, home=user_home)
    if item is None:
        raise ValueError(f"system mcp server not found: {server_id}")
    if item.origin == "system_builtin":
        server = _builtin_system_mcp_server_block(server_id)
        return SystemMcpDetail(
            item.id,
            item.name,
            item.enabled,
            item.path,
            "system_builtin",
            True,
            False,
            server,
            _builtin_system_mcp_tools(server_id),
        )
    server = _system_config_mcp_server(_system_config_root(user_home), server_id)
    if server is None:
        raise ValueError(f"system mcp server not found: {server_id}")
    return SystemMcpDetail(
        item.id,
        item.name,
        item.enabled,
        item.path,
        "system_config",
        True,
        item.overridden,
        server,
        _mcp_tools_from_server(server),
    )


def _system_item_for_id(
    section_id: str,
    item_id: str,
    *,
    home: Path,
) -> AgentConfigItem | None:
    config = list_system_agent_config(home=home)
    for section in config.sections:
        if section.id != section_id:
            continue
        return next((item for item in section.items if item.id == item_id), None)
    return None


def _system_config_skill_root(root: Path, skill_id: str) -> Path | None:
    for base in (root / SYSTEM_SKILLS_DIR, root / SYSTEM_DISABLED_SKILLS_DIR):
        candidate = base / skill_id
        if candidate.is_dir():
            return candidate
    return None


def _skill_directory_detail(
    item: AgentConfigItem,
    skill_root: Path,
    *,
    editable: bool,
) -> SystemSkillDetail:
    entries = _skill_directory_entries(skill_root)
    files = _skill_text_files(skill_root, editable=editable)
    return SystemSkillDetail(
        item.id,
        item.name,
        item.enabled,
        str(skill_root),
        item.origin,
        editable,
        item.overridden,
        entries,
        files,
    )


def _skill_directory_entries(skill_root: Path) -> list[SystemSkillEntry]:
    entries: list[SystemSkillEntry] = []
    for current_root, directory_names, file_names in os.walk(skill_root, followlinks=False):
        current = Path(current_root)
        directory_names[:] = sorted(
            name for name in directory_names if not (current / name).is_symlink()
        )
        for directory_name in directory_names:
            path = current / directory_name
            entries.append(SystemSkillEntry(_relative_skill_path(skill_root, path), "directory"))
        for file_name in sorted(file_names):
            path = current / file_name
            size = _path_size(path)
            entries.append(SystemSkillEntry(_relative_skill_path(skill_root, path), "file", size))
    return sorted(entries, key=lambda entry: (entry.path.lower(), entry.kind))


def _skill_text_files(skill_root: Path, *, editable: bool) -> list[SystemSkillFile]:
    files: list[SystemSkillFile] = []
    for path in sorted(candidate for candidate in skill_root.rglob("*") if candidate.is_file()):
        relative_path = _relative_skill_path(skill_root, path)
        size = _path_size(path) or 0
        content = _read_system_skill_text_file(path, size)
        files.append(
            SystemSkillFile(relative_path, content, size, editable and content is not None)
        )
    return files


def _relative_skill_path(skill_root: Path, path: Path) -> str:
    return path.relative_to(skill_root).as_posix()


def _path_size(path: Path) -> int | None:
    try:
        return path.lstat().st_size
    except OSError:
        return None


def _read_system_skill_text_file(path: Path, size: int) -> str | None:
    if size > MAX_SYSTEM_SKILL_DETAIL_FILE_BYTES or path.is_symlink():
        return None
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None


def _system_skill_file_path(skill_root: Path, relative_path: str) -> Path:
    path = PurePosixPath(relative_path)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        raise ValueError(f"invalid system skill file path: {relative_path}")
    target = skill_root.joinpath(*path.parts)
    try:
        target.resolve(strict=True).relative_to(skill_root.resolve(strict=True))
    except (FileNotFoundError, OSError, ValueError) as exc:
        raise ValueError(f"invalid system skill file path: {relative_path}") from exc
    return target


def _builtin_profile_skill_detail(item: AgentConfigItem) -> SystemSkillDetail | None:
    from app.contexts.agent_profiles.infrastructure import builtin_profile_specs

    content_by_id = {
        skill_id: skill_md
        for _name, _description, _agent_md, profile_skills in builtin_profile_specs.BUILTIN_PROFILE_SPECS.values()
        for skill_id, skill_md in profile_skills
    }
    content = content_by_id.get(item.id)
    if content is None:
        return None
    size = len(content.encode("utf-8"))
    return SystemSkillDetail(
        item.id,
        item.name,
        item.enabled,
        None,
        "system_builtin",
        True,
        False,
        [SystemSkillEntry("SKILL.md", "file", size)],
        [SystemSkillFile("SKILL.md", content, size, True)],
    )


def _builtin_system_skill_detail(item: AgentConfigItem) -> SystemSkillDetail | None:
    from app.contexts.agent_profiles.infrastructure import builtin_system_skills

    skill = builtin_system_skills.builtin_system_skill(item.id)
    if skill is None:
        return None
    entries: dict[str, SystemSkillEntry] = {}
    files: list[SystemSkillFile] = []
    for file in builtin_system_skills.builtin_system_skill_files(skill):
        path = PurePosixPath(file.path)
        parent = PurePosixPath()
        for part in path.parts[:-1]:
            parent /= part
            entries[parent.as_posix()] = SystemSkillEntry(parent.as_posix(), "directory")
        size = len(file.content.encode("utf-8"))
        entries[file.path] = SystemSkillEntry(file.path, "file", size)
        files.append(SystemSkillFile(file.path, file.content, size, False))
    return SystemSkillDetail(
        item.id,
        item.name,
        item.enabled,
        None,
        "system_builtin",
        True,
        False,
        sorted(entries.values(), key=lambda entry: (entry.path.lower(), entry.kind)),
        sorted(
            (SystemSkillFile(file.path, file.content, file.size, True) for file in files),
            key=lambda file: file.path.lower(),
        ),
    )


def _materialize_system_builtin_skill_override(
    skill_id: str,
    root: Path,
    user_home: Path,
) -> None:
    item = _system_builtin_item_for_id("skills", skill_id, home=user_home)
    if item is None:
        raise ValueError(f"system skill not found: {skill_id}")
    target = root / SYSTEM_SKILLS_DIR / skill_id
    disabled = root / SYSTEM_DISABLED_SKILLS_DIR / skill_id
    enabled = item.enabled
    destination_root = target if enabled else disabled
    with _locked_config_writes(target, disabled):
        if target.exists() or target.is_symlink():
            _remove_path(target)
        if disabled.exists() or disabled.is_symlink():
            _remove_path(disabled)
        profile_detail = _builtin_profile_skill_detail(item)
        if profile_detail is not None:
            for file in profile_detail.files:
                if file.content is not None:
                    _write_text_file_atomic(destination_root / file.path, file.content)
            return
        if _materialize_builtin_system_skill_override_files(item.id, destination_root):
            return
        if item.path is not None:
            shutil.copytree(Path(item.path), destination_root, symlinks=False)
            return
    raise ValueError(f"system skill content not available: {skill_id}")


def _materialize_builtin_system_skill_override_files(skill_id: str, target: Path) -> bool:
    from app.contexts.agent_profiles.infrastructure import builtin_system_skills

    skill = builtin_system_skills.builtin_system_skill(skill_id)
    if skill is None:
        return False
    for file in builtin_system_skills.builtin_system_skill_files(skill):
        destination = target / file.path
        _write_text_file_atomic(destination, file.content)
        if file.executable:
            destination.chmod(destination.stat().st_mode | 0o111)
    return True


def _system_config_mcp_server(root: Path, server_id: str) -> dict[str, Any] | None:
    for path in (root / SYSTEM_MCP_FILE, root / SYSTEM_MCP_DISABLED_FILE):
        server = _mcp_servers(_read_json_file(path)).get(server_id)
        if isinstance(server, dict):
            return server
    return None


def _builtin_system_mcp_server_block(server_id: str) -> dict[str, Any]:
    if server_id == WEB_TERMINAL_MCP_SERVER_ID:
        return _builtin_mcp_server_block(
            source_client_id="${WEB_TERMINAL_CLIENT_ID}",
            source_window_id="${WEB_TERMINAL_WINDOW_ID}",
            server_url="${WEB_TERMINAL_SERVER_URL}",
            mcp_token="${WEB_TERMINAL_MCP_TOKEN}",
        )
    return {}


def _builtin_system_mcp_tools(server_id: str) -> list[SystemMcpTool]:
    if server_id == WEB_TERMINAL_MCP_SERVER_ID:
        from app.client_agent import web_terminal_acp_mcp

        return _mcp_tools_from_raw(web_terminal_acp_mcp._tools())
    return []


def _mcp_tools_from_server(server: dict[str, Any]) -> list[SystemMcpTool]:
    for key in ("tools", "toolDefinitions", "tool_definitions"):
        tools = server.get(key)
        if isinstance(tools, list):
            return _mcp_tools_from_raw(tools)
    return []


def _mcp_tools_from_raw(tools: list[Any]) -> list[SystemMcpTool]:
    items: list[SystemMcpTool] = []
    for tool in tools:
        if not isinstance(tool, dict):
            continue
        name = _string(tool.get("name"))
        if name is None:
            continue
        input_schema = tool.get("inputSchema") or tool.get("input_schema") or tool.get("schema")
        items.append(
            SystemMcpTool(
                name,
                _string(tool.get("description")),
                input_schema if isinstance(input_schema, dict) else {},
            )
        )
    return sorted(items, key=lambda tool: tool.name.lower())
