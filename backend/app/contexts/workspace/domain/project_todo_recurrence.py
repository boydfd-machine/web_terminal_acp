from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

PROJECT_TODO_EXECUTION_ONCE = "ONCE"
PROJECT_TODO_EXECUTION_PERIODIC = "PERIODIC"
PROJECT_TODO_EXECUTION_KINDS = {
    PROJECT_TODO_EXECUTION_ONCE,
    PROJECT_TODO_EXECUTION_PERIODIC,
}

PROJECT_TODO_TERMINAL_NEW = "NEW_TERMINAL"
PROJECT_TODO_TERMINAL_REUSE = "REUSE_LATEST"
PROJECT_TODO_TERMINAL_POLICIES = {
    PROJECT_TODO_TERMINAL_NEW,
    PROJECT_TODO_TERMINAL_REUSE,
}

PROJECT_TODO_TRIGGER_MANUAL = "MANUAL"
PROJECT_TODO_TRIGGER_CRON = "CRON"
PROJECT_TODO_TRIGGER_STRATEGIES = {
    PROJECT_TODO_TRIGGER_MANUAL,
    PROJECT_TODO_TRIGGER_CRON,
}

PROJECT_TODO_RUN_STARTING = "STARTING"
PROJECT_TODO_RUN_DISPATCHED = "DISPATCHED"
PROJECT_TODO_RUN_COMPLETED = "COMPLETED"
PROJECT_TODO_RUN_FAILED = "FAILED"

_CRON_SEARCH_LIMIT_MINUTES = 366 * 24 * 60


@dataclass(frozen=True)
class ProjectTodoSchedule:
    execution_kind: str
    terminal_policy: str
    trigger_strategy: str
    cron_expression: str | None
    schedule_enabled: bool | None = None


def validate_project_todo_schedule(schedule: ProjectTodoSchedule) -> None:
    if schedule.execution_kind not in PROJECT_TODO_EXECUTION_KINDS:
        raise ValueError("invalid todo execution kind")
    if schedule.terminal_policy not in PROJECT_TODO_TERMINAL_POLICIES:
        raise ValueError("invalid todo terminal policy")
    if schedule.trigger_strategy not in PROJECT_TODO_TRIGGER_STRATEGIES:
        raise ValueError("invalid todo trigger strategy")
    schedule_enabled = _schedule_enabled(schedule)
    cron_expression = (schedule.cron_expression or "").strip()
    if schedule.trigger_strategy == PROJECT_TODO_TRIGGER_CRON:
        if schedule.execution_kind != PROJECT_TODO_EXECUTION_PERIODIC:
            raise ValueError("cron trigger requires a periodic todo")
        if not cron_expression:
            raise ValueError("cron trigger requires a cron expression")
        parse_cron_expression(cron_expression)
    elif cron_expression:
        raise ValueError("cron expression is only valid for cron-triggered todos")
    if schedule_enabled and schedule.trigger_strategy != PROJECT_TODO_TRIGGER_CRON:
        raise ValueError("schedule can only be enabled for cron-triggered todos")


def project_todo_schedule_enabled(schedule: ProjectTodoSchedule) -> bool:
    return _schedule_enabled(schedule) and schedule.trigger_strategy == PROJECT_TODO_TRIGGER_CRON


def next_cron_trigger_after(expression: str, after: datetime) -> datetime:
    parsed = parse_cron_expression(expression)
    cursor = _truncate_to_minute(_ensure_aware(after)) + timedelta(minutes=1)
    for _ in range(_CRON_SEARCH_LIMIT_MINUTES):
        if parsed.matches(cursor):
            return cursor
        cursor += timedelta(minutes=1)
    raise ValueError("cron expression has no trigger within one year")


def _schedule_enabled(schedule: ProjectTodoSchedule) -> bool:
    return schedule.schedule_enabled if schedule.schedule_enabled is not None else schedule.trigger_strategy == PROJECT_TODO_TRIGGER_CRON


def parse_cron_expression(expression: str) -> "_ParsedCron":
    fields = expression.split()
    if len(fields) != 5:
        raise ValueError("cron expression must have five fields")
    minute = _parse_cron_field(fields[0], 0, 59)
    hour = _parse_cron_field(fields[1], 0, 23)
    day = _parse_cron_field(fields[2], 1, 31)
    month = _parse_cron_field(fields[3], 1, 12)
    weekday = _parse_cron_field(fields[4], 0, 7)
    return _ParsedCron(minute, hour, day, month, {0 if value == 7 else value for value in weekday})


@dataclass(frozen=True)
class _ParsedCron:
    minute: set[int]
    hour: set[int]
    day: set[int]
    month: set[int]
    weekday: set[int]

    def matches(self, value: datetime) -> bool:
        return (
            value.minute in self.minute
            and value.hour in self.hour
            and value.day in self.day
            and value.month in self.month
            and _cron_weekday(value) in self.weekday
        )


def _parse_cron_field(value: str, minimum: int, maximum: int) -> set[int]:
    values: set[int] = set()
    for part in value.split(","):
        values.update(_parse_cron_part(part.strip(), minimum, maximum))
    if not values:
        raise ValueError("cron field is empty")
    return values


def _parse_cron_part(part: str, minimum: int, maximum: int) -> set[int]:
    if not part:
        raise ValueError("cron field contains an empty segment")
    base, step = _split_step(part)
    if base == "*":
        start = minimum
        end = maximum
    elif "-" in base:
        start_text, end_text = base.split("-", 1)
        start = _parse_int(start_text)
        end = _parse_int(end_text)
    else:
        start = _parse_int(base)
        end = start
    if step <= 0:
        raise ValueError("cron step must be positive")
    if start < minimum or end > maximum or start > end:
        raise ValueError("cron field value is out of range")
    return set(range(start, end + 1, step))


def _split_step(value: str) -> tuple[str, int]:
    if "/" not in value:
        return value, 1
    base, step_text = value.split("/", 1)
    return base, _parse_int(step_text)


def _parse_int(value: str) -> int:
    try:
        return int(value)
    except ValueError as exc:
        raise ValueError("cron field value must be numeric") from exc


def _cron_weekday(value: datetime) -> int:
    return (value.weekday() + 1) % 7


def _truncate_to_minute(value: datetime) -> datetime:
    return value.replace(second=0, microsecond=0)


def _ensure_aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)
