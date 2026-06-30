from __future__ import annotations

# ruff: noqa: F401,F821

from importlib import import_module

for _module_name in (
    "app.client_agent.runner.lifecycle",
    "app.client_agent.runner.runtime_availability",
    "app.client_agent.runner.cleanup_hooks",
    "app.client_agent.runner.message_io",
    "app.client_agent.runner.background_jobs",
    "app.client_agent.runner.file_git_config_handlers",
):
    _module = import_module(_module_name)
    globals().update(
        {name: value for name, value in _module.__dict__.items() if not name.startswith("__")}
    )

from app.client_agent.process_liveness import active_non_shell_processes_for_runtime_window


@dataclass(frozen=True)
class AgentMessageHandlerContext:
    control_writer: ControlMessageWriter
    bulk_writer: BulkUploadWriter
    config: ClientAgentConfig
    runtime: ClientTmuxRuntime
    terminal: ClientTerminalMultiplexer
    idle_supervisor: AgentIdleSupervisor
    agent_tool_watcher: UnifiedAgentToolWatcher
    aux_terminal: ClientAuxTerminalManager
    attach_snapshot_tasks: dict[UUID, asyncio.Task[None]]
    git_worktree_tasks: set[asyncio.Task[None]]
    git_worktree_semaphore: asyncio.Semaphore
    terminal_view_window_ids: dict[UUID, UUID]
    stale_window_cleanup: ClientStaleWindowCleanup | None = None
    create_window_tasks: set[asyncio.Task[None]] | None = None


AUX_TERMINAL_MESSAGE_TYPES = frozenset({
    "aux_terminal_ensure",
    "aux_terminal_attach",
    "aux_terminal_detach",
    "aux_terminal_kill",
    "aux_terminal_input",
    "aux_terminal_resize",
})
TERMINAL_MESSAGE_TYPES = frozenset({
    "terminal_attach",
    "terminal_detach",
    "terminal_input",
    "terminal_input_direct",
    "terminal_resize",
    "terminal_capture",
    "terminal_select_window",
    "process_liveness",
})
FILE_MESSAGE_TYPES = frozenset({"file_read", "file_list", "file_write"})
AGENT_CONFIG_MESSAGE_TYPES = frozenset({
    "agent_config_get",
    "system_agent_config_get",
    "agent_profile_config_get",
    "agent_profile_list",
    "agent_profile_create",
    "agent_profile_update",
    "agent_profile_delete",
    "agent_profile_config_set_enabled",
    "agent_config_set_enabled",
})
CREATE_WINDOW_CONCURRENCY = 4
_CREATE_WINDOW_SEMAPHORE_ATTR = "_web_terminal_create_window_semaphore"


