from __future__ import annotations

from app.contexts.terminal_runtime.application.runtime_binding import RuntimeWindowBinding
from app.models import Client, ClientStatus, VirtualWindow


def mcp_client_payload(client: Client) -> dict[str, object]:
    return {
        "id": client.id,
        "name": client.name,
        "status": client.status.value,
        "runtime": client.runtime.value,
        "hostname": client.hostname,
        "version": client.version,
        "online": client.status is ClientStatus.ONLINE,
    }


def mcp_window_payload(window: VirtualWindow) -> dict[str, object]:
    return {
        "id": window.id,
        "client_id": window.client_id,
        "title": window.title,
        "status": window.status.value,
        "cwd": window.cwd,
        "shell_command": window.shell_command,
        "runtime_ready": RuntimeWindowBinding.from_virtual_window(window) is not None,
        "derived_mode": window.derived_mode,
        "derived_context": window.derived_context,
    }
