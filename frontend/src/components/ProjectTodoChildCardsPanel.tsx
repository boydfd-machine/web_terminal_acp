import { useEffect, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { fetchProjectTodo } from "../api";
import { useI18n } from "../i18n";
import type { ProjectTodo, ProjectTodoArtifact, ProjectTodoAssignedTerminal, ProjectTodoRelation } from "../types";
import { ProjectTodoAgentRecord } from "./ProjectTodoAgentRecord";
import { ProjectTodoArtifactsPanel } from "./ProjectTodoArtifactsPanel";
import { projectTodoDetailQueryKey } from "./projectTodoPanelUtils";
import {
  formatProjectTodoShortDate,
  projectTodoStatusClass,
  projectTodoStatusLabel,
} from "./projectTodoDisplay";
import { UiIcon } from "./UiIcon";

type ProjectTodoChildCardsPanelProps = {
  clientId: string;
  projectPath: string;
  todo: ProjectTodo;
  onOpenArtifact?: (artifact: ProjectTodoArtifact) => void;
  onOpenTodo: (todoId: string) => void;
  onSelectWindow: (windowId: string, projectPath: string) => void;
};

export function ProjectTodoChildCardsPanel({
  clientId,
  projectPath,
  todo,
  onOpenArtifact,
  onOpenTodo,
  onSelectWindow,
}: ProjectTodoChildCardsPanelProps) {
  const { t } = useI18n();
  const children = todo.child_todos;
  const [selectedChildId, setSelectedChildId] = useState<string | null>(children[0]?.id ?? null);

  useEffect(() => {
    setSelectedChildId((current) => (
      current !== null && children.some((child) => child.id === current)
        ? current
        : children[0]?.id ?? null
    ));
  }, [children, todo.id]);

  const selectedChildSummary = useMemo(
    () => children.find((child) => child.id === selectedChildId) ?? children[0] ?? null,
    [children, selectedChildId]
  );
  const childDetailQuery = useQuery({
    queryKey: selectedChildId === null
      ? ["project-todo", clientId, projectPath, "child-card", "none"]
      : projectTodoDetailQueryKey(clientId, projectPath, selectedChildId),
    queryFn: () => fetchProjectTodo(clientId, projectPath, selectedChildId as string),
    enabled: selectedChildId !== null,
    meta: { suppressProjectTodoNotFoundToast: true },
    staleTime: 5000,
  });
  const selectedChild = childDetailQuery.data ?? null;

  if (children.length === 0) {
    return null;
  }

  return (
    <section className="project-todo-child-cards-panel" aria-label={t("projectTodo.children.title")}>
      <header>
        <strong>{t("projectTodo.children.title")}</strong>
        <span>{t("projectTodo.children.count", { count: children.length })}</span>
      </header>
      <div className="project-todo-child-card-layout">
        <div className="project-todo-child-card-list" aria-label={t("projectTodo.children.list")}>
          {children.map((child) => (
            <ProjectTodoChildCardListItem
              key={child.id}
              child={child}
              selected={selectedChildSummary?.id === child.id}
              onSelect={() => setSelectedChildId(child.id)}
            />
          ))}
        </div>
        <ProjectTodoChildCardDetail
          child={selectedChild}
          childSummary={selectedChildSummary}
          clientId={clientId}
          loading={childDetailQuery.isLoading || childDetailQuery.isFetching}
          loadFailed={childDetailQuery.isError}
          projectPath={projectPath}
          onOpenArtifact={onOpenArtifact}
          onOpenTodo={onOpenTodo}
          onSelectWindow={onSelectWindow}
        />
      </div>
    </section>
  );
}

function ProjectTodoChildCardListItem({
  child,
  selected,
  onSelect,
}: {
  child: ProjectTodoRelation;
  selected: boolean;
  onSelect: () => void;
}) {
  const { t } = useI18n();
  const completed = formatProjectTodoShortDate(child.completed_at);
  return (
    <button
      type="button"
      className={selected ? "project-todo-child-card-item selected" : "project-todo-child-card-item"}
      aria-pressed={selected}
      onClick={onSelect}
    >
      <span className={`project-todo-status-pill ${projectTodoStatusClass(child.status)}`}>
        {projectTodoStatusLabel(child.status, t)}
      </span>
      <span className="project-todo-child-card-item-main">
        <strong title={child.title}>{child.title}</strong>
        <small>{completed || child.id}</small>
      </span>
    </button>
  );
}

function ProjectTodoChildCardDetail({
  child,
  childSummary,
  clientId,
  loading,
  loadFailed,
  projectPath,
  onOpenArtifact,
  onOpenTodo,
  onSelectWindow,
}: {
  child: ProjectTodo | null;
  childSummary: ProjectTodoRelation | null;
  clientId: string;
  loading: boolean;
  loadFailed: boolean;
  projectPath: string;
  onOpenArtifact?: (artifact: ProjectTodoArtifact) => void;
  onOpenTodo: (todoId: string) => void;
  onSelectWindow: (windowId: string, projectPath: string) => void;
}) {
  const { t } = useI18n();

  if (childSummary === null) {
    return (
      <section className="project-todo-child-card-detail" aria-label={t("projectTodo.children.detail")}>
        <p className="muted">{t("projectTodo.children.select")}</p>
      </section>
    );
  }

  const title = child?.title ?? childSummary.title;
  const status = child?.status ?? childSummary.status;
  const terminalTarget = childTerminalTarget(child);
  const terminalTitle = terminalTarget.terminal?.title ?? title;

  return (
    <section className="project-todo-child-card-detail" aria-label={t("projectTodo.children.detail")}>
      <header className="project-todo-child-card-detail-header">
        <div className="project-todo-child-card-detail-heading">
          <span className={`project-todo-status-pill ${projectTodoStatusClass(status)}`}>
            {projectTodoStatusLabel(status, t)}
          </span>
          <strong title={title}>{title}</strong>
        </div>
        <div className="project-todo-child-card-actions">
          <button
            type="button"
            className="project-todo-detail-icon-button"
            aria-label={t("projectTodo.children.openCardNamed", { title })}
            title={t("projectTodo.children.openCard")}
            onClick={() => onOpenTodo(childSummary.id)}
          >
            <UiIcon name="external-link" />
          </button>
          <button
            type="button"
            className="project-todo-detail-icon-button"
            aria-label={t("projectTodo.action.openTerminalNamed", { title })}
            title={t("projectTodo.action.openTerminal")}
            disabled={terminalTarget.windowId === null}
            onClick={() => {
              if (terminalTarget.windowId !== null) {
                onSelectWindow(terminalTarget.windowId, projectPath);
              }
            }}
          >
            <UiIcon name="terminal" />
          </button>
        </div>
      </header>
      {loadFailed && <p className="error" role="alert">{t("projectTodo.children.loadFailed")}</p>}
      {loading && child === null && <p className="muted">{t("common.loading")}</p>}
      {child !== null && (
        <>
          <div className="project-todo-child-agent-preview" aria-label={t("projectTodo.execution.agentPreview")}>
            <header><strong>{t("projectTodo.execution.agentPreview")}</strong></header>
            <ProjectTodoAgentRecord
              clientId={clientId}
              projectPath={projectPath}
              terminal={terminalTarget.terminal}
              windowId={terminalTarget.windowId}
              title={t("projectTodo.execution.agentPreview")}
            />
          </div>
          <div className="project-todo-child-artifacts" aria-label={t("projectTodo.children.artifacts")}>
            <header><strong>{t("projectTodo.children.artifacts")}</strong></header>
            {child.artifacts.length === 0 ? (
              <p className="muted">{t("projectTodo.children.noArtifacts")}</p>
            ) : (
              <ProjectTodoArtifactsPanel artifacts={child.artifacts} onOpenArtifact={onOpenArtifact} />
            )}
          </div>
          {loading && <p className="muted project-todo-child-refreshing">{t("projectTodo.children.refreshing")}</p>}
        </>
      )}
      {child === null && !loading && !loadFailed && (
        <p className="muted">{terminalTitle}</p>
      )}
    </section>
  );
}

function childTerminalTarget(child: ProjectTodo | null): {
  terminal: Pick<ProjectTodoAssignedTerminal, "git_worktree" | "runtime_tags" | "title"> | null;
  windowId: string | null;
} {
  if (child === null) {
    return { terminal: null, windowId: null };
  }
  if (child.assigned_window_id !== null) {
    return { terminal: child.assigned_terminal, windowId: child.assigned_window_id };
  }
  const latestRun = [...child.execution_runs]
    .sort((left, right) => right.run_number - left.run_number)
    .find((run) => run.window_id !== null) ?? null;
  return {
    terminal: latestRun?.assigned_terminal ?? null,
    windowId: latestRun?.window_id ?? null,
  };
}
