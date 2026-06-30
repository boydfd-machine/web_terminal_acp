import type { FocusEvent, KeyboardEvent } from "react";

import { useI18n } from "../i18n";
import type { ProjectTodo, ProjectTodoListItem } from "../types";
import { ProjectTodoDescriptionMentionTextarea } from "./ProjectTodoDescriptionMentionTextarea";
import { ProjectTodoDescriptionText } from "./ProjectTodoDescriptionText";
import { UiIcon } from "./UiIcon";

export function ProjectTodoTitleEditForm({
  busy,
  editTitle,
  onCancelEdit,
  onEditTitleChange,
  onSaveEdit
}: {
  busy: boolean;
  editTitle: string;
  onCancelEdit: () => void;
  onEditTitleChange: (title: string) => void;
  onSaveEdit: () => void;
}) {
  const { t } = useI18n();
  const handleKeyDown = (event: KeyboardEvent<HTMLFormElement>) => {
    if (event.defaultPrevented) {
      return;
    }
    if (event.key === "Escape") {
      event.preventDefault();
      onCancelEdit();
    }
  };
  const saveIfFocusLeaves = (event: FocusEvent<HTMLFormElement>) => {
    const form = event.currentTarget;
    const nextTarget = event.relatedTarget;
    if (nextTarget instanceof Node && form.contains(nextTarget)) {
      return;
    }
    window.setTimeout(() => {
      if (form.isConnected && !form.contains(document.activeElement) && editTitle.trim().length > 0) {
        onSaveEdit();
      }
    }, 0);
  };

  return (
    <form
      className="project-todo-title-edit-form"
      onBlur={saveIfFocusLeaves}
      onKeyDown={handleKeyDown}
      onSubmit={(event) => {
        event.preventDefault();
        if (editTitle.trim().length > 0) {
          onSaveEdit();
        }
      }}
    >
      <input
        className="project-todo-title-input"
        value={editTitle}
        onChange={(event) => onEditTitleChange(event.target.value)}
        maxLength={255}
        aria-label={t("projectTodo.detail.titleLabel")}
        autoFocus
      />
      <button
        type="button"
        className="project-todo-detail-icon-button project-todo-title-cancel-edit-button"
        disabled={busy}
        aria-label={t("common.cancel")}
        title={t("common.cancel")}
        onMouseDown={(event) => event.preventDefault()}
        onClick={onCancelEdit}
      >
        <UiIcon name="x" />
      </button>
    </form>
  );
}

export function ProjectTodoDescriptionPanel({
  busy,
  descriptionEditable = true,
  todo,
  onBeginEdit,
  onOpenTodo
}: {
  busy: boolean;
  descriptionEditable?: boolean;
  todo: ProjectTodo;
  onBeginEdit: () => void;
  onOpenTodo: (todoId: string) => void;
}) {
  const { t } = useI18n();
  return (
    <section className="project-todo-detail-description-panel" aria-label={t("projectTodo.detail.description")}>
      <button
        type="button"
        className="project-todo-detail-icon-button project-todo-description-edit-button"
        aria-label={t("projectTodo.detail.editDescription")}
        title={t("common.edit")}
        disabled={busy || !descriptionEditable}
        onClick={onBeginEdit}
      >
        <UiIcon name="edit" />
      </button>
      <div
        className="project-todo-detail-description"
        onDoubleClick={(event) => {
          if (busy || !descriptionEditable) {
            return;
          }
          if (event.target instanceof HTMLElement && event.target.closest("button")) {
            return;
          }
          event.preventDefault();
          onBeginEdit();
        }}
      >
        <ProjectTodoDescriptionText
          description={todo.description}
          referencedTodos={todo.referenced_todos}
          onOpenTodo={onOpenTodo}
        />
      </div>
    </section>
  );
}

export function ProjectTodoDescriptionEditForm({
  busy,
  editDescription,
  todos,
  todoId,
  onCancelEdit,
  onEditDescriptionChange,
  onSaveEdit
}: {
  busy: boolean;
  editDescription: string;
  todos: ProjectTodoListItem[];
  todoId: string;
  onCancelEdit: () => void;
  onEditDescriptionChange: (description: string) => void;
  onSaveEdit: () => void;
}) {
  const { t } = useI18n();
  const handleKeyDown = (event: KeyboardEvent<HTMLFormElement>) => {
    if (event.defaultPrevented) {
      return;
    }
    if (event.key === "Escape") {
      event.preventDefault();
      onCancelEdit();
    }
  };
  const saveIfFocusLeaves = (event: FocusEvent<HTMLFormElement>) => {
    const form = event.currentTarget;
    const nextTarget = event.relatedTarget;
    if (nextTarget instanceof Node && form.contains(nextTarget)) {
      return;
    }
    window.setTimeout(() => {
      if (form.isConnected && !form.contains(document.activeElement)) {
        onSaveEdit();
      }
    }, 0);
  };

  return (
    <form
      className="project-todo-description-edit-form"
      onBlur={saveIfFocusLeaves}
      onKeyDown={handleKeyDown}
      onSubmit={(event) => {
        event.preventDefault();
        onSaveEdit();
      }}
    >
      <ProjectTodoDescriptionMentionTextarea
        value={editDescription}
        todos={todos}
        currentTodoId={todoId}
        onChange={onEditDescriptionChange}
        ariaLabel={t("projectTodo.detail.description")}
        autoResize
        autoFocus
      />
      <button
        type="button"
        className="project-todo-detail-icon-button project-todo-description-cancel-edit-button"
        disabled={busy}
        aria-label={t("common.cancel")}
        title={t("common.cancel")}
        onMouseDown={(event) => event.preventDefault()}
        onClick={onCancelEdit}
      >
        <UiIcon name="x" />
      </button>
    </form>
  );
}
