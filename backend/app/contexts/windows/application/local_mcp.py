from __future__ import annotations

from app.config import get_settings


def local_runtime_mcp_server_url(runtime_manager: object) -> str:
    server_url = getattr(runtime_manager, "server_url", None)
    if isinstance(server_url, str) and server_url.strip():
        return server_url

    settings = get_settings()
    return f"http://{settings.app_host}:{settings.app_port}"
