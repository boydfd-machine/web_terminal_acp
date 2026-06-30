import { useCallback, type ComponentProps, type Dispatch, type SetStateAction } from "react";
import { useQuery } from "@tanstack/react-query";

import { DEFAULT_AGENT_CLIENTS } from "../../agentLaunch";
import { fetchAgentClients } from "../../api";
import { ProjectTodoAttachmentPreviewDialog } from "../../components/ProjectTodoAttachments";
import { ProjectTodoCommentModal } from "../../components/ProjectTodoCommentModal";
import { ProjectTodoDetailDialog } from "../../components/ProjectTodoDetailDialog";
import { ProjectTodoDispatchModal } from "../../components/ProjectTodoDispatchModal";
import { ProjectTodoDispatchToast } from "../../components/ProjectTodoDispatchToast";
import { ProjectTodoTypeManagerModal } from "../../components/ProjectTodoTypeManager";
import type { TerminalCreateSubmit } from "../../components/TerminalCreateModal";
import type { Project, ProjectTodo, ProjectTodoArtifact, ProjectTodoListItem, ProjectTodoStatus } from "../../types";
import type { EditingTodoField } from "./projectTodoPanelUtils";
import { ProjectTodoCreateDialogHost } from "./ProjectTodoCreateDialogHost";
import type { useProjectTodoAttachmentMutations } from "./useProjectTodoAttachmentMutations";
import type { useProjectTodoCreateDialog } from "./useProjectTodoCreateDialog";
import type { useProjectTodoMutations } from "./useProjectTodoMutations";

type ProjectTodoMutations = ReturnType<typeof useProjectTodoMutations>;
type ProjectTodoAttachmentMutations = ReturnType<typeof useProjectTodoAttachmentMutations>;
type ProjectTodoCreateDialogState = ReturnType<typeof useProjectTodoCreateDialog>;

type ProjectTodoPanelDialogsProps = {
  artifactPlugins: ComponentProps<typeof ProjectTodoDetailDialog>["artifactPlugins"];
  attachments: ProjectTodoAttachmentMutations;
  availableProjects: Project[];
  busy: boolean;
  clientId: string;
  commentTarget: ProjectTodo | null;
  commentTargetId: string | null;
  createDialog: ProjectTodoCreateDialogState;
  createDialogCreatingTodo: boolean;
  detailLoaded: boolean;
  dispatchTarget: ProjectTodo | null;
  dispatchTargetId: string | null;
  editDescription: string;
  editingTodoField: EditingTodoField | null;
  editTitle: string;
  moveTodo: (todoId: string, nextStatus: ProjectTodoStatus) => void;
  mutations: ProjectTodoMutations;
  projectPreference?: Project["agent_preference"];
  projectPath: string;
  selectedTodo: ProjectTodo | null;
  selectedTodoAgentWorkStatus: ComponentProps<typeof ProjectTodoDetailDialog>["agentWorkStatus"];
  setCommentTargetId: Dispatch<SetStateAction<string | null>>;
  setCreateDialogCreatingTodo: Dispatch<SetStateAction<boolean>>;
  setDispatchTargetId: Dispatch<SetStateAction<string | null>>;
  setEditDescription: Dispatch<SetStateAction<string>>;
  setEditingTodoField: Dispatch<SetStateAction<EditingTodoField | null>>;
  setEditTitle: Dispatch<SetStateAction<string>>;
  setTodoTypeManagerOpen: Dispatch<SetStateAction<boolean>>;
  todoTypeManagerOpen: boolean;
  todos: ProjectTodoListItem[];
  onBeginDescriptionEdit: (todo: ProjectTodo) => void;
  onBeginTitleEdit: (todo: ProjectTodo) => void;
  onClearDetailRoute: () => void;
  onCreatedTodo: (todo: ProjectTodo) => void;
  onOpenArtifact?: (artifact: ProjectTodoArtifact, projectPath?: string | null) => void;
  onOpenCommentModal: (todo: ProjectTodoListItem | ProjectTodo) => void;
  onOpenDispatchModal: (todo: ProjectTodoListItem) => void;
  onOpenTodo: (todoId: string) => void;
  onSaveArtifactKinds: (todo: ProjectTodo, artifactKinds: string[]) => void;
  onSaveDescriptionEdit: (todo: ProjectTodo) => void;
  onSaveInputArtifactIds: (todo: ProjectTodo, inputArtifactIds: string[]) => void;
  onSaveTitleEdit: (todo: ProjectTodo) => void;
  onSelectWindow: (windowId: string, projectPath: string) => void;
};

