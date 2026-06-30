from __future__ import annotations

# ruff: noqa: F401,F821

import asyncio
import contextlib
import inspect
import logging
import socket
from dataclasses import asdict
from uuid import UUID

import websockets

from app.agent_plugins import list_agent_client_descriptors
from app.client_agent.agent_commands import agent_provider_from_command
from app.client_agent.agent_tool_watchers import UnifiedAgentToolWatcher
from app.client_agent.agent_idle import AgentIdleSupervisor
from app.contexts.agent_profiles.infrastructure import builtin_profiles
from app.services import agent_config as agent_config_service
from app.services import agent_profiles as agent_profile_service
from app.services.terminal_clone import clone_resume_command, clone_window_agent_homes
from app.client_agent.git_worktree import handle_git_worktree_request
from app.client_agent.config import ClientAgentConfig
from app.client_agent.aux_terminal import ClientAuxTerminalManager
from app.client_agent.outbound import BulkUploadWriter, ControlMessageWriter
from app.client_agent.otel_metrics import ClaudeCodeOtelMetricsReceiver
from app.client_agent.runner.cleanup_runtime import _await_cleanup_step, _run_cleanup_step
import app.client_agent.runner.resume_policy as resume_policy
from app.client_agent.runner.reconnect_policy import (
    _is_expected_reconnect_exception,
    _reconnect_sleep_seconds,
)
from app.client_agent.runner.supervisor import ConnectionSupervisor
from app.client_agent.runtime_window import ClientRuntimeWindow
from app.client_agent.stale_window_cleanup import ClientStaleWindowCleanup
from app.client_agent.terminal import ClientTerminalMultiplexer
from app.client_agent.tmux_runtime import ClientTmuxRuntime
from app.client_agent.updater import start_self_update
from app.services.runtime.protocol import (
    AgentMessage,
    TerminalPayload,
    decode_agent_message,
    encode_agent_message,
)
from app.version import __version__

HEARTBEAT_INTERVAL_SECONDS = 10
GIT_WORKTREE_REQUEST_CONCURRENCY = 1
FILE_READ_DEFAULT_MAX_BYTES = 2 * 1024 * 1024
FILE_WRITE_DEFAULT_MAX_BYTES = 20 * 1024 * 1024
logger = logging.getLogger(__name__)


def _agent_clients_payload() -> dict[str, object]:
    return {
        "agent_clients": [
            {
                "id": descriptor.id,
                "provider_id": descriptor.provider_id,
                "label": descriptor.label,
                "aliases": list(descriptor.aliases),
                "default_command": descriptor.default_command,
                "command_names": list(descriptor.command_names),
                "capabilities": asdict(descriptor.capabilities),
            }
            for descriptor in list_agent_client_descriptors()
        ]
    }


def _restore_system_config_files_from_message(message: AgentMessage) -> None:
    payload = message.payload.get("system_config_files")
    if payload is not None:
        agent_config_service.restore_system_agent_config_files_payload(payload)


def _providers_for_shell_command(command: str | None) -> frozenset[str] | None:
    provider = agent_provider_from_command(command)
    return frozenset({provider}) if provider is not None else None


def _view_id_for_message(message: AgentMessage) -> UUID:
    value = message.payload.get("view_id")
    return UUID(str(value)) if value is not None else _message_window_id(message)


async def run_client_agent(config: ClientAgentConfig) -> None:
    reconnect_delay = config.reconnect_initial_delay_seconds
    max_reconnect_delay = config.reconnect_max_delay_seconds

    while True:
        try:
            shutdown_requested = await _run_client_agent_once(config)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            expected_reconnect = _is_expected_reconnect_exception(exc)
            log = logger.info if expected_reconnect else logger.warning
            log(
                "client-agent connection failed; reconnecting",
                extra={
                    "client_id": str(config.client_id),
                    "websocket_url": config.websocket_url,
                    "exception_type": type(exc).__name__,
                    "reconnect_delay_seconds": reconnect_delay,
                },
                exc_info=not expected_reconnect,
            )
            await asyncio.sleep(_reconnect_sleep_seconds(reconnect_delay))
            reconnect_delay = min(max_reconnect_delay, reconnect_delay * 2)
            continue

        if shutdown_requested:
            return
        reconnect_delay = config.reconnect_initial_delay_seconds


