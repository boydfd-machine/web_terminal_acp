from __future__ import annotations

from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from app.contexts.agent_profiles.infrastructure import builtin_profiles, profile_store
from app.contexts.agent_profiles.infrastructure import profile_settings_repository

AgentProfile = profile_store.AgentProfile


def list_agent_profiles(*, home: Path | None = None) -> list[AgentProfile]:
    return profile_store.list_agent_profiles(home=home)


def get_agent_profile(profile_id: str, *, home: Path | None = None) -> AgentProfile:
    return profile_store.get_agent_profile(profile_id, home=home)


def create_agent_profile(
    *,
    name: str,
    description: str | None = None,
    default_agent_client: str = "codex",
    source_agent_client: str | None = None,
    home: Path | None = None,
) -> AgentProfile:
    return profile_store.create_agent_profile(
        name=name,
        description=description,
        default_agent_client=default_agent_client,
        source_agent_client=source_agent_client,
        home=home,
    )


def update_agent_profile(
    profile_id: str,
    *,
    name: str | None = None,
    description: str | None | object = profile_store._UNSET,
    default_agent_client: str | None = None,
    agent_md: str | None | object = profile_store._UNSET,
    home: Path | None = None,
) -> AgentProfile:
    return profile_store.update_agent_profile(
        profile_id,
        name=name,
        description=description,
        default_agent_client=default_agent_client,
        agent_md=agent_md,
        home=home,
    )


def delete_agent_profile(profile_id: str, *, home: Path | None = None) -> None:
    profile_store.delete_agent_profile(profile_id, home=home)


def list_agent_profile_config(
    profile_id: str,
    agent: str,
    *,
    home: Path | None = None,
):
    return profile_store.list_agent_profile_config(profile_id, agent, home=home)


def set_agent_profile_config_item_enabled(
    profile_id: str,
    agent: str,
    section_id: str,
    item_id: str,
    enabled: bool,
    *,
    home: Path | None = None,
):
    return profile_store.set_agent_profile_config_item_enabled(
        profile_id,
        agent,
        section_id,
        item_id,
        enabled,
        home=home,
    )


def materialize_agent_profile_for_window(
    profile_id: str,
    agent: str,
    *,
    window_id: str,
    home: Path | None = None,
):
    return profile_store.materialize_agent_profile_for_window(
        profile_id,
        agent,
        window_id=window_id,
        home=home,
    )


def is_builtin_profile_id(profile_id: str) -> bool:
    return builtin_profiles.is_builtin_profile_id(profile_id)


def builtin_agent_profiles() -> list[AgentProfile]:
    return builtin_profiles.builtin_agent_profiles()


def get_builtin_agent_profile(profile_id: str) -> AgentProfile | None:
    return builtin_profiles.get_builtin_agent_profile(profile_id)


def builtin_profile_config(profile_id: str, agent: str, *, home: Path | None = None):
    return builtin_profiles.builtin_profile_config(profile_id, agent, home=home)


def set_builtin_profile_config_item_enabled(
    profile_id: str,
    agent: str,
    section_id: str,
    item_id: str,
    enabled: bool,
    *,
    home: Path | None = None,
):
    return builtin_profiles.set_builtin_profile_config_item_enabled(
        profile_id,
        agent,
        section_id,
        item_id,
        enabled,
        home=home,
    )


def materialize_builtin_profile_for_window(
    profile_id: str,
    agent: str,
    *,
    window_id: str,
    home: Path | None = None,
):
    return builtin_profiles.materialize_builtin_profile_for_window(
        profile_id,
        agent,
        window_id=window_id,
        home=home,
    )


async def restore_agent_profile_files_to_disk(
    session: AsyncSession,
    *,
    owner_user_id: str | None = None,
    home: Path | None = None,
) -> Path:
    return await profile_settings_repository.restore_agent_profile_files_to_disk(
        session,
        owner_user_id=owner_user_id,
        home=home,
    )
