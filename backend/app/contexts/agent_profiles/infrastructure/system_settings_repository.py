from __future__ import annotations

import base64
import shutil
from pathlib import Path, PurePosixPath
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.contexts.agent_profiles.infrastructure import agent_config_store
from app.models import UiSetting
from app.platform.ui_settings_repository import (
    get_ui_setting,
    is_legacy_ui_settings_scope,
    put_ui_setting,
)

SYSTEM_AGENT_CONFIG_FILES_SETTING_KEY = "system_agent_config_files"


async def list_system_model_presets(
    session: AsyncSession,
    *,
    home: Path | None = None,
) -> agent_config_store.SystemModelPresetList:
    setting = await _system_model_presets_setting(session, home=home)
    return agent_config_store.system_model_preset_list_from_payload(setting.value_json)


async def upsert_system_model_preset(
    session: AsyncSession,
    preset: agent_config_store.SystemModelPreset,
    *,
    home: Path | None = None,
) -> agent_config_store.SystemModelPresetList:
    setting = await _system_model_presets_setting(session, home=home)
    payload, preset_list = agent_config_store.upsert_system_model_preset_payload(
        setting.value_json,
        preset,
    )
    setting.value_json = payload
    await session.flush()
    return preset_list


async def delete_system_model_preset(
    session: AsyncSession,
    preset_id: str,
    *,
    home: Path | None = None,
) -> agent_config_store.SystemModelPresetList:
    setting = await _system_model_presets_setting(session, home=home)
    payload, preset_list = agent_config_store.delete_system_model_preset_payload(
        setting.value_json,
        preset_id,
    )
    setting.value_json = payload
    await session.flush()
    return preset_list


async def restore_system_agent_config_files_to_disk(
    session: AsyncSession,
    *,
    home: Path | None = None,
) -> None:
    user_home = home or Path.home()
    setting = await get_ui_setting(session, SYSTEM_AGENT_CONFIG_FILES_SETTING_KEY)
    if setting is None:
        payload = (
            _system_agent_config_files_payload(user_home)
            if is_legacy_ui_settings_scope()
            else {"version": 1, "files": []}
        )
        if payload["files"]:
            await put_ui_setting(session, SYSTEM_AGENT_CONFIG_FILES_SETTING_KEY, payload)
        return
    _restore_system_agent_config_files(user_home, setting.value_json)


async def persist_system_agent_config_files(
    session: AsyncSession,
    *,
    home: Path | None = None,
) -> None:
    payload = _system_agent_config_files_payload(home or Path.home())
    await put_ui_setting(session, SYSTEM_AGENT_CONFIG_FILES_SETTING_KEY, payload)


async def _system_model_presets_setting(
    session: AsyncSession,
    *,
    home: Path | None,
) -> UiSetting:
    setting = await get_ui_setting(session, agent_config_store.SYSTEM_MODEL_PRESETS_SETTING_KEY)
    if setting is not None:
        return setting

    payload = (
        agent_config_store.legacy_system_model_preset_payload(home=home)
        if is_legacy_ui_settings_scope()
        else {"presets": {}}
    )
    return await put_ui_setting(session, agent_config_store.SYSTEM_MODEL_PRESETS_SETTING_KEY, payload)


def _system_config_root(home: Path) -> Path:
    return home / agent_config_store.SYSTEM_CONFIG_ROOT


def _managed_system_config_paths(root: Path) -> tuple[Path, ...]:
    return (
        root / agent_config_store.SYSTEM_SKILLS_DIR,
        root / agent_config_store.SYSTEM_DISABLED_SKILLS_DIR,
        root / agent_config_store.SYSTEM_MCP_FILE,
        root / agent_config_store.SYSTEM_MCP_DISABLED_FILE,
        root / agent_config_store.SYSTEM_DEFAULTS_FILE,
    )


def _system_agent_config_files_payload(home: Path) -> dict[str, object]:
    root = _system_config_root(home)
    files: list[dict[str, object]] = []
    if not root.is_dir():
        return {"version": 1, "files": files}
    for path in sorted(candidate for candidate in root.rglob("*") if candidate.is_file()):
        if path.is_symlink():
            continue
        relative_path = path.relative_to(root).as_posix()
        if relative_path == agent_config_store.SYSTEM_MODEL_PRESETS_FILE:
            continue
        try:
            content = path.read_bytes()
            mode = path.stat().st_mode & 0o777
        except FileNotFoundError:
            continue
        files.append(
            {
                "path": relative_path,
                "content_b64": base64.b64encode(content).decode("ascii"),
                "mode": mode,
            }
        )
    return {"version": 1, "files": files}


def _restore_system_agent_config_files(home: Path, payload: object) -> None:
    files = _system_agent_config_file_records(payload)
    root = _system_config_root(home)
    root.mkdir(parents=True, exist_ok=True)
    for path in _managed_system_config_paths(root):
        if path.is_dir() and not path.is_symlink():
            shutil.rmtree(path)
        else:
            path.unlink(missing_ok=True)
    for relative_path, content, mode in files:
        target = root.joinpath(*PurePosixPath(relative_path).parts)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
        if mode is not None:
            target.chmod(mode)


def _system_agent_config_file_records(
    payload: object,
) -> list[tuple[str, bytes, int | None]]:
    if not isinstance(payload, dict):
        return []
    raw_files = payload.get("files")
    if not isinstance(raw_files, list):
        return []
    files: list[tuple[str, bytes, int | None]] = []
    for item in raw_files:
        record = _system_agent_config_file_record(item)
        if record is not None:
            files.append(record)
    return files


def _system_agent_config_file_record(
    item: object,
) -> tuple[str, bytes, int | None] | None:
    if not isinstance(item, dict):
        return None
    relative_path = item.get("path")
    content_b64 = item.get("content_b64")
    if not isinstance(relative_path, str) or not isinstance(content_b64, str):
        return None
    path = PurePosixPath(relative_path)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        return None
    if relative_path == agent_config_store.SYSTEM_MODEL_PRESETS_FILE:
        return None
    try:
        content = base64.b64decode(content_b64.encode("ascii"), validate=True)
    except ValueError:
        return None
    mode = _file_mode(item.get("mode"))
    return path.as_posix(), content, mode


def _file_mode(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int) and 0 <= value <= 0o777:
        return value
    return None