async def _handle_agent_message(
    control_writer: ControlMessageWriter,
    bulk_writer: BulkUploadWriter,
    config: ClientAgentConfig,
    runtime: ClientTmuxRuntime,
    terminal: ClientTerminalMultiplexer,
    idle_supervisor: AgentIdleSupervisor,
    agent_tool_watcher: UnifiedAgentToolWatcher,
    aux_terminal: ClientAuxTerminalManager,
    attach_snapshot_tasks: dict[UUID, asyncio.Task[None]],
    git_worktree_tasks: set[asyncio.Task[None]],
    git_worktree_semaphore: asyncio.Semaphore,
    terminal_view_window_ids: dict[UUID, UUID],
    message: AgentMessage,
    *,
    create_window_tasks: set[asyncio.Task[None]] | None = None,
    stale_window_cleanup: ClientStaleWindowCleanup | None = None,
) -> bool:
    ctx = AgentMessageHandlerContext(
        control_writer=control_writer,
        bulk_writer=bulk_writer,
        config=config,
        runtime=runtime,
        terminal=terminal,
        idle_supervisor=idle_supervisor,
        agent_tool_watcher=agent_tool_watcher,
        aux_terminal=aux_terminal,
        attach_snapshot_tasks=attach_snapshot_tasks,
        git_worktree_tasks=git_worktree_tasks,
        git_worktree_semaphore=git_worktree_semaphore,
        terminal_view_window_ids=terminal_view_window_ids,
        stale_window_cleanup=stale_window_cleanup,
        create_window_tasks=create_window_tasks,
    )
    if message.type == "shutdown":
        return True
    if message.type == "self_update_prepare":
        result = await start_self_update(config, message.payload)
        await control_writer.send(
            AgentMessage(
                type="self_update_started",
                client_id=message.client_id,
                request_id=message.request_id,
                payload=result,
            )
        )
        return False
    if message.type == "agent_clients_list":
        await control_writer.send(
            AgentMessage(
                type="agent_client_result",
                client_id=message.client_id,
                request_id=message.request_id,
                payload=_agent_clients_payload(),
            )
        )
        return False
    if message.type == "cursor_official_models_list":
        from app.client_agent.cursor_official_models import list_cursor_official_models

        await control_writer.send(
            AgentMessage(
                type="agent_client_result",
                client_id=message.client_id,
                request_id=message.request_id,
                payload={"models": list_cursor_official_models()},
            )
        )
        return False
    if message.type == "create_window":
        return await _handle_create_window_message(ctx, message)
    if message.type == "kill_window":
        return await _handle_kill_window_message(ctx, message)
    if message.type in AUX_TERMINAL_MESSAGE_TYPES:
        return await _handle_aux_terminal_message(ctx, message)
    if message.type in TERMINAL_MESSAGE_TYPES:
        return await _handle_terminal_message(ctx, message)
    if message.type in FILE_MESSAGE_TYPES:
        return await _handle_file_message(ctx, message)
    if message.type == "git_worktree_request":
        return await _handle_git_worktree_message(ctx, message)
    if message.type in AGENT_CONFIG_MESSAGE_TYPES:
        return await _handle_agent_config_message(ctx, message)
    return False


async def _handle_create_window_message(
    ctx: AgentMessageHandlerContext,
    message: AgentMessage,
) -> bool:
    if ctx.create_window_tasks is None:
        await _handle_create_window_job(
            ctx.control_writer,
            ctx.runtime,
            ctx.terminal,
            ctx.idle_supervisor,
            ctx.agent_tool_watcher,
            ctx.stale_window_cleanup,
            message,
        )
        return False
    task = asyncio.create_task(
        _handle_create_window_job_with_limit(ctx, message)
    )
    ctx.create_window_tasks.add(task)
    task.add_done_callback(ctx.create_window_tasks.discard)
    return False


async def _handle_create_window_job_with_limit(
    ctx: AgentMessageHandlerContext,
    message: AgentMessage,
) -> None:
    async with _create_window_semaphore_for_runtime(ctx.runtime):
        await _handle_create_window_job(
            ctx.control_writer,
            ctx.runtime,
            ctx.terminal,
            ctx.idle_supervisor,
            ctx.agent_tool_watcher,
            ctx.stale_window_cleanup,
            message,
        )


def _create_window_semaphore_for_runtime(runtime: ClientTmuxRuntime) -> asyncio.Semaphore:
    semaphore = getattr(runtime, _CREATE_WINDOW_SEMAPHORE_ATTR, None)
    if semaphore is None:
        semaphore = asyncio.Semaphore(CREATE_WINDOW_CONCURRENCY)
        setattr(runtime, _CREATE_WINDOW_SEMAPHORE_ATTR, semaphore)
    return semaphore


async def _handle_kill_window_message(
    ctx: AgentMessageHandlerContext,
    message: AgentMessage,
) -> bool:
    window_id = _message_window_id(message)
    ctx.agent_tool_watcher.remove_window(window_id)
    cleanup_call(ctx.stale_window_cleanup, "unregister_window", window_id)
    ctx.idle_supervisor.remove_window(window_id)
    await ctx.terminal.remove_window(window_id)
    await ctx.runtime.kill_window(window_id)
    await ctx.control_writer.send(
        AgentMessage(
            type="kill_window_result",
            client_id=message.client_id,
            window_id=window_id,
            request_id=message.request_id,
            payload={},
        )
    )
    return False


