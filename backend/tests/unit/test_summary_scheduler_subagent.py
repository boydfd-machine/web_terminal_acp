from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from app.contexts.workspace.application import summary_scheduler as scheduler
from app.contexts.workspace.application import summary_subagent_state as subagent_state
from app.agent_tools.types import AgentSubagentState
from app.models import Event, EventSourceType, VirtualWindow, WindowStatus


def _make_window() -> VirtualWindow:
    return VirtualWindow(
        id=uuid4(),
        client_id=uuid4(),
        title="Terminal",
        status=WindowStatus.active,
        agent_activity_pending_subagent_count=0,
        agent_activity_generation=0,
    )


def _make_event(payload: dict, *, kind: str = "assistant_message", created_at: datetime | None = None) -> Event:
    return Event(
        client_id=uuid4(),
        source_type=EventSourceType.claude_jsonl,
        source_id="claude-session-1",
        kind=kind,
        payload_json=payload,
        fingerprint=str(uuid4()),
        created_at=created_at or datetime.now(timezone.utc),
    )


def _subagent_call_event(*, tool_use_id: str = "call-1", agent_id: str = "subagent-1", created_at: datetime | None = None) -> Event:
    return _make_event(
        {
            "type": "assistant",
            "message": {
                "role": "assistant",
                "content": [
                    {
                        "type": "tool_use",
                        "id": tool_use_id,
                        "name": "Agent",
                        "input": {
                            "description": "Test subagent",
                            "prompt": "do something",
                            "subagent_type": "claude",
                        },
                    }
                ],
            },
            "subagent_tool_use_results": [
                {"tool_use_id": tool_use_id, "agent_id": agent_id},
            ],
        },
        kind="assistant_message",
        created_at=created_at,
    )


def _subagent_result_event(*, tool_use_id: str = "call-1", agent_id: str = "subagent-1", created_at: datetime | None = None) -> Event:
    return _make_event(
        {
            "type": "user",
            "message": {
                "role": "user",
                "content": [
                    {
                        "type": "tool_result",
                        "tool_use_id": tool_use_id,
                        "content": [
                            {"type": "text", "text": "result"},
                            {"type": "text", "text": f"agentId: {agent_id}\n<usage>tokens</usage>"},
                        ],
                    }
                ],
            },
            "toolUseResult": {"agentId": agent_id, "toolUseId": tool_use_id},
        },
        kind="user_message",
        created_at=created_at,
    )


def _completion_event(*, created_at: datetime | None = None) -> Event:
    return _make_event(
        {
            "type": "assistant",
            "message": {
                "role": "assistant",
                "stop_reason": "end_turn",
                "content": [{"type": "text", "text": "done"}],
            },
        },
        kind="assistant_message",
        created_at=created_at,
    )


def test_subagent_call_increments_pending_counter() -> None:
    window = _make_window()
    when = datetime(2026, 6, 13, 10, 0, tzinfo=timezone.utc)
    event = _subagent_call_event(created_at=when)

    scheduler._touch_agent_activity_state(window, event, when)

    assert window.agent_activity_pending_subagent_count == 1
    assert window.agent_activity_latest_subagent_call_at == when


def test_completion_deferred_when_subagent_pending() -> None:
    window = _make_window()
    call_at = datetime(2026, 6, 13, 10, 0, tzinfo=timezone.utc)
    scheduler._touch_agent_activity_state(window, _subagent_call_event(created_at=call_at), call_at)

    completion_at = datetime(2026, 6, 13, 10, 1, tzinfo=timezone.utc)
    scheduler._touch_agent_activity_state(window, _completion_event(created_at=completion_at), completion_at)

    assert window.agent_activity_pending_subagent_count == 1
    assert window.agent_activity_latest_completed_at is None
    assert window.agent_activity_deferred_completed_at == completion_at


def test_result_returns_counter_to_zero_and_promotes_deferred() -> None:
    window = _make_window()
    call_at = datetime(2026, 6, 13, 10, 0, tzinfo=timezone.utc)
    scheduler._touch_agent_activity_state(window, _subagent_call_event(created_at=call_at), call_at)

    completion_at = datetime(2026, 6, 13, 10, 1, tzinfo=timezone.utc)
    scheduler._touch_agent_activity_state(window, _completion_event(created_at=completion_at), completion_at)

    result_at = datetime(2026, 6, 13, 10, 5, tzinfo=timezone.utc)
    scheduler._touch_agent_activity_state(window, _subagent_result_event(created_at=result_at), result_at)

    assert window.agent_activity_pending_subagent_count == 0
    assert window.agent_activity_latest_completed_at == completion_at
    assert window.agent_activity_deferred_completed_at is None


