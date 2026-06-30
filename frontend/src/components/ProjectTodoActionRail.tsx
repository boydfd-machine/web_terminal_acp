import { useEffect, useMemo, useState } from "react";

import { useI18n, type TranslateFn } from "../i18n";
import type { ArtifactPluginDescriptor, ArtifactScope, Project, ProjectTodo, ProjectTodoStatus } from "../types";
import {
  PROJECT_TODO_BOARD_COLUMN_ORDER,
  projectTodoBoardColumn,
  projectTodoBoardColumnLabel
} from "./projectTodoDisplay";
import {
  projectTodoDispatchStageActive,
  projectTodoDispatchTitle,
  projectTodoDispatchTone,
} from "./projectTodoDispatchStage";

type ProjectTodoActionRailProps = {
  artifactPlugins: ArtifactPluginDescriptor[];
  projects: Project[];
  todo: ProjectTodo;
  busy: boolean;
  dispatching: boolean;
  generatingArtifact: boolean;
  onDispatch: () => void;
  onGenerateArtifact: (artifactOption: ProjectTodoGenerateArtifactOption) => void;
  onMoveToColumn: (status: ProjectTodoStatus) => void;
  onMoveToProject: (projectPath: string) => void;
  onStatus: (status: ProjectTodoStatus) => void;
};

export type ProjectTodoGenerateArtifactOption = {
  artifactKind: string;
  artifactScope: ArtifactScope;
  title: string;
};

export function ProjectTodoActionRail({
  artifactPlugins,
  projects,
  todo,
  busy,
  dispatching,
  generatingArtifact,
  onDispatch,
  onGenerateArtifact,
  onMoveToColumn,
  onMoveToProject,
  onStatus
}: ProjectTodoActionRailProps) {
  const { t } = useI18n();
  const artifactWindowId = todo.review_window_id ?? todo.assigned_window_id;
  const artifactOptions = useMemo(
    () => projectTodoGenerateArtifactOptions(artifactPlugins, todo.artifact_kinds, todo.title, t),
    [artifactPlugins, todo.artifact_kinds, todo.title, t]
  );
  const defaultArtifactValue = artifactOptions[0]?.value ?? fallbackArtifactOption(todo.title, t).value;
  const [artifactSelection, setArtifactSelection] = useState(() => ({
    todoId: todo.id,
    userSelected: false,
    value: defaultArtifactValue
  }));
  useEffect(() => {
    const selectionValid = artifactOptions.some((option) => option.value === artifactSelection.value);
    if (
      artifactSelection.todoId !== todo.id
      || !selectionValid
      || (!artifactSelection.userSelected && artifactSelection.value !== defaultArtifactValue)
    ) {
      setArtifactSelection({ todoId: todo.id, userSelected: false, value: defaultArtifactValue });
    }
  }, [artifactOptions, artifactSelection, defaultArtifactValue, todo.id]);
  const selectedArtifactOption = artifactOptions.find((option) => option.value === artifactSelection.value)
    ?? artifactOptions[0]
    ?? fallbackArtifactOption(todo.title, t);
  return (
    <aside className="project-todo-action-rail" aria-label={t("projectTodo.action.todoActions")}>
      {artifactWindowId && (
        <section className="project-todo-action-group" aria-label={t("projectTodo.action.artifactActions")}>
          <header><strong>{t("projectTodo.action.artifacts")}</strong></header>
          <div className="project-todo-artifact-actions">
            <div className="project-todo-generate-artifact-control">
              <label htmlFor={`project-todo-generate-artifact-${todo.id}`}>
                {t("projectTodo.action.artifactType")}
              </label>
              <select
                id={`project-todo-generate-artifact-${todo.id}`}
                className="project-todo-generate-artifact-select"
                aria-label={t("projectTodo.action.artifactType")}
                disabled={busy || generatingArtifact}
                value={selectedArtifactOption.value}
                onChange={(event) => setArtifactSelection({
                  todoId: todo.id,
                  userSelected: true,
                  value: event.target.value
                })}
              >
                {artifactOptions.map((option) => (
                  <option key={option.value} value={option.value}>{option.label}</option>
                ))}
              </select>
              <button
                type="button"
                className="project-todo-action-button project-todo-action-secondary"
                disabled={busy}
                onClick={() => onGenerateArtifact(selectedArtifactOption)}
              >
                {generatingArtifact ? t("projectTodo.action.generating") : t("projectTodo.action.generateArtifact")}
              </button>
            </div>
          </div>
        </section>
      )}
      <section className="project-todo-action-group" aria-label={t("projectTodo.action.statusActions")}>
        <header><strong>{t("projectTodo.board.status")}</strong></header>
        <ProjectTodoMoveColumnSelect todo={todo} busy={busy} onMoveToColumn={onMoveToColumn} />
        <ProjectTodoMoveProjectSelect
          projects={projects}
          todo={todo}
          busy={busy}
          onMoveToProject={onMoveToProject}
        />
        <div className="project-todo-actions">
          <ProjectTodoLifecycleButtons todo={todo} busy={busy} dispatching={dispatching} onDispatch={onDispatch} onStatus={onStatus} />
        </div>
      </section>
    </aside>
  );
}

