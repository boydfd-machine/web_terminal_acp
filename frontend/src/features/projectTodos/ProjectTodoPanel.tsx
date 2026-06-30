import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";

import type { ProjectTodoFocusRequest } from "../../appState";
import { DEFAULT_AGENT_CLIENTS } from "../../agentLaunch";
import { fetchAgentClients, fetchArtifactPlugins } from "../../api";
import type { Project, ProjectTodo, ProjectTodoArtifact, ProjectTodoListItem } from "../../types";
import { useI18n } from "../../i18n";
import { projectTodoDetailFromListItem, type EditingTodoField } from "./projectTodoPanelUtils";
import { ProjectTodoBoard } from "../../components/ProjectTodoBoardView";
import { ProjectTodoList } from "../../components/ProjectTodoViews";
import { isProjectTodoNotFoundError, projectTodoFocusRequestKey, useProjectTodoDetailQuery } from "./useProjectTodoDetailQuery";
import { useProjectTodoAttachmentMutations } from "./useProjectTodoAttachmentMutations";
import { useProjectTodoCreateDialog } from "./useProjectTodoCreateDialog";
import { useProjectTodoCacheUpdates } from "./useProjectTodoCacheUpdates";
import { useProjectTodoMutations } from "./useProjectTodoMutations";
import { useProjectTodoOpenHandlers } from "./useProjectTodoOpenHandlers";
import { useProjectTodoRouteSync } from "./useProjectTodoRouteSync";
import { useProjectTodosQuery } from "./useProjectTodosQuery";
import { useProjectTodoMoveHandler } from "./useProjectTodoMoveHandler";
import type { ProjectTodoDateFilter } from "./projectTodoDateFilter";
import { ProjectTodoInlineCreateFormHost } from "./ProjectTodoInlineCreateFormHost";
import { ProjectTodoPanelDialogs } from "./ProjectTodoPanelDialogs";

type ProjectTodoPanelProps = {
  clientId: string;
  projectPath: string;
  focusRequest?: ProjectTodoFocusRequest | null;
  dateFilter?: ProjectTodoDateFilter;
  projects?: Project[];
  routeWindowId?: string | null;
  viewMode?: "list" | "board";
  onOpenArtifact?: (artifact: ProjectTodoArtifact, projectPath?: string | null) => void;
  onOpenTerminalWindow?: (windowId: string, projectPath: string, title?: string | null) => void;
  onSelectWindow: (windowId: string, projectPath: string) => void;
};

