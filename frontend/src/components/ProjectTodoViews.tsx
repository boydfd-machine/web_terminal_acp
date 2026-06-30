import { useI18n } from "../i18n";
import type { ProjectTodoListItem, WorkStatus } from "../types";
import { ProjectTodoAgentStatusIcon } from "./ProjectTodoAgentStatusIcon";
import {
  projectTodoStatusLabel,
  projectTodoStatusClass,
} from "./projectTodoDisplay";
import {
  projectTodoDispatchStageActive,
  projectTodoDispatchTitle,
  projectTodoDispatchTone,
} from "./projectTodoDispatchStage";
import { GitMergeStatusBadge } from "./GitMergeStatus";
import { ProjectTodoScheduleToggle } from "./ProjectTodoScheduleControls";
import { ProjectTodoCreateChildButton } from "./ProjectTodoCreateChildButton";

type ProjectTodoViewSharedProps = {
  agentWorkStatusByWindowId: Map<string, WorkStatus>;
  busy: boolean;
  projectPath: string;
  registerTodoRef: (todoId: string, element: HTMLElement | null) => void;
  onCreateChildTodo: (todo: ProjectTodoListItem) => void;
  onOpenTodo: (todoId: string) => void;
  onSelectWindow: (windowId: string, projectPath: string) => void;
  onToggleSchedule: (todo: ProjectTodoListItem, enabled: boolean) => void;
};

type ProjectTodoListProps = ProjectTodoViewSharedProps & {
  selectedTodoId: string | null;
  todos: ProjectTodoListItem[];
};

export function ProjectTodoList({
  agentWorkStatusByWindowId,
  busy,
  todos,
  projectPath,
  selectedTodoId,
  registerTodoRef,
  onCreateChildTodo,
  onOpenTodo,
  onSelectWindow,
  onToggleSchedule,
}: ProjectTodoListProps) {
  const { t } = useI18n();
  return (
    <div className="project-todo-list" aria-label={t("projectTodo.views.list")}>
      {todos.map((todo) => {
        const terminalWindowId = todo.assigned_window_id;
        const dispatchTitle = projectTodoDispatchTitle(todo.dispatch_stage, todo.dispatch_error, t);
        return (
          <article
            key={todo.id}
            ref={(element) => registerTodoRef(todo.id, element)}
            className={selectedTodoId === todo.id ? "project-todo-list-row selected" : "project-todo-list-row"}
            tabIndex={-1}
          >
            <button type="button" className="project-todo-list-main" onClick={() => onOpenTodo(todo.id)}>
              <ProjectTodoAgentStatusIcon
                status={terminalWindowId === null ? null : agentWorkStatusByWindowId.get(terminalWindowId) ?? null}
                terminalLinked={terminalWindowId !== null}
                dispatchActive={projectTodoDispatchStageActive(todo)}
                dispatchTitle={dispatchTitle}
                dispatchTone={projectTodoDispatchTone(todo.dispatch_stage)}
              />
              <strong>{todo.title}</strong>
              <span className={`project-todo-status-pill ${projectTodoStatusClass(todo.status)}`}>
                {projectTodoStatusLabel(todo.status, t)}
              </span>
            </button>
            <span className="project-todo-type-pill">{todo.todo_type.name.trim() || todo.todo_type.id}</span>
            <ProjectTodoScheduleToggle busy={busy} todo={todo} onToggleSchedule={onToggleSchedule} />
            <ProjectTodoCreateChildButton
              busy={busy}
              className="project-todo-card-action-button project-todo-list-action-button project-todo-create-child-button"
              todo={todo}
              onCreateChild={onCreateChildTodo}
            />
            <GitMergeStatusBadge source={todo.implementation_worktree} compact />
            {terminalWindowId && (
              <button
                type="button"
                className="project-todo-terminal-button"
                onClick={() => onSelectWindow(terminalWindowId, projectPath)}
              >
                {t("projectTodo.create.terminal")}
              </button>
            )}
          </article>
        );
      })}
      {todos.length === 0 && <p className="muted">{t("projectTodo.views.noTodos")}</p>}
    </div>
  );
}
