from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.contexts.activity.application.terminal_work_status import (
    TerminalWorkStatus,
    load_work_statuses,
    work_status_from_activity,
)
from app.contexts.activity.application.agent_activity_projection import event_is_agent_activity
from app.models import Event, VirtualWindow


async def load_projected_work_statuses(
    session: AsyncSession,
    client_id: UUID,
    window_ids: list[UUID],
    *,
    now: datetime | None = None,
) -> dict[UUID, TerminalWorkStatus]:
    unique_window_ids = list(dict.fromkeys(window_ids))
    if not unique_window_ids:
        return {}
    if _dialect_name(session) != "postgresql":
        return await load_work_statuses(session, client_id, unique_window_ids, now=now)

    rows = await session.execute(
        select(
            VirtualWindow.id,
            VirtualWindow.terminal_last_output_at,
            VirtualWindow.agent_activity_latest_at,
            VirtualWindow.agent_activity_latest_event_id,
            VirtualWindow.agent_activity_latest_completed_at,
            VirtualWindow.agent_activity_latest_user_input_at,
            VirtualWindow.agent_activity_pending_subagent_count,
            VirtualWindow.manual_work_status_state,
            VirtualWindow.manual_work_status_updated_at,
        ).where(
            VirtualWindow.client_id == client_id,
            VirtualWindow.id.in_(unique_window_ids),
        )
    )
    projection_rows = rows.all()
    stale_latest_event_ids_by_window = {
        window_id: latest_event_id
        for (
            window_id,
            _terminal_at,
            agent_at,
            latest_event_id,
            completed_at,
            _user_input_at,
            _pending_subagent_count,
            _manual_state,
            _manual_at,
        )
        in projection_rows
        if latest_event_id is not None
        and agent_at is not None
        and completed_at is not None
        and _aware_utc(agent_at) > _aware_utc(completed_at)
    }
    stale_latest_event_ids = set(stale_latest_event_ids_by_window.values())
    stale_latest_event_ids -= await _agent_activity_event_ids(session, stale_latest_event_ids_by_window)
    statuses: dict[UUID, TerminalWorkStatus] = {}
    for (
        window_id,
        terminal_at,
        agent_at,
        latest_event_id,
        completed_at,
        user_input_at,
        pending_subagent_count,
        manual_state,
        manual_at,
    ) in projection_rows:
        if latest_event_id in stale_latest_event_ids:
            agent_at = completed_at
        agent_output_at = _projected_agent_output_at(
            agent_at,
            user_input_at,
            pending_subagent_count,
        )
        status = work_status_from_activity(
            now=now,
            last_activity_at=_latest(terminal_at, agent_at, completed_at),
            last_terminal_activity_at=terminal_at,
            last_agent_active_at=agent_at,
            last_agent_output_at=agent_output_at,
            last_agent_completed_at=completed_at,
        )
        if manual_state:
            status = _manual_work_status_from_state(manual_state, base_status=status, updated_at=manual_at)
        statuses[window_id] = status
    return statuses


async def _agent_activity_event_ids(
    session: AsyncSession,
    event_ids_by_window: dict[UUID, UUID],
) -> set[UUID]:
    event_ids = set(event_ids_by_window.values())
    if not event_ids:
        return set()
    window_ids_by_event = {event_id: window_id for window_id, event_id in event_ids_by_window.items()}
    rows = await session.scalars(select(Event).where(Event.id.in_(event_ids)))
    return {
        event.id
        for event in rows
        if event.virtual_window_id == window_ids_by_event.get(event.id) and event_is_agent_activity(event)
    }


def _projected_agent_output_at(
    agent_at: datetime | None,
    user_input_at: datetime | None,
    pending_subagent_count: int | None,
) -> datetime | None:
    if agent_at is None:
        return None
    if int(pending_subagent_count or 0) > 0:
        return agent_at
    if user_input_at is None:
        return agent_at
    if _aware_utc(agent_at) > _aware_utc(user_input_at):
        return agent_at
    return None


def _latest(*values: datetime | None) -> datetime | None:
    aware_values = [_aware_utc(value) for value in values if value is not None]
    return max(aware_values) if aware_values else None


def _manual_work_status_from_state(
    state: str,
    *,
    base_status: TerminalWorkStatus,
    updated_at: datetime | None,
) -> TerminalWorkStatus:
    normalized = state.upper()
    label, color = {
        "LONG_IDLE": ("长时间没有工作了", "gray"),
        "RECENT_ACTIVE": ("Terminal 活跃", "green"),
        "WORKING": ("Agent 工作中", "orange"),
        "FINISHED": ("Agent 已完成", "green"),
        "ABORTED": ("Agent 可能已中断", "red"),
        "FAILED": ("Agent 运行失败", "red"),
    }.get(normalized, ("长时间没有工作了", "gray"))
    return TerminalWorkStatus(
        state=normalized,
        label=label,
        color=color,
        last_activity_at=base_status.last_activity_at,
        last_working_activity_at=base_status.last_working_activity_at,
        source="manual",
        manual_updated_at=_aware_utc(updated_at) if updated_at is not None else None,
    )


def _aware_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _dialect_name(session: AsyncSession) -> str:
    return session.get_bind().dialect.name
