from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from app.contexts.workspace.application import summary_scheduler as scheduler
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


def _subagent_call_event(*, tool_use_id: str = "call-1", created_at: datetime | None = None) -> Event:
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
                            "description": "Run sleep",
                            "prompt": "sleep 60",
                            "run_in_background": True,
                            "subagent_type": "general-purpose",
                        },
                    }
                ],
            },
        },
        kind="assistant_message",
        created_at=created_at,
    )


def _async_subagent_launch_event(*, tool_use_id: str = "call-1", agent_id: str = "subagent-1", created_at: datetime | None = None) -> Event:
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
                            {
                                "type": "text",
                                "text": (
                                    "Async agent launched successfully.\n"
                                    f"agentId: {agent_id} (internal ID - do not mention to user.)\n"
                                    "The agent is working in the background. You will be notified automatically when it completes."
                                ),
                            }
                        ],
                    }
                ],
            },
            "toolUseResult": {
                "isAsync": True,
                "status": "async_launched",
                "agentId": agent_id,
                "toolUseId": tool_use_id,
            },
        },
        kind="user_message",
        created_at=created_at,
    )


def _task_notification_event(*, tool_use_id: str = "call-1", agent_id: str = "subagent-1", created_at: datetime | None = None) -> Event:
    return _make_event(
        {
            "type": "user",
            "message": {
                "role": "user",
                "content": (
                    "<task-notification>\n"
                    f"<task-id>{agent_id}</task-id>\n"
                    f"<tool-use-id>{tool_use_id}</tool-use-id>\n"
                    "<status>completed</status>\n"
                    "<summary>Agent completed</summary>\n"
                    "<result>done</result>\n"
                    "</task-notification>"
                ),
            },
            "origin": {"kind": "task-notification"},
            "promptSource": "system",
        },
        kind="user_message",
        created_at=created_at,
    )


def _turn_duration_event(*, pending_count: int, created_at: datetime | None = None) -> Event:
    return _make_event(
        {
            "type": "system",
            "subtype": "turn_duration",
            "pendingBackgroundAgentCount": pending_count,
        },
        kind="system",
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


def test_async_launch_keeps_subagent_pending_until_task_notification() -> None:
    window = _make_window()
    call_at = datetime(2026, 6, 13, 10, 0, tzinfo=timezone.utc)
    scheduler._touch_agent_activity_state(window, _subagent_call_event(created_at=call_at), call_at)

    launch_at = call_at + timedelta(seconds=1)
    scheduler._touch_agent_activity_state(
        window,
        _async_subagent_launch_event(created_at=launch_at),
        launch_at,
    )

    assert window.agent_activity_pending_subagent_count == 1

    waiting_completion_at = call_at + timedelta(seconds=2)
    scheduler._touch_agent_activity_state(
        window,
        _completion_event(created_at=waiting_completion_at),
        waiting_completion_at,
    )

    assert window.agent_activity_pending_subagent_count == 1
    assert window.agent_activity_latest_completed_at is None
    assert window.agent_activity_deferred_completed_at == waiting_completion_at

    notification_at = call_at + timedelta(minutes=1)
    scheduler._touch_agent_activity_state(
        window,
        _task_notification_event(created_at=notification_at),
        notification_at,
    )

    assert window.agent_activity_pending_subagent_count == 0
    assert window.agent_activity_latest_completed_at is None
    assert window.agent_activity_deferred_completed_at == waiting_completion_at

    final_completion_at = notification_at + timedelta(seconds=5)
    scheduler._touch_agent_activity_state(
        window,
        _completion_event(created_at=final_completion_at),
        final_completion_at,
    )

    assert window.agent_activity_latest_completed_at == final_completion_at
    assert window.agent_activity_deferred_completed_at is None


@pytest.mark.asyncio
async def test_schedule_summary_waits_for_main_completion_after_async_subagent_notification() -> None:
    window = _make_window()
    base = datetime(2026, 6, 13, 10, 0, tzinfo=timezone.utc)
    window.agent_activity_burst_start_at = base
    window.agent_activity_latest_at = base

    events = [
        _subagent_call_event(created_at=base),
        _async_subagent_launch_event(created_at=base + timedelta(seconds=1)),
        _completion_event(created_at=base + timedelta(seconds=2)),
        _turn_duration_event(pending_count=1, created_at=base + timedelta(seconds=3)),
        _task_notification_event(created_at=base + timedelta(minutes=1)),
        _completion_event(created_at=base + timedelta(minutes=1, seconds=5)),
    ]

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
        for event in events:
            await scheduler.schedule_summary_after_agent_activity(
                session=None,
                window=window,
                event=event,
            )

    assert mock_sync.await_count == 1
    completed_at = base + timedelta(minutes=1, seconds=5)
    assert mock_sync.await_args.args[3] == completed_at
