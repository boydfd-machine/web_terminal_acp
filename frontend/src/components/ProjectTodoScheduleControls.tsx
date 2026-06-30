import { useEffect, useState } from "react";

import { useI18n } from "../i18n";
import type { ProjectTodo, ProjectTodoListItem, ProjectTodoTriggerStrategy } from "../types";
import { formatProjectTodoDate } from "./projectTodoDisplay";

export type ProjectTodoScheduleInput = {
  trigger_strategy: ProjectTodoTriggerStrategy;
  cron_expression: string | null;
  schedule_enabled: boolean;
};

type ProjectTodoScheduleToggleProps = {
  ariaLabel?: string;
  busy: boolean;
  todo: ProjectTodoListItem;
  onToggleSchedule: (todo: ProjectTodoListItem, enabled: boolean) => void;
};

export function ProjectTodoScheduleToggle({
  ariaLabel,
  busy,
  todo,
  onToggleSchedule
}: ProjectTodoScheduleToggleProps) {
  const { t } = useI18n();
  if (!projectTodoHasCronSchedule(todo)) {
    return null;
  }
  return (
    <label
      className="project-todo-schedule-toggle"
      title={todo.schedule_enabled ? t("projectTodo.schedule.scheduled") : t("projectTodo.schedule.paused")}
      onClick={(event) => event.stopPropagation()}
      onMouseDown={(event) => event.stopPropagation()}
    >
      <input
        type="checkbox"
        checked={todo.schedule_enabled}
        disabled={busy}
        aria-label={ariaLabel ?? t(todo.schedule_enabled ? "projectTodo.schedule.disableFor" : "projectTodo.schedule.enableFor", { title: todo.title })}
        onChange={(event) => onToggleSchedule(todo, event.target.checked)}
      />
      <span aria-hidden="true" />
    </label>
  );
}

export function ProjectTodoSchedulePanel({
  busy,
  todo,
  onSaveSchedule
}: {
  busy: boolean;
  todo: ProjectTodo;
  onSaveSchedule: (todo: ProjectTodo, input: ProjectTodoScheduleInput) => void;
}) {
  const { t } = useI18n();
  const [triggerStrategy, setTriggerStrategy] = useState<ProjectTodoTriggerStrategy>(todo.trigger_strategy);
  const [cronExpression, setCronExpression] = useState(todo.cron_expression ?? "");
  const [scheduleEnabled, setScheduleEnabled] = useState(todo.schedule_enabled);

  useEffect(() => {
    setTriggerStrategy(todo.trigger_strategy);
    setCronExpression(todo.cron_expression ?? "");
    setScheduleEnabled(todo.schedule_enabled);
  }, [todo.id, todo.trigger_strategy, todo.cron_expression, todo.schedule_enabled]);

  if (todo.execution_kind !== "PERIODIC") {
    return null;
  }

  const cronActive = triggerStrategy === "CRON";
  const trimmedCron = cronExpression.trim();
  const input = cronActive
    ? {
        trigger_strategy: "CRON" as const,
        cron_expression: trimmedCron,
        schedule_enabled: scheduleEnabled
      }
    : {
        trigger_strategy: "MANUAL" as const,
        cron_expression: null,
        schedule_enabled: false
      };
  const dirty = input.trigger_strategy !== todo.trigger_strategy
    || input.cron_expression !== todo.cron_expression
    || input.schedule_enabled !== todo.schedule_enabled;
  const canSave = dirty && !busy && (!cronActive || trimmedCron.length > 0);

  return (
    <section className="project-todo-schedule-panel" aria-label={t("projectTodo.schedule.periodicSchedule")}>
      <header>
        <strong>{t("projectTodo.schedule.schedule")}</strong>
        <ProjectTodoScheduleToggle
          ariaLabel={scheduleEnabled ? t("projectTodo.schedule.disable") : t("projectTodo.schedule.enable")}
          busy={busy || !cronActive || trimmedCron.length === 0}
          todo={{ ...todo, trigger_strategy: triggerStrategy, cron_expression: trimmedCron || null, schedule_enabled: scheduleEnabled }}
          onToggleSchedule={(_todo, enabled) => setScheduleEnabled(enabled)}
        />
      </header>
      <dl className="project-todo-schedule-readonly">
        <dt>{t("projectTodo.create.execution")}</dt>
        <dd>{t("projectTodo.schedule.periodic")}</dd>
        <dt>{t("projectTodo.create.terminal")}</dt>
        <dd>{todo.terminal_policy === "REUSE_LATEST" ? t("projectTodo.schedule.reuseLatest") : t("projectTodo.schedule.newTerminal")}</dd>
      </dl>
      <label>
        <span>{t("projectTodo.create.trigger")}</span>
        <select
          value={triggerStrategy}
          disabled={busy}
          aria-label={t("projectTodo.schedule.todoTrigger")}
          onChange={(event) => {
            const nextTrigger = event.target.value as ProjectTodoTriggerStrategy;
            setTriggerStrategy(nextTrigger);
            if (nextTrigger === "MANUAL") {
              setScheduleEnabled(false);
            }
          }}
        >
          <option value="MANUAL">{t("projectTodo.create.trigger.manual")}</option>
          <option value="CRON">{t("projectTodo.create.trigger.cron")}</option>
        </select>
      </label>
      {cronActive && (
        <label>
          <span>Cron</span>
          <input
            value={cronExpression}
            disabled={busy}
            aria-label={t("projectTodo.schedule.cronExpression")}
            placeholder="0 9 * * 1"
            maxLength={128}
            onChange={(event) => setCronExpression(event.target.value)}
          />
        </label>
      )}
      <dl className="project-todo-schedule-readonly">
        <dt>{t("projectTodo.schedule.next")}</dt>
        <dd>{formatProjectTodoDate(todo.next_trigger_at) || "-"}</dd>
        <dt>{t("projectTodo.schedule.last")}</dt>
        <dd>{formatProjectTodoDate(todo.last_triggered_at) || "-"}</dd>
      </dl>
      <div className="project-todo-schedule-actions">
        <button type="button" disabled={!canSave} onClick={() => onSaveSchedule(todo, input)}>
          {t("projectTodo.schedule.save")}
        </button>
        <button
          type="button"
          disabled={busy || !dirty}
          onClick={() => {
            setTriggerStrategy(todo.trigger_strategy);
            setCronExpression(todo.cron_expression ?? "");
            setScheduleEnabled(todo.schedule_enabled);
          }}
        >
          {t("common.reset")}
        </button>
      </div>
    </section>
  );
}

function projectTodoHasCronSchedule(todo: ProjectTodoListItem): boolean {
  return todo.execution_kind === "PERIODIC" && todo.trigger_strategy === "CRON" && todo.cron_expression !== null;
}