async def _run_client_agent_once(config: ClientAgentConfig) -> bool:
    headers = {
        "Authorization": f"Bearer {config.token}",
        "X-Client-Id": str(config.client_id),
    }

    header_argument = "extra_headers"
    if "additional_headers" in inspect.signature(websockets.connect).parameters:
        header_argument = "additional_headers"

    logger.info(
        "client-agent connecting",
        extra={"client_id": str(config.client_id), "websocket_url": config.websocket_url},
    )
    connect_kwargs = _websocket_connect_kwargs(config, headers, header_argument)
    async with websockets.connect(config.websocket_url, **connect_kwargs) as control_websocket:
        await control_websocket.send(
            encode_agent_message(
                AgentMessage(
                    type="hello",
                    client_id=config.client_id,
                    payload={
                        "hostname": socket.gethostname(),
                        "name": config.name,
                        "version": __version__,
                    },
                )
            )
        )
        hello_ack = decode_agent_message(await control_websocket.recv())
        logger.info(
            "client-agent hello acknowledged",
            extra={"client_id": str(config.client_id), "message_type": hello_ack.type},
        )

        logger.info(
            "client-agent bulk websocket connecting",
            extra={"client_id": str(config.client_id), "websocket_url": config.bulk_websocket_url},
        )
        async with websockets.connect(config.bulk_websocket_url, **connect_kwargs) as bulk_websocket:
            await bulk_websocket.send(
                encode_agent_message(
                    AgentMessage(
                        type="bulk_hello",
                        client_id=config.client_id,
                        payload={"version": __version__},
                    )
                )
            )
            bulk_hello_ack = decode_agent_message(await bulk_websocket.recv())
            if bulk_hello_ack.type != "bulk_hello_ack":
                raise RuntimeError(f"unexpected bulk websocket ack: {bulk_hello_ack.type}")
            logger.info(
                "client-agent bulk hello acknowledged",
                extra={"client_id": str(config.client_id), "message_type": bulk_hello_ack.type},
            )

            control_writer = ControlMessageWriter(control_websocket.send)
            bulk_writer = BulkUploadWriter(bulk_websocket.send)
            control_writer.start()
            bulk_writer.start()
            supervisor = ConnectionSupervisor()
            if control_writer.task is not None:
                supervisor.add_task("control_writer", control_writer.task)
            if bulk_writer.task is not None:
                supervisor.add_task("bulk_writer", bulk_writer.task)
            bulk_receive_task = start_bulk_receive_task(bulk_websocket, config.client_id)
            otel_metrics_receiver = ClaudeCodeOtelMetricsReceiver(
                bulk_writer.send_ai_event,
                client_id=config.client_id,
            )
            await otel_metrics_receiver.start()
            terminal: ClientTerminalMultiplexer | None = None
            aux_terminal: ClientAuxTerminalManager | None = None
            agent_tool_watcher: UnifiedAgentToolWatcher | None = None
            stale_window_cleanup: ClientStaleWindowCleanup | None = None
            stale_window_cleanup_task: asyncio.Task[None] | None = None
            attach_snapshot_tasks: dict[UUID, asyncio.Task[None]] = {}
            create_window_tasks: set[asyncio.Task[None]] = set()
            git_worktree_tasks: set[asyncio.Task[None]] = set()
            git_worktree_semaphore = asyncio.Semaphore(GIT_WORKTREE_REQUEST_CONCURRENCY)
            terminal_view_window_ids: dict[UUID, UUID] = {}
            heartbeat_task: asyncio.Task[None] | None = None
            try:
                runtime = ClientTmuxRuntime(
                    client_id=config.client_id,
                    server_url=config.server_url,
                    pool_session=config.tmux_pool_session,
                    default_shell=config.default_shell,
                    agent_otel_metrics_endpoint=otel_metrics_receiver.endpoint,
                )
                terminal = ClientTerminalMultiplexer()
                aux_terminal = ClientAuxTerminalManager(default_shell=config.default_shell)
                idle_supervisor = AgentIdleSupervisor(terminal=terminal, runtime=runtime)
                stale_window_cleanup = ClientStaleWindowCleanup(
                    cleanup_seconds=config.tmux_window_inactive_cleanup_seconds,
                    kill_window=runtime.kill_stale_window,
                )
                agent_tool_watcher = UnifiedAgentToolWatcher(
                    bulk_writer.send_ai_event,
                    config.client_id,
                    send_presence=bulk_writer.send_ai_event,
                    terminal=terminal,
                    runtime=runtime,
                    idle_supervisor=idle_supervisor,
                    stale_window_cleanup=stale_window_cleanup,
                )
                agent_tool_watcher.start()
                stale_window_cleanup_task = stale_window_cleanup.start()
                inventory = await runtime.list_windows()
                await _register_inventory_windows(runtime, terminal, stale_window_cleanup, inventory)
                for window in inventory:
                    if _should_restore_agent_tool_watcher(window):
                        agent_tool_watcher.watch_window(
                            window.local_window_id,
                            window.cwd,
                        )
                        idle_supervisor.register_window(window.local_window_id, window.cwd)
                await _send_inventory(control_writer, config.client_id, inventory)
                await control_writer.drain()
                logger.info(
                    "client-agent inventory sent",
                    extra={"client_id": str(config.client_id), "window_count": len(inventory)},
                )

                heartbeat_task = asyncio.create_task(_heartbeat_loop(control_writer, config.client_id))
                supervisor.add_task("heartbeat", heartbeat_task)
                while True:
                    message = await supervisor.wait_with(
                        receive_control_message(control_websocket, bulk_receive_task)
                    )
                    try:
                        if await _handle_agent_message(
                            control_writer,
                            bulk_writer,
                            config,
                            runtime,
                            terminal,
                            idle_supervisor,
                            agent_tool_watcher,
                            aux_terminal,
                            attach_snapshot_tasks,
                            git_worktree_tasks,
                            git_worktree_semaphore,
                            terminal_view_window_ids,
                            message,
                            create_window_tasks=create_window_tasks,
                            stale_window_cleanup=stale_window_cleanup,
                        ):
                            return True
                    except Exception as exc:
                        view_id = None
                        with contextlib.suppress(Exception):
                            view_id = _view_id_for_message(message)
                        await _send_terminal_error(
                            control_writer,
                            message.client_id,
                            message.window_id,
                            request_id=message.request_id,
                            message=str(exc),
                            view_id=view_id,
                        )
            finally:
                supervisor.cancel_all()
                if heartbeat_task is not None:
                    heartbeat_task.cancel()
                bulk_receive_task.cancel()
                pending_create_window_tasks = tuple(create_window_tasks)
                pending_git_worktree_tasks = tuple(git_worktree_tasks)
                for task in attach_snapshot_tasks.values():
                    task.cancel()
                for task in pending_create_window_tasks:
                    task.cancel()
                for task in pending_git_worktree_tasks:
                    task.cancel()
                await _run_cleanup_step(
                    "control_writer.close",
                    control_writer.close(),
                    client_id=config.client_id,
                )
                await _run_cleanup_step(
                    "bulk_writer.close",
                    bulk_writer.close(),
                    client_id=config.client_id,
                )
                if heartbeat_task is not None:
                    await _await_cleanup_step(
                        "heartbeat_task",
                        heartbeat_task,
                        client_id=config.client_id,
                    )
                await _await_cleanup_step(
                    "bulk_receive_task",
                    bulk_receive_task,
                    client_id=config.client_id,
                )
                for task in attach_snapshot_tasks.values():
                    await _await_cleanup_step(
                        "attach_snapshot_task",
                        task,
                        client_id=config.client_id,
                    )
                for task in pending_create_window_tasks:
                    await _await_cleanup_step(
                        "create_window_task",
                        task,
                        client_id=config.client_id,
                    )
                for task in pending_git_worktree_tasks:
                    await _await_cleanup_step(
                        "git_worktree_task",
                        task,
                        client_id=config.client_id,
                    )
                if agent_tool_watcher is not None:
                    await _run_cleanup_step(
                        "agent_tool_watcher.close",
                        agent_tool_watcher.close(),
                        client_id=config.client_id,
                    )
                await _run_cleanup_step(
                    "otel_metrics_receiver.close",
                    otel_metrics_receiver.close(),
                    client_id=config.client_id,
                )
                if stale_window_cleanup is not None:
                    stale_window_cleanup.close()
                if stale_window_cleanup_task is not None:
                    await _await_cleanup_step(
                        "stale_window_cleanup",
                        stale_window_cleanup_task,
                        client_id=config.client_id,
                    )
                if terminal is not None:
                    await _run_cleanup_step(
                        "terminal.close",
                        terminal.close(),
                        client_id=config.client_id,
                    )
                if aux_terminal is not None:
                    await _run_cleanup_step(
                        "aux_terminal.close",
                        aux_terminal.close(),
                        client_id=config.client_id,
                    )

    return False