async def _handle_aux_terminal_message(
    ctx: AgentMessageHandlerContext,
    message: AgentMessage,
) -> bool:
    if message.type == "aux_terminal_ensure":
        aux_terminal_id = _required_payload_string(message, "aux_terminal_id")
        target = await ctx.aux_terminal.ensure_terminal(
            aux_terminal_id,
            cwd=_optional_payload_string(message, "cwd"),
            shell_command=_optional_payload_string(message, "shell_command"),
        )
        await ctx.control_writer.send(
            AgentMessage(
                type="aux_terminal_ensure_result",
                client_id=message.client_id,
                window_id=message.window_id,
                request_id=message.request_id,
                payload={
                    "aux_terminal_id": target.aux_terminal_id,
                    "cwd": target.cwd,
                    "shell_command": target.shell_command,
                },
            )
        )
        return False
    if message.type == "aux_terminal_attach":
        aux_terminal_id = _required_payload_string(message, "aux_terminal_id")
        view_id = _view_id_for_message(message)

        async def send_aux_output(data: bytes) -> None:
            payload = TerminalPayload.from_bytes(_message_window_id(message), data).model_dump(mode="json")
            payload["view_id"] = str(view_id)
            payload["aux_terminal_id"] = aux_terminal_id
            await ctx.bulk_writer.send_terminal_output(
                AgentMessage(
                    type="aux_terminal_output",
                    client_id=message.client_id,
                    window_id=message.window_id,
                    payload=payload,
                )
            )

        await ctx.aux_terminal.attach(aux_terminal_id, send_aux_output, view_id=view_id)
        await ctx.control_writer.send(
            AgentMessage(
                type="aux_terminal_attach_result",
                client_id=message.client_id,
                window_id=message.window_id,
                request_id=message.request_id,
                payload={"ok": True, "aux_terminal_id": aux_terminal_id, "view_id": str(view_id)},
            )
        )
        return False
    if message.type == "aux_terminal_detach":
        await ctx.aux_terminal.detach(
            _required_payload_string(message, "aux_terminal_id"),
            view_id=_view_id_for_message(message),
        )
        return False
    if message.type == "aux_terminal_kill":
        await ctx.aux_terminal.kill(_required_payload_string(message, "aux_terminal_id"))
        return False
    if message.type == "aux_terminal_input":
        raw_data = _required_payload_string(message, "data")
        await ctx.aux_terminal.send_input(
            _required_payload_string(message, "aux_terminal_id"),
            bytes.fromhex(raw_data),
            view_id=_view_id_for_message(message),
        )
        return False
    if message.type == "aux_terminal_resize":
        await ctx.aux_terminal.resize(
            _required_payload_string(message, "aux_terminal_id"),
            cols=int(message.payload["cols"]),
            rows=int(message.payload["rows"]),
            view_id=_view_id_for_message(message),
        )
    return False


