from __future__ import annotations

import asyncio
import contextlib
import logging
from uuid import UUID

from app.client_agent.runner.reconnect_policy import _is_expected_reconnect_exception

CLIENT_AGENT_CLEANUP_STEP_TIMEOUT_SECONDS = 5.0
logger = logging.getLogger(__name__)


async def _await_cleanup_step(
    step_name: str,
    task: asyncio.Task,
    *,
    client_id: UUID,
    timeout_seconds: float = CLIENT_AGENT_CLEANUP_STEP_TIMEOUT_SECONDS,
) -> None:
    await _run_cleanup_step(step_name, task, client_id=client_id, timeout_seconds=timeout_seconds)


async def _run_cleanup_step(
    step_name: str,
    awaitable,
    *,
    client_id: UUID,
    timeout_seconds: float = CLIENT_AGENT_CLEANUP_STEP_TIMEOUT_SECONDS,
) -> None:
    task = awaitable if isinstance(awaitable, asyncio.Task) else asyncio.create_task(awaitable)
    try:
        await asyncio.wait_for(asyncio.shield(task), timeout=timeout_seconds)
    except asyncio.CancelledError:
        if asyncio.current_task() is not None and asyncio.current_task().cancelling():
            task.cancel()
            raise
    except asyncio.TimeoutError:
        task.cancel()
        task.add_done_callback(_consume_cleanup_task_exception)
        logger.warning(
            "client-agent cleanup step timed out",
            extra={
                "client_id": str(client_id),
                "step_name": step_name,
                "timeout_seconds": timeout_seconds,
            },
        )
    except Exception as exc:
        if _is_expected_reconnect_exception(exc) or isinstance(exc, TimeoutError):
            logger.debug(
                "client-agent cleanup step stopped after connection closed",
                extra={"client_id": str(client_id), "step_name": step_name},
            )
            return
        logger.exception(
            "client-agent cleanup step failed",
            extra={"client_id": str(client_id), "step_name": step_name},
        )


def _consume_cleanup_task_exception(task: asyncio.Task) -> None:
    if task.cancelled():
        return
    with contextlib.suppress(Exception):
        task.exception()
