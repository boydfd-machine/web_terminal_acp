from __future__ import annotations

from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from app.platform.ui_setting_files import file_tree_payload, restore_file_tree_payload
from app.platform.ui_settings_repository import (
    get_ui_setting,
    is_legacy_ui_settings_scope,
    put_ui_setting,
    user_scoped_settings_home,
)

AGENT_PROFILE_FILES_SETTING_KEY = "agent_profile_files"


def agent_profile_settings_home(
    owner_user_id: str | None = None,
    *,
    home: Path | None = None,
) -> Path:
    if home is not None:
        return home
    return user_scoped_settings_home(owner_user_id)


def agent_profiles_root(home: Path) -> Path:
    return home / ".web-terminal-acp" / "agents"


async def restore_agent_profile_files_to_disk(
    session: AsyncSession,
    *,
    owner_user_id: str | None = None,
    home: Path | None = None,
) -> Path:
    settings_home = agent_profile_settings_home(owner_user_id, home=home)
    setting = await get_ui_setting(session, AGENT_PROFILE_FILES_SETTING_KEY, owner_user_id)
    if setting is None:
        payload = (
            file_tree_payload(agent_profiles_root(settings_home))
            if is_legacy_ui_settings_scope() and owner_user_id is None
            else {"version": 1, "files": []}
        )
        if payload["files"]:
            await put_ui_setting(session, AGENT_PROFILE_FILES_SETTING_KEY, payload, owner_user_id)
        return settings_home
    restore_file_tree_payload(agent_profiles_root(settings_home), setting.value_json)
    return settings_home


async def persist_agent_profile_files(
    session: AsyncSession,
    *,
    owner_user_id: str | None = None,
    home: Path | None = None,
) -> None:
    settings_home = agent_profile_settings_home(owner_user_id, home=home)
    await put_ui_setting(
        session,
        AGENT_PROFILE_FILES_SETTING_KEY,
        file_tree_payload(agent_profiles_root(settings_home)),
        owner_user_id,
    )
