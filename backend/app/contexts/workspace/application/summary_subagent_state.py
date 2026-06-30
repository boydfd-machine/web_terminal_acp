from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.config import get_settings
from app.models import Event, VirtualWindow
from app.platform.plugins.agent_tools import get_agent_tool_registry
from app.platform.plugins.agent_tools.types import AgentSubagentState


def stale_subagent_seconds() -> float:
    return float(get_settings().stale_subagent_seconds)


def is_sidechain_event(event: Event) -> bool:
    return _subagent_state(event).is_sidechain


def should_skip_completion_sync(window: VirtualWindow, event: Event) -> bool:
    state = _subagent_state(event)
    if state.is_sidechain:
        return True
    pending_background_count = state.pending_background_agent_count
    if pending_background_count is not None and pending_background_count > 0:
        return True
    if int(window.agent_activity_pending_subagent_count or 0) > 0:
        return True
    return False


def is_subagent_state_event(event: Event) -> bool:
    return _subagent_state(event).has_state_event


def is_subagent_call_event(event: Event) -> bool:
    return _subagent_state(event).is_call


def is_subagent_result_event(event: Event) -> bool:
    return _subagent_state(event).is_result


def apply_subagent_event_to_window(
    window: VirtualWindow,
    event: Event,
    activity_at: datetime,
) -> None:
    state = _subagent_state(event)
    pending_background_count = state.pending_background_agent_count
    if pending_background_count is not None:
        count = int(window.agent_activity_pending_subagent_count or 0)
        if pending_background_count > count:
            window.agent_activity_pending_subagent_count = pending_background_count
            window.agent_activity_latest_subagent_call_at = _ensure_aware(activity_at)
        return
    if state.is_async_launch:
        count = int(window.agent_activity_pending_subagent_count or 0)
        if count <= 0:
            window.agent_activity_pending_subagent_count = 1
        window.agent_activity_latest_subagent_call_at = _ensure_aware(activity_at)
        return
    if state.is_call:
        window.agent_activity_pending_subagent_count = (
            int(window.agent_activity_pending_subagent_count or 0) + 1
        )
        window.agent_activity_latest_subagent_call_at = _ensure_aware(activity_at)
        return
    if state.is_finished_notification:
        count = int(window.agent_activity_pending_subagent_count or 0)
        if count > 0:
            window.agent_activity_pending_subagent_count = count - 1
        return
    if state.is_result:
        count = int(window.agent_activity_pending_subagent_count or 0)
        if count > 0:
            window.agent_activity_pending_subagent_count = count - 1
            if window.agent_activity_pending_subagent_count == 0:
                promote_deferred_completion(window)
        return


def _subagent_state(event: Event) -> AgentSubagentState:
    provider = _provider_name(event.payload_json)
    try:
        adapter = get_agent_tool_registry().by_source_type(event.source_type, provider)
    except (KeyError, ValueError):
        if provider is None:
            return AgentSubagentState()
        try:
            adapter = get_agent_tool_registry().by_provider(provider)
        except ValueError:
            return AgentSubagentState()
    return adapter.subagent_state(event)


def _provider_name(payload: dict) -> str | None:
    provider = payload.get("provider")
    if isinstance(provider, str):
        provider = provider.strip()
        return provider or None
    return None


def promote_deferred_completion(window: VirtualWindow) -> None:
    deferred = window.agent_activity_deferred_completed_at
    if deferred is None:
        return
    deferred_at = _ensure_aware(deferred)
    latest_completed = (
        _ensure_aware(window.agent_activity_latest_completed_at)
        if window.agent_activity_latest_completed_at
        else None
    )
    if latest_completed is None or deferred_at >= latest_completed:
        window.agent_activity_latest_completed_at = deferred_at
    window.agent_activity_deferred_completed_at = None


def maybe_promote_stale_subagent_state(window: VirtualWindow, *, now: datetime) -> bool:
    count = int(window.agent_activity_pending_subagent_count or 0)
    if count <= 0:
        return False
    latest_call_at = window.agent_activity_latest_subagent_call_at
    if latest_call_at is None:
        return False
    age = now - _ensure_aware(latest_call_at)
    if age <= timedelta(seconds=stale_subagent_seconds()):
        return False
    window.agent_activity_pending_subagent_count = 0
    promote_deferred_completion(window)
    return True


def _ensure_aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)