def _should_restore_agent_tool_watcher(window: ClientRuntimeWindow) -> bool:
    return window.local_window_id is not None and window.managed_agent_tools


async def _register_inventory_windows(
    runtime: ClientTmuxRuntime,
    terminal: ClientTerminalMultiplexer,
    stale_window_cleanup: ClientStaleWindowCleanup,
    windows: list[ClientRuntimeWindow],
) -> None:
    for window in windows:
        if window.local_window_id is not None:
            terminal.register_window(
                window.local_window_id,
                window.remote_session_id,
                window.remote_window_id,
            )
            stale_window_cleanup.register_window(
                window.local_window_id,
                window,
                activity_at=await runtime.window_activity_timestamp(
                    window.remote_window_id,
                    remote_session_id=window.remote_session_id,
                ),
            )


async def _send_inventory(
    writer: ControlMessageWriter,
    client_id: UUID,
    windows: list[ClientRuntimeWindow],
) -> None:
    await writer.send(
        AgentMessage(
            type="inventory",
            client_id=client_id,
            payload={"windows": [asdict(window) for window in windows]},
        )
    )


async def _heartbeat_loop(writer: ControlMessageWriter, client_id: UUID) -> None:
    while True:
        await writer.send(
            AgentMessage(
                type="heartbeat",
                client_id=client_id,
                payload={"version": __version__},
            )
        )
        await asyncio.sleep(HEARTBEAT_INTERVAL_SECONDS)


