import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { fetchProjectTodoHistory, restoreProjectTodoVersion } from "../api";
import { useI18n, type TranslateFn } from "../i18n";
import type { ProjectTodo, ProjectTodoAuditLog, ProjectTodoVersion } from "../types";
import { UiIcon } from "./UiIcon";
import { useAppPrompt } from "./AppPromptProvider";
import { formatProjectTodoDate } from "./projectTodoDisplay";

type ProjectTodoHistoryPanelProps = {
  busy: boolean;
  clientId: string;
  projectPath: string;
  todo: ProjectTodo;
};

export function ProjectTodoHistoryPanel({
  busy,
  clientId,
  projectPath,
  todo
}: ProjectTodoHistoryPanelProps) {
  const { t } = useI18n();
  const { confirm } = useAppPrompt();
  const queryClient = useQueryClient();
  const historyKey = ["project-todo-history", clientId, projectPath, todo.id] as const;
  const historyQuery = useQuery({
    queryKey: historyKey,
    queryFn: () => fetchProjectTodoHistory(clientId, projectPath, todo.id),
    staleTime: 5000
  });
  const versions = historyQuery.data?.versions ?? [];
  const auditLogs = historyQuery.data?.audit_logs ?? [];
  const latestVersionNumber = versions[0]?.version_number ?? null;
  const restoreMutation = useMutation({
    mutationFn: (versionNumber: number) =>
      restoreProjectTodoVersion(clientId, projectPath, todo.id, versionNumber),
    onSuccess: (restoredTodo) => {
      queryClient.setQueryData(["project-todo", clientId, projectPath, restoredTodo.id], restoredTodo);
      queryClient.invalidateQueries({ queryKey: ["project-todos", clientId, projectPath], exact: false });
      queryClient.invalidateQueries({ queryKey: historyKey });
    }
  });

  const restoreVersion = async (version: ProjectTodoVersion) => {
    if (busy || restoreMutation.isPending || version.version_number === latestVersionNumber) {
      return;
    }
    const confirmed = await confirm({
      title: t("projectTodo.history.restoreConfirmTitle"),
      message: t("projectTodo.history.restoreConfirm", { version: version.version_number }),
      confirmLabel: t("projectTodo.history.restore"),
      tone: "danger"
    });
    if (confirmed) {
      restoreMutation.mutate(version.version_number);
    }
  };

  return (
    <section className="project-todo-history-panel" aria-label={t("projectTodo.history.label")}>
      <header>
        <strong>{t("projectTodo.history.label")}</strong>
        {historyQuery.isFetching && <span>{t("history.refreshing")}</span>}
      </header>
      {historyQuery.isLoading ? (
        <p className="muted">{t("common.loading")}</p>
      ) : historyQuery.isError ? (
        <p className="error" role="alert">{t("projectTodo.history.failed")}</p>
      ) : (
        <>
          <ProjectTodoVersionList
            busy={busy || restoreMutation.isPending}
            latestVersionNumber={latestVersionNumber}
            restoringVersionNumber={restoreMutation.variables ?? null}
            versions={versions}
            onRestore={restoreVersion}
            t={t}
          />
          <ProjectTodoAuditLogList auditLogs={auditLogs} t={t} />
        </>
      )}
    </section>
  );
}

function ProjectTodoVersionList({
  busy,
  latestVersionNumber,
  restoringVersionNumber,
  versions,
  onRestore,
  t
}: {
  busy: boolean;
  latestVersionNumber: number | null;
  restoringVersionNumber: number | null;
  versions: ProjectTodoVersion[];
  onRestore: (version: ProjectTodoVersion) => void;
  t: TranslateFn;
}) {
  if (versions.length === 0) {
    return <p className="muted">{t("projectTodo.history.noVersions")}</p>;
  }
  return (
    <div className="project-todo-history-group">
      <span className="project-todo-history-group-label">{t("projectTodo.history.versions")}</span>
      <ol className="project-todo-history-list">
        {versions.map((version) => {
          const current = version.version_number === latestVersionNumber;
          const restoring = version.version_number === restoringVersionNumber;
          return (
            <li key={version.id} className="project-todo-history-version">
              <div className="project-todo-history-item-main">
                <strong>{t("projectTodo.history.version", { version: version.version_number })}</strong>
                <span>{version.title}</span>
                {version.description && <small>{previewText(version.description)}</small>}
                <small>{actorDateLabel(version, t)}</small>
              </div>
              <button
                type="button"
                className="project-todo-detail-icon-button project-todo-history-restore"
                aria-label={t("projectTodo.history.restoreVersion", { version: version.version_number })}
                title={t("projectTodo.history.restore")}
                disabled={busy || current}
                onClick={() => onRestore(version)}
              >
                {restoring ? <span className="project-todo-history-spinner" /> : <UiIcon name="rotate-ccw" />}
              </button>
            </li>
          );
        })}
      </ol>
    </div>
  );
}

function ProjectTodoAuditLogList({
  auditLogs,
  t
}: {
  auditLogs: ProjectTodoAuditLog[];
  t: TranslateFn;
}) {
  if (auditLogs.length === 0) {
    return null;
  }
  return (
    <div className="project-todo-history-group">
      <span className="project-todo-history-group-label">{t("projectTodo.history.auditLog")}</span>
      <ol className="project-todo-history-list">
        {auditLogs.slice(0, 5).map((log) => (
          <li key={log.id} className="project-todo-history-audit">
            <div className="project-todo-history-item-main">
              <strong>{auditActionLabel(log, t)}</strong>
              <span>{auditFieldsLabel(log, t)}</span>
              <small>{actorDateLabel(log, t)}</small>
            </div>
          </li>
        ))}
      </ol>
    </div>
  );
}

function auditActionLabel(log: ProjectTodoAuditLog, t: TranslateFn): string {
  if (log.action === "restored" && log.restored_version_number !== null) {
    return t("projectTodo.history.action.restoredFrom", { version: log.restored_version_number });
  }
  switch (log.action) {
    case "created":
      return t("projectTodo.history.action.created");
    case "updated":
      return t("projectTodo.history.action.updated");
    case "restored":
      return t("projectTodo.history.action.restored");
  }
}

function auditFieldsLabel(log: ProjectTodoAuditLog, t: TranslateFn): string {
  if (log.fields.length === 0) {
    return t("projectTodo.history.noFields");
  }
  return log.fields.map((field) => projectTodoHistoryFieldLabel(field, t)).join(", ");
}

function projectTodoHistoryFieldLabel(field: string, t: TranslateFn): string {
  switch (field) {
    case "title":
      return t("projectTodo.detail.titleLabel");
    case "description":
      return t("projectTodo.detail.description");
    case "status":
      return t("projectTodo.history.field.status");
    default:
      return field;
  }
}

function actorDateLabel(
  item: Pick<ProjectTodoAuditLog | ProjectTodoVersion, "actor_display" | "actor_type" | "created_at">,
  t: TranslateFn
): string {
  const actor = item.actor_display || actorFallbackLabel(item.actor_type, t);
  return `${actor} · ${formatProjectTodoDate(item.created_at)}`;
}

function actorFallbackLabel(actorType: ProjectTodoAuditLog["actor_type"], t: TranslateFn): string {
  switch (actorType) {
    case "agent":
      return t("projectTodo.history.actor.agent");
    case "system":
      return t("projectTodo.history.actor.system");
    case "user":
      return t("projectTodo.history.actor.user");
  }
}

function previewText(value: string): string {
  const normalized = value.replace(/\s+/g, " ").trim();
  return normalized.length > 120 ? `${normalized.slice(0, 117)}...` : normalized;
}
