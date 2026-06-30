from __future__ import annotations

from uuid import UUID

from app.client_agent.cursor_official_models import list_cursor_official_models
from app.contexts.clients.application.client_lookup import get_client
from app.contexts.terminal_runtime.application.runtime_provider import RemoteClientUnavailable, RemoteRuntime, RemoteTerminalError
from app.models import ClientRuntime


async def list_cursor_official_models_for_client(
    *,
    session,
    client_id: UUID,
    registry,
) -> list[dict[str, str]]:
    client = await get_client(session, client_id)
    if client is None:
        raise ValueError("client not found")
    if client.runtime is ClientRuntime.local:
        return list_cursor_official_models()
    runtime = RemoteRuntime(client_id=client_id, registry=registry)
    try:
        payload = await runtime.list_cursor_official_models()
    except RemoteClientUnavailable as exc:
        raise ValueError(f"remote client unavailable: {exc.reason}") from exc
    except RemoteTerminalError as exc:
        raise ValueError(str(exc)) from exc
    models = payload.get("models")
    if not isinstance(models, list):
        return []
    output: list[dict[str, str]] = []
    for item in models:
        if not isinstance(item, dict):
            continue
        model_id = item.get("id")
        label = item.get("label")
        if isinstance(model_id, str) and model_id.strip() and isinstance(label, str) and label.strip():
            output.append({"id": model_id.strip(), "label": label.strip()})
    return output
