from __future__ import annotations

import logging
import os
from datetime import UTC, datetime
from hashlib import sha256
from typing import Any
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ClientRuntime, LOCAL_CLIENT_ID, GitWorktreeRun
from app.repositories.git_worktree import (
    create_git_worktree_run,
    get_git_worktree_run,
    get_window_git_binding,
    upsert_window_git_binding,
    window_has_pending_commit,
)
from app.services.git_worktree_client import request_git_worktree_action
from app.services.git_worktree_ops import (
    compute_session_diff,
    parse_git_worktree_add_path,
    pending_commit_from_diff,
    pending_commit_from_live_snapshot,
)
from app.services.runtime.client_connections import ClientConnectionRegistry
from app.services.window_runtime_tags import agent_from_command

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
        return {"ok": True, "snapshot": await capture_worktree_snapshot(worktree_root, base_head=base_head)}

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


def _is_tracking_run(run: Any) -> bool:
    return str(getattr(run, "command_sequence", "")).startswith(_WORKTREE_TRACKING_SEQUENCE_PREFIX)


def command_needs_git_worktree_tracking(command: dict[str, Any]) -> bool:
    raw_command = command.get("command")
    if not isinstance(raw_command, str):
        return False
    phase = command.get("phase")
    cwd = command.get("cwd") if isinstance(command.get("cwd"), str) else None
    if phase in {"started", "finished"} and parse_git_worktree_add_path(raw_command, cwd):
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
) -> bool:
    binding = await get_window_git_binding(session, window_id)
    if binding is None:
        return False
    changed = False

    tracking_run = await _ensure_tracking_run(session, binding, client_id)
    changed = tracking_run is not None

    runs = list(
        await session.scalars(
            _runs_for_refresh_query(window_id, command_sequences, include_tracking_run)
        )
    )
    for run in runs:
        await _refresh_run_snapshot(session, run, client_id, registry, client_runtime)
        changed = True
    return changed


def _runs_for_refresh_query(
    window_id: UUID,
    command_sequences: set[str] | None,
    include_tracking_run: bool,
):
    query = select(GitWorktreeRun).where(
        GitWorktreeRun.virtual_window_id == window_id,
        GitWorktreeRun.worktree_root.is_not(None),
    )
    if command_sequences and include_tracking_run:
        return query.where(
            (
                GitWorktreeRun.command_sequence.in_(command_sequences)
                | GitWorktreeRun.command_sequence.like(f"{_WORKTREE_TRACKING_SEQUENCE_PREFIX}%")
            )
        )
    if command_sequences:
        return query.where(
            GitWorktreeRun.command_sequence.in_(command_sequences),
        )
    return query.where(
        GitWorktreeRun.command_sequence.like(f"{_WORKTREE_TRACKING_SEQUENCE_PREFIX}%")
    )


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
            existing = await get_git_worktree_run(session, window_id, sequence_str)
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
) -> Any | None:
    sequence = _tracking_sequence(binding.worktree_root)
    run = await get_git_worktree_run(session, binding.virtual_window_id, sequence)
    if run is None:
        run = await create_git_worktree_run(
            session,
            client_id=client_id,
            window_id=binding.virtual_window_id,
            command_sequence=sequence,
            agent_provider=None,
            status="bound",
        )

    await _bind_run_to_worktree(session, run, binding)
    return run


async def _bind_run_to_worktree(session: AsyncSession, run: Any, binding: Any) -> None:
    if run.status in {"awaiting_worktree", "no_worktree"}:
        run.status = "bound"
    run.main_repo_root = binding.main_repo_root
    run.worktree_root = binding.worktree_root
    run.discovery_method = binding.discovery_method
    await session.flush()


