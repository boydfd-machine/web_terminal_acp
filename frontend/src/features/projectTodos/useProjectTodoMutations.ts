import { useRef, useState, type Dispatch, type SetStateAction } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";

import {
  commentProjectTodo,
  createTerminalArtifact,
  deleteProjectTodo,
  dispatchProjectTodo,
  fetchProjectTodo,
  isApiFailure,
  linkProjectTodoArtifact,
  retryProjectTodoArtifact,
  updateProjectTodo
} from "../../api";
import { moveProjectTodoToProject } from "../../apiProjectTodos";
import { useI18n } from "../../i18n";
import type { ProjectTodo, ProjectTodoList as ProjectTodoListPayload } from "../../types";
import type { ProjectTodoDispatchToastState } from "../../components/ProjectTodoDispatchToast";
import { useAppPrompt } from "../../components/AppPromptProvider";
import { markTerminalListsStale } from "../../uiEvents";
import { projectTodoMergePayload } from "./projectTodoBoardModel";
import {
  isReviewSeenOnlyUpdate,
  projectTodoDetailQueryKey,
  projectTodoCommentErrorMessage,
  projectTodoDispatchErrorMessage,
  projectTodoQueryKey,
  upsertProjectTodoInList,
  type TodoCommentVariables,
  type TodoArtifactGenerateVariables,
  type TodoArtifactRetryVariables,
  type EditingTodoField,
  type TodoDispatchVariables,
  type TodoMergeVariables,
  type TodoProjectMoveVariables,
  type TodoUpdateVariables
} from "./projectTodoPanelUtils";

type UseProjectTodoMutationsArgs = {
  clientId: string;
  projectPath: string;
  queryKey: ReturnType<typeof projectTodoQueryKey>;
  selectedTodoId: string | null;
  onClearSelectedTodo: () => void;
  setEditingTodoField: Dispatch<SetStateAction<EditingTodoField | null>>;
};

