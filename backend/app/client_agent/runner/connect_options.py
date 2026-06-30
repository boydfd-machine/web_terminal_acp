from __future__ import annotations

from app.client_agent.config import ClientAgentConfig


def _websocket_connect_kwargs(
    config: ClientAgentConfig,
    headers: dict[str, str],
    header_argument: str,
) -> dict[str, object]:
    return {
        header_argument: headers,
        "max_size": None,
        "ping_interval": config.websocket_ping_interval_seconds,
        "ping_timeout": config.websocket_ping_timeout_seconds,
    }
