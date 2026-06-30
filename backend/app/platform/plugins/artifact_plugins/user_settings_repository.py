from __future__ import annotations

from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from app.platform.plugins.artifact_plugins.management import managed_artifact_plugins_root
from app.platform.ui_setting_files import file_tree_payload, restore_file_tree_payload
from app.platform.ui_settings_repository import (
    get_ui_setting,
    is_legacy_ui_settings_scope,
    put_ui_setting,
    user_scoped_settings_home,
)

ARTIFACT_PLUGIN_FILES_SETTING_KEY = "artifact_plugin_files"


def artifact_plugin_settings_home(
    owner_user_id: str | None = None,
    *,
    home: Path | None = None,
) -> Path:
    if home is not None:
        return home
    return user_scoped_settings_home(owner_user_id)


async def restore_artifact_plugin_files_to_disk(
    session: AsyncSession,
    *,
    owner_user_id: str | None = None,
    home: Path | None = None,
) -> Path:
    settings_home = artifact_plugin_settings_home(owner_user_id, home=home)
    setting = await get_ui_setting(
        session,
        ARTIFACT_PLUGIN_FILES_SETTING_KEY,
        owner_user_id,
    )
    if setting is None:
        payload = (
            file_tree_payload(managed_artifact_plugins_root(settings_home))
            if is_legacy_ui_settings_scope() and owner_user_id is None
            else {"version": 1, "files": []}
        )
        if payload["files"]:
            await put_ui_setting(
                session,
                ARTIFACT_PLUGIN_FILES_SETTING_KEY,
                payload,
                owner_user_id,
            )
        return settings_home
    restore_file_tree_payload(managed_artifact_plugins_root(settings_home), setting.value_json)
    return settings_home


async def persist_artifact_plugin_files(
    session: AsyncSession,
    *,
    owner_user_id: str | None = None,
    home: Path | None = None,
) -> None:
    settings_home = artifact_plugin_settings_home(owner_user_id, home=home)
    await put_ui_setting(
        session,
        ARTIFACT_PLUGIN_FILES_SETTING_KEY,
        file_tree_payload(managed_artifact_plugins_root(settings_home)),
        owner_user_id,
    )