export function useProjectTodoMutations({
  clientId,
  projectPath,
  queryKey,
  selectedTodoId,
  onClearSelectedTodo,
  setEditingTodoField,
}: UseProjectTodoMutationsArgs) {
  const { t } = useI18n();
  const { confirm } = useAppPrompt();
  const queryClient = useQueryClient();
  const [dispatchingTodoIds, setDispatchingTodoIds] = useState<Set<string>>(() => new Set());
  const [commentingTodoIds, setCommentingTodoIds] = useState<Set<string>>(() => new Set());
  const [dispatchErrors, setDispatchErrors] = useState<Record<string, string>>({});
  const [dispatchToast, setDispatchToast] = useState<ProjectTodoDispatchToastState | null>(null);
  const dispatchToastIdRef = useRef(0);
  const projectTodosQueryPrefix = projectTodoQueryKey(clientId, projectPath);
  const invalidateTodos = () => queryClient.invalidateQueries({ queryKey: projectTodosQueryPrefix });
  const markTodosStale = () => queryClient.invalidateQueries({
    queryKey: projectTodosQueryPrefix,
    refetchType: "none"
  });
  const setTodoDetail = (todo: ProjectTodo) => {
    queryClient.setQueryData(projectTodoDetailQueryKey(clientId, projectPath, todo.id), todo);
  };
  const upsertTodoInList = (todo: ProjectTodo) => {
    queryClient.setQueryData<ProjectTodoListPayload>(queryKey, (current) => upsertProjectTodoInList(current, todo));
  };

  const showDispatchToast = (message: string, tone: ProjectTodoDispatchToastState["tone"]) => {
    dispatchToastIdRef.current += 1;
    setDispatchToast({ id: dispatchToastIdRef.current, message, tone });
  };

  const updateMutation = useMutation({
    mutationFn: ({ todo, input }: TodoUpdateVariables) =>
      updateProjectTodo(clientId, projectPath, todo.id, input),
    onError: (_error, variables) => {
      if (variables.optimisticPrevious !== undefined) {
        queryClient.setQueryData(queryKey, variables.optimisticPrevious);
      }
    },
    onSuccess: (todo, variables) => {
      setTodoDetail(todo);
      if (!isReviewSeenOnlyUpdate(variables.input)) {
        setEditingTodoField(null);
      }
      void invalidateTodos();
    }
  });

  const deleteMutation = useMutation({
    mutationFn: (todo: ProjectTodo) => deleteProjectTodo(clientId, projectPath, todo.id),
    onSuccess: (_, todo) => {
      if (selectedTodoId === todo.id) {
        onClearSelectedTodo();
      }
      queryClient.removeQueries({ queryKey: projectTodoDetailQueryKey(clientId, projectPath, todo.id) });
      void invalidateTodos();
    }
  });
  const confirmDeleteTodo = async (todo: ProjectTodo, onSuccess?: () => void) => {
    if (deleteMutation.isPending) {
      return;
    }
    const confirmed = await confirm({
      title: t("projectTodo.detail.deleteConfirmTitle"),
      message: t("projectTodo.detail.deleteConfirm", { title: todo.title }),
      confirmLabel: t("projectTodo.detail.deleteConfirmSubmit"),
      tone: "danger"
    });
    if (!confirmed) {
      return;
    }
    deleteMutation.mutate(todo, onSuccess === undefined ? undefined : { onSuccess });
  };

  const mergeMutation = useMutation({
    mutationFn: async ({ sourceTodoId, targetTodoId }: TodoMergeVariables): Promise<ProjectTodo> => {
      if (sourceTodoId === targetTodoId) {
        throw new Error("cannot merge a todo into itself");
      }
      const [source, target] = await Promise.all([
        fetchProjectTodo(clientId, projectPath, sourceTodoId),
        fetchProjectTodo(clientId, projectPath, targetTodoId)
      ]);
      const mergedTodo = await updateProjectTodo(clientId, projectPath, target.id, projectTodoMergePayload({ target, source }));
      await deleteProjectTodo(clientId, projectPath, source.id);
      return mergedTodo;
    },
    onSuccess: (mergedTodo, variables) => {
      setTodoDetail(mergedTodo);
      queryClient.removeQueries({ queryKey: projectTodoDetailQueryKey(clientId, projectPath, variables.sourceTodoId) });
      if (selectedTodoId === variables.sourceTodoId) {
        onClearSelectedTodo();
      }
      queryClient.setQueryData<ProjectTodoListPayload>(queryKey, (current) => current === undefined
        ? current
        : {
            todos: current.todos
              .filter((todo) => todo.id !== variables.sourceTodoId)
              .map((todo) => todo.id === mergedTodo.id ? mergedTodo : todo)
          });
      void invalidateTodos();
    }
  });

  const projectMoveMutation = useMutation({
    mutationFn: ({ todo, targetProjectPath }: TodoProjectMoveVariables): Promise<ProjectTodo> =>
      moveProjectTodoToProject(clientId, projectPath, todo.id, targetProjectPath),
    onSuccess: (movedTodo, variables) => {
      queryClient.removeQueries({ queryKey: projectTodoDetailQueryKey(clientId, projectPath, variables.todo.id) });
      queryClient.setQueryData<ProjectTodoListPayload>(queryKey, (current) => current === undefined
        ? current
        : {
            todos: current.todos.filter((todo) => todo.id !== variables.todo.id)
          });
      if (selectedTodoId === variables.todo.id) {
        onClearSelectedTodo();
      }
      queryClient.setQueryData(projectTodoDetailQueryKey(clientId, movedTodo.project_path, movedTodo.id), movedTodo);
      queryClient.invalidateQueries({ queryKey: ["project-todos", clientId], exact: false });
    }
  });

  const dispatchMutation = useMutation({
    mutationFn: async ({ todo, payload, dispatchMode, dependencyIds, prompt, artifactModelSelection }: TodoDispatchVariables): Promise<ProjectTodo> => {
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
      setDispatchingTodoIds((current) => new Set(current).add(todo.id));
      setDispatchErrors((current) => {
        const { [todo.id]: _cleared, ...remaining } = current;
        return remaining;
      });
    },
    onSuccess: (dispatchedTodo) => {
      setTodoDetail(dispatchedTodo);
      upsertTodoInList(dispatchedTodo);
      void markTodosStale();
      markTerminalListsStale(queryClient, clientId);
      showDispatchToast(t("projectTodo.toast.dispatchStarted", { title: dispatchedTodo.title }), "success");
    },
    onError: (error, { todo }) => {
      const message = projectTodoDispatchErrorMessage(error, t);
      setDispatchErrors((current) => ({ ...current, [todo.id]: message }));
      if (!isApiFailure(error)) {
        showDispatchToast(message, "error");
      }
    },
    onSettled: (_data, _error, { todo }) => {
      setDispatchingTodoIds((current) => {
        const next = new Set(current);
        next.delete(todo.id);
        return next;
      });
    }
  });

  const commentMutation = useMutation({
    mutationFn: ({ todo, comment, artifactKinds }: TodoCommentVariables): Promise<ProjectTodo> =>
      commentProjectTodo(clientId, projectPath, todo.id, {
        comment,
        ...(artifactKinds === undefined ? {} : { artifact_kinds: artifactKinds })
      }),
    onMutate: ({ todo }) => {
      setCommentingTodoIds((current) => new Set(current).add(todo.id));
    },
    onSuccess: (commentedTodo) => {
      setTodoDetail(commentedTodo);
      void invalidateTodos();
      queryClient.invalidateQueries({ queryKey: ["window-activity", clientId], exact: false });
      if (commentedTodo.assigned_window_id !== null) {
        queryClient.invalidateQueries({ queryKey: ["window", clientId, commentedTodo.assigned_window_id], exact: false });
      }
      showDispatchToast(t("projectTodo.toast.commentSent", { title: commentedTodo.title }), "success");
    },
    onError: (error) => {
      if (!isApiFailure(error)) {
        showDispatchToast(projectTodoCommentErrorMessage(error, t), "error");
      }
    },
    onSettled: (_data, _error, { todo }) => {
      setCommentingTodoIds((current) => {
        const next = new Set(current);
        next.delete(todo.id);
        return next;
      });
    }
  });

  const artifactMutation = useMutation({
    mutationFn: async ({ todo, artifactKind, artifactScope, title }: TodoArtifactGenerateVariables) => {
      const windowId = todo.review_window_id ?? todo.assigned_window_id;
      if (windowId === null) {
        throw new Error("terminal required");
      }
      const artifact = await createTerminalArtifact(clientId, windowId, {
        artifact_kind: artifactKind,
        artifact_scope: artifactScope,
        project_path: artifactScope === "project" ? projectPath : null,
        title,
        ...(todo.artifact_model_selection !== null
          ? { artifact_model_selection: todo.artifact_model_selection }
          : {}),
        metadata_json: { project_todo_id: todo.id, purpose: "todo_artifact" }
      });
      return linkProjectTodoArtifact(clientId, projectPath, todo.id, {
        artifact_id: artifact.id,
        purpose: "todo_artifact"
      });
    },
    onSuccess: (todo) => {
      setTodoDetail(todo);
      void invalidateTodos();
      const windowId = todo.artifacts[0]?.window_id ?? todo.review_window_id ?? todo.assigned_window_id;
      if (windowId !== null) {
        queryClient.invalidateQueries({ queryKey: ["terminal-artifacts", clientId, windowId], exact: false });
      }
      queryClient.invalidateQueries({ queryKey: ["project-artifacts", clientId, projectPath], exact: false });
    }
  });

  const artifactRetryMutation = useMutation({
    mutationFn: ({ todo, artifact }: TodoArtifactRetryVariables): Promise<ProjectTodo> =>
      retryProjectTodoArtifact(clientId, projectPath, todo.id, artifact.id),
    onSuccess: (todo, variables) => {
      setTodoDetail(todo);
      queryClient.setQueryData<ProjectTodoListPayload>(queryKey, (current) => current === undefined
        ? current
        : {
            todos: current.todos.map((currentTodo) => currentTodo.id === todo.id ? todo : currentTodo)
          });
      void invalidateTodos();
      queryClient.invalidateQueries({ queryKey: ["terminal-artifacts", clientId, variables.artifact.window_id], exact: false });
      for (const artifact of todo.artifacts) {
        queryClient.invalidateQueries({ queryKey: ["terminal-artifacts", clientId, artifact.window_id], exact: false });
      }
      queryClient.invalidateQueries({ queryKey: ["window-activity", clientId], exact: false });
    }
  });

  return {
    artifactMutation,
    artifactRetryMutation,
    commentMutation,
    commentingTodoIds,
    confirmDeleteTodo,
    deleteMutation,
    dispatchErrors,
    dispatchMutation,
    dispatchToast,
    dispatchingTodoIds,
    invalidateTodos,
    mergeMutation,
    projectMoveMutation,
    queryClient,
    setDispatchToast,
    updateMutation
  };
}
