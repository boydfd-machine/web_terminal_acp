# ruff: noqa: F401,F821
"""Executed into the terminal_work_status package globals."""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import and_, desc, func, literal_column, select, true
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.models import AiSession, Event, EventSourceType, VirtualWindow
from app.contexts.activity.api.schemas import WorkStatusOut
from app.contexts.activity.application.agent_activity_projection import (
    event_activity_time,
    event_is_agent_activity,
    event_is_agent_completion,
    event_is_agent_failure,
    event_is_agent_user_input,
)
from app.contexts.activity.application.window_runtime_tags import (
    agent_command_has_inline_task,
    agent_from_command,
)

AGENT_ABORT_IDLE_SECONDS = 60 * 60
AGENT_EVENT_LATE_ARRIVAL_SECONDS = 30
RECENT_ACTIVE_WINDOW_SECONDS = 10 * 60

TERMINAL_ACTIVITY_KINDS = (
    "terminal_input_command",
    "terminal_command_finished",
)
TERMINAL_COMMAND_KIND = "terminal_input_command"
TERMINAL_COMMAND_FINISHED_KIND = "terminal_command_finished"
AGENT_EVENT_SCAN_LIMIT_PER_WINDOW = 200
AGENT_ACTIVITY_SOURCE_TYPES = (
    EventSourceType.agent_tool_record.value,
    EventSourceType.codex_trace.value,
    EventSourceType.claude_jsonl.value,
)

FINISHED_AGENT_TASK_STATUS = "FINISHED"
ABORTED_AGENT_TASK_STATUS = "ABORTED"
FAILED_AGENT_TASK_STATUS = "FAILED"


@dataclass(frozen=True)
class TerminalWorkStatus:
    state: str
    label: str
    color: str
    last_activity_at: datetime | None = None
    last_working_activity_at: datetime | None = None
    source: str = "activity"
    manual_updated_at: datetime | None = None


@dataclass(frozen=True)
class AgentTaskStatus:
    state: str
    occurred_at: datetime


@dataclass(frozen=True)
class TreeWindowActivity:
    work_statuses: dict[UUID, TerminalWorkStatus]
    last_agent_task_completed_at: dict[UUID, datetime]
    last_agent_task_status: dict[UUID, AgentTaskStatus]
    latest_ai_sessions: dict[UUID, AiSession]
    latest_terminal_agents: dict[UUID, str]


@dataclass(frozen=True)
class _WindowActivityData:
    latest_activity: dict[UUID, datetime]
    latest_terminal_activity: dict[UUID, datetime]
    latest_working_activity: dict[UUID, datetime]
    latest_agent_active_at: dict[UUID, datetime]
    latest_agent_completed_at: dict[UUID, datetime]
    latest_agent_failed_at: dict[UUID, datetime]
    latest_agent_user_input_at: dict[UUID, datetime]
    latest_commands: dict[UUID, Event]
    finished_sequences: dict[UUID, dict[str, datetime]]
    failed_sequences: dict[UUID, dict[str, datetime]]

    def work_statuses(self, window_ids: list[UUID], *, now: datetime | None) -> dict[UUID, TerminalWorkStatus]:
        return {
            window_id: work_status_from_activity(
                now=now,
                last_activity_at=self.latest_activity.get(window_id),
                last_terminal_activity_at=self.latest_terminal_activity.get(window_id),
                last_agent_active_at=self.latest_agent_active_at.get(window_id),
                last_agent_output_at=self.latest_working_activity.get(window_id),
                last_agent_completed_at=self.latest_agent_completed_at.get(window_id),
                last_agent_failed_at=self.latest_agent_failed_at.get(window_id),
            )
            for window_id in window_ids
        }

    def latest_terminal_agents(self) -> dict[UUID, str]:
        latest: dict[UUID, str] = {}
        for window_id, event in self.latest_commands.items():
            agent = _event_agent(event)
            if agent is not None:
                latest[window_id] = agent
        return latest


@dataclass(frozen=True)
class _WindowAgentActivityState:
    latest_activity: dict[UUID, datetime]
    latest_completed_at: dict[UUID, datetime]
    latest_failed_at: dict[UUID, datetime]
    latest_user_input_at: dict[UUID, datetime]
    pending_subagent_count: dict[UUID, int]


