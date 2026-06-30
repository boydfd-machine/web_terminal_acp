import logging
import os
from datetime import UTC, datetime
from hashlib import sha256
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ClientRuntime, LOCAL_CLIENT_ID, GitWorktreeRun
from app.contexts.terminal_runtime.infrastructure.git_worktree_repository import (
    create_git_worktree_run,
    get_git_worktree_run,
    get_window_git_binding,
    upsert_window_git_binding,
)
from app.contexts.terminal_runtime.application.git_worktree_client import request_git_worktree_action
from app.contexts.terminal_runtime.application.git_worktree_coordinator.snapshot_refresh import (
    _is_local_project_worktree_path as _snapshot_is_local_project_worktree_path,
    refresh_run_snapshot,
)
from app.contexts.terminal_runtime.application.git_worktree_coordinator.refresh_lock import (
    try_acquire_window_refresh_lock,
)
from app.contexts.terminal_runtime.application.git_worktree_coordinator.refresh_queries import (
    runs_for_refresh_query as _runs_for_refresh_query,
)
from app.contexts.terminal_runtime.domain.git_worktree_ops import (
    command_can_change_git_merge_state,
    parse_git_worktree_add_path,
)
from app.contexts.terminal_runtime.application.client_connections import ClientConnectionRegistry
from app.contexts.activity.application.window_runtime_tags import agent_from_command

logger = logging.getLogger(__name__)
_WORKTREE_TRACKING_SEQUENCE_PREFIX = "worktree:"


async def local_git_worktree_action(action: str, **payload: Any) -> dict[str, Any] | None:
    if action == "detect":
        path = payload.get("path")
        if not isinstance(path, str) or not path.strip():
            return {"ok": False, "error": "path is required"}
        from app.client_agent.git_worktree import detect_git_context

        return {"ok": True, "context": await detect_git_context(path)}

    if action == "snapshot":
        worktree_root = payload.get("worktree_root")
        if not isinstance(worktree_root, str) or not worktree_root.strip():
            return {"ok": False, "error": "worktree_root is required"}
        from app.client_agent.git_worktree import capture_worktree_snapshot

        base_head = payload.get("base_head") if isinstance(payload.get("base_head"), str) else None
        main_repo_root = payload.get("main_repo_root") if isinstance(payload.get("main_repo_root"), str) else None
        known_head_sha = payload.get("known_head_sha") if isinstance(payload.get("known_head_sha"), str) else None
        known_branch = payload.get("known_branch") if isinstance(payload.get("known_branch"), str) else None
        return {
            "ok": True,
            "snapshot": await capture_worktree_snapshot(
                worktree_root,
                base_head=base_head,
                main_repo_root=main_repo_root,
                known_head_sha=known_head_sha,
                known_branch=known_branch,
            ),
        }

    return None


async def _git_worktree_action(
    registry: ClientConnectionRegistry | None,
    client_id: UUID,
    client_runtime: ClientRuntime | None = None,
    *,
    action: str,
    **payload: Any,
) -> dict[str, Any] | None:
    result = await request_git_worktree_action(registry, client_id, action=action, **payload)
    if result is not None:
        return result
    if client_id != LOCAL_CLIENT_ID and client_runtime is not ClientRuntime.local:
        return None
    return await local_git_worktree_action(action, **payload)


def _tracking_sequence(worktree_root: str) -> str:
    digest = sha256(os.path.realpath(worktree_root).encode("utf-8")).hexdigest()[:16]
    return f"{_WORKTREE_TRACKING_SEQUENCE_PREFIX}{digest}"


def _is_local_project_worktree_path(worktree_root: str, main_repo_root: str | None) -> bool:
    return _snapshot_is_local_project_worktree_path(worktree_root, main_repo_root)


def command_needs_git_worktree_tracking(command: dict[str, Any]) -> bool:
    raw_command = command.get("command")
    if not isinstance(raw_command, str):
        return False
    phase = command.get("phase")
    cwd = command.get("cwd") if isinstance(command.get("cwd"), str) else None
    if phase in {"started", "finished"} and parse_git_worktree_add_path(raw_command, cwd):
        return True
    if phase in {"started", "finished"} and command_can_change_git_merge_state(raw_command):
        return True
    return phase in {"started", "finished"} and agent_from_command(raw_command) is not None


def commands_need_git_worktree_tracking(commands: list[dict[str, Any]]) -> bool:
    return any(command_needs_git_worktree_tracking(command) for command in commands)


def git_worktree_agent_run_sequences(commands: list[dict[str, Any]]) -> set[str]:
    sequences: set[str] = set()
    for command in commands:
        raw_command = command.get("command")
        if not isinstance(raw_command, str):
            continue
        if command.get("phase") not in {"started", "finished"} or agent_from_command(raw_command) is None:
            continue
        sequence = command.get("sequence")
        if sequence is not None:
            sequences.add(str(sequence))
    return sequences


