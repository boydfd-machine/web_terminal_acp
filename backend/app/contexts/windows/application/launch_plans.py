from __future__ import annotations

from dataclasses import dataclass

from app.client_agent.agent_commands import agent_command_with_official_model_flag
from app.platform.plugins.agent_plugins import get_agent_plugin_registry
from app.platform.common_schemas import AgentClaudeModelRoutingIn, AgentConfigSelectionIn, AgentModelSelectionIn
from app.contexts.windows.api.schemas import WindowCreateIn
from app.contexts.agent_profiles.application import config_selection as agent_config_service
from app.contexts.agent_profiles.domain.cursor_official_models import is_cursor_official_model_preset
from app.contexts.activity.application.window_runtime_tags import agent_from_command
from app.contexts.windows.application.errors import WindowServiceError


@dataclass(frozen=True)
class AgentProfileLaunch:
    profile_id: str
    agent: str


@dataclass(frozen=True)
class LocalWindowLaunchPlan:
    cwd: str | None
    shell_command: str
    agent_config_selection: agent_config_service.AgentConfigSelection | None
    agent_model_settings: agent_config_service.ResolvedAgentModelSettings | None
    agent_model_selection: agent_config_service.AgentModelSelection | None
    agent_model_agent: str | None
    agent_profile: AgentProfileLaunch | None
    terminal_agent: str | None


@dataclass(frozen=True)
class RemoteWindowLaunchPlan:
    cwd: str | None
    shell_command: str | None
    agent_config_payload: dict[str, object] | None
    agent_model_payload: dict[str, object] | None
    agent_model_agent: str | None
    agent_profile: AgentProfileLaunch | None
    runtime_terminal_agent: str | None


def local_window_launch_plan(
    payload: WindowCreateIn,
    *,
    default_shell: str,
    model_presets: agent_config_service.SystemModelPresetList | None = None,
) -> LocalWindowLaunchPlan:
    shell_command = _shell_command_for_launch(payload) or default_shell
    agent_config_selection = _local_agent_config_for_launch(payload)
    profile = _local_agent_profile_for_launch(payload)
    model_selection = _local_agent_model_selection_for_launch(payload)
    return LocalWindowLaunchPlan(
        cwd=payload.cwd,
        shell_command=shell_command,
        agent_config_selection=(
            _agent_selection_from_schema(agent_config_selection)
            if agent_config_selection is not None
            else None
        ),
        agent_model_settings=_local_agent_model_settings_for_launch(payload, model_presets),
        agent_model_selection=model_selection,
        agent_model_agent=_local_agent_for_model_selection(payload),
        agent_profile=profile,
        terminal_agent=_agent_for_launch(payload) or agent_from_command(shell_command),
    )


def _local_agent_model_selection_for_launch(
    payload: WindowCreateIn,
) -> agent_config_service.AgentModelSelection | None:
    launch = payload.agent_launch
    if launch is None or launch.model_selection is None:
        return None
    return _agent_model_selection_from_schema(launch.model_selection)


def remote_window_launch_plan(
    payload: WindowCreateIn,
    *,
    model_presets: agent_config_service.SystemModelPresetList | None = None,
) -> RemoteWindowLaunchPlan:
    shell_command = _shell_command_for_launch(payload)
    schema_selection = _remote_agent_config_for_launch(payload)
    agent_config_payload = None
    if schema_selection is not None:
        agent_config_payload = _agent_selection_payload(_agent_selection_from_schema(schema_selection))
    profile = _remote_agent_profile_for_launch(payload)
    model_settings = _remote_agent_model_settings_for_launch(payload, model_presets)
    return RemoteWindowLaunchPlan(
        cwd=payload.cwd,
        shell_command=shell_command,
        agent_config_payload=agent_config_payload,
        agent_model_payload=agent_config_service.resolved_agent_model_settings_payload(model_settings),
        agent_model_agent=_remote_agent_for_model_selection(payload),
        agent_profile=profile,
        runtime_terminal_agent=_known_agent_for_launch(payload) or agent_from_command(shell_command),
    )


def agent_selection_from_schema(
    selection: AgentConfigSelectionIn,
) -> agent_config_service.AgentConfigSelection:
    return _agent_selection_from_schema(selection)


