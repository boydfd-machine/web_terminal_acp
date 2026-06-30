from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta

from app.contexts.activity.domain.terminal_time_range import (
    TERMINAL_TIME_RANGE_DAYS,
    TerminalTimeRange,
    TerminalTimeRangeError,
)

PROJECT_TODO_CUSTOM_DATE_RANGE = "custom"


class ProjectTodoDateFilterError(ValueError):
    pass


@dataclass(frozen=True)
class ProjectTodoUpdatedBounds:
    start: datetime | None = None
    end: datetime | None = None


def project_todo_updated_bounds(
    range_value: str | None,
    *,
    start_date: date | None = None,
    end_date: date | None = None,
    now: datetime | None = None,
) -> ProjectTodoUpdatedBounds:
    if range_value in (None, "", "all"):
        return ProjectTodoUpdatedBounds()

    if range_value == PROJECT_TODO_CUSTOM_DATE_RANGE:
        if start_date is not None and end_date is not None and start_date > end_date:
            raise ProjectTodoDateFilterError("start_date must be before or equal to end_date")
        return ProjectTodoUpdatedBounds(
            start=_start_of_day(start_date),
            end=_start_of_day(end_date + timedelta(days=1)) if end_date is not None else None,
        )

    try:
        return ProjectTodoUpdatedBounds(start=TerminalTimeRange(range_value).visible_since(now=now))
    except TerminalTimeRangeError as exc:
        allowed = ", ".join([*TERMINAL_TIME_RANGE_DAYS.keys(), "all", PROJECT_TODO_CUSTOM_DATE_RANGE])
        raise ProjectTodoDateFilterError(
            f"invalid project todo date range; expected one of: {allowed}"
        ) from exc


def _start_of_day(value: date | None) -> datetime | None:
    if value is None:
        return None
    return datetime.combine(value, time.min, tzinfo=UTC)
