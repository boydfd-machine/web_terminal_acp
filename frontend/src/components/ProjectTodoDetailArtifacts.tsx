import { useI18n } from "../i18n";
import type { ArtifactPluginDescriptor, ProjectTodo, ProjectTodoArtifact } from "../types";
import { ProjectTodoArtifactAgents } from "./ProjectTodoArtifactAgents";
import { ProjectTodoArtifactKindSelector } from "./ProjectTodoArtifactKindSelector";

type ProjectTodoArtifactAgentsPanelProps = {
  artifacts: ProjectTodoArtifact[];
  onOpenArtifact?: (artifact: ProjectTodoArtifact) => void;
};

export function ProjectTodoArtifactAgentsPanel({
  artifacts,
  onOpenArtifact
}: ProjectTodoArtifactAgentsPanelProps) {
  const { t } = useI18n();
  if (artifacts.length === 0) {
    return null;
  }
  return (
    <section className="project-todo-detail-artifact-agents-panel" aria-label={t("projectTodo.detailArtifacts.agents")}>
      <header><strong>{t("projectTodo.detailArtifacts.agents")}</strong></header>
      <ProjectTodoArtifactAgents artifacts={artifacts} onOpenArtifact={onOpenArtifact} />
    </section>
  );
}

type ProjectTodoRequestedArtifactsPanelProps = {
  artifactPlugins: ArtifactPluginDescriptor[];
  busy: boolean;
  todo: ProjectTodo;
  onSaveArtifactKinds: (todo: ProjectTodo, artifactKinds: string[]) => void;
};

export function ProjectTodoRequestedArtifactsPanel({
  artifactPlugins,
  busy,
  todo,
  onSaveArtifactKinds
}: ProjectTodoRequestedArtifactsPanelProps) {
  const { t } = useI18n();
  if (!projectTodoRequestedArtifactsEditable(todo) || artifactPlugins.length === 0) {
    return null;
  }
  return (
    <section className="project-todo-requested-artifacts-panel" aria-label={t("projectTodo.detailArtifacts.requested")}>
      <ProjectTodoArtifactKindSelector
        artifactPlugins={artifactPlugins}
        selectedKinds={todo.artifact_kinds}
        className="project-todo-detail-artifacts"
        disabled={busy}
        legend={t("projectTodo.detailArtifacts.requested")}
        onSelectionChange={(artifactKinds) => onSaveArtifactKinds(todo, artifactKinds)}
      />
    </section>
  );
}

export function projectTodoRequestedArtifactsEditable(todo: ProjectTodo): boolean {
  return todo.status === "TODO";
}