def to_work_status_out(status: TerminalWorkStatus) -> WorkStatusOut:
    return WorkStatusOut(
        state=status.state,
        label=status.label,
        color=status.color,
        last_activity_at=status.last_activity_at,
        last_working_activity_at=status.last_working_activity_at,
        source=status.source,
        manual_updated_at=status.manual_updated_at,
    )


def long_idle_work_status(
    *,
    last_activity_at: datetime | None = None,
    last_working_activity_at: datetime | None = None,
) -> TerminalWorkStatus:
    return TerminalWorkStatus(
        state="LONG_IDLE",
        label="长时间没有工作了",
        color="gray",
        last_activity_at=last_activity_at,
        last_working_activity_at=last_working_activity_at,
    )


def work_status_from_activity(
    *,
    now: datetime | None = None,
    last_activity_at: datetime | None,
    last_working_activity_at: datetime | None = None,
    last_terminal_activity_at: datetime | None = None,
    last_agent_active_at: datetime | None = None,
    last_agent_started_at: datetime | None = None,
    last_agent_output_at: datetime | None = None,
    last_agent_completed_at: datetime | None = None,
    last_agent_failed_at: datetime | None = None,
) -> TerminalWorkStatus:
    current = _aware_utc(now or datetime.now(UTC))
    last_activity = _aware_utc(last_activity_at) if last_activity_at is not None else None
    last_terminal_activity = (
        _aware_utc(last_terminal_activity_at) if last_terminal_activity_at is not None else None
    )
    raw_agent_active_at = last_agent_active_at or last_agent_started_at
    last_agent_active = _aware_utc(raw_agent_active_at) if raw_agent_active_at is not None else None
    last_agent_output = _aware_utc(last_agent_output_at) if last_agent_output_at is not None else None
    last_agent_completed = (
        _aware_utc(last_agent_completed_at) if last_agent_completed_at is not None else None
    )
    last_agent_failed = _aware_utc(last_agent_failed_at) if last_agent_failed_at is not None else None
    if last_agent_output is not None:
        last_working_activity = last_agent_output
    elif last_working_activity_at is not None:
        last_working_activity = _aware_utc(last_working_activity_at)
    else:
        last_working_activity = None

    active_marker_running = (
        last_agent_active is not None
        and (last_agent_completed is None or last_agent_completed < last_agent_active)
        and (last_agent_failed is None or last_agent_failed < last_agent_active)
    )
    recent_unmanaged_output = (
        last_agent_active is None
        and last_agent_output is not None
        and (last_agent_completed is None or last_agent_completed < last_agent_output)
        and (last_agent_failed is None or last_agent_failed < last_agent_output)
        and (last_terminal_activity is None or last_terminal_activity < last_agent_output)
        and current - last_agent_output <= timedelta(seconds=RECENT_ACTIVE_WINDOW_SECONDS)
    )
    agent_active = active_marker_running or recent_unmanaged_output
    if agent_active:
        abort_reference = last_agent_output or last_agent_active
        if abort_reference is not None:
            abort_at = abort_reference + timedelta(seconds=AGENT_ABORT_IDLE_SECONDS)
            if current >= abort_at:
                if current - abort_at <= timedelta(seconds=RECENT_ACTIVE_WINDOW_SECONDS):
                    return TerminalWorkStatus(
                        state="ABORTED",
                        label="Agent 可能已中断",
                        color="red",
                        last_activity_at=last_activity,
                        last_working_activity_at=last_working_activity,
                    )
                agent_active = False
    if agent_active and last_agent_output is not None:
        return TerminalWorkStatus(
            state="WORKING",
            label="Agent 工作中",
            color="orange",
            last_activity_at=last_activity,
            last_working_activity_at=last_working_activity,
        )

    if (
        last_agent_failed is not None
        and (last_agent_active is None or last_agent_failed >= last_agent_active)
        and (last_agent_completed is None or last_agent_failed >= last_agent_completed)
        and current - last_agent_failed <= timedelta(seconds=RECENT_ACTIVE_WINDOW_SECONDS)
    ):
        return TerminalWorkStatus(
            state="FAILED",
            label="Agent 运行失败",
            color="red",
            last_activity_at=last_activity,
            last_working_activity_at=last_working_activity,
        )

    if (
        last_agent_completed is not None
        and (last_agent_active is None or last_agent_completed >= last_agent_active)
        and (last_agent_failed is None or last_agent_completed >= last_agent_failed)
        and current - last_agent_completed <= timedelta(seconds=RECENT_ACTIVE_WINDOW_SECONDS)
    ):
        return TerminalWorkStatus(
            state="FINISHED",
            label="Agent 已完成",
            color="green",
            last_activity_at=last_activity,
            last_working_activity_at=last_working_activity,
        )

    if last_activity is not None and current - last_activity <= timedelta(seconds=RECENT_ACTIVE_WINDOW_SECONDS):
        return TerminalWorkStatus(
            state="RECENT_ACTIVE",
            label="Terminal 活跃",
            color="green",
            last_activity_at=last_activity,
            last_working_activity_at=last_working_activity,
        )

    return long_idle_work_status(
        last_activity_at=last_activity,
        last_working_activity_at=last_working_activity,
    )


