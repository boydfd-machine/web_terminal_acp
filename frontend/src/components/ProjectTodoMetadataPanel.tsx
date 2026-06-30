import { useState } from "react";

import { useI18n } from "../i18n";
import type { ProjectTodo, ProjectTodoListItem, ProjectTodoType } from "../types";
import { ProjectTodoInputArtifactIdsField } from "./ProjectTodoInputArtifactIdsField";
import { ProjectTodoParentSelector } from "./ProjectTodoParentSelector";
import { UiIcon } from "./UiIcon";
import {
  formatProjectTodoDate,
  projectTodoReviewStatusLabel,
  projectTodoTypeLabel,
} from "./projectTodoDisplay";

type ProjectTodoMetadataPanelProps = {
  busy: boolean;
  canEditParent: boolean;
  canEditTodoType: boolean;
  clientId: string;
  editableTodoTypes: ProjectTodoType[];
  projectPath: string;
  todos: ProjectTodoListItem[];
  todo: ProjectTodo;
  todoTypeLabel: string;
  todoTypesLoading: boolean;
  onSaveParentTodo: (todo: ProjectTodo, parentTodoId: string | null) => void;
  onSaveInputArtifactIds: (todo: ProjectTodo, inputArtifactIds: string[]) => void;
  onSaveTodoType: (todo: ProjectTodo, todoTypeId: string) => void;
};

