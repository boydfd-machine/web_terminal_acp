from __future__ import annotations

import hashlib
from pathlib import Path

from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import UiSetting
from app.platform.auth_context import current_auth_identity
from app.platform.ui_settings_schemas import (
    AppPreferencesOut,
    AppPreferencesPutIn,
    CustomQuickKeyOut,
)

APP_PREFERENCES_SETTING_KEY = "app_preferences"
CUSTOM_QUICK_KEYS_SETTING_KEY = "custom_quick_keys"


def current_user_setting_owner_id() -> str | None:
    identity = current_auth_identity()
    if identity is None or identity.user_id == "local":
        return None
    return identity.user_id


def is_legacy_ui_settings_scope() -> bool:
    return current_user_setting_owner_id() is None


def scoped_ui_setting_key(key: str, owner_user_id: str | None = None) -> str:
    owner = current_user_setting_owner_id() if owner_user_id is None else owner_user_id
    if owner is None or owner == "local":
        return key
    return f"u:{user_setting_scope_id(owner)}:{key}"


def user_setting_scope_id(owner_user_id: str) -> str:
    return hashlib.sha256(owner_user_id.encode("utf-8")).hexdigest()[:24]


def user_scoped_settings_home(
    owner_user_id: str | None = None,
    *,
    home: Path | None = None,
) -> Path:
    owner = current_user_setting_owner_id() if owner_user_id is None else owner_user_id
    root = home or Path.home()
    if owner is None or owner == "local":
        return root
    return root / ".web-terminal-acp" / "user-settings" / user_setting_scope_id(owner)


async def get_ui_setting(
    session: AsyncSession,
    key: str,
    owner_user_id: str | None = None,
) -> UiSetting | None:
    return await session.get(UiSetting, scoped_ui_setting_key(key, owner_user_id))


async def put_ui_setting(
    session: AsyncSession,
    key: str,
    value_json: dict,
    owner_user_id: str | None = None,
) -> UiSetting:
    setting = await get_ui_setting(session, key, owner_user_id)
    if setting is None:
        setting = UiSetting(key=scoped_ui_setting_key(key, owner_user_id), value_json=value_json)
        session.add(setting)
    else:
        setting.value_json = value_json
    await session.flush()
    return setting


async def get_app_preferences(session: AsyncSession) -> AppPreferencesOut:
    setting = await get_ui_setting(session, APP_PREFERENCES_SETTING_KEY)
    if setting is None:
        return AppPreferencesOut(configured=False)
    try:
        preferences = AppPreferencesPutIn.model_validate(setting.value_json)
    except ValidationError:
        return AppPreferencesOut(configured=False)
    return AppPreferencesOut(configured=True, **preferences.model_dump(mode="json"))


async def put_app_preferences(
    session: AsyncSession,
    preferences: AppPreferencesPutIn,
) -> AppPreferencesOut:
    await put_ui_setting(
        session,
        APP_PREFERENCES_SETTING_KEY,
        preferences.model_dump(mode="json"),
    )
    return AppPreferencesOut(configured=True, **preferences.model_dump(mode="json"))


async def get_custom_quick_keys(session: AsyncSession) -> list[CustomQuickKeyOut]:
    setting = await get_ui_setting(session, CUSTOM_QUICK_KEYS_SETTING_KEY)
    if setting is None:
        return []

    raw_quick_keys = setting.value_json.get("quick_keys")
    if not isinstance(raw_quick_keys, list):
        return []

    quick_keys: list[CustomQuickKeyOut] = []
    for item in raw_quick_keys:
        try:
            quick_keys.append(CustomQuickKeyOut.model_validate(item))
        except ValidationError:
            continue
    return quick_keys


async def put_custom_quick_keys(
    session: AsyncSession,
    quick_keys: list[CustomQuickKeyOut],
) -> list[CustomQuickKeyOut]:
    value_json = {
        "quick_keys": [
            quick_key.model_dump(mode="json", exclude_none=True)
            for quick_key in quick_keys
        ],
    }
    await put_ui_setting(session, CUSTOM_QUICK_KEYS_SETTING_KEY, value_json)
    return quick_keys