async def load_tree_window_activity(
    session: AsyncSession,
    client_id: UUID,
    window_ids: list[UUID],
    *,
    now: datetime | None = None,
    include_runtime_tags: bool = True,
) -> TreeWindowActivity:
    if not window_ids:
        return TreeWindowActivity({}, {}, {}, {}, {})

    activity, latest_ai_sessions = await _load_tree_activity_bundle(
        session,
        client_id,
        window_ids,
        now=now,
        include_runtime_tags=include_runtime_tags,
    )
    work_statuses = activity.work_statuses(window_ids, now=now)
    manual_overrides = await _manual_work_status_overrides(session, client_id, window_ids)
    work_statuses = _apply_manual_work_statuses(work_statuses, manual_overrides)
    last_agent_task_completed_at = _apply_manual_completed_at(
        _last_agent_task_completed_at_from_activity(
            window_ids,
            activity=activity,
        ),
        manual_overrides,
    )
    last_agent_task_status = _apply_manual_task_statuses(
        _last_agent_task_status_from_activity(
            window_ids,
            activity=activity,
            now=now,
        ),
        manual_overrides,
    )
    return TreeWindowActivity(
        work_statuses=work_statuses,
        last_agent_task_completed_at=last_agent_task_completed_at,
        last_agent_task_status=last_agent_task_status,
        latest_ai_sessions=latest_ai_sessions,
        latest_terminal_agents=activity.latest_terminal_agents(),
    )


async def load_work_statuses(
    session: AsyncSession,
    client_id: UUID,
    window_ids: list[UUID],
    *,
    now: datetime | None = None,
    include_manual_override: bool = True,
) -> dict[UUID, TerminalWorkStatus]:
    if not window_ids:
        return {}

    activity = await _load_window_activity_data(session, client_id, window_ids, now=now)
    work_statuses = activity.work_statuses(window_ids, now=now)
    if not include_manual_override:
        return work_statuses
    return _apply_manual_work_statuses(
        work_statuses,
        await _manual_work_status_overrides(session, client_id, window_ids),
    )


async def load_work_status(
    session: AsyncSession,
    client_id: UUID,
    window_id: UUID,
    *,
    now: datetime | None = None,
    include_manual_override: bool = True,
) -> TerminalWorkStatus:
    statuses = await load_work_statuses(
        session,
        client_id,
        [window_id],
        now=now,
        include_manual_override=include_manual_override,
    )
    return statuses.get(window_id, long_idle_work_status())


async def load_last_agent_task_completed_at_by_window(
    session: AsyncSession,
    client_id: UUID,
    window_ids: list[UUID],
    *,
    now: datetime | None = None,
    include_manual_override: bool = True,
) -> dict[UUID, datetime]:
    if not window_ids:
        return {}

    activity = await _load_window_activity_data(session, client_id, window_ids, now=now)
    completed_at = _last_agent_task_completed_at_from_activity(
        window_ids,
        activity=activity,
    )
    if not include_manual_override:
        return completed_at
    return _apply_manual_completed_at(
        completed_at,
        await _manual_work_status_overrides(session, client_id, window_ids),
    )


