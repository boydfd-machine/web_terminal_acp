from __future__ import annotations

# ruff: noqa: F821

from importlib import import_module

_event_collectors = import_module("app.client_agent.agent_tool_watchers.event_collectors")

globals().update(
    {name: value for name, value in _event_collectors.__dict__.items() if not name.startswith("__")}
)

def _collect_all_events(
    state: AgentToolWatcherState,
    *,
    client_id: UUID,
    window_id: UUID,
    project_path: str | None,
    providers: frozenset[str] | None = None,
) -> list[ManagedAiEvent]:
    events: list[ManagedAiEvent] = []
    for provider_id, collector_name in AGENT_TOOL_COLLECTORS:
        if providers is not None and provider_id not in providers:
            continue
        collector = globals()[collector_name]
        events.extend(
            collector(
                state,
                client_id=client_id,
                window_id=window_id,
                project_path=project_path,
            )
        )
    return events


def _normalize_provider_filter(providers: frozenset[str] | set[str] | None) -> frozenset[str] | None:
    if providers is None:
        return None
    registry = get_agent_plugin_registry()
    normalized: set[str] = set()
    for provider in providers:
        normalized.add(registry.by_provider(provider).provider_id)
    return frozenset(normalized)


async def enqueue_managed_ai_event(send_event: ManagedEventSender, event: ManagedAiEvent) -> bool:
    validated_event = managed_event_from_payload(
        event.client_id,
        event.window_id,
        event.provider,
        event.payload,
        source_path=event.source_path,
        offset=event.offset,
        cursor=event.cursor,
        project_path=event.project_path,
    )
    if validated_event is None:
        return False

    await send_event(
        AgentMessage(
            type="ai_event",
            client_id=validated_event.client_id,
            window_id=validated_event.window_id,
            payload={
                "provider": validated_event.provider,
                "source_path": validated_event.source_path,
                "offset": validated_event.offset,
                "cursor": validated_event.cursor,
                "project_path": validated_event.project_path,
                "payload": validated_event.payload,
            },
        )
    )
    return True


__all__ = [name for name in globals() if not name.startswith("__")]
