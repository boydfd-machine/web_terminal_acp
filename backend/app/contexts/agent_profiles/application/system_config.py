from __future__ import annotations

import asyncio

from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from app.contexts.agent_profiles.infrastructure import agent_config_store
from app.contexts.agent_profiles.infrastructure import system_settings_repository

SystemModelPreset = agent_config_store.SystemModelPreset
SystemModelConfig = agent_config_store.SystemModelConfig


async def restore_system_agent_config_files_to_disk(
    session: AsyncSession,
    *,
    home: Path | None = None,
) -> None:
    await system_settings_repository.restore_system_agent_config_files_to_disk(session, home=home)


async def system_agent_config_files_payload(
    session: AsyncSession,
    *,
    home: Path | None = None,
) -> dict[str, object]:
    await system_settings_repository.restore_system_agent_config_files_to_disk(session, home=home)
    return await asyncio.to_thread(
        lambda: agent_config_store.system_agent_config_files_payload(home=home)
    )


async def list_system_agent_config(session: AsyncSession | None = None):
    if session is None:
        return await asyncio.to_thread(agent_config_store.list_system_agent_config)
    await system_settings_repository.restore_system_agent_config_files_to_disk(session)
    return await asyncio.to_thread(agent_config_store.list_system_agent_config)


async def set_system_agent_config_item_enabled(
    section_id: str,
    item_id: str,
    enabled: bool,
    session: AsyncSession | None = None,
):
    if session is not None:
        await system_settings_repository.restore_system_agent_config_files_to_disk(session)
        result = await asyncio.to_thread(
            agent_config_store.set_system_agent_config_item_enabled,
            section_id,
            item_id,
            enabled,
        )
        await system_settings_repository.persist_system_agent_config_files(session)
        return result
    return await asyncio.to_thread(
        agent_config_store.set_system_agent_config_item_enabled,
        section_id,
        item_id,
        enabled,
    )


async def delete_system_agent_config_item(
    section_id: str,
    item_id: str,
    session: AsyncSession | None = None,
):
    if session is not None:
        await system_settings_repository.restore_system_agent_config_files_to_disk(session)
        result = await asyncio.to_thread(
            agent_config_store.delete_system_agent_config_item,
            section_id,
            item_id,
        )
        await system_settings_repository.persist_system_agent_config_files(session)
        return result
    return await asyncio.to_thread(
        agent_config_store.delete_system_agent_config_item,
        section_id,
        item_id,
    )


async def reset_system_agent_config_item(
    section_id: str,
    item_id: str,
    session: AsyncSession | None = None,
):
    if session is not None:
        await system_settings_repository.restore_system_agent_config_files_to_disk(session)
        result = await asyncio.to_thread(
            agent_config_store.reset_system_agent_config_item,
            section_id,
            item_id,
        )
        await system_settings_repository.persist_system_agent_config_files(session)
        return result
    return await asyncio.to_thread(
        agent_config_store.reset_system_agent_config_item,
        section_id,
        item_id,
    )


async def upsert_system_mcp_server(
    server_id: str,
    server: dict,
    *,
    enabled: bool = True,
    session: AsyncSession | None = None,
):
    if session is not None:
        await system_settings_repository.restore_system_agent_config_files_to_disk(session)
        result = await asyncio.to_thread(
            agent_config_store.upsert_system_mcp_server,
            server_id,
            server,
            enabled=enabled,
        )
        await system_settings_repository.persist_system_agent_config_files(session)
        return result
    return await asyncio.to_thread(
        agent_config_store.upsert_system_mcp_server,
        server_id,
        server,
        enabled=enabled,
    )


async def list_system_model_presets(session: AsyncSession):
    return await system_settings_repository.list_system_model_presets(session)


async def upsert_system_model_preset(session: AsyncSession, preset):
    return await system_settings_repository.upsert_system_model_preset(session, preset)


async def delete_system_model_preset(session: AsyncSession, preset_id: str):
    return await system_settings_repository.delete_system_model_preset(session, preset_id)


async def install_system_skill_from_zip(
    skill_id: str,
    archive: bytes,
    *,
    enabled: bool = True,
    session: AsyncSession | None = None,
):
    if session is not None:
        await system_settings_repository.restore_system_agent_config_files_to_disk(session)
        result = await asyncio.to_thread(
            agent_config_store.install_system_skill_from_zip,
            skill_id,
            archive,
            enabled=enabled,
        )
        await system_settings_repository.persist_system_agent_config_files(session)
        return result
    return await asyncio.to_thread(
        agent_config_store.install_system_skill_from_zip,
        skill_id,
        archive,
        enabled=enabled,
    )


async def system_skill_zip_bytes(skill_id: str, session: AsyncSession | None = None) -> bytes:
    if session is not None:
        await system_settings_repository.restore_system_agent_config_files_to_disk(session)
    return await asyncio.to_thread(agent_config_store.system_skill_zip_bytes, skill_id)


async def system_skill_detail(skill_id: str, session: AsyncSession | None = None):
    if session is not None:
        await system_settings_repository.restore_system_agent_config_files_to_disk(session)
    return await asyncio.to_thread(agent_config_store.system_skill_detail, skill_id)


async def update_system_skill_file(
    skill_id: str,
    path: str,
    content: str,
    session: AsyncSession | None = None,
):
    if session is not None:
        await system_settings_repository.restore_system_agent_config_files_to_disk(session)
        result = await asyncio.to_thread(
            agent_config_store.update_system_skill_file,
            skill_id,
            path,
            content,
        )
        await system_settings_repository.persist_system_agent_config_files(session)
        return result
    return await asyncio.to_thread(agent_config_store.update_system_skill_file, skill_id, path, content)


async def system_mcp_detail(server_id: str, session: AsyncSession | None = None):
    if session is not None:
        await system_settings_repository.restore_system_agent_config_files_to_disk(session)
    return await asyncio.to_thread(agent_config_store.system_mcp_detail, server_id)