async def bind_worktree_for_window(
    session: AsyncSession,
    *,
    client_id: UUID,
    window_id: UUID,
    worktree_root: str,
    main_repo_root: str | None,
    branch: str | None,
    discovery_method: str,
    registry: ClientConnectionRegistry | None,
    client_runtime: ClientRuntime | None = None,
) -> bool:
    normalized_root = os.path.realpath(worktree_root)
    main_root = main_repo_root
    if not main_root:
        detect = await _git_worktree_action(
            registry,
            client_id,
            client_runtime,
            action="detect",
            path=normalized_root,
        )
        if detect and detect.get("ok"):
            context = detect.get("context") or {}
            main_root = context.get("main_repo_root")
            branch = branch or context.get("branch")
        if not main_root:
            return False

    binding = await upsert_window_git_binding(
        session,
        client_id=client_id,
        window_id=window_id,
        main_repo_root=os.path.realpath(main_root),
        worktree_root=normalized_root,
        branch=branch,
        discovery_method=discovery_method,
    )
    await _ensure_tracking_run(session, binding, client_id)
    return True


async def process_worktree_registration(
    session: AsyncSession,
    *,
    client_id: UUID,
    window_id: UUID,
    marker: dict[str, Any],
    registry: ClientConnectionRegistry | None,
    client_runtime: ClientRuntime | None = None,
) -> None:
    worktree_root = marker.get("worktree_root")
    if not isinstance(worktree_root, str) or not worktree_root.strip():
        return
    branch = marker.get("branch") if isinstance(marker.get("branch"), str) else None
    main_repo_root = marker.get("main_repo_root") if isinstance(marker.get("main_repo_root"), str) else None
    await bind_worktree_for_window(
        session,
        client_id=client_id,
        window_id=window_id,
        worktree_root=worktree_root,
        main_repo_root=main_repo_root,
        branch=branch,
        discovery_method="osc",
        registry=registry,
        client_runtime=client_runtime,
    )
    await _complete_awaiting_runs_after_bind(session, client_id, window_id, registry, client_runtime)


async def process_git_worktree_snapshot_refresh(
    session: AsyncSession,
    *,
    client_id: UUID,
    window_id: UUID,
    registry: ClientConnectionRegistry | None,
    client_runtime: ClientRuntime | None = None,
    command_sequences: set[str] | None = None,
    include_tracking_run: bool = True,
    include_unresolved_runs: bool = False,
) -> bool:
    binding = await get_window_git_binding(session, window_id)
    if binding is None:
        return False
    if not await try_acquire_window_refresh_lock(session, window_id):
        logger.debug(
            "skipping duplicate git worktree snapshot refresh",
            extra={"client_id": str(client_id), "window_id": str(window_id)},
        )
        return False
    changed = False

    _tracking_run, tracking_changed = await _ensure_tracking_run(session, binding, client_id)
    changed = tracking_changed

    runs = list(
        await session.scalars(
            _runs_for_refresh_query(
                window_id,
                command_sequences,
                include_tracking_run,
                include_unresolved_runs,
            )
        )
    )
    for run in runs:
        snapshot_changed = await refresh_run_snapshot(
            session,
            run,
            client_id,
            registry,
            client_runtime,
            git_worktree_action=_git_worktree_action,
            local_git_worktree_action=local_git_worktree_action,
        )
        changed = snapshot_changed or changed
    return changed


async def process_terminal_commands_for_git(
    session: AsyncSession,
    *,
    client_id: UUID,
    window_id: UUID,
    commands: list[dict[str, Any]],
    registry: ClientConnectionRegistry | None,
    client_runtime: ClientRuntime | None = None,
) -> None:
    for command in commands:
        phase = command.get("phase")
        raw_command = command.get("command")
        cwd = command.get("cwd") if isinstance(command.get("cwd"), str) else None
        sequence = command.get("sequence")
        if sequence is None:
            continue
        sequence_str = str(sequence)

        if phase in {"started", "finished"} and isinstance(raw_command, str):
            worktree_path = parse_git_worktree_add_path(raw_command, cwd)
            if worktree_path:
                if phase == "finished" and _command_finished_unsuccessfully(command):
                    continue
                main_repo_root = None
                if phase == "finished" and cwd:
                    main_repo_root = await _main_repo_root_from_path(
                        registry,
                        client_id,
                        client_runtime,
                        path=cwd,
                    )
                await bind_worktree_for_window(
                    session,
                    client_id=client_id,
                    window_id=window_id,
                    worktree_root=worktree_path,
                    main_repo_root=main_repo_root,
                    branch=None,
                    discovery_method="command",
                    registry=registry,
                    client_runtime=client_runtime,
                )
                await _complete_awaiting_runs_after_bind(session, client_id, window_id, registry, client_runtime)
                continue

        if phase == "started" and isinstance(raw_command, str):
            agent = agent_from_command(raw_command)

            if agent is None:
                continue
            existing = await get_git_worktree_run(
                session,
                window_id,
                sequence_str,
                include_payloads=False,
            )
            if existing is None:
                await create_git_worktree_run(
                    session,
                    client_id=client_id,
                    window_id=window_id,
                    command_sequence=sequence_str,
                    agent_provider=agent,
                )

            if cwd:
                await _try_bind_from_path(
                    session,
                    client_id=client_id,
                    window_id=window_id,
                    path=cwd,
                    discovery_method="cwd",
                    registry=registry,
                    client_runtime=client_runtime,
                )
            continue

        if phase == "finished" and isinstance(raw_command, str):
            agent = agent_from_command(raw_command)
            if agent is None:
                continue
            await _finish_agent_run(
                session,
                client_id=client_id,
                window_id=window_id,
                sequence_str=sequence_str,
                registry=registry,
                client_runtime=client_runtime,
            )


