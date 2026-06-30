import { useRef } from "react";

import { useI18n } from "../i18n";
import type { ProjectTodoArtifact } from "../types";
import { ProjectTodoAgentStatusIcon } from "./ProjectTodoAgentStatusIcon";
import {
  projectTodoArtifactAgentLabel,
  projectTodoArtifactHasTerminal,
  projectTodoArtifactStatusText,
} from "./projectTodoArtifacts";

type ProjectTodoArtifactAgentsProps = {
  artifacts: ProjectTodoArtifact[];
  label?: string;
  onOpenArtifact?: (artifact: ProjectTodoArtifact) => void;
};

export function ProjectTodoArtifactAgents({
  artifacts,
  label,
  onOpenArtifact
}: ProjectTodoArtifactAgentsProps) {
  const { t } = useI18n();
  const scrollerRef = useRef<HTMLDivElement | null>(null);
  if (artifacts.length === 0) {
    return null;
  }
  const effectiveLabel = label ?? t("projectTodo.artifactAgents.label");

  const scroll = (direction: -1 | 1) => {
    scrollerRef.current?.scrollBy({ left: direction * 140, behavior: "smooth" });
  };

  return (
    <div className="project-todo-artifact-agents" aria-label={effectiveLabel}>
      <button
        type="button"
        className="project-todo-artifact-agent-arrow left"
        aria-label={t("projectTodo.artifactAgents.scrollLeft")}
        onClick={() => scroll(-1)}
      >
        <ArrowIcon direction="left" />
      </button>
      <div ref={scrollerRef} className="project-todo-artifact-agent-scroll">
        {artifacts.map((artifact) => (
          <ArtifactAgentChip
            key={artifact.id}
            artifact={artifact}
            onOpenArtifact={onOpenArtifact}
          />
        ))}
      </div>
      <button
        type="button"
        className="project-todo-artifact-agent-arrow right"
        aria-label={t("projectTodo.artifactAgents.scrollRight")}
        onClick={() => scroll(1)}
      >
        <ArrowIcon direction="right" />
      </button>
    </div>
  );
}

function ArtifactAgentChip({
  artifact,
  onOpenArtifact
}: {
  artifact: ProjectTodoArtifact;
  onOpenArtifact?: (artifact: ProjectTodoArtifact) => void;
}) {
  const { t } = useI18n();
  const name = projectTodoArtifactAgentLabel(artifact);
  const status = projectTodoArtifactStatusText(artifact.status, t);
  const content = (
    <>
      <ProjectTodoAgentStatusIcon
        status={artifact.agent_status}
        terminalLinked={projectTodoArtifactHasTerminal(artifact)}
        label={t("projectTodo.artifactAgents.agentArtifact", { name })}
      />
      <span className="project-todo-artifact-agent-name" title={name}>{name}</span>
      <small>{status}</small>
    </>
  );

  if (onOpenArtifact === undefined) {
    return <span className="project-todo-artifact-agent-chip">{content}</span>;
  }

  return (
    <button
      type="button"
      className="project-todo-artifact-agent-chip clickable"
      onClick={() => onOpenArtifact(artifact)}
    >
      {content}
    </button>
  );
}

function ArrowIcon({ direction }: { direction: "left" | "right" }) {
  return (
    <svg
      aria-hidden="true"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      {direction === "left" ? <path d="m15 6-6 6 6 6" /> : <path d="m9 6 6 6-6 6" />}
    </svg>
  );
}
