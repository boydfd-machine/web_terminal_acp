import { useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { dispatchProjectTodo, fetchAgentClients, fetchProjectTodos, isApiFailure } from "../api";
import { DEFAULT_AGENT_CLIENTS } from "../agentLaunch";
import { useI18n } from "../i18n";
import type { AgentModelSelection, ProjectAgentPreference, ProjectTodo, ProjectTodoDispatchMode, ProjectTodoList } from "../types";
import type { TerminalCreateSubmit } from "./TerminalCreateModal";
import { ProjectTodoCreateForm } from "./ProjectTodoCreateForm";
import { ProjectTodoDispatchModal } from "./ProjectTodoDispatchModal";
import {
  ProjectTodoDispatchToast,
  type ProjectTodoDispatchToastState
} from "./ProjectTodoDispatchToast";
import { ProjectTodoTypeManagerModal } from "./ProjectTodoTypeManager";
import {
  projectTodoDetailQueryKey,
  projectTodoDispatchErrorMessage,
  projectTodoQueryKey,
  upsertProjectTodoInList
} from "./projectTodoPanelUtils";
import { ProjectTodoDateFilterControls } from "./ProjectTodoDateFilterControls";
import {
  defaultProjectTodoDateFilter,
  projectTodoDateFilterRequest,
  projectTodoUpdatedAtMatchesDateFilter,
  type ProjectTodoDateFilter
} from "../features/projectTodos/projectTodoDateFilter";
import { markTerminalListsStale } from "../uiEvents";
import { projectTodoDirectDispatchAgentLaunch } from "../features/projectTodos/projectTodoDirectDispatch";

type ProjectTodoSidebarControlsProps = {
  clientId: string;
  dateFilter?: ProjectTodoDateFilter;
  projectPreference?: ProjectAgentPreference | null;
  projectPath: string;
  onDateFilterChange?: (filter: ProjectTodoDateFilter) => void;
};

type SidebarTodoDispatchVariables = {
  todo: ProjectTodo;
  payload: TerminalCreateSubmit;
  dispatchMode: ProjectTodoDispatchMode;
  dependencyIds: string[];
  prompt: string | null;
  artifactModelSelection: AgentModelSelection | null;
};

export function ProjectTodoSidebarControls({
  clientId,
  dateFilter,
  projectPreference = null,
  projectPath,
  onDateFilterChange
}: ProjectTodoSidebarControlsProps) {
  const { t } = useI18n();
  const queryClient = useQueryClient();
  const queryKey = projectTodoQueryKey(clientId, projectPath);
  const [creatingTodo, setCreatingTodo] = useState(false);
  const [createFormResetToken, setCreateFormResetToken] = useState(0);
  const [dispatchTarget, setDispatchTarget] = useState<ProjectTodo | null>(null);
  const [dispatchingTodoId, setDispatchingTodoId] = useState<string | null>(null);
  const [dispatchToast, setDispatchToast] = useState<ProjectTodoDispatchToastState | null>(null);
  const [internalDateFilter, setInternalDateFilter] = useState(defaultProjectTodoDateFilter);
  const [todoTypeManagerOpen, setTodoTypeManagerOpen] = useState(false);
  const dispatchToastIdRef = useRef(0);
  const effectiveDateFilter = dateFilter ?? internalDateFilter;
  const activeQueryKey = projectTodoQueryKey(clientId, projectPath, effectiveDateFilter);
  const todosQuery = useQuery({
    queryKey: activeQueryKey,
    queryFn: () => fetchProjectTodos(clientId, projectPath, projectTodoDateFilterRequest(effectiveDateFilter)),
    refetchInterval: 10000
  });
  const agentClientsQuery = useQuery({
    queryKey: ["agent-clients", clientId],
    queryFn: () => fetchAgentClients(clientId),
    staleTime: 60000
  });
  const todos = todosQuery.data?.todos ?? [];
  const agentClients = agentClientsQuery.data?.agent_clients ?? DEFAULT_AGENT_CLIENTS;

  const showDispatchToast = (message: string, tone: ProjectTodoDispatchToastState["tone"]) => {
    dispatchToastIdRef.current += 1;
    setDispatchToast({ id: dispatchToastIdRef.current, message, tone });
  };
  const setTodoDetail = (todo: ProjectTodo) => {
    queryClient.setQueryData(projectTodoDetailQueryKey(clientId, projectPath, todo.id), todo);
  };
  const upsertTodoInList = (todo: ProjectTodo) => {
    queryClient.setQueryData<ProjectTodoList>(
      activeQueryKey,
      (current) => upsertProjectTodoInList(current, todo, {
        allowInsert: projectTodoUpdatedAtMatchesDateFilter(todo, effectiveDateFilter)
      })
    );
  };
  const markTodosStale = () => queryClient.invalidateQueries({ queryKey, refetchType: "none" });
  const dispatchMutation = useMutation({
    mutationFn: async ({
      todo,
      payload,
      dispatchMode,
      dependencyIds,
      prompt,
      artifactModelSelection
    }: SidebarTodoDispatchVariables): Promise<ProjectTodo> => {
      if (payload.agent_launch === null || payload.agent_launch === undefined) {
        throw new Error(t("projectTodo.dispatch.agentRequired"));
      }
      return dispatchProjectTodo(clientId, projectPath, todo.id, {
        agent_launch: payload.agent_launch,
        dispatch_mode: dispatchMode,
        dispatch_after_todo_ids: dependencyIds,
        prompt,
        ...(artifactModelSelection !== null ? { artifact_model_selection: artifactModelSelection } : {})
      });
    },
    onMutate: ({ todo }) => {
      setDispatchingTodoId(todo.id);
      const dispatchingTodo: ProjectTodo = {
        ...todo,
        dispatch_stage: "STARTING",
        dispatch_error: null
      };
      setTodoDetail(dispatchingTodo);
      upsertTodoInList(dispatchingTodo);
      void markTodosStale();
    },
    onSuccess: (dispatchedTodo) => {
      setTodoDetail(dispatchedTodo);
      upsertTodoInList(dispatchedTodo);
      void markTodosStale();
      markTerminalListsStale(queryClient, clientId);
      showDispatchToast(t("projectTodo.toast.dispatchStarted", { title: dispatchedTodo.title }), "success");
    },
    onError: (error, { todo }) => {
      setTodoDetail(todo);
      upsertTodoInList(todo);
      void markTodosStale();
      if (!isApiFailure(error)) {
        showDispatchToast(projectTodoDispatchErrorMessage(error, t), "error");
      }
    },
    onSettled: () => {
      setDispatchingTodoId(null);
    }
  });

  return (
    <>
      <div className="project-todo-sidebar-controls" aria-label={t("projectTodo.sidebar.controls")}>
        <div className="project-todo-management-bar">
          <ProjectTodoDateFilterControls
            filter={effectiveDateFilter}
            onChange={onDateFilterChange ?? setInternalDateFilter}
          />
          <button
            type="button"
            onClick={() => setTodoTypeManagerOpen(true)}
          >
            {t("projectTodo.panel.manageCardTypes")}
          </button>
        </div>
        <ProjectTodoCreateForm
          key={`sidebar:${createFormResetToken}`}
          clientId={clientId}
          directDispatch
          agentClients={agentClients}
          mode="quick"
          projectPreference={projectPreference}
          projectPath={projectPath}
          todos={todos}
          onCreated={(todo, action) => {
            setCreateFormResetToken((current) => current + 1);
            setTodoDetail(todo);
            upsertTodoInList(todo);
            void markTodosStale();
            if (action === "direct-dispatch") {
              dispatchMutation.mutate({
                todo,
                payload: {
                  cwd: projectPath,
                  agent_launch: projectTodoDirectDispatchAgentLaunch(todo, agentClients, projectPreference)
                },
                dispatchMode: "submit",
                dependencyIds: [],
                prompt: null,
                artifactModelSelection: todo.artifact_model_selection ?? null
              });
              return;
            }
            if (action === "dispatch") {
              setDispatchTarget(todo);
            }
          }}
          onPendingChange={setCreatingTodo}
        />
      </div>
      <ProjectTodoDispatchModal
        isOpen={dispatchTarget !== null}
        clientId={clientId}
        projectPath={projectPath}
        projectPreference={projectPreference}
        agentClients={agentClients}
        todo={dispatchTarget}
        todos={todos}
        creatingTerminal={creatingTodo || dispatchMutation.isPending || (dispatchTarget !== null && dispatchingTodoId === dispatchTarget.id)}
        onClose={() => {
          if (!dispatchMutation.isPending) {
            setDispatchTarget(null);
          }
        }}
        onSubmit={(payload, dispatchMode, dependencyIds, prompt, artifactModelSelection) => {
          if (dispatchTarget !== null) {
            const todo = dispatchTarget;
            setDispatchTarget(null);
            dispatchMutation.mutate({ todo, payload, dispatchMode, dependencyIds, prompt, artifactModelSelection });
          }
        }}
      />
      <ProjectTodoDispatchToast
        toast={dispatchToast}
        onDismiss={(id) => setDispatchToast((current) => current?.id === id ? null : current)}
      />
      <ProjectTodoTypeManagerModal
        isOpen={todoTypeManagerOpen}
        clientId={clientId}
        projectPath={projectPath}
        contextLabel={projectPath}
        onClose={() => setTodoTypeManagerOpen(false)}
      />
    </>
  );
}
