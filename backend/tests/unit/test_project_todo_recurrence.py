from datetime import UTC, datetime

import pytest

from app.contexts.workspace.domain.project_todo_recurrence import (
    ProjectTodoSchedule,
    next_cron_trigger_after,
    project_todo_schedule_enabled,
    validate_project_todo_schedule,
)


def test_next_cron_trigger_after_supports_ranges_steps_and_weekday_alias() -> None:
    next_trigger = next_cron_trigger_after(
        "*/15 9-10 * * 1,7",
        datetime(2026, 6, 7, 8, 59, tzinfo=UTC),
    )

    assert next_trigger == datetime(2026, 6, 7, 9, 0, tzinfo=UTC)


def test_cron_trigger_requires_periodic_card_and_expression() -> None:
    with pytest.raises(ValueError, match="periodic"):
        validate_project_todo_schedule(ProjectTodoSchedule("ONCE", "NEW_TERMINAL", "CRON", "0 9 * * *"))

    with pytest.raises(ValueError, match="cron expression"):
        validate_project_todo_schedule(ProjectTodoSchedule("PERIODIC", "NEW_TERMINAL", "CRON", None))


def test_cron_expression_is_rejected_for_manual_trigger() -> None:
    with pytest.raises(ValueError, match="only valid"):
        validate_project_todo_schedule(ProjectTodoSchedule("PERIODIC", "NEW_TERMINAL", "MANUAL", "0 9 * * *"))


def test_cron_schedule_can_be_disabled_without_losing_expression() -> None:
    schedule = ProjectTodoSchedule(
        "PERIODIC",
        "NEW_TERMINAL",
        "CRON",
        "0 9 * * *",
        schedule_enabled=False,
    )

    validate_project_todo_schedule(schedule)

    assert project_todo_schedule_enabled(schedule) is False


def test_manual_schedule_cannot_be_enabled() -> None:
    with pytest.raises(ValueError, match="cron-triggered"):
        validate_project_todo_schedule(
            ProjectTodoSchedule("PERIODIC", "NEW_TERMINAL", "MANUAL", None, schedule_enabled=True)
        )
