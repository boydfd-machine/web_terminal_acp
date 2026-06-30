import {
  PROJECT_TODO_CUSTOM_DATE_RANGE,
  type ProjectTodoDateFilter,
  type ProjectTodoDateRange
} from "../features/projectTodos/projectTodoDateFilter";
import { useI18n } from "../i18n";
import { TERMINAL_TIME_RANGE_OPTIONS } from "../terminalTimeRange";

export function ProjectTodoDateFilterControls({
  filter,
  onChange
}: {
  filter: ProjectTodoDateFilter;
  onChange: (filter: ProjectTodoDateFilter) => void;
}) {
  const { t } = useI18n();
  const updateCustomStart = (customStart: string) => onChange({ ...filter, customStart });
  const updateCustomEnd = (customEnd: string) => onChange({ ...filter, customEnd });
  return (
    <div className="project-todo-date-filter">
      <label>
        <span>{t("projectTodo.filter.updatedRange")}</span>
        <select
          value={filter.range}
          aria-label={t("projectTodo.filter.updatedRange")}
          onChange={(event) => onChange({
            ...filter,
            range: event.target.value as ProjectTodoDateRange
          })}
        >
          {TERMINAL_TIME_RANGE_OPTIONS.map((option) => (
            <option key={option.value} value={option.value}>{t(option.labelKey)}</option>
          ))}
          <option value={PROJECT_TODO_CUSTOM_DATE_RANGE}>{t("projectTodo.filter.custom")}</option>
        </select>
      </label>
      {filter.range === PROJECT_TODO_CUSTOM_DATE_RANGE && (
        <div className="project-todo-date-filter-custom">
          <label>
            <span>{t("projectTodo.filter.startDate")}</span>
            <input
              type="date"
              value={filter.customStart}
              aria-label={t("projectTodo.filter.startDate")}
              onInput={(event) => updateCustomStart(event.currentTarget.value)}
              onChange={(event) => updateCustomStart(event.target.value)}
            />
          </label>
          <label>
            <span>{t("projectTodo.filter.endDate")}</span>
            <input
              type="date"
              value={filter.customEnd}
              aria-label={t("projectTodo.filter.endDate")}
              onInput={(event) => updateCustomEnd(event.currentTarget.value)}
              onChange={(event) => updateCustomEnd(event.target.value)}
            />
          </label>
        </div>
      )}
    </div>
  );
}
