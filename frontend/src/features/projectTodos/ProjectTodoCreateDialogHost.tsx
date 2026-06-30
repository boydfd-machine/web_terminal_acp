import { ProjectTodoCreateDialog } from "../../components/ProjectTodoCreateDialog";
import type { TerminalCreateSubmit } from "../../components/TerminalCreateModal";
import type { AgentClient, ProjectAgentPreference, ProjectTodo, ProjectTodoListItem } from "../../types";
import { projectTodoDirectDispatchAgentLaunch } from "./projectTodoDirectDispatch";

type ProjectTodoCreateDialogHostProps = {
  clientId: string;
  creating: boolean;
  isOpen: boolean;
  parentTodoId: string | null;
  agentClients: AgentClient[];
  projectPreference?: ProjectAgentPreference | null;
  projectPath: string;
  todos: ProjectTodoListItem[];
  onClearDetailRoute: () => void;
  onClose: () => void;
  onCreated: (todo: ProjectTodo) => void;
  onDirectDispatch: (todo: ProjectTodo, agentLaunch: TerminalCreateSubmit["agent_launch"]) => void;
  onOpenDispatch: (todoId: string) => void;
  onPendingChange: (pending: boolean) => void;
};

export function ProjectTodoCreateDialogHost({
  clientId,
  creating,
  isOpen,
  parentTodoId,
  agentClients,
  projectPreference = null,
  projectPath,
  todos,
  onClearDetailRoute,
  onClose,
  onCreated,
  onDirectDispatch,
  onOpenDispatch,
  onPendingChange
}: ProjectTodoCreateDialogHostProps) {
  return (
    <ProjectTodoCreateDialog
      clientId={clientId}
      directDispatch
      isOpen={isOpen}
      parentTodoId={parentTodoId}
      agentClients={agentClients}
      projectPreference={projectPreference}
      projectPath={projectPath}
      todos={todos}
      creating={creating}
      onClose={onClose}
      onCreated={(todo, action) => {
        onCreated(todo);
        onClose();
        if (action === "direct-dispatch") {
          onClearDetailRoute();
          onDirectDispatch(todo, projectTodoDirectDispatchAgentLaunch(todo, agentClients, projectPreference));
          return;
        }
        if (action === "dispatch") {
          onClearDetailRoute();
          onOpenDispatch(todo.id);
        }
      }}
      onPendingChange={onPendingChange}
    />
  );
}
