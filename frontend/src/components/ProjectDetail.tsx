import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { useEffect, useState } from "react";

import { fetchProject } from "../api";
import type { ProjectTodoFocusRequest, WorkspaceMode } from "../appState";
import type { Project, ProjectTodoArtifact } from "../types";
import type { TerminalTimeRange } from "../terminalTimeRange";
import { useI18n } from "../i18n";
import { ProjectAgentPreferenceSettings } from "./ProjectAgentPreferenceSettings";
import { ProjectArtifactsPanel } from "./ProjectArtifactsPanel";
import { ProjectReviewSettings } from "./ProjectReviewSettings";
import { ProjectTodoPanel } from "./ProjectTodoPanel";

type ProjectDetailTab = "overview" | "todos" | "review" | "artifacts";

type ProjectDetailProps = {
  clientId: string | null;
  projectPath: string | null;
  project?: Project | null;
  projects: Project[];
  todoFocusRequest?: ProjectTodoFocusRequest | null;
  timeRange: TerminalTimeRange;
  workspaceMode?: WorkspaceMode;
  onOpenArtifact?: (artifact: ProjectTodoArtifact, projectPath?: string | null) => void;
  onSelectWindow: (windowId: string, projectPath: string) => void;
};

function formatDateTime(value: string | null | undefined): string {
  if (!value) {
    return "-";
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return date.toLocaleString();
}

function projectFallbackName(projectPath: string): string {
  const parts = projectPath.split("/").filter(Boolean);
  return parts[parts.length - 1] ?? projectPath;
}

function DetailValue({ value }: { value: string | number | null | undefined }) {
  return <span className="detail-value-text">{value ?? "-"}</span>;
}

export function ProjectDetail({
  clientId,
  projectPath,
  project,
  projects,
  todoFocusRequest,
  timeRange,
  workspaceMode = "terminal",
  onOpenArtifact,
  onSelectWindow
}: ProjectDetailProps) {
  const { t } = useI18n();
  const [detailTab, setDetailTab] = useState<ProjectDetailTab>("overview");
  const projectQuery = useQuery({
    queryKey: ["project", clientId, projectPath, timeRange],
    queryFn: () => fetchProject(clientId as string, projectPath as string, timeRange),
    enabled: clientId !== null && projectPath !== null && project === undefined,
    placeholderData: keepPreviousData,
    refetchInterval: 10000
  });

  useEffect(() => {
    setDetailTab("overview");
  }, [clientId, projectPath]);

  useEffect(() => {
    if (
      todoFocusRequest != null
      && workspaceMode !== "kanban"
      && todoFocusRequest.clientId === clientId
      && todoFocusRequest.projectPath === projectPath
    ) {
      setDetailTab("todos");
    }
  }, [clientId, projectPath, todoFocusRequest, workspaceMode]);

  if (clientId === null || projectPath === null) {
    return (
      <div className="detail-empty">
        <p>{t("project.detail.selectProject")}</p>
      </div>
    );
  }

  const item = project ?? projectQuery.data ?? null;
  const displayName = item?.display_name?.trim() || projectFallbackName(projectPath);

  return (
    <div className="window-detail project-detail">
      <div className="detail-panel-tabs" role="tablist" aria-label={t("detail.tabs.project")}>
        <button
          type="button"
          role="tab"
          aria-selected={detailTab === "overview"}
          className={detailTab === "overview" ? "selected" : undefined}
          onClick={() => setDetailTab("overview")}
        >
          {t("detail.tabs.overview")}
        </button>
        <button
          type="button"
          role="tab"
          aria-selected={detailTab === "todos"}
          className={detailTab === "todos" ? "selected" : undefined}
          onClick={() => setDetailTab("todos")}
        >
          {t("detail.tabs.todos")}
        </button>
        <button
          type="button"
          role="tab"
          aria-selected={detailTab === "review"}
          className={detailTab === "review" ? "selected" : undefined}
          onClick={() => setDetailTab("review")}
        >
          {t("detail.tabs.review")}
        </button>
        <button
          type="button"
          role="tab"
          aria-selected={detailTab === "artifacts"}
          className={detailTab === "artifacts" ? "selected" : undefined}
          onClick={() => setDetailTab("artifacts")}
        >
          {t("detail.tabs.artifacts")}
        </button>
      </div>

      {projectQuery.isError && item === null && (
        <p className="error" role="alert">{t("project.detail.loadFailed")}</p>
      )}

      {detailTab === "overview" && (
        <section className="detail-section" aria-label={t("project.detail.overview")}>
          <h3>{displayName}</h3>
          <dl className="detail-list">
            <dt>{t("project.detail.path")}</dt>
            <dd><DetailValue value={projectPath} /></dd>
            <dt>{t("project.detail.terminals")}</dt>
            <dd><DetailValue value={item?.window_count ?? 0} /></dd>
            <dt>{t("project.detail.summaryStatus")}</dt>
            <dd><DetailValue value={item?.summary_status?.toLowerCase() ?? "none"} /></dd>
            <dt>{t("project.detail.summaryUpdated")}</dt>
            <dd><DetailValue value={formatDateTime(item?.summary_updated_at)} /></dd>
          </dl>
          <ProjectAgentPreferenceSettings
            clientId={clientId}
            projectPath={projectPath}
            value={item?.agent_preference ?? null}
          />
        </section>
      )}

      {detailTab === "todos" && (
        <ProjectTodoPanel
          clientId={clientId}
          focusRequest={workspaceMode === "kanban" ? null : todoFocusRequest}
          projects={projects}
          projectPath={projectPath}
          onOpenArtifact={onOpenArtifact}
          onSelectWindow={onSelectWindow}
        />
      )}

      {detailTab === "review" && (
        <ProjectReviewSettings clientId={clientId} projectPath={projectPath} />
      )}

      {detailTab === "artifacts" && (
        <ProjectArtifactsPanel clientId={clientId} projectPath={projectPath} />
      )}
    </div>
  );
}
