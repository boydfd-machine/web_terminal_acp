# ruff: noqa: F821
"""Executed into the terminal_work_status package globals."""

from importlib import import_module

_status_service = import_module("app.contexts.activity.application.terminal_work_status.status_service")
globals().update(
    {name: value for name, value in _status_service.__dict__.items() if not name.startswith("__")}
)


def _last_agent_task_completed_at_from_activity(
    window_ids: list[UUID],
    *,
    activity: _WindowActivityData,
) -> dict[UUID, datetime]:
    latest: dict[UUID, datetime] = {}
    for window_id in window_ids:
        completed_at = activity.latest_agent_completed_at.get(window_id)
        if completed_at is None:
            continue
        active_at = activity.latest_agent_active_at.get(window_id)
        if active_at is not None and _aware_utc(active_at) > _aware_utc(completed_at):
            continue
        failed_at = activity.latest_agent_failed_at.get(window_id)
        if failed_at is not None and _aware_utc(failed_at) >= _aware_utc(completed_at):
            continue
        latest[window_id] = completed_at
    return latest


def _last_agent_task_status_from_activity(
    window_ids: list[UUID],
    *,
    activity: _WindowActivityData,
    now: datetime | None,
) -> dict[UUID, AgentTaskStatus]:
    current = _aware_utc(now or datetime.now(UTC))
    latest: dict[UUID, AgentTaskStatus] = {}
    for window_id in window_ids:
        failed_at = activity.latest_agent_failed_at.get(window_id)
        completed_at = activity.latest_agent_completed_at.get(window_id)
        active_at = activity.latest_agent_active_at.get(window_id)
        if failed_at is not None and (
            (completed_at is None or _aware_utc(failed_at) >= _aware_utc(completed_at))
            and (active_at is None or _aware_utc(failed_at) >= _aware_utc(active_at))
        ):
            latest[window_id] = AgentTaskStatus(
                state=FAILED_AGENT_TASK_STATUS,
                occurred_at=_aware_utc(failed_at),
            )
            continue
        if active_at is not None and (completed_at is None or _aware_utc(active_at) > _aware_utc(completed_at)):
            abort_reference = activity.latest_working_activity.get(window_id) or active_at
            abort_at = _aware_utc(abort_reference) + timedelta(seconds=AGENT_ABORT_IDLE_SECONDS)
            if current >= abort_at:
                latest[window_id] = AgentTaskStatus(
                    state=ABORTED_AGENT_TASK_STATUS,
                    occurred_at=abort_at,
                )
            continue

        if completed_at is not None:
            latest[window_id] = AgentTaskStatus(
                state=FINISHED_AGENT_TASK_STATUS,
                occurred_at=_aware_utc(completed_at),
            )
    return latest
