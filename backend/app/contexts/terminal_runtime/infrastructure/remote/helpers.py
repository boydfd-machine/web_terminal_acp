from __future__ import annotations

from app.contexts.terminal_runtime.domain.protocol import AgentMessage
from app.contexts.terminal_runtime.domain.types import RuntimeWindow


class RemoteClientUnavailable(RuntimeError):
    def __init__(self, message: str, *, reason: str = "unknown") -> None:
        super().__init__(message)
        self.reason = reason


class RemoteTerminalError(RuntimeError):
    pass


def message_from_error_response(response: AgentMessage) -> str:
    message = response.payload.get("message")
    if isinstance(message, str) and message:
        return message
    return f"remote terminal operation failed: {response.type}"


def runtime_window_from_response(
    response: AgentMessage,
    *,
    fallback: RuntimeWindow,
) -> RuntimeWindow:
    remote_session_id = response.payload.get("remote_session_id")
    remote_window_id = response.payload.get("remote_window_id")
    if not isinstance(remote_session_id, str) or not isinstance(remote_window_id, str):
        return fallback
    response_cwd = response.payload.get("cwd")
    response_shell = response.payload.get("shell_command")
    return RuntimeWindow(
        session_id=remote_session_id,
        window_id=remote_window_id,
        cwd=response_cwd if isinstance(response_cwd, str) else fallback.cwd,
        shell_command=response_shell if isinstance(response_shell, str) else fallback.shell_command,
    )


def runtime_window_from_create_response(
    response: AgentMessage,
    *,
    cwd: str | None,
    shell_command: str | None,
) -> RuntimeWindow:
    remote_session_id = response.payload.get("remote_session_id")
    remote_window_id = response.payload.get("remote_window_id")
    if not isinstance(remote_session_id, str) or not isinstance(remote_window_id, str):
        raise ValueError("create_window response missing remote session/window ids")
    response_cwd = response.payload.get("cwd")
    response_shell = response.payload.get("shell_command")
    return RuntimeWindow(
        session_id=remote_session_id,
        window_id=remote_window_id,
        cwd=response_cwd if isinstance(response_cwd, str) else cwd,
        shell_command=response_shell if isinstance(response_shell, str) else shell_command,
    )


def drop_none_payload_values(payload: dict[str, object], *keys: str) -> None:
    for key in keys:
        if payload.get(key) is None:
            payload.pop(key, None)