async def _refresh_run_snapshot(
    session: AsyncSession,
    run: Any,
    client_id: UUID,
    registry: ClientConnectionRegistry | None,
    client_runtime: ClientRuntime | None = None,
) -> None:
    worktree_root = run.worktree_root
    if not isinstance(worktree_root, str) or not worktree_root.strip():
        return

    snapshot_payload = {
        "worktree_root": worktree_root,
        "base_head": _snapshot_head(run.start_snapshot_json),
    }
    result = await _git_worktree_action(
        registry,
        client_id,
        client_runtime,
        action="snapshot",
        **snapshot_payload,
    )
    if result is None and _is_local_project_worktree_path(worktree_root, run.main_repo_root):
        result = await local_git_worktree_action("snapshot", **snapshot_payload)
    snapshot = result.get("snapshot") if result and result.get("ok") else None
    if not isinstance(snapshot, dict) or not snapshot.get("is_linked_worktree"):
        return

    if not isinstance(run.start_snapshot_json, dict):
        run.start_snapshot_json = snapshot
    run.end_snapshot_json = snapshot
    session_diff = compute_session_diff(run.start_snapshot_json, run.end_snapshot_json)
    run.session_diff_json = session_diff
    run.pending_commit = pending_commit_from_diff(session_diff)
    run.status = "completed" if _is_tracking_run(run) else run.status
    if run.ended_at is None and _is_tracking_run(run):
        run.ended_at = datetime.now(UTC)
    if run.pending_commit:
        run.resolved_at = None
    else:
        run.resolved_at = datetime.now(UTC)
    await session.flush()


def _snapshot_head(snapshot: Any) -> str | None:
    if not isinstance(snapshot, dict):
        return None
    head = snapshot.get("head_sha")
    return head if isinstance(head, str) and head else None


def _is_local_project_worktree_path(worktree_root: str, main_repo_root: str | None) -> bool:
    if not isinstance(main_repo_root, str) or not main_repo_root.strip():
        return False
    normalized = os.path.realpath(worktree_root)
    expected_root = os.path.join(os.path.realpath(main_repo_root), ".web-terminal-acp", "worktrees")
    try:
        if os.path.commonpath([normalized, expected_root]) != expected_root:
            return False
    except ValueError:
        return False
    return os.path.isdir(normalized) and os.path.isfile(os.path.join(normalized, ".git"))


async def _finish_agent_run(
    session: AsyncSession,
    *,
    client_id: UUID,
    window_id: UUID,
    sequence_str: str,
    registry: ClientConnectionRegistry | None,
    client_runtime: ClientRuntime | None = None,
) -> None:
    run = await get_git_worktree_run(session, window_id, sequence_str)
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


async def load_git_worktree_activity_for_window(
    session: AsyncSession,
    *,
    client_id: UUID,
    window_id: UUID,
    registry: ClientConnectionRegistry | None,
    client_runtime: ClientRuntime | None = None,
) -> dict[str, Any] | None:
    binding = await get_window_git_binding(session, window_id)
    if binding is None:
        return None

    if registry is not None:
        result = await _git_worktree_action(
            registry,
            client_id,
            client_runtime,
            action="detect",
            path=binding.worktree_root,
        )
        if result and result.get("ok"):
            context = result.get("context") or {}
            if not context.get("is_linked_worktree"):
                return None
            binding.branch = context.get("branch") or binding.branch

        live = await _git_worktree_action(
            registry,
            client_id,
            client_runtime,
            action="snapshot",
            worktree_root=binding.worktree_root,
        )
        if live and live.get("ok"):
            snapshot = live.get("snapshot") or {}
            pending = await window_has_pending_commit(session, window_id)
            if pending:
                still_pending = pending_commit_from_live_snapshot(snapshot)
                if not still_pending:
                    await session.execute(
                        update(GitWorktreeRun)
                        .where(
                            GitWorktreeRun.virtual_window_id == window_id,
                            GitWorktreeRun.pending_commit.is_(True),
                        )
                        .values(pending_commit=False, resolved_at=datetime.now(UTC))
                    )

    pending_commit = await window_has_pending_commit(session, window_id)
    return {
        "worktree_root": binding.worktree_root,
        "main_repo_root": binding.main_repo_root,
        "branch": binding.branch,
        "pending_commit": pending_commit,
    }
