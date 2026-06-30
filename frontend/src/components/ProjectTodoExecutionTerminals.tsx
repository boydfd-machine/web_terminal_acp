import { useMemo, useState } from "react";

import { useI18n } from "../i18n";
import type { ProjectTodo, ProjectTodoRun } from "../types";
import { formatProjectTodoShortDate } from "./projectTodoDisplay";
import { ProjectTodoAgentRecord } from "./ProjectTodoAgentRecord";

type ProjectTodoExecutionTerminalsProps = {
  clientId: string;
  projectPath: string;
  todo: ProjectTodo;
  onSelectWindow: (windowId: string, projectPath: string) => void;
};

export function ProjectTodoExecutionTerminals({
  clientId,
  projectPath,
  todo,
  onSelectWindow
}: ProjectTodoExecutionTerminalsProps) {
  const { t } = useI18n();
  if (todo.execution_kind !== "PERIODIC" || todo.terminal_policy !== "NEW_TERMINAL") {
    return (
      <section className="project-todo-execution-terminals" aria-label={t("projectTodo.execution.agentPreview")}>
        <ProjectTodoAgentRecord
          clientId={clientId}
          projectPath={projectPath}
          terminal={todo.assigned_terminal}
          windowId={todo.assigned_window_id}
          title={t("projectTodo.execution.agentPreview")}
        />
      </section>
    );
  }

  return (
    <ProjectTodoPeriodicTerminalList
      clientId={clientId}
      projectPath={projectPath}
      runs={todo.execution_runs}
      onSelectWindow={onSelectWindow}
    />
  );
}

function ProjectTodoPeriodicTerminalList({
  clientId,
  projectPath,
  runs,
  onSelectWindow
}: {
  clientId: string;
  projectPath: string;
  runs: ProjectTodoRun[];
  onSelectWindow: (windowId: string, projectPath: string) => void;
}) {
  const { t } = useI18n();
  const sortedRuns = useMemo(
    () => [...runs].sort((left, right) => right.run_number - left.run_number),
    [runs]
  );
  const [selectedRunId, setSelectedRunId] = useState<string | null>(null);
  const selectedRun = sortedRuns.find((run) => run.id === selectedRunId) ?? sortedRuns[0] ?? null;

  return (
    <section className="project-todo-execution-terminals" aria-label={t("projectTodo.execution.terminals")}>
      <header>
        <strong>{t("projectTodo.execution.terminals")}</strong>
        <span>{t("projectTodo.execution.executionsCount", { count: sortedRuns.length })}</span>
      </header>
      {sortedRuns.length === 0 ? (
        <p className="muted">{t("projectTodo.execution.empty")}</p>
      ) : (
        <div className="project-todo-execution-terminal-layout">
          <div className="project-todo-execution-terminal-list" aria-label={t("projectTodo.execution.list")}>
            {sortedRuns.map((run) => (
              <ProjectTodoExecutionTerminalItem
                key={run.id}
                run={run}
                selected={selectedRun?.id === run.id}
                onSelect={() => setSelectedRunId(run.id)}
              />
            ))}
          </div>
          {selectedRun && (
            <ProjectTodoExecutionTerminalDetail
              clientId={clientId}
              projectPath={projectPath}
              run={selectedRun}
              onSelectWindow={onSelectWindow}
            />
          )}
        </div>
      )}
    </section>
  );
}

function ProjectTodoExecutionTerminalItem({
  run,
  selected,
  onSelect
}: {
  run: ProjectTodoRun;
  selected: boolean;
  onSelect: () => void;
}) {
  const { t } = useI18n();
  const title = run.assigned_terminal?.title ?? t("projectTodo.execution.run", { number: run.run_number });
  const timestamp = formatProjectTodoShortDate(run.started_at ?? run.created_at);
  return (
    <button
      type="button"
      className={selected ? "project-todo-execution-terminal-item selected" : "project-todo-execution-terminal-item"}
      aria-pressed={selected}
      onClick={onSelect}
    >
      <span className="project-todo-execution-terminal-index">#{run.run_number}</span>
      <span className="project-todo-execution-terminal-main">
        <strong title={title}>{title}</strong>
        <small>{timestamp ? `${run.status} - ${timestamp}` : run.status}</small>
      </span>
    </button>
  );
}

function ProjectTodoExecutionTerminalDetail({
  clientId,
  projectPath,
  run,
  onSelectWindow
}: {
  clientId: string;
  projectPath: string;
  run: ProjectTodoRun;
  onSelectWindow: (windowId: string, projectPath: string) => void;
}) {
  const { t } = useI18n();
  return (
    <section className="project-todo-execution-terminal-detail" aria-label={t("projectTodo.execution.details", { number: run.run_number })}>
      <div className="project-todo-execution-agent-preview" aria-label={t("projectTodo.execution.agentPreview")}>
        <header><strong>{t("projectTodo.execution.agentPreview")}</strong></header>
        <ProjectTodoAgentRecord
          clientId={clientId}
          projectPath={projectPath}
          terminal={run.assigned_terminal}
          windowId={run.window_id}
          title={t("projectTodo.execution.agentPreview")}
        />
      </div>
      <button
        type="button"
        className="project-todo-action-button project-todo-terminal-action"
        disabled={run.window_id === null}
        onClick={() => {
          if (run.window_id !== null) {
            onSelectWindow(run.window_id, projectPath);
          }
        }}
      >
        {t("projectTodo.action.openTerminal")}
      </button>
    </section>
  );
}
