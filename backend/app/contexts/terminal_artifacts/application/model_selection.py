from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.contexts.activity.application.window_runtime_tags import agent_from_command
from app.contexts.agent_profiles.application import config_selection as agent_config_service
from app.contexts.agent_profiles.application import system_config as system_config_service
from app.models import TerminalArtifact, VirtualWindow
from app.platform.common_schemas import AgentModelSelectionIn
from app.platform.plugins.agent_plugins import get_agent_plugin_registry
from app.platform.ui_settings_repository import get_app_preferences

ARTIFACT_MODEL_SELECTION_METADATA_KEY = "artifact_model_selection"


def artifact_model_selection_payload(selection: AgentModelSelectionIn | None) -> dict[str, Any] | None:
    return selection.model_dump(mode="json", exclude_none=True) if selection is not None else None


def metadata_with_artifact_model_selection(
    metadata_json: dict[str, Any] | None,
    selection: AgentModelSelectionIn | None,
) -> dict[str, Any] | None:
    payload = artifact_model_selection_payload(selection)
    if payload is None:
        return metadata_json
    metadata = dict(metadata_json or {})
    metadata[ARTIFACT_MODEL_SELECTION_METADATA_KEY] = payload
    return metadata


def artifact_model_selection_from_metadata(
    metadata_json: dict[str, Any] | None,
) -> agent_config_service.AgentModelSelection | None:
    if not isinstance(metadata_json, dict):
        return None
    return agent_config_service.agent_model_selection_from_payload(
        metadata_json.get(ARTIFACT_MODEL_SELECTION_METADATA_KEY)
    )


async def artifact_model_selection_for_generation(
    session: AsyncSession,
    source_window: VirtualWindow,
    artifact: TerminalArtifact,
    *,
    source_agent_command: str | None,
) -> tuple[str | None, agent_config_service.ResolvedAgentModelSettings | None]:
    agent = _artifact_source_agent(source_window, source_agent_command)
    if agent is None:
        return None, None

    selection = (
        artifact_model_selection_from_metadata(artifact.metadata_json)
        or await _system_artifact_model_selection(session, agent)
    )
    if selection is None:
        return None, None

    presets = await system_config_service.list_system_model_presets(session)
    try:
        return agent, agent_config_service.resolve_agent_model_selection_from_presets(
            agent,
            selection,
            presets,
        )
    except ValueError as exc:
        raise ValueError(f"artifact model selection invalid: {exc}") from exc


async def _system_artifact_model_selection(
    session: AsyncSession,
    agent: str,
) -> agent_config_service.AgentModelSelection | None:
    preferences = await get_app_preferences(session)
    return agent_config_service.agent_model_selection_from_payload(
        preferences.artifact_model_selection_settings.get(agent)
    )


def _artifact_source_agent(source_window: VirtualWindow, source_agent_command: str | None) -> str | None:
    agent = _provider_agent(agent_from_command(source_agent_command or source_window.shell_command))
    if agent is not None:
        return agent
    return None


def _provider_agent(provider_or_agent: str | None) -> str | None:
    if provider_or_agent is None:
        return None
    registry = get_agent_plugin_registry()
    try:
        return registry.by_provider(provider_or_agent).agent_client_id
    except ValueError:
        pass
    try:
        return registry.by_agent_id(provider_or_agent).agent_client_id
    except ValueError:
        return None
