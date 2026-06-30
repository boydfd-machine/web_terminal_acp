from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.contexts.agent_profiles.api.schemas import (
    SystemModelPresetListOut,
    SystemModelPresetOut,
    SystemModelPresetUpsertIn,
    SystemMcpDetailOut,
    SystemSkillDetailOut,
    SystemSkillFileUpdateIn,
)
from app.contexts.agent_profiles.application import system_config as system_config_service

router = APIRouter(prefix="/api/system-agent-config", tags=["agent-profiles"])
MODEL_PRESET_BUNDLE_KIND = "web-terminal-model-preset"
MODEL_PRESET_BUNDLE_VERSION = 1


def _model_preset_out(preset) -> SystemModelPresetOut:
    return SystemModelPresetOut(
        id=preset.id,
        name=preset.name,
        provider=preset.provider,
        providers=preset.providers or [preset.provider],
        base_url=preset.base_url,
        api_key=preset.api_key,
        models=preset.models,
        model_configs=[
            _model_config_out(config)
            for config in (preset.model_configs or [])
        ],
    )


def _model_config_out(config) -> dict[str, object]:
    payload = {
        "name": config.name,
        "max_output_tokens": config.max_output_tokens,
        "context_window": config.context_window,
        "auto_compact_token_limit": config.auto_compact_token_limit,
        "codex_model_reasoning_effort": config.codex_model_reasoning_effort,
        "codex_plan_mode_reasoning_effort": config.codex_plan_mode_reasoning_effort,
        "claude_reasoning_effort": config.claude_reasoning_effort,
    }
    return {key: value for key, value in payload.items() if value is not None}


def _model_preset_list_out(preset_list) -> SystemModelPresetListOut:
    return SystemModelPresetListOut(
        presets=[_model_preset_out(preset) for preset in preset_list.presets]
    )


def _model_preset_from_upsert(preset_id: str, payload: SystemModelPresetUpsertIn):
    providers = payload.providers or ([payload.provider] if payload.provider is not None else [])
    if not providers:
        raise ValueError("at least one model provider is required")
    return system_config_service.SystemModelPreset(
        id=preset_id,
        name=payload.name,
        provider=payload.provider or providers[0],
        base_url=payload.base_url,
        api_key=payload.api_key,
        models=payload.models,
        providers=providers,
        model_configs=[
            system_config_service.SystemModelConfig(
                name=config.name,
                max_output_tokens=config.max_output_tokens,
                context_window=config.context_window,
                auto_compact_token_limit=config.auto_compact_token_limit,
                codex_model_reasoning_effort=config.codex_model_reasoning_effort,
                codex_plan_mode_reasoning_effort=config.codex_plan_mode_reasoning_effort,
                claude_reasoning_effort=config.claude_reasoning_effort,
            )
            for config in payload.model_configs
        ],
    )


def _model_preset_from_import_payload(payload: dict[str, object]):
    record = payload.get("preset") if payload.get("kind") == MODEL_PRESET_BUNDLE_KIND else payload
    if not isinstance(record, dict):
        raise ValueError("model preset import payload is missing preset")
    preset_id = record.get("id")
    if not isinstance(preset_id, str) or preset_id.strip() == "":
        raise ValueError("model preset id is required")
    try:
        input_payload = SystemModelPresetUpsertIn.model_validate(record)
    except ValidationError as exc:
        raise ValueError(str(exc)) from exc
    return _model_preset_from_upsert(preset_id.strip(), input_payload)


@router.get("/skills/{skill_id}/detail", response_model=SystemSkillDetailOut)
async def read_system_skill_detail(
    skill_id: str,
    session: AsyncSession = Depends(get_session),
) -> SystemSkillDetailOut:
    try:
        detail = await system_config_service.system_skill_detail(skill_id, session)
        await session.commit()
        return detail
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.patch("/skills/{skill_id}/files", response_model=SystemSkillDetailOut)
async def update_system_skill_file(
    skill_id: str,
    payload: SystemSkillFileUpdateIn,
    session: AsyncSession = Depends(get_session),
) -> SystemSkillDetailOut:
    try:
        detail = await system_config_service.update_system_skill_file(
            skill_id,
            payload.path,
            payload.content,
            session,
        )
        await session.commit()
        return detail
    except ValueError as exc:
        detail = str(exc)
        status_code = (
            status.HTTP_400_BAD_REQUEST
            if "read-only" in detail or "invalid" in detail
            else status.HTTP_404_NOT_FOUND
        )
        raise HTTPException(status_code=status_code, detail=detail) from exc


@router.get("/mcp/{server_id:path}/detail", response_model=SystemMcpDetailOut)
async def read_system_mcp_detail(
    server_id: str,
    session: AsyncSession = Depends(get_session),
) -> SystemMcpDetailOut:
    try:
        detail = await system_config_service.system_mcp_detail(server_id, session)
        await session.commit()
        return detail
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.get(
    "/model-presets",
    response_model=SystemModelPresetListOut,
    response_model_exclude_none=True,
)
async def read_system_model_presets(
    session: AsyncSession = Depends(get_session),
) -> SystemModelPresetListOut:
    preset_list = await system_config_service.list_system_model_presets(session)
    await session.commit()
    return _model_preset_list_out(preset_list)


@router.get("/model-presets/{preset_id}/export")
async def export_system_model_preset(
    preset_id: str,
    session: AsyncSession = Depends(get_session),
) -> Response:
    preset_list = await system_config_service.list_system_model_presets(session)
    await session.commit()
    preset = next((candidate for candidate in preset_list.presets if candidate.id == preset_id), None)
    if preset is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="model preset not found")
    payload = {
        "kind": MODEL_PRESET_BUNDLE_KIND,
        "version": MODEL_PRESET_BUNDLE_VERSION,
        "preset": _model_preset_out(preset).model_dump(mode="json", exclude_none=True),
    }
    return Response(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        media_type="application/json; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{preset_id}.json"'},
    )


@router.post(
    "/model-presets/import",
    response_model=SystemModelPresetListOut,
    response_model_exclude_none=True,
)
async def import_system_model_preset(
    payload: dict[str, object],
    session: AsyncSession = Depends(get_session),
) -> SystemModelPresetListOut:
    try:
        preset = _model_preset_from_import_payload(payload)
        preset_list = await system_config_service.upsert_system_model_preset(session, preset)
        await session.commit()
        return _model_preset_list_out(preset_list)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.put(
    "/model-presets/{preset_id}",
    response_model=SystemModelPresetListOut,
    response_model_exclude_none=True,
)
async def upsert_system_model_preset(
    preset_id: str,
    payload: SystemModelPresetUpsertIn,
    session: AsyncSession = Depends(get_session),
) -> SystemModelPresetListOut:
    try:
        preset = _model_preset_from_upsert(preset_id, payload)
        preset_list = await system_config_service.upsert_system_model_preset(session, preset)
        await session.commit()
        return _model_preset_list_out(preset_list)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.delete(
    "/model-presets/{preset_id}",
    response_model=SystemModelPresetListOut,
    response_model_exclude_none=True,
)
async def delete_system_model_preset(
    preset_id: str,
    session: AsyncSession = Depends(get_session),
) -> SystemModelPresetListOut:
    try:
        preset_list = await system_config_service.delete_system_model_preset(session, preset_id)
        await session.commit()
        return _model_preset_list_out(preset_list)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