function ProjectTodoMoveProjectSelect({
  projects,
  todo,
  busy,
  onMoveToProject
}: {
  projects: Project[];
  todo: ProjectTodo;
  busy: boolean;
  onMoveToProject: (projectPath: string) => void;
}) {
  const { t } = useI18n();
  const projectOptions = projects
    .filter((project) => project.path !== todo.project_path)
    .sort((left, right) => projectLabel(left).localeCompare(projectLabel(right)));
  if (todo.status !== "TODO" || todo.queued_dispatch || projectOptions.length === 0) {
    return null;
  }
  return (
    <label className="project-todo-move-project-control">
      <span>{t("projectTodo.action.moveToProject")}</span>
      <select
        className="project-todo-move-project-select"
        aria-label={t("projectTodo.action.moveToProject")}
        disabled={busy}
        value=""
        onChange={(event) => {
          if (event.target.value.length > 0) {
            onMoveToProject(event.target.value);
          }
        }}
      >
        <option value="" disabled>{t("projectTodo.action.selectProject")}</option>
        {projectOptions.map((project) => (
          <option key={project.path} value={project.path}>
            {projectLabel(project)}
          </option>
        ))}
      </select>
    </label>
  );
}

function projectLabel(project: Project): string {
  return project.display_name?.trim() || project.path;
}

function ProjectTodoMoveColumnSelect({
  todo,
  busy,
  onMoveToColumn
}: {
  todo: ProjectTodo;
  busy: boolean;
  onMoveToColumn: (status: ProjectTodoStatus) => void;
}) {
  const { t } = useI18n();
  const currentColumn = projectTodoBoardColumn(todo);
  const targetColumns = PROJECT_TODO_BOARD_COLUMN_ORDER
    .filter((column): column is ProjectTodoStatus => column !== "PENDING")
    .filter((column) => currentColumn !== "PENDING" || todo.queued_dispatch || column !== todo.status);
  const columns = currentColumn === "PENDING" ? [currentColumn, ...targetColumns] : targetColumns;
  return (
    <label className="project-todo-move-column-control">
      <span>{t("projectTodo.action.moveToColumn")}</span>
      <select
        className="project-todo-move-column-select"
        aria-label={t("projectTodo.action.moveToColumn")}
        disabled={busy}
        value={currentColumn}
        onChange={(event) => {
          if (event.target.value !== "PENDING") {
            onMoveToColumn(event.target.value as ProjectTodoStatus);
          }
        }}
      >
        {columns.map((column) => (
          <option key={column} value={column} disabled={column === "PENDING"}>
            {projectTodoBoardColumnLabel(column, t)}
          </option>
        ))}
      </select>
    </label>
  );
}

type GenerateArtifactSelectOption = ProjectTodoGenerateArtifactOption & {
  label: string;
  value: string;
};

function projectTodoGenerateArtifactOptions(
  artifactPlugins: ArtifactPluginDescriptor[],
  requestedKinds: string[],
  todoTitle: string,
  t: TranslateFn
): GenerateArtifactSelectOption[] {
  const requestedOrder = new Map(requestedKinds.map((kind, index) => [kind, index]));
  const orderedPlugins = artifactPlugins
    .filter((plugin) => plugin.validation_error == null)
    .sort((left, right) => artifactPluginSortIndex(left, requestedOrder) - artifactPluginSortIndex(right, requestedOrder));
  const options = orderedPlugins.map((plugin) => artifactPluginGenerateOption(plugin, todoTitle, t));
  const fallback = fallbackArtifactOption(todoTitle, t);
  if (!options.some((option) => option.value === fallback.value)) {
    options.push(fallback);
  }
  return options;
}

