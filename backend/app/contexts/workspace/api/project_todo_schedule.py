from __future__ import annotations

from app.contexts.workspace.api.schemas import ProjectTodoCreateIn, ProjectTodoPatchIn
from app.contexts.workspace.domain.project_todo_recurrence import ProjectTodoSchedule
from app.models import ProjectTodo


def project_todo_schedule_from_create(payload: ProjectTodoCreateIn) -> ProjectTodoSchedule:
    return ProjectTodoSchedule(
        execution_kind=payload.execution_kind,
        terminal_policy=payload.terminal_policy,
        trigger_strategy=payload.trigger_strategy,
        cron_expression=payload.cron_expression,
        schedule_enabled=payload.schedule_enabled,
    )


def project_todo_schedule_was_patched(provided_fields: set[str]) -> bool:
    return bool(
        {
            "execution_kind",
            "terminal_policy",
            "trigger_strategy",
            "cron_expression",
            "schedule_enabled",
        }
        & provided_fields
    )


def project_todo_schedule_from_patch(
    todo: ProjectTodo,
    payload: ProjectTodoPatchIn,
    provided_fields: set[str],
) -> ProjectTodoSchedule:
    execution_kind = payload.execution_kind if payload.execution_kind is not None else todo.execution_kind
    terminal_policy = payload.terminal_policy if payload.terminal_policy is not None else todo.terminal_policy
    trigger_strategy = payload.trigger_strategy if payload.trigger_strategy is not None else todo.trigger_strategy
    cron_expression = payload.cron_expression if "cron_expression" in provided_fields else todo.cron_expression
    schedule_enabled = _patched_schedule_enabled(todo, payload, provided_fields, trigger_strategy)
    if execution_kind == "ONCE" and "trigger_strategy" not in provided_fields:
        trigger_strategy = "MANUAL"
        schedule_enabled = False
    if trigger_strategy != "CRON":
        schedule_enabled = False
        if "cron_expression" not in provided_fields:
            cron_expression = None
    return ProjectTodoSchedule(
        execution_kind=execution_kind,
        terminal_policy=terminal_policy,
        trigger_strategy=trigger_strategy,
        cron_expression=cron_expression,
        schedule_enabled=schedule_enabled,
    )


def _patched_schedule_enabled(
    todo: ProjectTodo,
    payload: ProjectTodoPatchIn,
    provided_fields: set[str],
    trigger_strategy: str,
) -> bool:
    if "schedule_enabled" in provided_fields:
        return bool(payload.schedule_enabled)
    if "trigger_strategy" in provided_fields:
        return trigger_strategy == "CRON"
    return bool(todo.schedule_enabled)