def agent_selection_payload(
    selection: agent_config_service.AgentConfigSelection,
) -> dict[str, object]:
    return _agent_selection_payload(selection)


def launch_agent_profile_id(payload: WindowCreateIn) -> str | None:
    return _agent_profile_id_for_launch(payload)


def launch_agent_provider(payload: WindowCreateIn) -> str | None:
    return _agent_for_launch(payload)


def launch_agent_command(payload: WindowCreateIn) -> str | None:
    return _agent_command_for_launch(payload)


def agent_model_selection_from_schema(
    selection: AgentModelSelectionIn,
) -> agent_config_service.AgentModelSelection:
    return _agent_model_selection_from_schema(selection)


def _agent_selection_from_schema(
    selection: AgentConfigSelectionIn,
) -> agent_config_service.AgentConfigSelection:
    return agent_config_service.AgentConfigSelection(
        agent=selection.agent,
        sections=[
            agent_config_service.AgentConfigSectionSelection(
                id=section.id,
                items=[
                    agent_config_service.AgentConfigItemSelection(id=item.id, enabled=item.enabled)
                    for item in section.items
                ],
            )
            for section in selection.sections
        ],
    )


def _agent_selection_payload(selection: agent_config_service.AgentConfigSelection) -> dict[str, object]:
    return {
        "agent": selection.agent,
        "sections": [
            {
                "id": section.id,
                "items": [
                    {"id": item.id, "enabled": item.enabled}
                    for item in section.items
                ],
            }
            for section in selection.sections
        ],
    }


def _agent_model_selection_from_schema(
    selection: AgentModelSelectionIn,
) -> agent_config_service.AgentModelSelection:
    return agent_config_service.AgentModelSelection(
        preset_id=selection.preset_id,
        model=selection.model,
        claude=(
            _claude_model_routing_from_schema(selection.claude)
            if selection.claude is not None
            else None
        ),
        codex_model_reasoning_effort=selection.codex_model_reasoning_effort,
        codex_plan_mode_reasoning_effort=selection.codex_plan_mode_reasoning_effort,
        claude_reasoning_effort=selection.claude_reasoning_effort,
    )


def _claude_model_routing_from_schema(
    routing: AgentClaudeModelRoutingIn,
) -> agent_config_service.ClaudeModelRouting:
    return agent_config_service.ClaudeModelRouting(
        mode=routing.mode,
        model=routing.model,
        opus_model=routing.opus_model,
        sonnet_model=routing.sonnet_model,
        haiku_model=routing.haiku_model,
    )


def _agent_command_for_launch(payload: WindowCreateIn) -> str | None:
    launch = payload.agent_launch
    if launch is None:
        return payload.shell_command
    return launch.command or launch.agent


def _shell_command_for_launch(payload: WindowCreateIn) -> str | None:
    command = _agent_command_for_launch(payload)
    if command is None:
        return None
    launch = payload.agent_launch
    if launch is None or launch.model_selection is None:
        return command
    if not is_cursor_official_model_preset(launch.model_selection.preset_id):
        return command
    return agent_command_with_official_model_flag(command, launch.model_selection.model)


def _agent_for_launch(payload: WindowCreateIn) -> str | None:
    launch = payload.agent_launch
    if launch is None:
        return None
    try:
        return get_agent_plugin_registry().by_agent_id(launch.agent).provider_id
    except ValueError as exc:
        raise WindowServiceError(400, str(exc)) from exc


def _known_agent_for_launch(payload: WindowCreateIn) -> str | None:
    try:
        return _agent_for_launch(payload)
    except WindowServiceError:
        return None


def _local_agent_config_for_launch(payload: WindowCreateIn) -> AgentConfigSelectionIn | None:
    launch = payload.agent_launch
    if launch is None or launch.config is None:
        return None
    launch_agent = _require_local_agent_capability(launch.agent, "launch")
    config_agent = agent_config_service.normalize_agent_kind(launch.config.agent)
    if config_agent != launch_agent:
        raise WindowServiceError(400, "agent launch config agent must match launch agent")
    return launch.config


