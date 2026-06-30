import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { useCallback, useEffect, useMemo, useState } from "react";

import { fetchProjectArtifactHtml, fetchProjectArtifacts } from "../api";
import type { ArtifactProjectTodoCreateInput } from "../artifactProjectTodoBridge";
import { useI18n, type TranslateFn } from "../i18n";
import type { ProjectArtifactVersion, ProjectTodo } from "../types";
import { ArtifactProjectTodoFrame } from "./ArtifactProjectTodoFrame";
import { UiIcon } from "./UiIcon";
import { useArtifactProjectTodoCreator } from "./useArtifactProjectTodoCreator";
import { ARTIFACT_PAGE_SIZE, artifactKindLabel, artifactStatusLabel, formatDateTime } from "./windowDetailData";
import { nextSelectedProjectArtifactId, projectArtifactGroups } from "./projectArtifactsModel";

type ProjectArtifactsPanelProps = {
  clientId: string;
  projectPath: string;
};

export function ProjectArtifactsPanel({
  clientId,
  projectPath
}: ProjectArtifactsPanelProps) {
  const { t } = useI18n();
  const [artifactPage, setArtifactPage] = useState(0);
  const [selectedArtifactKind, setSelectedArtifactKind] = useState<string | null>(null);
  const [selectedArtifactId, setSelectedArtifactId] = useState<string | null>(null);
  const [artifactFullscreen, setArtifactFullscreen] = useState(false);
  const artifactsQuery = useQuery({
    queryKey: ["project-artifacts", clientId, projectPath, artifactPage, ARTIFACT_PAGE_SIZE],
    queryFn: () => fetchProjectArtifacts(
      clientId,
      projectPath,
      ARTIFACT_PAGE_SIZE,
      artifactPage * ARTIFACT_PAGE_SIZE
    ),
    placeholderData: keepPreviousData,
    refetchInterval: (query) => {
      const artifacts = query.state.data?.artifacts ?? [];
      return artifacts.some((artifact) => ["PENDING", "RUNNING"].includes(artifact.status.toUpperCase()))
        ? 2500
        : 10000;
    }
  });
  const artifacts = artifactsQuery.data?.artifacts ?? [];
  const artifactGroups = useMemo(
    () => projectArtifactGroups(artifactsQuery.data),
    [artifactsQuery.data]
  );
  const selectedGroup =
    artifactGroups.find((group) => group.artifact_kind === selectedArtifactKind)
    ?? artifactGroups[0]
    ?? null;
  const selectedArtifact = artifacts.find((artifact) => artifact.id === selectedArtifactId) ?? null;
  const selectedReady = selectedArtifact?.status.toUpperCase() === "SUCCEEDED";
  const htmlQuery = useQuery({
    queryKey: [
      "project-artifact-html",
      clientId,
      projectPath,
      selectedArtifact?.id ?? null,
      selectedArtifact?.updated_at ?? null
    ],
    queryFn: () => fetchProjectArtifactHtml(clientId, projectPath, selectedArtifact?.id ?? ""),
    enabled: selectedArtifact !== null && selectedReady,
    staleTime: Infinity
  });
  const createTodoFromArtifactMutation = useArtifactProjectTodoCreator();
  const createTodoFromArtifact = useCallback((
    card: ArtifactProjectTodoCreateInput,
    artifactId: string | null
  ): Promise<ProjectTodo> =>
    createTodoFromArtifactMutation.mutateAsync({
      artifactId,
      card,
      clientId,
      projectPath
    }), [clientId, createTodoFromArtifactMutation, projectPath]);

  useEffect(() => {
    setArtifactPage(0);
    setSelectedArtifactKind(null);
    setSelectedArtifactId(null);
    setArtifactFullscreen(false);
  }, [clientId, projectPath]);

  useEffect(() => {
    setArtifactFullscreen(false);
  }, [selectedArtifactId]);

  useEffect(() => {
    if (artifactGroups.length === 0) {
      setSelectedArtifactKind(null);
      setSelectedArtifactId(null);
      return;
    }
    const group = artifactGroups.find((item) => item.artifact_kind === selectedArtifactKind) ?? artifactGroups[0];
    if (group.artifact_kind !== selectedArtifactKind) {
      setSelectedArtifactKind(group.artifact_kind);
    }
    const nextSelectedArtifactId = nextSelectedProjectArtifactId(
      artifactGroups,
      selectedArtifactId,
      group.artifact_kind
    );
    if (nextSelectedArtifactId !== selectedArtifactId) {
      setSelectedArtifactId(nextSelectedArtifactId);
    }
  }, [artifactGroups, selectedArtifactId, selectedArtifactKind]);

  return (
    <section className="detail-section project-artifacts-panel" aria-label={t("artifacts.projectTitle")}>
      <header className="project-artifacts-header">
        <div>
          <h3>{t("artifacts.projectTitle")}</h3>
          <p className="muted">{projectPath}</p>
        </div>
        {artifactsQuery.isFetching && <span className="muted">{t("artifacts.projectLoading")}</span>}
      </header>
      {artifactsQuery.isError && (
        <p className="error" role="alert">{t("artifacts.projectLoadFailed")}</p>
      )}
      {!artifactsQuery.isLoading && !artifactsQuery.isError && artifacts.length === 0 && (
        <p className="muted">{t("artifacts.projectEmpty")}</p>
      )}
      {artifactGroups.length > 0 && (
        <>
          <div className="artifact-browser project-artifact-browser">
            <div className="project-artifact-navigation" aria-label={t("artifacts.projectTitle")}>
              <div className="project-artifact-kind-list" role="listbox" aria-label={t("artifacts.types")}>
                {artifactGroups.map((group) => (
                  <button
                    key={group.artifact_kind}
                    type="button"
                    role="option"
                    aria-selected={group.artifact_kind === selectedGroup?.artifact_kind}
                    className={group.artifact_kind === selectedGroup?.artifact_kind ? "selected" : undefined}
                    onClick={() => {
                      setSelectedArtifactKind(group.artifact_kind);
                      setSelectedArtifactId(group.versions[0]?.artifact.id ?? null);
                    }}
                  >
                    <strong>{artifactKindLabel(group.artifact_kind, t)}</strong>
                    <span>{t("artifacts.versionCount", { count: group.version_count })}</span>
                  </button>
                ))}
              </div>
              {selectedGroup !== null && (
                <div className="project-artifact-version-list" role="listbox" aria-label={t("artifacts.versions")}>
                  {selectedGroup.versions.map((version) => (
                    <ProjectArtifactVersionRow
                      key={version.artifact.id}
                      version={version}
                      selected={version.artifact.id === selectedArtifactId}
                      t={t}
                      onSelect={() => setSelectedArtifactId(version.artifact.id)}
                    />
                  ))}
                </div>
              )}
            </div>
            <div className={selectedReady && htmlQuery.data
              ? "artifact-preview project-artifact-preview with-actions"
              : "artifact-preview project-artifact-preview"}>
              {selectedArtifact === null ? (
                <p className="muted">{t("artifacts.select")}</p>
              ) : selectedArtifact.status.toUpperCase() === "FAILED" ? (
                <p className="error" role="alert">
                  {selectedArtifact.last_error ?? t("artifacts.generationFailed")}
                </p>
              ) : selectedReady && htmlQuery.isError ? (
                <p className="error" role="alert">{t("artifacts.previewFailed")}</p>
              ) : selectedReady && htmlQuery.data ? (
                <>
                  <div className="project-artifact-preview-actions">
                    <button
                      type="button"
                      className="ui-icon-button"
                      aria-label={t("artifacts.openFullscreen")}
                      title={t("artifacts.fullscreen")}
                      onClick={() => setArtifactFullscreen(true)}
                    >
                      <UiIcon name="maximize" />
                    </button>
                  </div>
                  <ArtifactProjectTodoFrame
                    artifactId={selectedArtifact.id}
                    clientId={clientId}
                    projectPath={projectPath}
                    srcDoc={htmlQuery.data}
                    title={selectedArtifact.title}
                    onCreateProjectTodo={createTodoFromArtifact}
                  />
                </>
              ) : selectedReady ? (
                <p className="muted">{t("artifacts.previewLoading")}</p>
              ) : (
                <p className="muted">{artifactStatusLabel(selectedArtifact, t)}...</p>
              )}
            </div>
          </div>
          {artifactsQuery.data && (artifactsQuery.data.offset > 0 || artifactsQuery.data.has_more) && (
            <div className="detail-pagination">
              <button
                type="button"
                disabled={artifactPage === 0 || artifactsQuery.isFetching}
                onClick={() => setArtifactPage((page) => Math.max(0, page - 1))}
              >
                {t("common.previous")}
              </button>
              <button
                type="button"
                disabled={!artifactsQuery.data.has_more || artifactsQuery.isFetching}
                onClick={() => setArtifactPage((page) => page + 1)}
              >
                {t("common.next")}
              </button>
            </div>
          )}
          {artifactFullscreen && selectedArtifact !== null && selectedReady && htmlQuery.data && (
            <div className="artifact-fullscreen" role="dialog" aria-modal="true" aria-label={t("artifacts.terminalArtifact")}>
              <button type="button" className="artifact-fullscreen-backdrop" aria-label={t("artifacts.closeArtifact")} onClick={() => setArtifactFullscreen(false)} />
              <section className="artifact-fullscreen-panel">
                <header>
                  <strong>{selectedArtifact.title}</strong>
                  <button
                    type="button"
                    className="ui-icon-button"
                    aria-label={t("artifacts.closeArtifact")}
                    title={t("common.close")}
                    onClick={() => setArtifactFullscreen(false)}
                  >
                    <UiIcon name="x" />
                  </button>
                </header>
                <ArtifactProjectTodoFrame
                  artifactId={selectedArtifact.id}
                  clientId={clientId}
                  projectPath={projectPath}
                  srcDoc={htmlQuery.data}
                  title={selectedArtifact.title}
                  onCreateProjectTodo={createTodoFromArtifact}
                />
              </section>
            </div>
          )}
        </>
      )}
    </section>
  );
}

function ProjectArtifactVersionRow({
  version,
  selected,
  t,
  onSelect
}: {
  version: ProjectArtifactVersion;
  selected: boolean;
  t: TranslateFn;
  onSelect: () => void;
}) {
  const artifact = version.artifact;
  const terminalTitle = version.source_window_title ?? version.virtual_window_title;
  const titleText = terminalTitle === null ? artifact.title : `${artifact.title}\n${terminalTitle}`;
  return (
    <button
      type="button"
      role="option"
      aria-selected={selected}
      className={selected ? "selected project-artifact-version-card" : "project-artifact-version-card"}
      title={titleText}
      onClick={onSelect}
    >
      <span className="project-artifact-version-header">
        <strong>{artifact.title}</strong>
        <small>{t("artifacts.versionLabel", { version: version.version_number })}</small>
      </span>
      <span className="project-artifact-version-time">
        {formatDateTime(version.completed_at ?? version.created_at)}
      </span>
      {terminalTitle !== null && <span className="project-artifact-version-terminal">{terminalTitle}</span>}
      <small className={`artifact-status ${artifact.status.toLowerCase()}`}>
        {artifactStatusLabel(artifact, t)}
      </small>
    </button>
  );
}
