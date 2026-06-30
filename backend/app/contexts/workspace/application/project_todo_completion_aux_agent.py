from __future__ import annotations

import logging
from uuid import UUID, uuid4

from app.config import get_settings
from app.contexts.terminal_runtime.application.agent_task_runner import AgentTaskSpec, run_agent_task
from app.contexts.terminal_runtime.application.broker import TerminalBroker
from app.contexts.terminal_runtime.application.client_connections import ClientConnectionRegistry
from app.contexts.terminal_runtime.application.runtime_provider import TmuxManager
from app.contexts.workspace.application.project_todo_completion_prompt import (
    VerificationVerdict,
    build_verification_prompt,
    parse_verification_verdict,
    verification_json_complete,
)
from app.models import ProjectTodo

logger = logging.getLogger(__name__)


async def run_verification_prompt(
    *,
    todo_id: UUID,
    client_id: UUID,
    window_id: UUID,
    attempt: int,
    active_processes: list[str],
    session_factory,
    tmux_manager: TmuxManager,
    terminal_broker: TerminalBroker | None,
    registry: ClientConnectionRegistry | None,
    waited_for_background_work: bool = False,
) -> VerificationVerdict:
    settings = get_settings()
    output_path = f"/tmp/web-terminal-todo-verification-{todo_id}-{attempt}-{uuid4().hex}.json"
    async with session_factory() as session:
        todo = await session.get(ProjectTodo, todo_id)
        if todo is None:
            return VerificationVerdict("error", "todo not found", [])
        prompt = build_verification_prompt(
            todo,
            attempt=attempt,
            active_processes=active_processes,
            waited_for_background_work=waited_for_background_work,
            output_path=output_path,
        )

        spec = AgentTaskSpec(
            prompt=prompt,
            source_window_id=window_id,
            is_complete=verification_json_complete,
            timeout_seconds=settings.project_todo_completion_verification_timeout_seconds,
            title=f"Todo {todo_id} verification (attempt {attempt})",
            output_path=output_path,
            derived_context_extras={
                "purpose": "todo_completion_verification",
                "todo_id": str(todo_id),
                "attempt": attempt,
            },
        )
        try:
            result = await run_agent_task(
                session,
                spec,
                client_id=client_id,
                session_factory=session_factory,
                terminal_broker=terminal_broker,
                tmux_manager=tmux_manager,
                registry=registry,
                ephemeral_retention_seconds=0.0,
            )
        except Exception as exc:
            logger.warning("todo verification prompt failed", exc_info=True)
            return VerificationVerdict("error", f"prompt execution failed: {exc}"[:500], active_processes)
    return parse_verification_verdict(result.output, fallback_processes=active_processes)
