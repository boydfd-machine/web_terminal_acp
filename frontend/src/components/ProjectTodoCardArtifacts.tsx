import type { ProjectTodoArtifact, ProjectTodoListItem, WorkStatus } from "../types";
import { useI18n } from "../i18n";
import { ProjectTodoAgentStatusIcon } from "./ProjectTodoAgentStatusIcon";
import { UiIcon } from "./UiIcon";
import {
  projectTodoArtifactAgentLabel,
  projectTodoArtifactHasTerminal,
  projectTodoArtifactStatusText,
} from "./projectTodoArtifacts";

type ProjectTodoCardArtifactStatusProps = {
  agentWorkStatusByWindowId: Map<string, WorkStatus>;
  busy: boolean;
  retryingArtifactLinkId: string | null;
  todo: ProjectTodoListItem;
  onRetryArtifact: (todo: ProjectTodoListItem, artifact: ProjectTodoArtifact) => void;
};

export function ProjectTodoCardArtifactStatus({
  agentWorkStatusByWindowId,
  busy,
  retryingArtifactLinkId,
  todo,
  onRetryArtifact,
}: ProjectTodoCardArtifactStatusProps) {
  const { t } = useI18n();
  const artifact = projectTodoCardArtifact(todo);
  if (artifact === null) {
    return null;
  }
  const artifactWorkStatus = artifact.ephemeral_window_id === null
    ? artifact.agent_status
    : agentWorkStatusByWindowId.get(artifact.ephemeral_window_id) ?? artifact.agent_status;
  const retryable = projectTodoArtifactCanRetry(artifact);
  const retrying = retryingArtifactLinkId === artifact.id;
  const label = projectTodoArtifactAgentLabel(artifact);

  return (
    <span className="project-todo-card-artifact-agent">
      <ProjectTodoAgentStatusIcon
        status={artifactWorkStatus}
        terminalLinked={projectTodoArtifactHasTerminal(artifact)}
        label={`${label} artifact`}
      />
      <small>{projectTodoArtifactStatusText(artifact.status, t)}</small>
      {retryable && (
        <button
          type="button"
          className="project-todo-card-artifact-retry"
          aria-label={t("projectTodo.action.retryArtifactNamed", { title: artifact.title })}
          title={t("projectTodo.action.retryArtifact")}
          disabled={busy || retrying}
          onClick={(event) => {
            event.stopPropagation();
            onRetryArtifact(todo, artifact);
          }}
        >
          {retrying ? (
            <span className="terminal-create-progress-spinner project-todo-card-action-spinner blue" aria-hidden="true" />
          ) : (
            <UiIcon name="rotate-ccw" />
          )}
        </button>
      )}
    </span>
  );
}

function projectTodoCardArtifact(todo: ProjectTodoListItem): ProjectTodoArtifact | null {
  if (todo.artifacts.length === 0) {
    return null;
  }
  return todo.artifacts.find((artifact) => artifact.status.toUpperCase() === "FAILED" && artifact.purpose === "todo_artifact")
    ?? todo.artifacts.find((artifact) => artifact.status.toUpperCase() === "RUNNING")
    ?? todo.artifacts.find((artifact) => artifact.status.toUpperCase() === "PENDING")
    ?? todo.artifacts[0];
}

function projectTodoArtifactCanRetry(artifact: ProjectTodoArtifact): boolean {
  return artifact.purpose === "todo_artifact" && artifact.status.toUpperCase() === "FAILED";
}
