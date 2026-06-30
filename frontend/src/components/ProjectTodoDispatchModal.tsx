import { useEffect, useMemo, useState } from "react";

import {
  artifactModelAgentFromTodo,
  artifactModelDefaultSelection
} from "../artifactModelSelection";
import { useI18n } from "../i18n";
import type { AgentClient, AgentLaunchKind, AgentModelSelection, ProjectAgentPreference, ProjectTodo, ProjectTodoDispatchMode, ProjectTodoListItem } from "../types";
import { DEFAULT_AGENT_CLIENTS } from "../agentLaunch";
import { ArtifactModelSelectionField } from "./ArtifactModelSelectionField";
import {
  PROJECT_TODO_BOARD_COLUMN_ORDER,
  projectTodoBoardColumnLabel,
  projectTodoStatusLabel,
  projectTodoBoardColumn,
  projectTodoStatusClass,
  type ProjectTodoBoardColumn
} from "./projectTodoDisplay";
import { projectTodoBoardOrder } from "./projectTodoPanelUtils";
import {
  ProjectTodoDispatchTemplateEditor,
  projectTodoDispatchPromptPreview
} from "./ProjectTodoDispatchTemplateEditor";
import { TerminalCreateModal, type TerminalCreateSubmit } from "./TerminalCreateModal";

type ProjectTodoDispatchModalProps = {
  isOpen: boolean;
  clientId: string;
  projectPath: string;
  projectPreference?: ProjectAgentPreference | null;
  agentClients?: AgentClient[];
  todo: ProjectTodo | null;
  todos: ProjectTodoListItem[];
  creatingTerminal: boolean;
  onClose: () => void;
  onSubmit: (
    payload: TerminalCreateSubmit,
    dispatchMode: ProjectTodoDispatchMode,
    dependencyIds: string[],
    prompt: string | null,
    artifactModelSelection: AgentModelSelection | null
  ) => void;
};

type DispatchAfterColumnFilter = "ALL" | ProjectTodoBoardColumn;

export function ProjectTodoDispatchModal({
  isOpen,
  clientId,
  projectPath,
  projectPreference = null,
  agentClients = DEFAULT_AGENT_CLIENTS,
  todo,
  todos,
  creatingTerminal,
  onClose,
  onSubmit,
}: ProjectTodoDispatchModalProps) {
  const { t } = useI18n();
  const [dispatchMode, setDispatchMode] = useState<ProjectTodoDispatchMode>("submit");
  const [dependencyIds, setDependencyIds] = useState<string[]>([]);
  const [artifactModelSelection, setArtifactModelSelection] = useState<AgentModelSelection | null>(null);
  const defaultPrompt = useMemo(
    () => todo === null ? "" : projectTodoDispatchPromptPreview(todo, projectPath),
    [projectPath, todo],
  );
  const [prompt, setPrompt] = useState(defaultPrompt);
  const candidates = useMemo(
    () => todos.filter((candidate) => candidate.id !== todo?.id).sort(projectTodoBoardOrder),
    [todo?.id, todos],
  );

  useEffect(() => {
    setDispatchMode("submit");
    setDependencyIds(todo?.dependencies.map((dependency) => dependency.id) ?? []);
    setPrompt(defaultPrompt);
    setArtifactModelSelection(todo?.artifact_model_selection ?? null);
  }, [defaultPrompt, todo?.id, todo?.dependencies, todo?.artifact_model_selection]);

  const preferenceAgent = todo?.assigned_agent == null ? projectPreference?.agent_client ?? undefined : undefined;
  const preferenceProfileId = todo?.agent_profile_id == null ? projectPreference?.agent_profile_id ?? null : todo.agent_profile_id;
  const artifactModelAgent = artifactModelAgentFromTodo(todo, projectPreference, agentClients);
  const effectiveArtifactModelSelection = artifactModelSelection ?? artifactModelDefaultSelection(artifactModelAgent);

  return (
    <TerminalCreateModal
      isOpen={isOpen}
      clientId={clientId}
      context={todo === null ? null : {
        title: t("projectTodo.dispatch.title"),
        description: todo.title,
        cwd: projectPath,
        initialAgent: todo.assigned_agent === null ? preferenceAgent as AgentLaunchKind | undefined : todo.assigned_agent as AgentLaunchKind,
        initialAgentProfileId: preferenceProfileId,
        initialAgentCommand: todo.assigned_agent === null ? projectPreference?.agent_command ?? null : null,
        initialAgentModelSelection: todo.assigned_agent === null ? projectPreference?.agent_model_selection ?? null : null,
        requireAgent: true,
        showConfigInitially: true,
        submitLabel: t("projectTodo.dispatch.submit")
      }}
      creatingTerminal={creatingTerminal}
      onClose={onClose}
      onSubmit={(payload) => {
        const promptOverride = prompt.trim().length === 0 || prompt.trim() === defaultPrompt.trim() ? null : prompt;
        onSubmit(payload, dispatchMode, dependencyIds, promptOverride, effectiveArtifactModelSelection);
      }}
    >
      <ArtifactModelSelectionField
        agent={artifactModelAgent}
        className="project-todo-dispatch-artifact-model"
        value={artifactModelSelection}
        onChange={setArtifactModelSelection}
      />
      <div className="project-todo-dispatch-mode" role="group" aria-label={t("projectTodo.dispatch.inputMode")}>
        <span>{t("projectTodo.dispatch.inputMode")}</span>
        <div className="project-todo-dispatch-mode-options">
          <button
            type="button"
            className={dispatchMode === "submit" ? "active" : undefined}
            aria-pressed={dispatchMode === "submit"}
            onClick={() => setDispatchMode("submit")}
          >
            {t("projectTodo.dispatch.enter")}
          </button>
          <button
            type="button"
            className={dispatchMode === "compose" ? "active" : undefined}
            aria-pressed={dispatchMode === "compose"}
            onClick={() => setDispatchMode("compose")}
          >
            {t("projectTodo.dispatch.compose")}
          </button>
        </div>
      </div>
      {candidates.length > 0 && (
        <ProjectTodoDispatchAfterSelector
          candidates={candidates}
          selectedIds={dependencyIds}
          onSelectionChange={setDependencyIds}
        />
      )}
      {todo !== null && (
        <ProjectTodoDispatchTemplateEditor
          value={prompt}
          onChange={setPrompt}
          label={t("projectTodo.dispatch.prompt")}
          rows={7}
          compact
          showVariables={false}
        />
      )}
    </TerminalCreateModal>
  );
}