export function ProjectTodoMetadataPanel({
  busy,
  canEditParent,
  canEditTodoType,
  clientId,
  editableTodoTypes,
  projectPath,
  todos,
  todo,
  todoTypeLabel,
  todoTypesLoading,
  onSaveParentTodo,
  onSaveInputArtifactIds,
  onSaveTodoType,
}: ProjectTodoMetadataPanelProps) {
  const { t } = useI18n();
  const [expanded, setExpanded] = useState(false);
  const inputArtifactIds = todo.input_artifact_ids ?? [];
  const summary = [
    {
      label: t("projectTodo.detail.parent"),
      value: todo.parent_todo?.title ?? t("projectTodo.create.noParent")
    },
    {
      label: t("projectTodo.detail.type"),
      value: todoTypeLabel
    },
    {
      label: t("projectTodo.detail.agent"),
      value: todo.assigned_agent ?? "-"
    },
    {
      label: t("projectTodo.detail.agentProfile"),
      value: todo.agent_profile_id ?? "-"
    },
    {
      label: t("projectTodo.inputArtifacts.label"),
      value: inputArtifactIds.length > 0 ? inputArtifactIds.join(", ") : "-"
    },
    {
      label: t("projectTodo.detail.created"),
      value: formatProjectTodoDate(todo.created_at)
    },
    {
      label: t("projectTodo.detail.updated"),
      value: formatProjectTodoDate(todo.updated_at)
    },
    {
      label: t("projectTodo.detail.dispatched"),
      value: formatProjectTodoDate(todo.dispatched_at) || "-"
    }
  ];

  return (
    <section className="project-todo-metadata-panel" aria-label={t("projectTodo.detail.metadataLabel")}>
      <header>
        <strong>{t("projectTodo.detail.metadata")}</strong>
        <button
          type="button"
          className="project-todo-metadata-toggle"
          aria-expanded={expanded}
          aria-controls="project-todo-metadata-content"
          aria-label={expanded ? t("common.collapse") : t("common.expand")}
          title={expanded ? t("common.collapse") : t("common.expand")}
          onClick={() => setExpanded((value) => !value)}
        >
          <UiIcon name={expanded ? "chevron-up" : "chevron-down"} />
        </button>
      </header>
      {expanded ? (
        <dl className="project-todo-detail-list" id="project-todo-metadata-content">
          <dt>{t("projectTodo.detail.parent")}</dt>
          <dd>
            {canEditParent ? (
              <ProjectTodoParentSelector
                ariaLabel={t("projectTodo.detail.parent")}
                className="project-todo-detail-parent-selector"
                currentParent={todo.parent_todo}
                disabled={busy}
                excludeTodoId={todo.id}
                label={t("projectTodo.detail.parent")}
                todos={todos}
                value={todo.parent_todo_id ?? ""}
                onChange={(parentTodoId) => onSaveParentTodo(todo, parentTodoId || null)}
              />
            ) : todo.parent_todo?.title ?? t("projectTodo.create.noParent")}
          </dd>
          <dt>{t("projectTodo.detail.type")}</dt>
          <dd>
            {canEditTodoType ? (
              <select
                className="project-todo-type-select"
                value={todo.todo_type_id}
                disabled={busy || todoTypesLoading}
                aria-label={t("projectTodo.detail.type")}
                onChange={(event) => onSaveTodoType(todo, event.target.value)}
              >
                {editableTodoTypes.map((todoType) => (
                  <option key={`${todoType.scope}:${todoType.id}`} value={todoType.id}>
                    {projectTodoTypeLabel(todoType, t)}
                  </option>
                ))}
              </select>
            ) : todoTypeLabel}
          </dd>
          <dt>{t("projectTodo.detail.agent")}</dt>
          <dd>{todo.assigned_agent ?? "-"}</dd>
          <dt>{t("projectTodo.detail.agentProfile")}</dt>
          <dd>{todo.agent_profile_id ?? "-"}</dd>
          <dt>{t("projectTodo.inputArtifacts.label")}</dt>
          <dd>
            {canEditTodoType ? (
              <ProjectTodoInputArtifactIdsField
                clientId={clientId}
                projectPath={projectPath}
                value={inputArtifactIds}
                disabled={busy}
                onChange={(inputArtifactIds) => onSaveInputArtifactIds(todo, inputArtifactIds)}
              />
            ) : inputArtifactIds.length > 0 ? inputArtifactIds.join(", ") : "-"}
          </dd>
          <dt>{t("projectTodo.detail.created")}</dt>
          <dd>{formatProjectTodoDate(todo.created_at)}</dd>
          <dt>{t("projectTodo.detail.updated")}</dt>
          <dd>{formatProjectTodoDate(todo.updated_at)}</dd>
          <dt>{t("projectTodo.detail.dispatched")}</dt>
          <dd>{formatProjectTodoDate(todo.dispatched_at) || "-"}</dd>
          <dt>{t("projectTodo.detail.review")}</dt>
          <dd>{formatProjectTodoDate(todo.awaiting_review_at) || "-"}</dd>
          <dt>{t("projectTodo.detail.reviewStatus")}</dt>
          <dd>{projectTodoReviewStatusLabel(todo.review_status, t)}</dd>
          <dt>{t("projectTodo.detail.reviewer")}</dt>
          <dd>{todo.review_agent ?? "-"}</dd>
          <dt>{t("projectTodo.detail.reviewerProfile")}</dt>
          <dd>{todo.review_agent_profile_id ?? "-"}</dd>
          <dt>{t("projectTodo.detail.reviewed")}</dt>
          <dd>{formatProjectTodoDate(todo.reviewed_at) || "-"}</dd>
          <dt>{t("projectTodo.detail.humanReview")}</dt>
          <dd>{todo.needs_human_review ? t("projectTodo.detail.required") : "-"}</dd>
          <dt>{t("projectTodo.detail.completed")}</dt>
          <dd>{formatProjectTodoDate(todo.completed_at) || "-"}</dd>
        </dl>
      ) : (
        <dl className="project-todo-detail-list project-todo-detail-list-compact" id="project-todo-metadata-content">
          {summary.map((row) => (
            <div key={row.label} className="project-todo-detail-summary-row">
              <dt>{row.label}</dt>
              <dd>{row.value}</dd>
            </div>
          ))}
        </dl>
      )}
    </section>
  );
}