def test_multiple_subagent_pairs_are_counted_correctly() -> None:
    window = _make_window()
    base = datetime(2026, 6, 13, 10, 0, tzinfo=timezone.utc)

    scheduler._touch_agent_activity_state(
        window, _subagent_call_event(tool_use_id="call-1", agent_id="sub-1", created_at=base), base
    )
    scheduler._touch_agent_activity_state(
        window,
        _subagent_call_event(tool_use_id="call-2", agent_id="sub-2", created_at=base + timedelta(seconds=10)),
        base + timedelta(seconds=10),
    )
    assert window.agent_activity_pending_subagent_count == 2

    scheduler._touch_agent_activity_state(
        window,
        _subagent_result_event(tool_use_id="call-1", agent_id="sub-1", created_at=base + timedelta(seconds=20)),
        base + timedelta(seconds=20),
    )
    assert window.agent_activity_pending_subagent_count == 1

    scheduler._touch_agent_activity_state(
        window,
        _subagent_result_event(tool_use_id="call-2", agent_id="sub-2", created_at=base + timedelta(seconds=30)),
        base + timedelta(seconds=30),
    )
    assert window.agent_activity_pending_subagent_count == 0


def test_result_below_zero_is_clamped() -> None:
    window = _make_window()
    when = datetime(2026, 6, 13, 10, 0, tzinfo=timezone.utc)
    scheduler._touch_agent_activity_state(window, _subagent_result_event(created_at=when), when)
    assert window.agent_activity_pending_subagent_count == 0


def test_stale_subagent_state_is_force_promoted() -> None:
    window = _make_window()
    call_at = datetime(2026, 6, 13, 10, 0, tzinfo=timezone.utc)
    scheduler._touch_agent_activity_state(window, _subagent_call_event(created_at=call_at), call_at)

    completion_at = datetime(2026, 6, 13, 10, 1, tzinfo=timezone.utc)
    scheduler._touch_agent_activity_state(window, _completion_event(created_at=completion_at), completion_at)

    future_event_at = call_at + timedelta(minutes=20)
    with patch.object(subagent_state, "stale_subagent_seconds", return_value=60.0):
        scheduler._touch_agent_activity_state(
            window, _make_event({"type": "system", "subtype": "ping"}, kind="system_message"), future_event_at
        )

    assert window.agent_activity_pending_subagent_count == 0
    assert window.agent_activity_latest_completed_at == completion_at
    assert window.agent_activity_deferred_completed_at is None


def test_completion_without_pending_subagent_writes_latest_immediately() -> None:
    window = _make_window()
    when = datetime(2026, 6, 13, 10, 0, tzinfo=timezone.utc)
    scheduler._touch_agent_activity_state(window, _completion_event(created_at=when), when)

    assert window.agent_activity_pending_subagent_count == 0
    assert window.agent_activity_latest_completed_at == when
    assert window.agent_activity_deferred_completed_at is None


def _sidechain_completion_event(*, agent_id: str = "subagent-1", created_at: datetime | None = None) -> Event:
    """Subagent's own end_turn event. isSidechain=True + agentId set."""
    return _make_event(
        {
            "provider": "claude_code",
            "type": "assistant",
            "isSidechain": True,
            "agentId": agent_id,
            "message": {
                "role": "assistant",
                "stop_reason": "end_turn",
                "content": [{"type": "text", "text": "subagent done"}],
            },
        },
        kind="assistant_message",
        created_at=created_at,
    )


def test_is_event_sidechain_completion_detected() -> None:
    """Helper `is_sidechain_event` must flag sidechain events."""
    event = _sidechain_completion_event()
    assert subagent_state.is_sidechain_event(event) is True

    main_event = _completion_event()
    assert subagent_state.is_sidechain_event(main_event) is False


def test_should_skip_completion_sync_for_sidechain_event() -> None:
    """Sidechain (subagent's own) end_turn must not trigger todo completion sync.

    Regression: previously the main flow treated subagent end_turn events as
    main-agent completion, immediately scheduling verification, which marked the
    todo complete while the parent agent was still waiting for the subagent
    tool_result.
    """
    window = _make_window()
    event = _sidechain_completion_event()
    assert subagent_state.should_skip_completion_sync(window, event) is True


def test_should_skip_completion_sync_when_subagent_pending() -> None:
    """When pending_subagent_count > 0, even main-agent end_turn must not
    trigger todo completion sync (deferred until counter returns to 0)."""
    window = _make_window()
    window.agent_activity_pending_subagent_count = 1
    main_event = _completion_event()
    assert subagent_state.should_skip_completion_sync(window, main_event) is True


def test_should_not_skip_completion_sync_for_main_agent_idle() -> None:
    """Main agent end_turn with no pending subagent proceeds normally."""
    window = _make_window()
    main_event = _completion_event()
    assert subagent_state.should_skip_completion_sync(window, main_event) is False


