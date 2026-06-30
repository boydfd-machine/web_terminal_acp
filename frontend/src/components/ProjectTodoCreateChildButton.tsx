import { useI18n } from "../i18n";
import type { ProjectTodo, ProjectTodoListItem } from "../types";
import { UiIcon } from "./UiIcon";

type ProjectTodoCreateChildButtonProps<TTodo extends ProjectTodo | ProjectTodoListItem> = {
  busy: boolean;
  className: string;
  todo: TTodo;
  onCreateChild: (todo: TTodo) => void;
};

export function ProjectTodoCreateChildButton<TTodo extends ProjectTodo | ProjectTodoListItem>({
  busy,
  className,
  todo,
  onCreateChild
}: ProjectTodoCreateChildButtonProps<TTodo>) {
  const { t } = useI18n();
  return (
    <button
      type="button"
      className={className}
      aria-label={t("projectTodo.action.createChildNamed", { title: todo.title })}
      title={t("projectTodo.action.createChild")}
      disabled={busy}
      onClick={(event) => {
        event.stopPropagation();
        onCreateChild(todo);
      }}
    >
      <UiIcon name="branch-plus" />
    </button>
  );
}
