from __future__ import annotations

from pathlib import Path

from app.contexts.agent_profiles.infrastructure import agent_config_store

AgentKind = agent_config_store.AgentKind
AgentConfigItem = agent_config_store.AgentConfigItem
AgentConfigSection = agent_config_store.AgentConfigSection
AgentConfig = agent_config_store.AgentConfig
AgentConfigItemSelection = agent_config_store.AgentConfigItemSelection
AgentConfigSectionSelection = agent_config_store.AgentConfigSectionSelection
AgentConfigSelection = agent_config_store.AgentConfigSelection
AgentModelSelection = agent_config_store.AgentModelSelection
ClaudeModelRouting = agent_config_store.ClaudeModelRouting
ResolvedAgentModelSettings = agent_config_store.ResolvedAgentModelSettings
SystemModelPresetList = agent_config_store.SystemModelPresetList


def normalize_agent_kind(agent: str) -> AgentKind:
    return agent_config_store.normalize_agent_kind(agent)


def list_agent_config(agent: str, *, home: Path | None = None) -> AgentConfig:
    return agent_config_store.list_agent_config(agent, home=home)


def set_agent_config_item_enabled(
    agent: str,
    section_id: str,
    item_id: str,
    enabled: bool,
    *,
    home: Path | None = None,
) -> AgentConfig:
    return agent_config_store.set_agent_config_item_enabled(
        agent,
        section_id,
        item_id,
        enabled,
        home=home,
    )


def list_window_agent_config(
    agent: str,
    *,
    window_id: str,
    home: Path | None = None,
) -> AgentConfig:
    return agent_config_store.list_window_agent_config(agent, window_id=window_id, home=home)


def set_window_agent_config_item_enabled(
    agent: str,
    section_id: str,
    item_id: str,
    enabled: bool,
    *,
    window_id: str,
    home: Path | None = None,
) -> AgentConfig:
    return agent_config_store.set_window_agent_config_item_enabled(
        agent,
        section_id,
        item_id,
        enabled,
        window_id=window_id,
        home=home,
    )


def apply_agent_config_selection(
    selection: AgentConfigSelection,
    *,
    window_id: str,
    home: Path | None = None,
    protect_system_config_skills: bool = False,
) -> AgentConfig:
    return agent_config_store.apply_agent_config_selection(
        selection,
        window_id=window_id,
        home=home,
        protect_system_config_skills=protect_system_config_skills,
    )


def install_system_config_for_window(
    *,
    window_id: str,
    home: Path | None = None,
) -> None:
    agent_config_store.install_system_config_for_window(window_id=window_id, home=home)


def restore_system_agent_config_files_payload(
    payload: object,
    *,
    home: Path | None = None,
) -> None:
    agent_config_store.restore_system_agent_config_files_payload(payload, home=home)


def install_system_config_for_agent_window(
    agent: str,
    *,
    window_id: str,
    home: Path | None = None,
) -> None:
    agent_config_store.install_system_config_for_agent_window(
        agent,
        window_id=window_id,
        home=home,
    )


def install_builtin_mcp_for_window(
    *,
    window_id: str,
    source_client_id: str,
    source_window_id: str,
    server_url: str,
    mcp_token: str | None = None,
    home: Path | None = None,
) -> None:
    agent_config_store.install_builtin_mcp_for_window(
        window_id=window_id,
        source_client_id=source_client_id,
        source_window_id=source_window_id,
        server_url=server_url,
        mcp_token=mcp_token,
        home=home,
    )


def resolve_agent_model_selection(
    agent: str,
    selection: AgentModelSelection | None,
    *,
    home: Path | None = None,
) -> ResolvedAgentModelSettings | None:
    return agent_config_store.resolve_agent_model_selection(agent, selection, home=home)


def resolve_agent_model_selection_from_presets(
    agent: str,
    selection: AgentModelSelection | None,
    preset_list: agent_config_store.SystemModelPresetList,
) -> ResolvedAgentModelSettings | None:
    return agent_config_store.resolve_agent_model_selection_from_presets(
        agent,
        selection,
        preset_list,
    )


def materialize_agent_model_settings_for_window(
    agent: str,
    settings: ResolvedAgentModelSettings | None,
    *,
    window_id: str,
    home: Path | None = None,
) -> None:
    agent_config_store.materialize_agent_model_settings_for_window(
        agent,
        settings,
        window_id=window_id,
        home=home,
    )


def apply_window_agent_model_selection(
    agent: str,
    selection: AgentModelSelection | None,
    *,
    window_id: str,
    home: Path | None = None,
) -> None:
    agent_config_store.apply_window_agent_model_selection(
        agent, selection, window_id=window_id, home=home
    )


def save_window_agent_model_selection(
    agent: str,
    selection: AgentModelSelection,
    *,
    window_id: str,
    home: Path | None = None,
) -> None:
    agent_config_store.save_window_agent_model_selection(
        agent, selection, window_id=window_id, home=home
    )


def load_window_agent_model_selection(
    agent: str,
    *,
    window_id: str,
    home: Path | None = None,
) -> AgentModelSelection | None:
    return agent_config_store.load_window_agent_model_selection(
        agent, window_id=window_id, home=home
    )


def resolved_agent_model_settings_payload(
    settings: ResolvedAgentModelSettings | None,
) -> dict[str, object] | None:
    return agent_config_store.resolved_agent_model_settings_payload(settings)


def safe_agent_model_settings_payload(
    settings: ResolvedAgentModelSettings | None,
) -> dict[str, object] | None:
    return agent_config_store.safe_agent_model_settings_payload(settings)


def resolved_agent_model_settings_from_payload(value: object) -> ResolvedAgentModelSettings | None:
    return agent_config_store.resolved_agent_model_settings_from_payload(value)


def agent_model_selection_from_payload(value: object) -> AgentModelSelection | None:
    return agent_config_store.agent_model_selection_from_payload(value)


def window_agent_model_metadata(
    agent: str,
    *,
    window_id: str,
    home: Path | None = None,
) -> dict[str, object] | None:
    return agent_config_store.window_agent_model_metadata(agent, window_id=window_id, home=home)


def window_agent_model_view(
    agent: str,
    *,
    window_id: str,
    home: Path | None = None,
    preset_list: SystemModelPresetList | None = None,
) -> dict[str, object] | None:
    return agent_config_store.window_agent_model_view(
        agent, window_id=window_id, home=home, preset_list=preset_list
    )


WindowAgentModelUpdate = agent_config_store.WindowAgentModelUpdate


def update_window_agent_model(
    agent: str,
    update: WindowAgentModelUpdate,
    *,
    window_id: str,
    home: Path | None = None,
    preset_list: SystemModelPresetList | None = None,
) -> AgentConfig:
    return agent_config_store.update_window_agent_model(
        agent, update, window_id=window_id, home=home, preset_list=preset_list
    )
