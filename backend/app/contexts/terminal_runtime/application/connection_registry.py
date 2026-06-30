from __future__ import annotations

from app.contexts.terminal_runtime.application.client_connections import ClientConnectionRegistry


def client_connection_registry_from_state(state) -> ClientConnectionRegistry:
    registry = getattr(state, "client_connections", None)
    if registry is None:
        registry = ClientConnectionRegistry()
        state.client_connections = registry
    return registry
