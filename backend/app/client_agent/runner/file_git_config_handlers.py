from __future__ import annotations

# ruff: noqa: F401,F821

from importlib import import_module

for _module_name in (
    "app.client_agent.runner.lifecycle",
    "app.client_agent.runner.message_io",
    "app.client_agent.runner.background_jobs",
):
    _module = import_module(_module_name)
    globals().update(
        {name: value for name, value in _module.__dict__.items() if not name.startswith("__")}
    )


async def _handle_file_message(
    ctx: AgentMessageHandlerContext,
    message: AgentMessage,
) -> bool:
    if message.type == "file_read":
        path = _required_payload_string(message, "path")
        max_bytes = (
            _optional_positive_int_payload(message, "max_bytes") or FILE_READ_DEFAULT_MAX_BYTES
        )
        output = await asyncio.to_thread(_read_limited_file, path, max_bytes=max_bytes)
        await ctx.control_writer.send(
            AgentMessage(
                type="file_read_result",
                client_id=message.client_id,
                window_id=message.window_id,
                request_id=message.request_id,
                payload=TerminalPayload.from_bytes(message.client_id, output).model_dump(
                    mode="json"
                ),
            )
        )
        return False
    if message.type == "file_list":
        path = _required_payload_string(message, "path")
        entries = await asyncio.to_thread(_list_file_entries, path)
        await ctx.control_writer.send(
            AgentMessage(
                type="file_list_result",
                client_id=message.client_id,
                window_id=message.window_id,
                request_id=message.request_id,
                payload={"entries": entries},
            )
        )
        return False
    if message.type == "file_write":
        path = _required_payload_string(message, "path")
        overwrite_value = message.payload.get("overwrite")
        overwrite = overwrite_value if isinstance(overwrite_value, bool) else True
        payload = TerminalPayload.model_validate(message.payload)
        data = payload.to_bytes()
        if len(data) > FILE_WRITE_DEFAULT_MAX_BYTES:
            raise ValueError(f"file exceeds maximum size: {path}")
        await asyncio.to_thread(_write_file, path, data=data, overwrite=overwrite)
        await ctx.control_writer.send(
            AgentMessage(
                type="file_write_result",
                client_id=message.client_id,
                window_id=message.window_id,
                request_id=message.request_id,
                payload={"path": path},
            )
        )
    return False


async def _handle_git_worktree_message(
    ctx: AgentMessageHandlerContext,
    message: AgentMessage,
) -> bool:
    task = asyncio.create_task(
        _handle_git_worktree_request_job(
            ctx.control_writer,
            ctx.git_worktree_semaphore,
            message,
        )
    )
    ctx.git_worktree_tasks.add(task)
    task.add_done_callback(ctx.git_worktree_tasks.discard)
    return False


