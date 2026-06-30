import { ProjectTodoCreateForm } from "../../components/ProjectTodoCreateForm";
import type { AgentClient, ProjectAgentPreference, ProjectTodo, ProjectTodoListItem } from "../../types";

type ProjectTodoInlineCreateFormHostProps = {
  clientId: string;
  projectPath: string;
  resetToken: number;
  agentClients?: AgentClient[];
  projectPreference?: ProjectAgentPreference | null;
  todos: ProjectTodoListItem[];
  viewMode: "list" | "board";
  onClearDetailRoute: () => void;
  onCreated: (todo: ProjectTodo) => void;
  onOpenDispatch: (todoId: string) => void;
  onPendingChange: (pending: boolean) => void;
};

export function ProjectTodoInlineCreateFormHost({
  clientId,
  projectPath,
  resetToken,
  agentClients,
  projectPreference = null,
  todos,
  viewMode,
  onClearDetailRoute,
  onCreated,
  onOpenDispatch,
  onPendingChange
}: ProjectTodoInlineCreateFormHostProps) {
  return (
    <ProjectTodoCreateForm
      key={`inline:${viewMode}:${resetToken}`}
      clientId={clientId}
      mode="full"
      agentClients={agentClients}
      projectPreference={projectPreference}
      projectPath={projectPath}
      todos={todos}
      onCreated={(todo: ProjectTodo, action) => {
        onCreated(todo);
        if (action === "dispatch") {
          onClearDetailRoute();
          onOpenDispatch(todo.id);
        }
      }}
      onPendingChange={onPendingChange}
    />
  );
}