function ProjectTodoDispatchAfterSelector({
  candidates,
  selectedIds,
  onSelectionChange,
}: {
  candidates: ProjectTodoListItem[];
  selectedIds: string[];
  onSelectionChange: (ids: string[]) => void;
}) {
  const { t } = useI18n();
  const [columnFilter, setColumnFilter] = useState<DispatchAfterColumnFilter>("ALL");
  const selected = new Set(selectedIds);
  const counts = useMemo(() => {
    const next = new Map<DispatchAfterColumnFilter, number>([["ALL", candidates.length]]);
    for (const column of PROJECT_TODO_BOARD_COLUMN_ORDER) {
      next.set(column, 0);
    }
    for (const candidate of candidates) {
      const column = projectTodoBoardColumn(candidate);
      next.set(column, (next.get(column) ?? 0) + 1);
    }
    return next;
  }, [candidates]);
  const visibleCandidates = useMemo(
    () => columnFilter === "ALL"
      ? candidates
      : candidates.filter((candidate) => projectTodoBoardColumn(candidate) === columnFilter),
    [candidates, columnFilter],
  );
  return (
    <fieldset className="project-todo-dispatch-after">
      <legend>{t("projectTodo.dispatch.after")}</legend>
      <div className="project-todo-dispatch-after-filters" role="group" aria-label={t("projectTodo.dispatch.dependencyFilter")}>
        <button
          type="button"
          className={columnFilter === "ALL" ? "active" : undefined}
          aria-pressed={columnFilter === "ALL"}
          onClick={() => setColumnFilter("ALL")}
        >
          <span>{t("projectTodo.board.all")}</span>
          <small>{counts.get("ALL") ?? 0}</small>
        </button>
        {PROJECT_TODO_BOARD_COLUMN_ORDER.map((column) => (
          <button
            key={column}
            type="button"
            className={columnFilter === column ? "active" : undefined}
            aria-pressed={columnFilter === column}
            onClick={() => setColumnFilter(column)}
          >
            <span>{projectTodoBoardColumnLabel(column, t)}</span>
            <small>{counts.get(column) ?? 0}</small>
          </button>
        ))}
      </div>
      <div className="project-todo-dispatch-after-list">
        {visibleCandidates.map((candidate) => (
          <label key={candidate.id} className="project-todo-dispatch-after-option">
            <input
              type="checkbox"
              checked={selected.has(candidate.id)}
              onChange={(event) => {
                onSelectionChange(
                  event.target.checked
                    ? [...selectedIds, candidate.id]
                    : selectedIds.filter((id) => id !== candidate.id)
                );
              }}
            />
            <span className={`project-todo-status-pill ${projectTodoStatusClass(candidate.status)}`}>
              {projectTodoStatusLabel(candidate.status, t)}
            </span>
            <strong>{candidate.title}</strong>
          </label>
        ))}
        {visibleCandidates.length === 0 && <span className="project-todo-dispatch-after-empty">{t("projectTodo.dispatch.noCards")}</span>}
      </div>
    </fieldset>
  );
}