export function ProjectTodoPanel({
  clientId,
  projectPath,
  focusRequest = null,
  dateFilter,
  projects = [],
  routeWindowId = null,
  viewMode = "list",
  onOpenArtifact,
  onSelectWindow,
  onOpenTerminalWindow = onSelectWindow
}: ProjectTodoPanelProps) {
  const { t } = useI18n();
  const [inlineCreatingTodo, setInlineCreatingTodo] = useState(false);
  const [createDialogCreatingTodo, setCreateDialogCreatingTodo] = useState(false);
  const createDialog = useProjectTodoCreateDialog();
  const [createFormResetToken, setCreateFormResetToken] = useState(0);
  const [commentTargetId, setCommentTargetId] = useState<string | null>(null);
  const [dispatchTargetId, setDispatchTargetId] = useState<string | null>(null);
  const [todoTypeManagerOpen, setTodoTypeManagerOpen] = useState(false);
  const [selectedTodoId, setSelectedTodoId] = useState<string | null>(null);
  const [focusedSelectionRequestKey, setFocusedSelectionRequestKey] = useState<string | null>(null);
  const [editingTodoField, setEditingTodoField] = useState<EditingTodoField | null>(null);
  const [editTitle, setEditTitle] = useState("");
  const [editDescription, setEditDescription] = useState("");
  const todoRefs = useRef(new Map<string, HTMLElement>());
  const handledFocusRequestRef = useRef<string | null>(null);
  const {
    agentWorkStatusByWindowId,
    grouped,
    queryKey,
    todos,
    todosQuery
  } = useProjectTodosQuery({ clientId, dateFilter, projectPath });
  const artifactPluginsQuery = useQuery({
    queryKey: ["artifact-plugins", "project-todo-panel"],
    queryFn: fetchArtifactPlugins,
    staleTime: 60000
  });
  const agentClientsQuery = useQuery({
    queryKey: ["agent-clients", clientId],
    queryFn: () => fetchAgentClients(clientId),
    staleTime: 60000
  });
  const agentClients = agentClientsQuery.data?.agent_clients ?? DEFAULT_AGENT_CLIENTS;
  const artifactPlugins = artifactPluginsQuery.data?.plugins ?? [];
  const availableProjects = useMemo(
    () => projects.some((project) => project.path === projectPath)
      ? projects
      : [{
          client_id: clientId,
          path: projectPath,
          display_name: null,
          summary_status: null,
          summary_updated_at: null,
          window_count: 0
        }, ...projects],
    [clientId, projectPath, projects]
  );
  const projectPreference = availableProjects.find((project) => project.path === projectPath)?.agent_preference ?? null;
  const selectedListTodo = selectedTodoId === null ? null : todos.find((todo) => todo.id === selectedTodoId) ?? null;
  const selectedTodoQuery = useProjectTodoDetailQuery(clientId, projectPath, selectedTodoId);
  const selectedListTodoDetail = useMemo(
    () => selectedListTodo === null ? null : projectTodoDetailFromListItem(selectedListTodo),
    [selectedListTodo]
  );
  const selectedTodo = selectedTodoQuery.data ?? selectedListTodoDetail;
  const commentTarget = useProjectTodoDetailQuery(clientId, projectPath, commentTargetId).data ?? null;
  const dispatchTarget = useProjectTodoDetailQuery(clientId, projectPath, dispatchTargetId).data ?? null;
  const selectedWindowId = selectedTodo?.assigned_window_id;
  const selectedTodoAgentWorkStatus = selectedWindowId == null
    ? null
    : agentWorkStatusByWindowId.get(selectedWindowId)
      ?? selectedTodo?.assigned_terminal?.work_status
      ?? null;
  const clearSelectedTodo = useCallback(() => {
    setSelectedTodoId(null);
    setEditingTodoField(null);
  }, []);
  const {
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
  } = useProjectTodoMutations({
    clientId,
    projectPath,
    queryKey,
    selectedTodoId,
    onClearSelectedTodo: clearSelectedTodo,
    setEditingTodoField,
  });
  const {
    attachmentOpenError,
    attachmentPreview,
    attachmentDeleteMutation,
    attachmentUploadMutation,
    closeAttachmentPreview,
    deletingAttachmentIds,
    uploadingAttachmentTodoIds,
    openAttachment,
    uploadAttachments
  } = useProjectTodoAttachmentMutations({
    clientId,
    projectPath,
    queryKey
  });
  const { openTodo } = useProjectTodoOpenHandlers({
    queryClient,
    queryKey,
    todos,
    updateMutation,
    setEditingTodoField,
    setFocusedSelectionRequestKey,
    setSelectedTodoId
  });
  const cacheCreatedTodo = useProjectTodoCacheUpdates({
    clientId,
    dateFilter,
    projectPath,
    queryClient,
    queryKey
  });
  const moveTodo = useProjectTodoMoveHandler({
    grouped,
    queryClient,
    queryKey,
    todos,
    updateMutation
  });
  const creatingTodo = inlineCreatingTodo || createDialogCreatingTodo;
  const busy = creatingTodo
    || updateMutation.isPending
    || deleteMutation.isPending
    || mergeMutation.isPending
    || projectMoveMutation.isPending
    || artifactMutation.isPending
    || artifactRetryMutation.isPending;
  const focusTargetLoaded = focusRequest !== null && todos.some((todo) => todo.id === focusRequest.todoId);
  const matchingFocusRequestKey = focusRequest !== null
    && focusRequest.clientId === clientId
    && focusRequest.projectPath === projectPath
      ? projectTodoFocusRequestKey(focusRequest)
      : null;
  const { writeTodoRoute } = useProjectTodoRouteSync({
    clientId,
    projectPath,
    selectedTodoId,
    viewMode,
    windowId: routeWindowId,
    onRouteClear: clearSelectedTodo,
    onRouteTodo: (todoId) => openTodo(todoId, "focus"),
  });
  const openTodoFromUi = useCallback((todoId: string) => {
    openTodo(todoId);
    writeTodoRoute(todoId, "push");
  }, [openTodo, writeTodoRoute]);

  useEffect(() => {
    if (
      focusRequest === null
      || focusRequest.clientId !== clientId
      || focusRequest.projectPath !== projectPath
      || !focusTargetLoaded
    ) {
      return;
    }
    const focusRequestKey = projectTodoFocusRequestKey(focusRequest);
    if (handledFocusRequestRef.current === focusRequestKey) {
      return;
    }
    handledFocusRequestRef.current = focusRequestKey;
    setFocusedSelectionRequestKey(focusRequestKey);
    openTodo(focusRequest.todoId, "focus");
    const frame = window.requestAnimationFrame(() => {
      const element = todoRefs.current.get(focusRequest.todoId);
      element?.scrollIntoView({ block: "center", inline: "center" });
      element?.focus({ preventScroll: true });
    });
    return () => window.cancelAnimationFrame(frame);
  }, [clientId, focusRequest, focusTargetLoaded, openTodo, projectPath]);
  useEffect(() => {
    if (focusedSelectionRequestKey === null || matchingFocusRequestKey !== null) {
      return;
    }
    setSelectedTodoId(null);
    setEditingTodoField(null);
    setFocusedSelectionRequestKey(null);
  }, [focusedSelectionRequestKey, matchingFocusRequestKey]);

  const beginTitleEdit = (todo: ProjectTodo) => {
    setSelectedTodoId(todo.id);
    setEditingTodoField({ todoId: todo.id, field: "title" });
    setEditTitle(todo.title);
  };
  const beginDescriptionEdit = (todo: ProjectTodo) => {
    setSelectedTodoId(todo.id);
    setEditingTodoField({ todoId: todo.id, field: "description" });
    setEditDescription(todo.description ?? "");
  };
  const clearDetailRoute = () => { clearSelectedTodo(); writeTodoRoute(null, "push"); };
  const replaceStaleDetailRoute = useCallback(() => {
    clearSelectedTodo();
    writeTodoRoute(null, "replace");
  }, [clearSelectedTodo, writeTodoRoute]);

  useEffect(() => {
    if (
      selectedTodoId === null
      || !selectedTodoQuery.isError
      || !isProjectTodoNotFoundError(selectedTodoQuery.error)
    ) {
      return;
    }

    replaceStaleDetailRoute();
    void queryClient.invalidateQueries({ queryKey });
  }, [
    queryClient,
    queryKey,
    replaceStaleDetailRoute,
    selectedTodoId,
    selectedTodoQuery.error,
    selectedTodoQuery.isError,
  ]);
  const openDispatchModal = (todo: ProjectTodoListItem) => {
    clearDetailRoute();
    setDispatchTargetId(todo.id);
  };
  const openCommentModal = (todo: ProjectTodoListItem | ProjectTodo) => {
    clearDetailRoute();
    setCommentTargetId(todo.id);
  };
  const saveTitleEdit = (todo: ProjectTodo) => {
    if (editTitle.trim().length === 0 || updateMutation.isPending) {
      return;
    }
    updateMutation.mutate({ todo, input: { title: editTitle.trim() } });
  };
  const saveDescriptionEdit = (todo: ProjectTodo) => {
    if (updateMutation.isPending) {
      return;
    }
    updateMutation.mutate({ todo, input: { description: editDescription.trim() || null } });
  };
  const saveArtifactKinds = (todo: ProjectTodo, artifactKinds: string[]) => {
    if (updateMutation.isPending) {
      return;
    }
    updateMutation.mutate({ todo, input: { artifact_kinds: artifactKinds } });
  };
  const saveInputArtifactIds = (todo: ProjectTodo, inputArtifactIds: string[]) => {
    if (updateMutation.isPending) {
      return;
    }
    updateMutation.mutate({ todo, input: { input_artifact_ids: inputArtifactIds } });
  };
  const toggleSchedule = (todo: ProjectTodoListItem, enabled: boolean) => {
    if (updateMutation.isPending) {
      return;
    }
    updateMutation.mutate({ todo, input: { schedule_enabled: enabled } });
  };
  const registerTodoRef = (todoId: string, element: HTMLElement | null) => {
    if (element === null) {
      todoRefs.current.delete(todoId);
      return;
    }
    todoRefs.current.set(todoId, element);
  };
  const managementBar = (
    <div className="project-todo-management-bar">
      <button type="button" onClick={() => setTodoTypeManagerOpen(true)}>{t("projectTodo.panel.manageCardTypes")}</button>
    </div>
  );
  const createTodoForm = (
    <ProjectTodoInlineCreateFormHost
      clientId={clientId}
      projectPath={projectPath}
      resetToken={createFormResetToken}
      agentClients={agentClients}
      projectPreference={projectPreference}
      todos={todos}
      viewMode={viewMode}
      onClearDetailRoute={clearDetailRoute}
      onCreated={(todo) => {
        setCreateFormResetToken((current) => current + 1);
        cacheCreatedTodo(todo);
      }}
      onOpenDispatch={setDispatchTargetId}
      onPendingChange={setInlineCreatingTodo}
    />
  );
  const loadError = todosQuery.isError ? <p className="error" role="alert">{t("projectTodo.panel.loadFailed")}</p> : null;
  const board = (
    <ProjectTodoBoard
      agentWorkStatusByWindowId={agentWorkStatusByWindowId}
      busy={busy}
      clientId={clientId}
      commentingTodoIds={commentingTodoIds}
      dispatchErrors={dispatchErrors}
      dispatchingTodoIds={dispatchingTodoIds}
      initialLoading={todosQuery.isLoading && todosQuery.data === undefined}
      projectPath={projectPath}
      selectedTodoId={selectedTodoId}
      todos={todos}
      registerTodoRef={registerTodoRef}
      onCreateChildTodo={createDialog.openCreateChildTodo}
      onCreateTodo={createDialog.openCreateTodo}
      onMoveTodo={moveTodo}
      onComment={openCommentModal}
      onDispatch={openDispatchModal}
      onMergeTodo={(sourceTodoId, targetTodoId) => {
        if (!mergeMutation.isPending) {
          mergeMutation.mutate({ sourceTodoId, targetTodoId });
        }
      }}
      onUploadAttachment={uploadAttachments}
      onOpenTodo={openTodoFromUi}
      onOpenTerminalWindow={onOpenTerminalWindow}
      onRetryArtifact={(todo, artifact) => {
        if (!artifactRetryMutation.isPending) {
          artifactRetryMutation.mutate({ todo, artifact });
        }
      }}
      onToggleSchedule={toggleSchedule}
      retryingArtifactLinkId={artifactRetryMutation.isPending ? artifactRetryMutation.variables.artifact.id : null}
      uploadingAttachmentTodoIds={uploadingAttachmentTodoIds}
    />
  );

  return (
    <section className="detail-section project-todos" aria-label={t("projectTodo.panel.label")}>
      {viewMode === "board" ? (
        <>
          {loadError}
          {board}
        </>
      ) : (
        <>
          {managementBar}
          {createTodoForm}
          {loadError}
          <ProjectTodoList
            agentWorkStatusByWindowId={agentWorkStatusByWindowId}
            busy={busy}
            todos={todos}
            projectPath={projectPath}
            selectedTodoId={selectedTodoId}
            registerTodoRef={registerTodoRef}
            onOpenTodo={openTodoFromUi}
            onCreateChildTodo={createDialog.openCreateChildTodo}
            onSelectWindow={onSelectWindow}
            onToggleSchedule={toggleSchedule}
          />
        </>
      )}
      <ProjectTodoPanelDialogs
        artifactPlugins={artifactPlugins}
        attachments={{
          attachmentOpenError,
          attachmentPreview,
          attachmentDeleteMutation,
          attachmentUploadMutation,
          closeAttachmentPreview,
          deletingAttachmentIds,
          openAttachment,
          uploadingAttachmentTodoIds,
          uploadAttachments
        }}
        availableProjects={availableProjects}
        busy={busy}
        clientId={clientId}
        commentTarget={commentTarget}
        commentTargetId={commentTargetId}
        createDialog={createDialog}
        createDialogCreatingTodo={createDialogCreatingTodo}
        detailLoaded={selectedTodoQuery.data !== undefined}
        dispatchTarget={dispatchTarget}
        dispatchTargetId={dispatchTargetId}
        editDescription={editDescription}
        editingTodoField={editingTodoField}
        editTitle={editTitle}
        moveTodo={moveTodo}
        mutations={{
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
        }}
        projectPreference={projectPreference}
        projectPath={projectPath}
        selectedTodo={selectedTodo}
        selectedTodoAgentWorkStatus={selectedTodoAgentWorkStatus}
        setCommentTargetId={setCommentTargetId}
        setCreateDialogCreatingTodo={setCreateDialogCreatingTodo}
        setDispatchTargetId={setDispatchTargetId}
        setEditDescription={setEditDescription}
        setEditingTodoField={setEditingTodoField}
        setEditTitle={setEditTitle}
        setTodoTypeManagerOpen={setTodoTypeManagerOpen}
        todoTypeManagerOpen={todoTypeManagerOpen}
        todos={todos}
        onBeginDescriptionEdit={beginDescriptionEdit}
        onBeginTitleEdit={beginTitleEdit}
        onClearDetailRoute={clearDetailRoute}
        onCreatedTodo={(todo) => {
          setCreateFormResetToken((current) => current + 1);
          cacheCreatedTodo(todo);
        }}
        onOpenArtifact={onOpenArtifact}
        onOpenCommentModal={openCommentModal}
        onOpenDispatchModal={openDispatchModal}
        onOpenTodo={openTodoFromUi}
        onSaveArtifactKinds={saveArtifactKinds}
        onSaveDescriptionEdit={saveDescriptionEdit}
        onSaveInputArtifactIds={saveInputArtifactIds}
        onSaveTitleEdit={saveTitleEdit}
        onSelectWindow={onSelectWindow}
      />
    </section>
  );
}