def _agent_config_selection_from_payload(value: object) -> agent_config_service.AgentConfigSelection | None:
    if not isinstance(value, dict):
        return None
    agent = value.get("agent")
    if not isinstance(agent, str):
        return None
    sections: list[agent_config_service.AgentConfigSectionSelection] = []
    raw_sections = value.get("sections")
    if isinstance(raw_sections, list):
        for raw_section in raw_sections:
            if not isinstance(raw_section, dict):
                continue
            section_id = raw_section.get("id")
            if section_id not in {"skills", "plugins", "hooks", "mcp"}:
                continue
            items: list[agent_config_service.AgentConfigItemSelection] = []
            raw_items = raw_section.get("items")
            if isinstance(raw_items, list):
                for raw_item in raw_items:
                    if not isinstance(raw_item, dict):
                        continue
                    item_id = raw_item.get("id")
                    enabled = raw_item.get("enabled")
                    if isinstance(item_id, str) and item_id and isinstance(enabled, bool):
                        items.append(agent_config_service.AgentConfigItemSelection(item_id, enabled))
            sections.append(agent_config_service.AgentConfigSectionSelection(section_id, items))
    return agent_config_service.AgentConfigSelection(
        agent=agent_config_service.normalize_agent_kind(agent),
        sections=sections,
    )
