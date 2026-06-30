# ruff: noqa: F401,F821
"""Executed into the terminal_work_status package globals."""

from importlib import import_module
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import VirtualWindow

_status_service = import_module("app.contexts.activity.application.terminal_work_status.status_service")
globals().update(
    {name: value for name, value in _status_service.__dict__.items() if not name.startswith("__")}
)

MANUAL_WORK_STATUS_STATES = frozenset(
    {"LONG_IDLE", "RECENT_ACTIVE", "WORKING", "FINISHED", "ABORTED", "FAILED"}
)
_MANUAL_WORK_STATUS_META = {
    "LONG_IDLE": ("长时间没有工作了", "gray"),
    "RECENT_ACTIVE": ("Terminal 活跃", "green"),
    "WORKING": ("Agent 工作中", "orange"),
    "FINISHED": ("Agent 已完成", "green"),
    "ABORTED": ("Agent 可能已中断", "red"),
    "FAILED": ("Agent 运行失败", "red"),
}
_MANUAL_TASK_STATUS_STATES = frozenset(
    {FINISHED_AGENT_TASK_STATUS, ABORTED_AGENT_TASK_STATUS, FAILED_AGENT_TASK_STATUS}
)


def manual_work_status_from_state(
    state: str,
    *,
    base_status: TerminalWorkStatus,
    updated_at: datetime | None,
) -> TerminalWorkStatus:
    normalized = state.upper()
    if normalized not in MANUAL_WORK_STATUS_STATES:
        raise ValueError(f"unsupported manual work status: {state}")
    label, color = _MANUAL_WORK_STATUS_META[normalized]
    return TerminalWorkStatus(
        state=normalized,
        label=label,
        color=color,
        last_activity_at=base_status.last_activity_at,
        last_working_activity_at=base_status.last_working_activity_at,
        source="manual",
        manual_updated_at=_aware_utc(updated_at) if updated_at is not None else None,
    )


async def set_manual_work_status(
    session: AsyncSession,
    window: VirtualWindow,
    state: str | None,
    *,
    now: datetime | None = None,
) -> TerminalWorkStatus:
    current_status = await load_work_status(
        session,
        window.client_id,
        window.id,
        now=now,
        include_manual_override=False,
    )
    if state is None:
        window.manual_work_status_state = None
        window.manual_work_status_updated_at = None
        await session.flush()
        return current_status

    normalized = state.upper()
    if normalized not in MANUAL_WORK_STATUS_STATES:
        raise ValueError(f"unsupported manual work status: {state}")
    updated_at = _aware_utc(now or datetime.now(UTC))
    window.manual_work_status_state = normalized
    window.manual_work_status_updated_at = updated_at
    await session.flush()
    return manual_work_status_from_state(
        normalized,
        base_status=current_status,
        updated_at=updated_at,
    )


async def _manual_work_status_overrides(
    session: AsyncSession,
    client_id: UUID,
    window_ids: list[UUID],
) -> dict[UUID, tuple[str, datetime | None]]:
    if not window_ids:
        return {}
    rows = await session.execute(
        select(
            VirtualWindow.id,
            VirtualWindow.manual_work_status_state,
            VirtualWindow.manual_work_status_updated_at,
        ).where(
            VirtualWindow.client_id == client_id,
            VirtualWindow.id.in_(window_ids),
            VirtualWindow.manual_work_status_state.is_not(None),
        )
    )
    overrides: dict[UUID, tuple[str, datetime | None]] = {}
    for window_id, state, updated_at in rows:
        if state in MANUAL_WORK_STATUS_STATES:
            overrides[window_id] = (state, updated_at)
    return overrides


def _apply_manual_work_statuses(
    work_statuses: dict[UUID, TerminalWorkStatus],
    overrides: dict[UUID, tuple[str, datetime | None]],
) -> dict[UUID, TerminalWorkStatus]:
    if not overrides:
        return work_statuses
    next_statuses: dict[UUID, TerminalWorkStatus] = {}
    for window_id, status in work_statuses.items():
        override = overrides.get(window_id)
        next_statuses[window_id] = (
            manual_work_status_from_state(
                override[0],
                base_status=status,
                updated_at=override[1],
            )
            if override is not None
            else status
        )
    return next_statuses


def _manual_task_statuses(
    overrides: dict[UUID, tuple[str, datetime | None]],
) -> dict[UUID, AgentTaskStatus]:
    task_statuses: dict[UUID, AgentTaskStatus] = {}
    for window_id, (state, updated_at) in overrides.items():
        if state not in _MANUAL_TASK_STATUS_STATES:
            continue
        task_statuses[window_id] = AgentTaskStatus(
            state=state,
            occurred_at=_aware_utc(updated_at) if updated_at is not None else datetime.now(UTC),
        )
    return task_statuses


def _apply_manual_task_statuses(
    base_statuses: dict[UUID, AgentTaskStatus],
    overrides: dict[UUID, tuple[str, datetime | None]],
) -> dict[UUID, AgentTaskStatus]:
    if not overrides:
        return base_statuses
    next_statuses = {
        window_id: status
        for window_id, status in base_statuses.items()
        if window_id not in overrides
    }
    next_statuses.update(_manual_task_statuses(overrides))
    return next_statuses


def _apply_manual_completed_at(
    base_completed_at: dict[UUID, datetime],
    overrides: dict[UUID, tuple[str, datetime | None]],
) -> dict[UUID, datetime]:
    if not overrides:
        return base_completed_at
    next_completed_at = {
        window_id: completed_at
        for window_id, completed_at in base_completed_at.items()
        if window_id not in overrides
    }
    for window_id, (state, updated_at) in overrides.items():
        if state == FINISHED_AGENT_TASK_STATUS and updated_at is not None:
            next_completed_at[window_id] = _aware_utc(updated_at)
    return next_completed_at
