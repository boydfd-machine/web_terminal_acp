import { useI18n } from "../i18n";
import type { ProjectTodoListItem, ProjectTodoRelation } from "../types";

type ProjectTodoParentSelectorProps = {
  ariaLabel?: string;
  className?: string;
  currentParent?: ProjectTodoRelation | null;
  disabled?: boolean;
  excludeTodoId?: string;
  label?: string;
  todos: ProjectTodoListItem[];
  value: string;
  onChange: (todoId: string) => void;
};

type ProjectTodoParentOption = Pick<ProjectTodoListItem, "id" | "title" | "status">;

export function ProjectTodoParentSelector({
  ariaLabel,
  className = "project-todo-parent-selector",
  currentParent = null,
  disabled = false,
  excludeTodoId,
  label,
  todos,
  value,
  onChange
}: ProjectTodoParentSelectorProps) {
  const { t } = useI18n();
  const options = parentOptions(todos, currentParent, excludeTodoId);
  const selectedValue = options.some((todo) => todo.id === value) ? value : "";

  return (
    <label className={className}>
      <span>{label ?? t("projectTodo.create.parent")}</span>
      <select
        aria-label={ariaLabel}
        disabled={disabled}
        value={selectedValue}
        onChange={(event) => onChange(event.target.value)}
      >
        <option value="">{t("projectTodo.create.noParent")}</option>
        {options.map((todo) => (
          <option key={todo.id} value={todo.id}>
            {todo.title} [{todo.status}]
          </option>
        ))}
      </select>
    </label>
  );
}

function parentOptions(
  todos: ProjectTodoListItem[],
  currentParent: ProjectTodoRelation | null,
  excludeTodoId: string | undefined,
): ProjectTodoParentOption[] {
  const options = todos.filter((todo) => todo.id !== excludeTodoId);
  if (currentParent === null || options.some((todo) => todo.id === currentParent.id)) {
    return options;
  }
  return [currentParent, ...options];
}
