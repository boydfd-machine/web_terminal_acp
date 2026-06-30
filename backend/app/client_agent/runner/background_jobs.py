from __future__ import annotations

# ruff: noqa: F401,F821

from importlib import import_module

for _module_name in (
    "app.client_agent.runner.lifecycle",
    "app.client_agent.runner.message_io",
):
    _module = import_module(_module_name)
    globals().update(
        {name: value for name, value in _module.__dict__.items() if not name.startswith("__")}
    )


def _agent_profile_payload(profile: agent_profile_service.AgentProfile) -> dict[str, object]:
    return {
        "id": profile.id,
        "name": profile.name,
        "description": profile.description,
        "default_agent_client": profile.default_agent_client,
        "agent_md": profile.agent_md,
        "created_at": profile.created_at,
        "updated_at": profile.updated_at,
    }


async def _handle_create_window_job(
    control_writer: ControlMessageWriter,
    runtime: ClientTmuxRuntime,
    terminal: ClientTerminalMultiplexer,
    idle_supervisor: AgentIdleSupervisor,
    agent_tool_watcher: UnifiedAgentToolWatcher,
    stale_window_cleanup: ClientStaleWindowCleanup | None,
    message: AgentMessage,
) -> None:
    window_id = _message_window_id(message)
    logger.info(
        "client-agent create_window started",
        extra={"client_id": str(message.client_id), "window_id": str(window_id)},
    )
    try:
        clone_source_window_id = _optional_payload_string(message, "clone_source_window_id")
        clone_result = None
        project_path = _optional_payload_string(message, "cwd")
        _restore_system_config_files_from_message(message)
        if clone_source_window_id is not None:
            clone_result = clone_window_agent_homes(
                clone_source_window_id,
                window_id,
                source_cwd=project_path,
                isolate_sessions=_optional_payload_bool(message, "isolate_clone_sessions"),
            )
        else:
            agent_config_service.install_system_config_for_window(window_id=str(window_id))
        agent_config_selection = _agent_config_selection_from_payload(
            message.payload.get("agent_config_selection")
        )
        agent_profile_id = message.payload.get("agent_profile_id")
        if isinstance(agent_profile_id, str) and agent_profile_id.strip():
            agent_profile_agent = message.payload.get("agent_profile_agent")
            if isinstance(agent_profile_agent, str) and agent_profile_agent.strip():
                materialized = builtin_profiles.materialize_builtin_profile_for_window(
                    agent_profile_id.strip(), agent_profile_agent.strip(), window_id=str(window_id)
                )
                if materialized is None:
                    agent_profile_service.materialize_agent_profile_for_window(
                        agent_profile_id.strip(),
                        agent_profile_agent.strip(),
                        window_id=str(window_id),
                    )
        if agent_config_selection is not None:
            has_agent_profile = isinstance(agent_profile_id, str) and bool(agent_profile_id.strip())
            agent_config_service.apply_agent_config_selection(
                agent_config_selection,
                window_id=str(window_id),
                protect_system_config_skills=has_agent_profile,
            )
        agent_model_agent = _optional_payload_string(message, "agent_model_agent")
        if agent_model_agent is not None:
            agent_config_service.materialize_agent_model_settings_for_window(
                agent_model_agent,
                agent_config_service.resolved_agent_model_settings_from_payload(
                    message.payload.get("agent_model_settings")
                ),
                window_id=str(window_id),
            )
        shell_command = _optional_payload_string(message, "shell_command")
        runtime_shell_command = (
            clone_resume_command(shell_command, clone_result)
            if clone_result is not None
            else None
        ) or shell_command
        runtime_window = await runtime.create_window(
            window_id,
            cwd=project_path,
            shell_command=runtime_shell_command,
            agent_ops_token=_optional_payload_string(message, "agent_ops_token"),
        )
        terminal.register_window(
            window_id,
            runtime_window.remote_session_id,
            runtime_window.remote_window_id,
        )
        if stale_window_cleanup is not None:
            stale_window_cleanup.register_window(window_id, runtime_window)
        idle_supervisor.register_window(window_id, project_path)
        agent_tool_watcher.watch_window(
            window_id,
            project_path,
            providers=_providers_for_shell_command(shell_command),
        )
        await control_writer.send(
            AgentMessage(
                type="create_window_result",
                client_id=message.client_id,
                window_id=window_id,
                request_id=message.request_id,
                payload=asdict(runtime_window),
            )
        )
        logger.info(
            "client-agent create_window completed",
            extra={
                "client_id": str(message.client_id),
                "window_id": str(window_id),
                "remote_session_id": runtime_window.remote_session_id,
                "remote_window_id": runtime_window.remote_window_id,
            },
        )
    except asyncio.CancelledError:
        raise
    except Exception as exc:
        logger.exception(
            "client-agent create_window failed",
            extra={"client_id": str(message.client_id), "window_id": str(window_id)},
        )
        await _send_terminal_error(
            control_writer,
            message.client_id,
            window_id,
            request_id=message.request_id,
            message=str(exc),
        )


async def _handle_git_worktree_request_job(
    control_writer: ControlMessageWriter,
    semaphore: asyncio.Semaphore,
    message: AgentMessage,
) -> None:
    try:
        async with semaphore:
            result = await handle_git_worktree_request(message.payload)
    except asyncio.CancelledError:
        raise
    except Exception as exc:
        logger.exception(
            "client-agent git worktree request failed",
            extra={
                "client_id": str(message.client_id),
                "request_id": message.request_id,
            },
        )
        result = {"ok": False, "error": str(exc)}
    await control_writer.send(
        AgentMessage(
            type="git_worktree_result",
            client_id=message.client_id,
            request_id=message.request_id,
            payload=result,
        )
    )


async def _send_terminal_output(
    writer: BulkUploadWriter,
    client_id: UUID,
    window_id: UUID,
    data: bytes,
    *,
    view_id: UUID | None = None,
    is_snapshot: bool = False,
) -> None:
    if not data:
        return
    payload = TerminalPayload.from_bytes(window_id, data).model_dump(mode="json")
    if view_id is not None:
        payload["view_id"] = str(view_id)
    if is_snapshot:
        payload["is_snapshot"] = True
    await writer.send_terminal_output(
        AgentMessage(
            type="terminal_output",
            client_id=client_id,
            window_id=window_id,
            payload=payload,
        )
    )


async def _expire_attach_snapshot_if_silent(
    first_output_seen: asyncio.Event,
    consume_attach_snapshot,
) -> None:
    try:
        await asyncio.wait_for(first_output_seen.wait(), timeout=0.25)
    except asyncio.TimeoutError:
        consume_attach_snapshot()


async def _send_terminal_selection(
    writer: ControlMessageWriter,
    client_id: UUID,
    window_id: UUID,
    *,
    view_id: UUID | None = None,
) -> None:
    payload = {}
    if view_id is not None:
        payload["view_id"] = str(view_id)
    await writer.send(
        AgentMessage(
            type="terminal_selection",
            client_id=client_id,
            window_id=window_id,
            payload=payload,
        )
    )