async def _handle_terminal_message(
    ctx: AgentMessageHandlerContext,
    message: AgentMessage,
) -> bool:
    if message.type == "terminal_attach":
        await _handle_terminal_attach_message(ctx, message)
        return False
    if message.type == "terminal_detach":
        window_id = _message_window_id(message)
        view_id = _view_id_for_message(message)
        attached_window_id = ctx.terminal_view_window_ids.get(view_id, window_id)
        snapshot_task = ctx.attach_snapshot_tasks.pop(view_id, None)
        if snapshot_task is not None:
            snapshot_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await snapshot_task
        await ctx.terminal.detach(window_id, view_id=view_id)
        ctx.terminal_view_window_ids.pop(view_id, None)
        cleanup_call(ctx.stale_window_cleanup, "detach_view", attached_window_id)
        ctx.idle_supervisor.detach_view(view_id)
        return False
    if message.type == "terminal_input":
        payload = TerminalPayload.model_validate(message.payload)
        view_id = _view_id_for_message(message)
        await ctx.bulk_writer.prioritize_terminal_window(payload.window_id)
        await ctx.terminal.send_input(payload.window_id, payload.to_bytes(), view_id=view_id)
        return False
    if message.type == "terminal_input_direct":
        payload = TerminalPayload.model_validate(message.payload)
        await ctx.terminal.send_input_direct(payload.window_id, payload.to_bytes())
        return False
    if message.type == "terminal_resize":
        window_id = _message_window_id(message)
        view_id = _view_id_for_message(message)
        await ctx.terminal.resize(
            window_id,
            cols=int(message.payload["cols"]),
            rows=int(message.payload["rows"]),
            view_id=view_id,
        )
        return False
    if message.type == "terminal_capture":
        window_id = _message_window_id(message)
        view_id = _optional_payload_string(message, "view_id")
        history_lines = _optional_positive_int_payload(message, "history_lines")
        output = await ctx.terminal.capture_output_bytes(window_id, view_id=view_id, history_lines=history_lines)
        await ctx.control_writer.send(
            AgentMessage(
                type="terminal_capture_result",
                client_id=message.client_id,
                window_id=window_id,
                request_id=message.request_id,
                payload=TerminalPayload.from_bytes(window_id, output).model_dump(mode="json"),
            )
        )
        return False
    if message.type == "process_liveness":
        window_id = _message_window_id(message)
        active_processes = await active_non_shell_processes_for_runtime_window(
            ctx.runtime,
            remote_session_id=_required_payload_string(message, "remote_session_id"),
            remote_window_id=_required_payload_string(message, "remote_window_id"),
        )
        await ctx.control_writer.send(
            AgentMessage(
                type="process_liveness_result",
                client_id=message.client_id,
                window_id=window_id,
                request_id=message.request_id,
                payload={"active_processes": active_processes},
            )
        )
        return False
    if message.type == "terminal_select_window":
        await _handle_terminal_select_window_message(ctx, message)
    return False