def test_subagent_state_comes_from_agent_tool_adapter(monkeypatch) -> None:
    """Workspace application should consume generic adapter subagent signals."""

    class FutureAdapter:
        provider_id = "future_provider"

        def subagent_state(self, event: Event) -> AgentSubagentState:
            if event.payload_json.get("future_subagent_call") is True:
                return AgentSubagentState(is_call=True)
            return AgentSubagentState()

    class FutureRegistry:
        def by_source_type(
            self,
            source_type: EventSourceType | str,
            provider: str | None = None,
        ) -> FutureAdapter:
            assert source_type == EventSourceType.agent_tool_record
            assert provider == "future_provider"
            return FutureAdapter()

    monkeypatch.setattr(subagent_state, "get_agent_tool_registry", lambda: FutureRegistry())
    event = Event(
        client_id=uuid4(),
        source_type=EventSourceType.agent_tool_record,
        source_id="future-session-1",
        kind="assistant_message",
        payload_json={"provider": "future_provider", "future_subagent_call": True},
        fingerprint=str(uuid4()),
    )
    window = _make_window()
    when = datetime(2026, 6, 13, 10, 0, tzinfo=timezone.utc)

    assert subagent_state.is_subagent_state_event(event) is True
    subagent_state.apply_subagent_event_to_window(window, event, when)

    assert window.agent_activity_pending_subagent_count == 1
    assert window.agent_activity_latest_subagent_call_at == when


@pytest.mark.asyncio
async def test_schedule_summary_skips_sync_for_sidechain_end_turn() -> None:
    """End-to-end: schedule_summary_after_agent_activity must not call
    sync_project_todos_for_completed_window when the completion event is a
    sidechain subagent event."""
    window = _make_window()
    window.agent_activity_burst_start_at = datetime(2026, 6, 13, 10, 0, tzinfo=timezone.utc)
    window.agent_activity_latest_at = datetime(2026, 6, 13, 10, 0, tzinfo=timezone.utc)
    event = _sidechain_completion_event(
        created_at=datetime(2026, 6, 13, 10, 1, tzinfo=timezone.utc)
    )

    with patch.object(
        scheduler,
        "sync_project_todos_for_completed_window",
        new=AsyncMock(return_value=(False, [])),
    ) as mock_sync, patch.object(
        scheduler,
        "_schedule_after_latest_agent_user_message",
        new=AsyncMock(return_value=None),
    ), patch.object(
        scheduler,
        "_was_idle_before",
        new=AsyncMock(return_value=False),
    ):
        await scheduler.schedule_summary_after_agent_activity(
            session=None,
            window=window,
            event=event,
        )
    mock_sync.assert_not_called()


@pytest.mark.asyncio
async def test_schedule_summary_skips_sync_when_subagent_still_pending() -> None:
    """End-to-end: main-agent end_turn while subagent is pending must not call
    sync_project_todos_for_completed_window."""
    window = _make_window()
    window.agent_activity_burst_start_at = datetime(2026, 6, 13, 10, 0, tzinfo=timezone.utc)
    window.agent_activity_latest_at = datetime(2026, 6, 13, 10, 0, tzinfo=timezone.utc)
    window.agent_activity_pending_subagent_count = 1
    event = _completion_event(
        created_at=datetime(2026, 6, 13, 10, 1, tzinfo=timezone.utc)
    )

    with patch.object(
        scheduler,
        "sync_project_todos_for_completed_window",
        new=AsyncMock(return_value=(False, [])),
    ) as mock_sync, patch.object(
        scheduler,
        "_schedule_after_latest_agent_user_message",
        new=AsyncMock(return_value=None),
    ), patch.object(
        scheduler,
        "_was_idle_before",
        new=AsyncMock(return_value=False),
    ):
        await scheduler.schedule_summary_after_agent_activity(
            session=None,
            window=window,
            event=event,
        )
    mock_sync.assert_not_called()


@pytest.mark.asyncio
async def test_schedule_summary_runs_sync_for_main_agent_idle_when_no_pending() -> None:
    """End-to-end: main-agent end_turn with no pending subagent must call sync
    (regression guard)."""
    window = _make_window()
    window.agent_activity_burst_start_at = datetime(2026, 6, 13, 10, 0, tzinfo=timezone.utc)
    window.agent_activity_latest_at = datetime(2026, 6, 13, 10, 0, tzinfo=timezone.utc)
    event = _completion_event(
        created_at=datetime(2026, 6, 13, 10, 1, tzinfo=timezone.utc)
    )

    with patch.object(
        scheduler,
        "sync_project_todos_for_completed_window",
        new=AsyncMock(return_value=(False, [])),
    ) as mock_sync, patch.object(
        scheduler,
        "_schedule_after_latest_agent_user_message",
        new=AsyncMock(return_value=None),
    ), patch.object(
        scheduler,
        "_was_idle_before",
        new=AsyncMock(return_value=False),
    ):
        await scheduler.schedule_summary_after_agent_activity(
            session=None,
            window=window,
            event=event,
        )
    mock_sync.assert_called_once()
