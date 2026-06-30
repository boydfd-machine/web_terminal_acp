from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import TypeVar

from app.contexts.mcp_acp.application.errors import McpAcpServiceError
from app.contexts.terminal_runtime.application.mcp_terminal_ops import TerminalRuntimeNotReady

T = TypeVar("T")


async def map_terminal_runtime_not_ready(operation: Callable[[], Awaitable[T]]) -> T:
    try:
        return await operation()
    except TerminalRuntimeNotReady as exc:
        raise McpAcpServiceError(503, str(exc)) from exc