def _command_finished_unsuccessfully(command: dict[str, Any]) -> bool:
    exit_status = command.get("exit_status")
    if exit_status in (None, ""):
        return False
    try:
        return int(exit_status) != 0
    except (TypeError, ValueError):
        return str(exit_status) != "0"


async def _finish_agent_run(
    session: AsyncSession,
    *,
    client_id: UUID,
    window_id: UUID,
    sequence_str: str,
    registry: ClientConnectionRegistry | None,
    client_runtime: ClientRuntime | None = None,
) -> None:
    run = await get_git_worktree_run(session, window_id, sequence_str, include_payloads=False)
    if run is None:
        return

    binding = await get_window_git_binding(session, window_id)
    if binding is None:
        run.status = "no_worktree"
        run.ended_at = datetime.now(UTC)
        await session.flush()
        return

    if run.status == "awaiting_worktree":
        await _bind_run_to_worktree(session, run, binding)

    if not run.worktree_root:
        run.worktree_root = binding.worktree_root
        run.main_repo_root = binding.main_repo_root

    run.status = "completed"
    run.ended_at = datetime.now(UTC)
    await session.flush()


async def _main_repo_root_from_path(
    registry: ClientConnectionRegistry | None,
    client_id: UUID,
    client_runtime: ClientRuntime | None,
    *,
    path: str,
) -> str | None:
    detect = await _git_worktree_action(registry, client_id, client_runtime, action="detect", path=path)
    if not detect or not detect.get("ok"):
        return None
    context = detect.get("context") or {}
    if not context.get("is_git"):
        return None
    main_root = context.get("main_repo_root") or context.get("worktree_root")
    return main_root if isinstance(main_root, str) and main_root.strip() else None


async def _try_bind_from_path(
    session: AsyncSession,
    *,
    client_id: UUID,
    window_id: UUID,
    path: str,
    discovery_method: str,
    registry: ClientConnectionRegistry | None,
    client_runtime: ClientRuntime | None = None,
) -> None:
    detect = await _git_worktree_action(registry, client_id, client_runtime, action="detect", path=path)
    if not detect or not detect.get("ok"):
        return
    context = detect.get("context") or {}
    if not context.get("is_linked_worktree"):
        return
    worktree_root = context.get("worktree_root")
    if not isinstance(worktree_root, str):
        return
    await bind_worktree_for_window(
        session,
        client_id=client_id,
        window_id=window_id,
        worktree_root=worktree_root,
        main_repo_root=context.get("main_repo_root"),
        branch=context.get("branch") if isinstance(context.get("branch"), str) else None,
        discovery_method=discovery_method,
        registry=registry,
        client_runtime=client_runtime,
    )
    await _complete_awaiting_runs_after_bind(session, client_id, window_id, registry, client_runtime)


async def _complete_awaiting_runs_after_bind(
    session: AsyncSession,
    client_id: UUID,
    window_id: UUID,
    registry: ClientConnectionRegistry | None,
    client_runtime: ClientRuntime | None = None,
) -> None:
    binding = await get_window_git_binding(session, window_id)
    if binding is None:
        return

    runs = list(
        await session.scalars(
            select(GitWorktreeRun).where(
                GitWorktreeRun.virtual_window_id == window_id,
                GitWorktreeRun.status == "awaiting_worktree",
            )
        )
    )
    for run in runs:
        await _bind_run_to_worktree(session, run, binding)


async def _ensure_tracking_run(
    session: AsyncSession,
    binding: Any,
    client_id: UUID,
) -> tuple[Any, bool]:
    sequence = _tracking_sequence(binding.worktree_root)
    run = await get_git_worktree_run(
        session,
        binding.virtual_window_id,
        sequence,
        include_payloads=False,
    )
    changed = False
    if run is None:
        run = await create_git_worktree_run(
            session,
            client_id=client_id,
            window_id=binding.virtual_window_id,
            command_sequence=sequence,
            agent_provider=None,
            status="bound",
        )
        changed = True

    binding_changed = await _bind_run_to_worktree(session, run, binding)
    return run, changed or binding_changed


async def _bind_run_to_worktree(session: AsyncSession, run: Any, binding: Any) -> bool:
    changed = False
    if run.status in {"awaiting_worktree", "no_worktree"}:
        run.status = "bound"
        changed = True
    if run.main_repo_root != binding.main_repo_root:
        run.main_repo_root = binding.main_repo_root
        changed = True
    if run.worktree_root != binding.worktree_root:
        run.worktree_root = binding.worktree_root
        changed = True
    if run.discovery_method != binding.discovery_method:
        run.discovery_method = binding.discovery_method
        changed = True
    if changed:
        await session.flush()
    return changed