export function ProjectTodoPanelDialogs({
  artifactPlugins,
  attachments,
  availableProjects,
  busy,
  clientId,
  commentTarget,
  commentTargetId,
  createDialog,
  createDialogCreatingTodo,
  detailLoaded,
  dispatchTarget,
  dispatchTargetId,
  editDescription,
  editingTodoField,
  editTitle,
  moveTodo,
  mutations,
  projectPreference = null,
  projectPath,
  selectedTodo,
  selectedTodoAgentWorkStatus,
  setCommentTargetId,
  setCreateDialogCreatingTodo,
  setDispatchTargetId,
  setEditDescription,
  setEditingTodoField,
  setEditTitle,
  setTodoTypeManagerOpen,
  todoTypeManagerOpen,
  todos,
  onBeginDescriptionEdit,
  onBeginTitleEdit,
  onClearDetailRoute,
  onCreatedTodo,
  onOpenArtifact,
  onOpenCommentModal,
  onOpenDispatchModal,
  onOpenTodo,
  onSaveArtifactKinds,
  onSaveDescriptionEdit,
  onSaveInputArtifactIds,
  onSaveTitleEdit,
  onSelectWindow
}: ProjectTodoPanelDialogsProps) {
  const {
    artifactMutation,
    commentMutation,
    commentingTodoIds,
    confirmDeleteTodo,
    dispatchMutation,
    dispatchToast,
    dispatchingTodoIds,
    projectMoveMutation,
    setDispatchToast,
    updateMutation
  } = mutations;
  const {
    attachmentDeleteMutation,
    attachmentOpenError,
    attachmentPreview,
    closeAttachmentPreview,
    deletingAttachmentIds,
    openAttachment,
    uploadingAttachmentTodoIds,
    uploadAttachments
  } = attachments;
  const agentClientsQuery = useQuery({
    queryKey: ["agent-clients", clientId],
    queryFn: () => fetchAgentClients(clientId),
    staleTime: 60000
  });
  const agentClients = agentClientsQuery.data?.agent_clients ?? DEFAULT_AGENT_CLIENTS;
  const closeDetailDialog = useCallback(() => {
    if (selectedTodo !== null && editingTodoField?.todoId === selectedTodo.id) {
      if (editingTodoField.field === "title") {
        onSaveTitleEdit(selectedTodo);
      } else {
        onSaveDescriptionEdit(selectedTodo);
      }
    }
    onClearDetailRoute();
  }, [
    editingTodoField,
    onClearDetailRoute,
    onSaveDescriptionEdit,
    onSaveTitleEdit,
    selectedTodo
  ]);

  return (
    <>
      <ProjectTodoCreateDialogHost
        clientId={clientId}
        creating={createDialogCreatingTodo}
        isOpen={createDialog.isOpen}
        parentTodoId={createDialog.parentTodoId}
        agentClients={agentClients}
        projectPreference={projectPreference}
        projectPath={projectPath}
        todos={todos}
        onClearDetailRoute={onClearDetailRoute}
        onClose={createDialog.close}
        onCreated={onCreatedTodo}
        onDirectDispatch={(todo, agentLaunch: TerminalCreateSubmit["agent_launch"]) => {
          dispatchMutation.mutate({
            todo,
            payload: { cwd: projectPath, agent_launch: agentLaunch },
            dispatchMode: "submit",
            dependencyIds: [],
            prompt: null,
            artifactModelSelection: todo.artifact_model_selection ?? null
          });
        }}
        onOpenDispatch={setDispatchTargetId}
        onPendingChange={setCreateDialogCreatingTodo}
      />
      <ProjectTodoDetailDialog
        agentWorkStatus={selectedTodoAgentWorkStatus}
        artifactPlugins={artifactPlugins}
        projects={availableProjects}
        clientId={clientId}
        projectPath={projectPath}
        todo={selectedTodo}
        detailLoaded={detailLoaded}
        busy={busy}
        commenting={selectedTodo !== null && commentingTodoIds.has(selectedTodo.id)}
        dispatching={selectedTodo !== null && dispatchingTodoIds.has(selectedTodo.id)}
        generatingArtifact={artifactMutation.isPending}
        attachmentOpenError={attachmentOpenError}
        uploadingAttachment={selectedTodo !== null && uploadingAttachmentTodoIds.has(selectedTodo.id)}
        deletingAttachmentIds={deletingAttachmentIds}
        editingField={selectedTodo !== null && editingTodoField?.todoId === selectedTodo.id ? editingTodoField.field : null}
        editTitle={editTitle}
        editDescription={editDescription}
        todos={todos}
        onBeginDescriptionEdit={onBeginDescriptionEdit}
        onBeginTitleEdit={onBeginTitleEdit}
        onCancelEdit={() => setEditingTodoField(null)}
        onClose={closeDetailDialog}
        onDelete={(todo) => { void confirmDeleteTodo(todo, onClearDetailRoute); }}
        onComment={onOpenCommentModal}
        onCreateChild={createDialog.openCreateChildTodo}
        onDispatch={onOpenDispatchModal}
        onEditDescriptionChange={setEditDescription}
        onEditTitleChange={setEditTitle}
        onGenerateArtifact={(todo, artifactOption) => artifactMutation.mutate({ todo, ...artifactOption })}
        onOpenAttachment={openAttachment}
        onOpenArtifact={(artifact) => onOpenArtifact?.(artifact, projectPath)}
        onDeleteAttachment={(todo, attachment) => attachmentDeleteMutation.mutate({ todo, attachment })}
        onOpenTodo={onOpenTodo}
        onMoveToColumn={moveTodo}
        onMoveToProject={(todo, targetProjectPath) => {
          if (!projectMoveMutation.isPending) {
            projectMoveMutation.mutate({ todo, targetProjectPath });
          }
        }}
        onSaveArtifactKinds={onSaveArtifactKinds}
        onSaveInputArtifactIds={onSaveInputArtifactIds}
        onSaveParentTodo={(todo, parentTodoId) => updateMutation.mutate({ todo, input: { parent_todo_id: parentTodoId } })}
        onSaveTodoType={(todo, todoTypeId) => updateMutation.mutate({ todo, input: { todo_type_id: todoTypeId } })}
        onSaveDescriptionEdit={onSaveDescriptionEdit}
        onSaveTitleEdit={onSaveTitleEdit}
        onSelectWindow={onSelectWindow}
        onSaveSchedule={(todo, input) => updateMutation.mutate({ todo, input })}
        onStatus={(todo, nextStatus) => updateMutation.mutate({ todo, input: { status: nextStatus } })}
        onUploadAttachment={uploadAttachments}
      />
      <ProjectTodoAttachmentPreviewDialog preview={attachmentPreview} onClose={closeAttachmentPreview} />
      <ProjectTodoCommentModal
        artifactPlugins={artifactPlugins}
        isOpen={commentTarget !== null}
        todo={commentTarget}
        todos={todos}
        submitting={commentTargetId !== null && commentingTodoIds.has(commentTargetId)}
        onClose={() => {
          if (commentTargetId !== null && !commentingTodoIds.has(commentTargetId)) {
            setCommentTargetId(null);
          }
        }}
        onSubmit={(comment, artifactKinds) => {
          if (commentTarget !== null) {
            const todo = commentTarget;
            commentMutation.mutate({ todo, comment, artifactKinds }, {
              onSuccess: () => setCommentTargetId(null)
            });
          }
        }}
      />
      <ProjectTodoDispatchModal
        isOpen={dispatchTargetId !== null}
        clientId={clientId}
        projectPath={projectPath}
        projectPreference={projectPreference}
        agentClients={agentClients}
        todo={dispatchTarget}
        todos={todos}
        creatingTerminal={dispatchTargetId !== null && dispatchingTodoIds.has(dispatchTargetId)}
        onClose={() => setDispatchTargetId(null)}
        onSubmit={(payload, dispatchMode, dependencyIds, prompt, artifactModelSelection) => {
          if (dispatchTarget !== null) {
            const todo = dispatchTarget;
            setDispatchTargetId(null);
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
