import shlex

from app.contexts.windows.application.remote_agent_resolution import require_remote_agent_id
from app.contexts.windows.api.agent_record_projection import *  # noqa: F403
from app.contexts.windows.api.response_projection import *  # noqa: F403


def _agent_config_out(payload: object, *, model: object = None) -> AgentConfigOut:
    return agent_config_out(payload, model=model)


def _agent_selection_from_schema(
    selection: AgentConfigSelectionIn,
) -> agent_config_service.AgentConfigSelection:
    return agent_selection_from_schema(selection)


def _agent_selection_payload(selection: agent_config_service.AgentConfigSelection) -> dict[str, object]:
    return agent_selection_payload(selection)


def _launch_agent_kind(payload: WindowCreateIn) -> str:
    if payload.agent_launch is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="agent launch is required")
    return _require_local_agent_capability(payload.agent_launch.agent, "launch")


def _agent_command_for_launch(payload: WindowCreateIn) -> str | None:
    return launch_agent_command(payload)


def _agent_for_launch(payload: WindowCreateIn) -> str | None:
    try:
        return launch_agent_provider(payload)
    except WindowServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc


def _known_agent_for_launch(payload: WindowCreateIn) -> str | None:
    try:
        return _agent_for_launch(payload)
    except HTTPException:
        return None


def _agent_config_for_launch(payload: WindowCreateIn) -> AgentConfigSelectionIn | None:
    try:
        plan = local_window_launch_plan(payload, default_shell=get_settings().default_shell)
    except WindowServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
    return payload.agent_launch.config if plan.agent_config_selection is not None and payload.agent_launch else None


def _remote_agent_for_launch(payload: WindowCreateIn) -> str:
    launch = payload.agent_launch
    if launch is None or not launch.agent.strip():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="agent launch is required")
    return launch.agent.strip()


def _remote_agent_config_for_launch(payload: WindowCreateIn) -> AgentConfigSelectionIn | None:
    try:
        remote_window_launch_plan(payload)
    except WindowServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
    return payload.agent_launch.config if payload.agent_launch else None


def _remote_agent_descriptors(payload: dict[str, object]) -> list[dict[str, object]]:
    return [descriptor.payload for descriptor in RemoteAgentCatalog.from_payload(payload).descriptors]


def _remote_descriptor_agent_id(descriptor: dict[str, object]) -> str | None:
    agent_id = descriptor.get("id")
    if isinstance(agent_id, str) and agent_id.strip():
        return agent_id.strip()
    return None


def _remote_descriptor_alias_candidates(descriptor: dict[str, object]) -> list[str]:
    candidates: list[str] = []
    for key in ("id", "provider_id", "default_command"):
        value = descriptor.get(key)
        if isinstance(value, str) and value.strip():
            candidates.append(value.strip())
    for key in ("aliases", "command_names"):
        values = descriptor.get(key)
        if isinstance(values, list):
            candidates.extend(value.strip() for value in values if isinstance(value, str) and value.strip())
    return candidates


def _remote_descriptor_for_agent(payload: dict[str, object], agent: str) -> dict[str, object] | None:
    clean_agent = agent.strip().lower()
    if not clean_agent:
        return None
    for descriptor in _remote_agent_descriptors(payload):
        for candidate in _remote_descriptor_alias_candidates(descriptor):
            if candidate.lower() == clean_agent:
                return descriptor
    return None


def _remote_descriptor_supports_capability(
    descriptor: dict[str, object],
    capability: AgentClientCapability,
) -> bool:
    capabilities = descriptor.get("capabilities")
    if not isinstance(capabilities, dict):
        return _REMOTE_CAPABILITY_DEFAULTS[capability]
    value = capabilities.get(capability)
    if isinstance(value, bool):
        return value
    return _REMOTE_CAPABILITY_DEFAULTS[capability]


def _remote_agent_id_with_capability(
    descriptors: dict[str, object],
    agent: str,
    capability: AgentClientCapability,
) -> str:
    try:
        return require_remote_agent_id(
            RemoteAgentCatalog.from_payload(descriptors),
            agent,
            capability,
        )
    except WindowServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc


async def _require_remote_agent_capability(
    remote_runtime: RemoteRuntime,
    agent: str,
    capability: AgentClientCapability,
) -> str:
    return _remote_agent_id_with_capability(
        await remote_runtime.list_agent_clients(),
        agent,
        capability,
    )


async def _require_remote_launch_capabilities(
    payload: WindowCreateIn,
    remote_runtime: RemoteRuntime,
) -> None:
    try:
        await require_remote_launch_capabilities(payload, remote_runtime)
    except WindowServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc


async def _remote_agent_request_id_for_capability(
    remote_runtime: RemoteRuntime,
    agent: str,
    capability: AgentClientCapability,
) -> str:
    return await _require_remote_agent_capability(remote_runtime, agent, capability)


async def _remote_agent_for_window(
    session: AsyncSession,
    window: VirtualWindow,
    remote_runtime: RemoteRuntime,
) -> str:
    provider = await _agent_provider_for_window(session, window)
    if provider is not None:
        with contextlib.suppress(HTTPException):
            return await _require_remote_agent_capability(remote_runtime, provider, "window_config")

    descriptors = await remote_runtime.list_agent_clients()
    remote_agent = _remote_agent_from_command(await _agent_command_for_window(session, window), descriptors)
    if remote_agent is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="agent config unavailable for this terminal",
        )
    return _remote_agent_id_with_capability(descriptors, remote_agent, "window_config")


def _remote_agent_from_command(command: str | None, payload: dict[str, object]) -> str | None:
    return RemoteAgentCatalog.from_payload(payload).agent_from_command(command)


def _remote_command_agent_map(payload: dict[str, object]) -> dict[str, str]:
    result: dict[str, str] = {}
    for descriptor in _remote_agent_descriptors(payload):
        agent_id = _remote_descriptor_agent_id(descriptor)
        if agent_id is None:
            continue
        for candidate in _remote_descriptor_command_candidates(descriptor):
            result[posixpath.basename(candidate).lower()] = agent_id
    return result


def _remote_descriptor_command_candidates(descriptor: dict[str, object]) -> list[str]:
    candidates: list[str] = []
    for key in ("id", "provider_id", "default_command"):
        value = descriptor.get(key)
        if isinstance(value, str) and value.strip():
            candidates.append(value.strip())
    for key in ("aliases", "command_names"):
        values = descriptor.get(key)
        if isinstance(values, list):
            candidates.extend(value.strip() for value in values if isinstance(value, str) and value.strip())
    return candidates


def _command_tokens(segment: str) -> list[str]:
    try:
        return shlex.split(segment.strip())
    except ValueError:
        return segment.strip().split()


def _agent_profile_for_launch(payload: WindowCreateIn) -> str | None:
    return launch_agent_profile_id(payload)


async def _assign_window_folder_path(
    session: AsyncSession,
    client_id: UUID,
    window: VirtualWindow,
    folder_path: str | None,
) -> None:
    try:
        await assign_window_folder_path(session, client_id, window, folder_path)
    except WindowServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc


def _client_connection_registry(request: Request) -> ClientConnectionRegistry:
    return client_connection_registry_from_state(request.app.state)


def _background_session_factory_for(session: AsyncSession) -> Callable[[], object]:
    bind = getattr(session, "bind", None)
    if bind is None:
        return SessionLocal
    return async_sessionmaker(bind, expire_on_commit=False, class_=AsyncSession)


__all__ = [name for name in globals() if not name.startswith("__")]