async def _handle_terminal_attach_message(
    ctx: AgentMessageHandlerContext,
    message: AgentMessage,
) -> None:
    window_id = _message_window_id(message)
    view_id = _view_id_for_message(message)
    previous_window_id = ctx.terminal_view_window_ids.get(view_id)
    if previous_window_id is not None and previous_window_id != window_id:
        cleanup_call(ctx.stale_window_cleanup, "detach_view", previous_window_id)
    ctx.terminal_view_window_ids[view_id] = window_id
    ctx.idle_supervisor.attach_view(view_id, window_id)
    current_window_id = window_id
    first_output_seen = asyncio.Event()
    snapshot_pending = True

    def consume_attach_snapshot() -> bool:
        nonlocal snapshot_pending
        if not snapshot_pending:
            return False
        snapshot_pending = False
        return True

    async def send_selected_window(selected_window_id: UUID) -> None:
        nonlocal current_window_id
        previous_window_id = ctx.terminal_view_window_ids.get(view_id)
        if previous_window_id != selected_window_id:
            cleanup_call(ctx.stale_window_cleanup, "detach_view", previous_window_id)
        current_window_id = selected_window_id
        ctx.terminal_view_window_ids[view_id] = selected_window_id
        ctx.idle_supervisor.attach_view(view_id, selected_window_id)
        cleanup_call(ctx.stale_window_cleanup, "touch_window", selected_window_id)
        cleanup_call(
            ctx.stale_window_cleanup,
            "attach_view",
            selected_window_id,
            when=previous_window_id != selected_window_id,
        )
        await _send_terminal_selection(ctx.control_writer, message.client_id, selected_window_id, view_id=view_id)

    async def send_active_terminal_output(data: bytes) -> None:
        first_output_seen.set()
        await _send_terminal_output(
            ctx.bulk_writer,
            message.client_id,
            ctx.terminal_view_window_ids.get(view_id, current_window_id),
            data,
            view_id=view_id,
            is_snapshot=consume_attach_snapshot(),
        )

    try:
        availability = await ensure_runtime_window_available(
            ctx.runtime,
            ctx.terminal,
            ctx.idle_supervisor,
            window_id,
            remote_session_id=_required_payload_string(message, "remote_session_id"),
            remote_window_id=_required_payload_string(message, "remote_window_id"),
            cwd=_optional_payload_string(message, "cwd"),
            shell_command=_optional_payload_string(message, "shell_command"),
            allow_missing_window_recreate=_optional_payload_bool(
                message,
                "allow_missing_window_recreate",
            ),
        )
    except Exception:
        ctx.terminal_view_window_ids.pop(view_id, None)
        ctx.idle_supervisor.detach_view(view_id)
        raise
    runtime_window = availability.window
    cleanup_register(ctx.stale_window_cleanup, window_id, runtime_window)
    cleanup_mark_terminal_viewed(ctx.stale_window_cleanup, message, window_id)
    if previous_window_id != window_id:
        cleanup_call(ctx.stale_window_cleanup, "attach_view", window_id)
    await resume_policy.resume_window_from_decision(
        ctx.idle_supervisor,
        window_id,
        availability.resume_decision,
    )
    await ctx.terminal.attach_with_selection(
        window_id,
        send_active_terminal_output,
        selection_sender=send_selected_window,
        view_id=view_id,
    )
    existing_snapshot_task = ctx.attach_snapshot_tasks.pop(view_id, None)
    if existing_snapshot_task is not None:
        existing_snapshot_task.cancel()
    ctx.attach_snapshot_tasks[view_id] = asyncio.create_task(
        _expire_attach_snapshot_if_silent(first_output_seen, consume_attach_snapshot)
    )
    await _send_terminal_attach_result(
        ctx.control_writer,
        message.client_id,
        window_id,
        request_id=message.request_id,
        runtime_window=runtime_window,
    )


async def _handle_terminal_select_window_message(
    ctx: AgentMessageHandlerContext,
    message: AgentMessage,
) -> None:
    window_id = _message_window_id(message)
    view_id = _view_id_for_message(message)
    availability = await ensure_runtime_window_available(
        ctx.runtime,
        ctx.terminal,
        ctx.idle_supervisor,
        window_id,
        remote_session_id=_required_payload_string(message, "remote_session_id"),
        remote_window_id=_required_payload_string(message, "remote_window_id"),
        cwd=_optional_payload_string(message, "cwd"),
        shell_command=_optional_payload_string(message, "shell_command"),
        allow_missing_window_recreate=_optional_payload_bool(
            message,
            "allow_missing_window_recreate",
        ),
    )
    runtime_window = availability.window
    previous_window_id = ctx.terminal_view_window_ids.get(view_id)
    if previous_window_id != window_id:
        cleanup_call(ctx.stale_window_cleanup, "detach_view", previous_window_id)
    ctx.terminal_view_window_ids[view_id] = window_id
    ctx.idle_supervisor.attach_view(view_id, window_id)
    cleanup_register(ctx.stale_window_cleanup, window_id, runtime_window)
    cleanup_mark_terminal_viewed(ctx.stale_window_cleanup, message, window_id)
    cleanup_call(ctx.stale_window_cleanup, "attach_view", window_id, when=previous_window_id != window_id)
    await resume_policy.resume_window_from_decision(
        ctx.idle_supervisor,
        window_id,
        availability.resume_decision,
    )
    await ctx.terminal.select_window(window_id, view_id=view_id)
    await _send_terminal_attach_result(
        ctx.control_writer,
        message.client_id,
        window_id,
        request_id=message.request_id,
        runtime_window=runtime_window,
    )
