import { useI18n } from "../i18n";
import type { ProjectTodoArtifact } from "../types";
import { ProjectTodoAgentStatusIcon } from "./ProjectTodoAgentStatusIcon";
import {
  projectTodoArtifactAgentLabel,
  projectTodoArtifactHasTerminal,
  projectTodoArtifactStatusText,
} from "./projectTodoArtifacts";

type ProjectTodoArtifactsPanelProps = {
  artifacts: ProjectTodoArtifact[];
  onOpenArtifact?: (artifact: ProjectTodoArtifact) => void;
};

export function ProjectTodoArtifactsPanel({
  artifacts,
  onOpenArtifact
}: ProjectTodoArtifactsPanelProps) {
  const { t } = useI18n();

  if (artifacts.length === 0) {
    return null;
  }

  return (
    <div className="project-todo-artifacts" aria-label={t("projectTodo.artifacts.linked")}>
      {artifacts.map((artifact) => {
        const agentName = projectTodoArtifactAgentLabel(artifact);
        return (
          <button
            key={artifact.id}
            type="button"
            disabled={onOpenArtifact === undefined}
            onClick={() => onOpenArtifact?.(artifact)}
          >
            <ProjectTodoAgentStatusIcon
              status={artifact.agent_status}
              terminalLinked={projectTodoArtifactHasTerminal(artifact)}
              label={t("projectTodo.artifacts.agentArtifact", { agentName })}
            />
            <span className="project-todo-artifact-agent-detail">
              <strong>{agentName}</strong>
              <small>{artifact.title}</small>
            </span>
            <span>{artifact.purpose}</span>
            <small>{projectTodoArtifactStatusText(artifact.status, t)}</small>
          </button>
        );
      })}
    </div>
  );
}
