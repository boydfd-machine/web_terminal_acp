from __future__ import annotations

# ruff: noqa: F401,F821

from importlib import import_module
from pathlib import Path

_lifecycle = import_module("app.client_agent.runner.lifecycle")
globals().update(
    {name: value for name, value in _lifecycle.__dict__.items() if not name.startswith("__")}
)


async def _send_terminal_attach_result(
    writer: ControlMessageWriter,
    client_id: UUID,
    window_id: UUID,
    *,
    request_id: str | None,
    runtime_window: ClientRuntimeWindow | None = None,
) -> None:
    payload: dict[str, object] = {"ok": True}
    if runtime_window is not None:
        payload.update(
            {
                "remote_session_id": runtime_window.remote_session_id,
                "remote_window_id": runtime_window.remote_window_id,
                "cwd": runtime_window.cwd,
                "shell_command": runtime_window.shell_command,
            }
        )
    await writer.send(
        AgentMessage(
            type="terminal_attach_result",
            client_id=client_id,
            window_id=window_id,
            request_id=request_id,
            payload=payload,
        )
    )


async def _send_terminal_error(
    writer: ControlMessageWriter,
    client_id: UUID,
    window_id: UUID | None,
    *,
    request_id: str | None,
    message: str,
    view_id: UUID | None = None,
) -> None:
    payload = {"message": message}
    if view_id is not None:
        payload["view_id"] = str(view_id)
    await writer.send(
        AgentMessage(
            type="terminal_error",
            client_id=client_id,
            window_id=window_id,
            request_id=request_id,
            payload=payload,
        )
    )


def _message_window_id(message: AgentMessage) -> UUID:
    if message.window_id is not None:
        return message.window_id
    payload_window_id = message.payload.get("window_id")
    if payload_window_id is not None:
        return UUID(str(payload_window_id))
    raise ValueError(f"agent message requires window_id: {message.type}")


def _required_payload_string(message: AgentMessage, key: str) -> str:
    value = message.payload.get(key)
    if not isinstance(value, str) or not value:
        raise ValueError(f"agent message requires payload string: {key}")
    return value


def _optional_payload_string(message: AgentMessage, key: str) -> str | None:
    value = message.payload.get(key)
    return value if isinstance(value, str) and value else None


def _optional_payload_bool(message: AgentMessage, key: str) -> bool:
    return message.payload.get(key) is True


def _optional_payload_float(message: AgentMessage, key: str) -> float | None:
    value = message.payload.get(key)
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _optional_positive_int_payload(message: AgentMessage, key: str) -> int | None:
    value = message.payload.get(key)
    if value is None:
        return None
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 0 else None


def _read_limited_file(path: str, *, max_bytes: int) -> bytes:
    if max_bytes <= 0:
        raise ValueError("max_bytes must be positive")
    with Path(path).open("rb") as handle:
        return handle.read(max_bytes)


def _list_file_entries(path: str) -> list[dict[str, object]]:
    entries: list[dict[str, object]] = []
    for entry in Path(path).iterdir():
        try:
            stat_result = entry.stat()
        except OSError:
            continue
        if entry.is_dir():
            kind = "directory"
            size = None
        elif entry.is_file():
            kind = "file"
            size = stat_result.st_size
        else:
            continue
        entries.append(
            {
                "name": entry.name,
                "path": str(entry),
                "kind": kind,
                "size": size,
                "mtime": stat_result.st_mtime,
            }
        )
    entries.sort(key=lambda item: (item["kind"] != "directory", str(item["name"]).lower(), str(item["name"])))
    return entries


def _write_file(path: str, *, data: bytes, overwrite: bool) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    mode = "wb" if overwrite else "xb"
    with target.open(mode) as handle:
        handle.write(data)