def _remote_agent_config_for_launch(payload: WindowCreateIn) -> AgentConfigSelectionIn | None:
    launch = payload.agent_launch
    if launch is None or launch.config is None:
        return None
    if launch.config.agent.strip().lower() != launch.agent.strip().lower():
        raise WindowServiceError(400, "agent launch config agent must match launch agent")
    if launch.config.agent.strip() != launch.agent.strip():
        launch.config.agent = launch.agent.strip()
    return launch.config


def _local_agent_model_settings_for_launch(
    payload: WindowCreateIn,
    model_presets: agent_config_service.SystemModelPresetList | None,
) -> agent_config_service.ResolvedAgentModelSettings | None:
    launch = payload.agent_launch
    if launch is None or launch.model_selection is None:
        return None
    if is_cursor_official_model_preset(launch.model_selection.preset_id):
        return None
    agent = _require_local_agent_capability(launch.agent, "launch")
    selection = _agent_model_selection_from_schema(launch.model_selection)
    try:
        if model_presets is not None:
            return agent_config_service.resolve_agent_model_selection_from_presets(
                agent,
                selection,
                model_presets,
            )
        return agent_config_service.resolve_agent_model_selection(agent, selection)
    except ValueError as exc:
        raise WindowServiceError(400, str(exc)) from exc


def _remote_agent_model_settings_for_launch(
    payload: WindowCreateIn,
    model_presets: agent_config_service.SystemModelPresetList | None,
) -> agent_config_service.ResolvedAgentModelSettings | None:
    launch = payload.agent_launch
    if launch is None or launch.model_selection is None:
        return None
    if is_cursor_official_model_preset(launch.model_selection.preset_id):
        return None
    selection = _agent_model_selection_from_schema(launch.model_selection)
    try:
        if model_presets is not None:
            return agent_config_service.resolve_agent_model_selection_from_presets(
                _required_remote_launch_agent(payload),
                selection,
                model_presets,
            )
        return agent_config_service.resolve_agent_model_selection(
            _required_remote_launch_agent(payload),
            selection,
        )
    except ValueError as exc:
        raise WindowServiceError(400, str(exc)) from exc


def _local_agent_for_model_selection(payload: WindowCreateIn) -> str | None:
    launch = payload.agent_launch
    if launch is None or launch.model_selection is None:
        return None
    return _require_local_agent_capability(launch.agent, "launch")


def _remote_agent_for_model_selection(payload: WindowCreateIn) -> str | None:
    launch = payload.agent_launch
    if launch is None or launch.model_selection is None:
        return None
    return _required_remote_launch_agent(payload)


def _local_agent_profile_for_launch(payload: WindowCreateIn) -> AgentProfileLaunch | None:
    profile_id = _agent_profile_id_for_launch(payload)
    if profile_id is None:
        return None
    return AgentProfileLaunch(
        profile_id=profile_id,
        agent=_require_local_agent_capability(_required_launch_agent(payload), "launch"),
    )


def _remote_agent_profile_for_launch(payload: WindowCreateIn) -> AgentProfileLaunch | None:
    profile_id = _agent_profile_id_for_launch(payload)
    if profile_id is None:
        return None
    return AgentProfileLaunch(profile_id=profile_id, agent=_required_remote_launch_agent(payload))


def _agent_profile_id_for_launch(payload: WindowCreateIn) -> str | None:
    launch = payload.agent_launch
    if launch is None:
        return None
    profile_id = launch.profile_id
    if profile_id is None or not profile_id.strip():
        return None
    return profile_id.strip()


def _required_launch_agent(payload: WindowCreateIn) -> str:
    if payload.agent_launch is None:
        raise WindowServiceError(400, "agent launch is required")
    return payload.agent_launch.agent


def _required_remote_launch_agent(payload: WindowCreateIn) -> str:
    launch = payload.agent_launch
    if launch is None or not launch.agent.strip():
        raise WindowServiceError(400, "agent launch is required")
    return launch.agent.strip()


def _require_local_agent_capability(agent: str, capability: str) -> str:
    try:
        plugin = get_agent_plugin_registry().by_agent_id(agent)
    except ValueError as exc:
        raise WindowServiceError(400, str(exc)) from exc
    if not getattr(plugin.capabilities, capability):
        raise WindowServiceError(400, f"agent client does not support {capability}")
    return plugin.agent_client_id
