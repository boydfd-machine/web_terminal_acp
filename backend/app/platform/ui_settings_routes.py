from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.platform.ui_settings_repository import (
    get_app_preferences,
    get_custom_quick_keys,
    put_app_preferences,
    put_custom_quick_keys,
)
from app.platform.ui_events import ui_event_hub_from_state
from app.platform.ui_settings_schemas import (
    AppPreferencesOut,
    AppPreferencesPutIn,
    CustomQuickKeysOut,
    CustomQuickKeysPutIn,
)

router = APIRouter(prefix="/api/ui-settings", tags=["ui-settings"])


@router.get(
    "/app-preferences",
    response_model=AppPreferencesOut,
    response_model_exclude_none=True,
)
async def read_app_preferences(
    session: AsyncSession = Depends(get_session),
) -> AppPreferencesOut:
    return await get_app_preferences(session)


@router.put(
    "/app-preferences",
    response_model=AppPreferencesOut,
    response_model_exclude_none=True,
)
async def update_app_preferences(
    payload: AppPreferencesPutIn,
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> AppPreferencesOut:
    preferences = await put_app_preferences(session, payload)
    await session.commit()
    await ui_event_hub_from_state(request.app.state).publish_invalidation(
        ["ui_settings"],
        reason="app_preferences_updated",
    )
    return preferences


@router.get(
    "/custom-quick-keys",
    response_model=CustomQuickKeysOut,
    response_model_exclude_none=True,
)
async def read_custom_quick_keys(
    session: AsyncSession = Depends(get_session),
) -> CustomQuickKeysOut:
    return CustomQuickKeysOut(quick_keys=await get_custom_quick_keys(session))


@router.put(
    "/custom-quick-keys",
    response_model=CustomQuickKeysOut,
    response_model_exclude_none=True,
)
async def update_custom_quick_keys(
    payload: CustomQuickKeysPutIn,
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> CustomQuickKeysOut:
    quick_keys = await put_custom_quick_keys(session, payload.quick_keys)
    await session.commit()
    await ui_event_hub_from_state(request.app.state).publish_invalidation(
        ["ui_settings"],
        reason="custom_quick_keys_updated",
    )
    return CustomQuickKeysOut(quick_keys=quick_keys)