async def _handle_agent_config_message(
    ctx: AgentMessageHandlerContext,
    message: AgentMessage,
) -> bool:
    _restore_system_config_files_from_message(message)
    if message.type == "system_agent_config_get":
        config = agent_config_service.list_system_agent_config()
        await ctx.control_writer.send(
            AgentMessage(
                type="agent_config_result",
                client_id=message.client_id,
                window_id=message.window_id,
                request_id=message.request_id,
                payload=_agent_config_payload(config),
            )
        )
        return False
    if message.type == "agent_config_get":
        agent = _required_payload_string(message, "agent")
        window_id = _agent_config_request_window_id(message)
        if window_id is not None:
            config = agent_config_service.list_window_agent_config(
                agent,
                window_id=str(window_id),
            )
            payload = _agent_config_payload(config)
            model_view = agent_config_service.window_agent_model_view(
                agent,
                window_id=str(window_id),
            )
            if model_view is not None:
                payload["model"] = model_view
        else:
            config = agent_config_service.list_agent_config(agent)
            payload = _agent_config_payload(config)
        await ctx.control_writer.send(
            AgentMessage(
                type="agent_config_result",
                client_id=message.client_id,
                window_id=message.window_id,
                request_id=message.request_id,
                payload=payload,
            )
        )
        return False
    if message.type == "agent_profile_config_get":
        agent = _required_payload_string(message, "agent")
        profile_id = _required_payload_string(message, "profile_id")
        if builtin_profiles.is_builtin_profile_id(profile_id):
            config = builtin_profiles.builtin_profile_config(profile_id, agent)
            if config is None:
                config = agent_config_service.list_agent_config(agent)
        else:
            config = agent_profile_service.list_agent_profile_config(profile_id, agent)
        await ctx.control_writer.send(
            AgentMessage(
                type="agent_config_result",
                client_id=message.client_id,
                request_id=message.request_id,
                payload=_agent_config_payload(config),
            )
        )
        return False
    if message.type == "agent_profile_list":
        profiles = (
            agent_profile_service.list_agent_profiles() + builtin_profiles.builtin_agent_profiles()
        )
        await ctx.control_writer.send(
            AgentMessage(
                type="agent_profile_result",
                client_id=message.client_id,
                request_id=message.request_id,
                payload={"profiles": [_agent_profile_payload(profile) for profile in profiles]},
            )
        )
        return False
    if message.type == "agent_profile_create":
        profile = agent_profile_service.create_agent_profile(
            name=_required_payload_string(message, "name"),
            description=_optional_payload_string(message, "description"),
            default_agent_client=_optional_payload_string(message, "default_agent_client")
            or "codex",
            source_agent_client=_optional_payload_string(message, "source_agent_client"),
        )
        await ctx.control_writer.send(
            AgentMessage(
                type="agent_profile_result",
                client_id=message.client_id,
                request_id=message.request_id,
                payload=_agent_profile_payload(profile),
            )
        )
        return False
    if message.type == "agent_profile_update":
        update_kwargs: dict[str, object] = {}
        for key in ("name", "description", "default_agent_client", "agent_md"):
            if key in message.payload:
                update_kwargs[key] = message.payload.get(key)
        profile = agent_profile_service.update_agent_profile(
            _required_payload_string(message, "profile_id"),
            **update_kwargs,
        )
        await ctx.control_writer.send(
            AgentMessage(
                type="agent_profile_result",
                client_id=message.client_id,
                request_id=message.request_id,
                payload=_agent_profile_payload(profile),
            )
        )
        return False
    if message.type == "agent_profile_delete":
        agent_profile_service.delete_agent_profile(_required_payload_string(message, "profile_id"))
        await ctx.control_writer.send(
            AgentMessage(
                type="agent_profile_result",
                client_id=message.client_id,
                request_id=message.request_id,
                payload={},
            )
        )
        return False
    if message.type == "agent_profile_config_set_enabled":
        agent = _required_payload_string(message, "agent")
        profile_id = _required_payload_string(message, "profile_id")
        section_id = _required_payload_string(message, "section_id")
        item_id = _required_payload_string(message, "item_id")
        enabled = message.payload.get("enabled")
        if not isinstance(enabled, bool):
            raise ValueError("agent profile config enabled must be a boolean")
        if builtin_profiles.is_builtin_profile_id(profile_id):
            config = builtin_profiles.set_builtin_profile_config_item_enabled(
                profile_id,
                agent,
                section_id,
                item_id,
                enabled,
            )
        else:
            config = agent_profile_service.set_agent_profile_config_item_enabled(
                profile_id,
                agent,
                section_id,
                item_id,
                enabled,
            )
        await ctx.control_writer.send(
            AgentMessage(
                type="agent_config_result",
                client_id=message.client_id,
                request_id=message.request_id,
                payload=_agent_config_payload(config),
            )
        )
        return False
    if message.type == "agent_config_set_enabled":
        window_id = _message_window_id(message)
        agent = _required_payload_string(message, "agent")
        section_id = _required_payload_string(message, "section_id")
        item_id = _required_payload_string(message, "item_id")
        enabled = message.payload.get("enabled")
        if not isinstance(enabled, bool):
            raise ValueError("agent config enabled must be a boolean")
        config = agent_config_service.set_window_agent_config_item_enabled(
            agent,
            section_id,
            item_id,
            enabled,
            window_id=str(window_id),
        )
        await ctx.control_writer.send(
            AgentMessage(
                type="agent_config_result",
                client_id=message.client_id,
                window_id=message.window_id,
                request_id=message.request_id,
                payload=_agent_config_payload(config),
            )
        )
        return False
    if message.type == "agent_config_set_model":
        window_id = _message_window_id(message)
        agent = _required_payload_string(message, "agent")
        update = agent_config_service.WindowAgentModelUpdate(
            model=message.payload.get("model"),
            codex_model_reasoning_effort=message.payload.get("codex_model_reasoning_effort"),
            codex_plan_mode_reasoning_effort=message.payload.get("codex_plan_mode_reasoning_effort"),
            claude_reasoning_effort=message.payload.get("claude_reasoning_effort"),
            clear_codex_model_reasoning_effort=bool(message.payload.get("clear_codex_model_reasoning_effort")),
            clear_codex_plan_mode_reasoning_effort=bool(message.payload.get("clear_codex_plan_mode_reasoning_effort")),
            clear_claude_reasoning_effort=bool(message.payload.get("clear_claude_reasoning_effort")),
        )
        config = agent_config_service.update_window_agent_model(
            agent,
            update,
            window_id=str(window_id),
        )
        payload = _agent_config_payload(config)
        model_view = agent_config_service.window_agent_model_view(
            agent,
            window_id=str(window_id),
        )
        if model_view is not None:
            payload["model"] = model_view
        await ctx.control_writer.send(
            AgentMessage(
                type="agent_config_result",
                client_id=message.client_id,
                window_id=message.window_id,
                request_id=message.request_id,
                payload=payload,
            )
        )
    return False


def _agent_config_request_window_id(message: AgentMessage) -> UUID | None:
    if message.window_id is not None:
        return message.window_id
    payload_window_id = message.payload.get("window_id")
    return UUID(str(payload_window_id)) if payload_window_id is not None else None


def _agent_config_payload(config: agent_config_service.AgentConfig) -> dict[str, object]:
    return {
        "agent": config.agent,
        "sections": [
            {
                "id": section.id,
                "name": section.name,
                "items": [
                    {
                        "id": item.id,
                        "name": item.name,
                        "enabled": item.enabled,
                        "path": item.path,
                        "origin": item.origin,
                    }
                    for item in section.items
                ],
            }
            for section in config.sections
        ],
    }