async def _load_tree_activity_bundle(
    session: AsyncSession,
    client_id: UUID,
    window_ids: list[UUID],
    *,
    now: datetime | None = None,
    include_runtime_tags: bool = True,
) -> tuple[_WindowActivityData, dict[UUID, AiSession]]:
    activity = await _load_window_activity_data(session, client_id, window_ids, now=now)
    if include_runtime_tags:
        latest_ai_sessions = await _latest_ai_sessions_by_window(session, client_id, window_ids)
    else:
        latest_ai_sessions = {}
    return activity, latest_ai_sessions


async def _load_window_activity_data(
    session: AsyncSession,
    client_id: UUID,
    window_ids: list[UUID],
    *,
    now: datetime | None = None,
) -> _WindowActivityData:
    current = _aware_utc(now or datetime.now(UTC))
    agent_activity = await _agent_activity_state_by_window(session, client_id, window_ids)
    latest_commands = await _latest_events_by_window(
        session,
        client_id,
        window_ids,
        kind=TERMINAL_COMMAND_KIND,
    )
    latest_terminal_events = await _latest_created_at_by_window_and_kinds(
        session,
        client_id,
        window_ids,
        kinds=TERMINAL_ACTIVITY_KINDS,
    )
    latest_terminal_output = await _latest_terminal_output_activity_by_window(
        session,
        client_id,
        window_ids,
    )
    agent_command_windows = [
        window_id
        for window_id, event in latest_commands.items()
        if _event_agent(event) is not None
    ]
    command_finishes = await _finished_command_sequences_by_window(
        session,
        client_id,
        agent_command_windows,
        latest_commands=latest_commands,
    )
    finished_sequences = command_finishes.finished
    failed_sequences = command_finishes.failed
    latest_agent_user_input_at = dict(agent_activity.latest_user_input_at)
    if _dialect_name(session) != "postgresql":
        projected_user_input_window_ids = [
            window_id
            for window_id in window_ids
            if window_id in agent_activity.latest_activity
            and window_id not in latest_agent_user_input_at
            and (
                (command := latest_commands.get(window_id)) is None
                or (_event_agent(command) is not None and not _event_has_agent_task(command))
            )
        ]
        latest_agent_user_input_at.update(
            await _latest_agent_user_input_at_by_window(
                session,
                client_id,
                projected_user_input_window_ids,
            )
        )
    latest_working_activity = _merge_latest_working_activity(
        window_ids,
        latest_commands=latest_commands,
        latest_ai=agent_activity.latest_activity,
        latest_agent_user_input_at=latest_agent_user_input_at,
        pending_subagent_count=agent_activity.pending_subagent_count,
        finished_sequences=finished_sequences,
        now=current,
    )
    latest_agent_active_at = _latest_agent_active_at(
        window_ids,
        latest_commands=latest_commands,
        latest_ai=agent_activity.latest_activity,
        latest_agent_user_input_at=latest_agent_user_input_at,
        finished_sequences=finished_sequences,
    )
    latest_agent_completed_at = agent_activity.latest_completed_at
    latest_agent_failed_at = _merge_latest_created_at(
        agent_activity.latest_failed_at,
        _latest_failed_agent_command_at(window_ids, failed_sequences=failed_sequences),
    )
    latest_terminal_activity = _merge_latest_created_at(latest_terminal_events, latest_terminal_output)
    latest_activity = _merge_latest_created_at(
        latest_terminal_activity,
        latest_working_activity,
        latest_agent_completed_at,
        latest_agent_failed_at,
    )

    return _WindowActivityData(
        latest_activity=latest_activity,
        latest_terminal_activity=latest_terminal_activity,
        latest_working_activity=latest_working_activity,
        latest_agent_active_at=latest_agent_active_at,
        latest_agent_completed_at=latest_agent_completed_at,
        latest_agent_failed_at=latest_agent_failed_at,
        latest_agent_user_input_at=latest_agent_user_input_at,
        latest_commands=latest_commands,
        finished_sequences=finished_sequences,
        failed_sequences=failed_sequences,
    )


async def _recent_agent_events_by_window(
    session: AsyncSession,
    client_id: UUID,
    window_ids: list[UUID],
) -> dict[UUID, list[Event]]:
    if not window_ids:
        return {}

    if _dialect_name(session) == "postgresql":
        return await _recent_agent_events_by_window_postgresql(session, client_id, window_ids)
    return await _recent_agent_events_by_window_ranked(session, client_id, window_ids)