function artifactPluginSortIndex(plugin: ArtifactPluginDescriptor, requestedOrder: Map<string, number>): number {
  return requestedOrder.get(artifactPluginEncodedValue(plugin)) ?? Number.MAX_SAFE_INTEGER;
}

function artifactPluginGenerateOption(
  plugin: ArtifactPluginDescriptor,
  todoTitle: string,
  t: TranslateFn
): GenerateArtifactSelectOption {
  const label = plugin.domain === "project"
    ? t("settings.cardTypes.projectArtifact", { label: plugin.label.trim() || plugin.artifact_kind })
    : plugin.label.trim() || plugin.artifact_kind;
  return {
    artifactKind: plugin.artifact_kind,
    artifactScope: plugin.domain,
    label,
    title: `${todoTitle} - ${plugin.default_title.trim() || label}`,
    value: artifactPluginEncodedValue(plugin)
  };
}

function fallbackArtifactOption(todoTitle: string, t: TranslateFn): GenerateArtifactSelectOption {
  const label = t("projectTodo.action.defaultArtifactType");
  return {
    artifactKind: "agent_trace_graph",
    artifactScope: "terminal",
    label,
    title: `${todoTitle} - ${label}`,
    value: "agent_trace_graph"
  };
}

function artifactPluginEncodedValue(plugin: ArtifactPluginDescriptor): string {
  return plugin.domain === "project" ? `project:${plugin.artifact_kind}` : plugin.artifact_kind;
}

function ProjectTodoLifecycleButtons({
  todo,
  busy,
  dispatching,
  onDispatch,
  onStatus
}: {
  todo: ProjectTodo;
  busy: boolean;
  dispatching: boolean;
  onDispatch: () => void;
  onStatus: (status: ProjectTodoStatus) => void;
}) {
  const { t } = useI18n();
  const stageDispatching = projectTodoDispatchStageActive(todo);
  const dispatchTone = projectTodoDispatchTone(todo.dispatch_stage);
  const dispatchWaiting = todo.queued_dispatch && !stageDispatching;
  const dispatchTitle = projectTodoDispatchTitle(todo.dispatch_stage, todo.dispatch_error, t)
    ?? (dispatchWaiting ? t("projectTodo.dispatch.waiting") : null);
  const dispatchBusy = dispatching || stageDispatching;
  if (todo.status === "DONE") {
    return <button type="button" disabled={busy} onClick={() => onStatus("TODO")}>{t("projectTodo.action.reopen")}</button>;
  }
  if (todo.status === "AWAITING_REVIEW") {
    return (
      <>
        <button type="button" className="project-todo-action-done" disabled={busy} onClick={() => onStatus("DONE")}>
          {t("projectTodo.action.done")}
        </button>
        <button type="button" className="project-todo-action-reopen" disabled={busy} onClick={() => onStatus("TODO")}>
          {t("projectTodo.action.reopen")}
        </button>
      </>
    );
  }
  if (todo.status === "DISPATCHED") {
    return (
      <button type="button" className="project-todo-action-primary" disabled={busy} onClick={() => onStatus("AWAITING_REVIEW")}>
        {t("projectTodo.action.review")}
      </button>
    );
  }
  if (todo.status === "BLOCKED") {
    return (
      <button type="button" className="project-todo-action-reopen" disabled={busy} onClick={() => onStatus("TODO")}>
        {t("projectTodo.action.unblock")}
      </button>
    );
  }
  return (
    <>
      <button
        type="button"
        className="project-todo-action-primary"
        disabled={busy || dispatchBusy || dispatchWaiting}
        title={dispatchTitle ?? undefined}
        onClick={onDispatch}
      >
        {dispatchBusy && (
          <span
            className={`terminal-create-progress-spinner project-todo-button-spinner ${dispatchTone ?? "blue"}`}
            aria-hidden="true"
          />
        )}
        <span>{dispatchBusy ? t("projectTodo.action.starting") : dispatchWaiting ? t("projectTodo.action.pending") : t("projectTodo.action.dispatch")}</span>
      </button>
      <button
        type="button"
        className="project-todo-action-request"
        disabled={busy || dispatchBusy}
        onClick={() => onStatus("BLOCKED")}
      >
        {t("projectTodo.action.block")}
      </button>
    </>
  );
}
