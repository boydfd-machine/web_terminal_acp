import { useRef } from "react";
import { useQuery } from "@tanstack/react-query";

import { fetchProjectTodoTypes } from "../api";
import { useI18n } from "../i18n";
import type {
  ArtifactPluginDescriptor,
  Project,
  ProjectTodo,
  ProjectTodoAttachment,
  ProjectTodoArtifact,
  ProjectTodoListItem,
  ProjectTodoStatus,
  ProjectTodoType,
  WorkStatus
} from "../types";
import { ProjectTodoActionRail } from "./ProjectTodoActionRail";
import type { ProjectTodoGenerateArtifactOption } from "./ProjectTodoActionRail";
import { ProjectTodoAgentRecord } from "./ProjectTodoAgentRecord";
import { ProjectTodoAgentStatusIcon } from "./ProjectTodoAgentStatusIcon";
import { ProjectTodoAttachmentsPanel } from "./ProjectTodoAttachments";
import { ProjectTodoChildCardsPanel } from "./ProjectTodoChildCardsPanel";
import { ProjectTodoCreateChildButton } from "./ProjectTodoCreateChildButton";
import {
  ProjectTodoArtifactAgentsPanel,
  ProjectTodoRequestedArtifactsPanel
} from "./ProjectTodoDetailArtifacts";
import {
  ProjectTodoDescriptionEditForm,
  ProjectTodoDescriptionPanel,
  ProjectTodoTitleEditForm
} from "./ProjectTodoDetailEditControls";
import { ProjectTodoExecutionTerminals } from "./ProjectTodoExecutionTerminals";
import { ProjectTodoHistoryPanel } from "./ProjectTodoHistoryPanel";
import { ProjectTodoMetadataPanel } from "./ProjectTodoMetadataPanel";
import { ProjectTodoRelations } from "./ProjectTodoRelations";
import { ProjectTodoReviewContext } from "./ProjectTodoReviewContext";
import { ProjectTodoSchedulePanel, type ProjectTodoScheduleInput } from "./ProjectTodoScheduleControls";
import { ProjectTodoTerminalActions } from "./ProjectTodoTerminalActions";
import {
  projectTodoStatusClass,
  projectTodoStatusLabel,
} from "./projectTodoDisplay";
import {
  projectTodoDispatchStageActive,
  projectTodoDispatchTitle,
  projectTodoDispatchTone,
} from "./projectTodoDispatchStage";
import { UiIcon } from "./UiIcon";
import { useOverlayFocus } from "./useOverlayFocus";

type ProjectTodoDetailDialogProps = {
  agentWorkStatus: WorkStatus | null;
  artifactPlugins: ArtifactPluginDescriptor[];
  projects: Project[];
  clientId: string;
  projectPath: string;
  todo: ProjectTodo | null;
  detailLoaded: boolean;
  busy: boolean;
  commenting: boolean;
  dispatching: boolean;
  generatingArtifact: boolean;
  attachmentOpenError: string | null;
  uploadingAttachment: boolean;
  deletingAttachmentIds: Set<string>;
  editingField: ProjectTodoEditableField | null;
  editTitle: string;
  editDescription: string;
  todos: ProjectTodoListItem[];
  onBeginDescriptionEdit: (todo: ProjectTodo) => void;
  onBeginTitleEdit: (todo: ProjectTodo) => void;
  onCancelEdit: () => void;
  onClose: () => void;
  onDelete: (todo: ProjectTodo) => void;
  onCreateChild: (todo: ProjectTodo) => void;
  onComment: (todo: ProjectTodo) => void;
  onDispatch: (todo: ProjectTodo) => void;
  onEditDescriptionChange: (description: string) => void;
  onEditTitleChange: (title: string) => void;
  onGenerateArtifact: (todo: ProjectTodo, artifactOption: ProjectTodoGenerateArtifactOption) => void;
  onDeleteAttachment: (todo: ProjectTodo, attachment: ProjectTodoAttachment) => void;
  onOpenAttachment: (todo: ProjectTodo, attachment: ProjectTodoAttachment) => void;
  onOpenArtifact?: (artifact: ProjectTodoArtifact) => void;
  onOpenTodo: (todoId: string) => void;
  onMoveToColumn: (todoId: string, status: ProjectTodoStatus) => void;
  onMoveToProject: (todo: ProjectTodo, projectPath: string) => void;
  onSaveArtifactKinds: (todo: ProjectTodo, artifactKinds: string[]) => void;
  onSaveInputArtifactIds: (todo: ProjectTodo, inputArtifactIds: string[]) => void;
  onSaveParentTodo: (todo: ProjectTodo, parentTodoId: string | null) => void;
  onSaveTodoType: (todo: ProjectTodo, todoTypeId: string) => void;
  onSaveDescriptionEdit: (todo: ProjectTodo) => void;
  onSaveSchedule: (todo: ProjectTodo, input: ProjectTodoScheduleInput) => void;
  onSaveTitleEdit: (todo: ProjectTodo) => void;
  onSelectWindow: (windowId: string, projectPath: string) => void;
  onStatus: (todo: ProjectTodo, status: ProjectTodoStatus) => void;
  onUploadAttachment: (todo: ProjectTodo, files: FileList | File[]) => void;
};

type ProjectTodoEditableField = "title" | "description";

export function ProjectTodoDetailDialog({
  agentWorkStatus,
  artifactPlugins,
  projects,
  clientId,
  projectPath,
  todo,
  detailLoaded,
  busy,
  commenting,
  dispatching,
  generatingArtifact,
  attachmentOpenError,
  uploadingAttachment,
  deletingAttachmentIds,
  editingField,
  editTitle,
  editDescription,
  todos,
  onBeginDescriptionEdit,
  onBeginTitleEdit,
  onCancelEdit,
  onClose,
  onDelete,
  onCreateChild,
  onComment,
  onDispatch,
  onEditDescriptionChange,
  onEditTitleChange,
  onGenerateArtifact,
  onDeleteAttachment,
  onOpenAttachment,
  onOpenArtifact,
  onOpenTodo,
  onMoveToColumn,
  onMoveToProject,
  onSaveArtifactKinds,
  onSaveInputArtifactIds,
  onSaveParentTodo,
  onSaveTodoType,
  onSaveDescriptionEdit,
  onSaveSchedule,
  onSaveTitleEdit,
  onSelectWindow,
  onStatus,
  onUploadAttachment,
}: ProjectTodoDetailDialogProps) {
  const { t } = useI18n();
  const panelRef = useRef<HTMLElement | null>(null);
  useOverlayFocus({
    isOpen: todo !== null,
    ref: panelRef,
    onEscape: editingField === null ? onClose : undefined,
  });
  const todoTypesQuery = useQuery({
    queryKey: ["project-todo-types", clientId, projectPath],
    queryFn: () => fetchProjectTodoTypes(clientId, projectPath),
    enabled: todo?.status === "TODO",
    staleTime: 30000
  });

  if (todo === null) {
    return null;
  }

  const titleEditing = editingField === "title";
  const descriptionEditing = editingField === "description";
  const dispatchTitle = projectTodoDispatchTitle(todo.dispatch_stage, todo.dispatch_error, t);
  const todoTypeLabel = todo.todo_type.name.trim() || todo.todo_type.id;
  const canEditParent = todo.status === "TODO";
  const canEditTodoType = todo.status === "TODO";
  const todoTypes = todoTypesForSelection(todo.todo_type, todoTypesQuery.data?.todo_types ?? []);
  const editableTodoTypes = todoTypes.length > 0 ? todoTypes : [todo.todo_type];

  return (
    <div
      className="project-todo-detail-backdrop"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) {
          onClose();
        }
      }}
    >
      <section
        ref={panelRef}
        className="project-todo-detail-dialog"
        data-debug-id="project-todo-detail-dialog"
        data-project-todo-id={todo.id}
        role="dialog"
        aria-modal="true"
        aria-label={t("projectTodo.detail.title")}
      >
        <header className="project-todo-detail-header">
          <div className="project-todo-detail-heading">
            <div className="project-todo-detail-badges">
              <ProjectTodoAgentStatusIcon
                status={agentWorkStatus}
                terminalLinked={todo.assigned_window_id !== null}
                dispatchActive={projectTodoDispatchStageActive(todo)}
                dispatchTitle={dispatchTitle}
                dispatchTone={projectTodoDispatchTone(todo.dispatch_stage)}
              />
              <span className={`project-todo-status-pill ${projectTodoStatusClass(todo.status)}`}>
                {projectTodoStatusLabel(todo.status, t)}
              </span>
              <span className="project-todo-detail-type project-todo-type-pill">{todoTypeLabel}</span>
            </div>
            {titleEditing ? (
              <ProjectTodoTitleEditForm
                busy={busy}
                editTitle={editTitle}
                onCancelEdit={onCancelEdit}
                onEditTitleChange={onEditTitleChange}
                onSaveEdit={() => onSaveTitleEdit(todo)}
              />
            ) : (
              <h2>
                <button
                  type="button"
                  className="project-todo-title-button"
                  aria-label={t("projectTodo.detail.editTitle")}
                  disabled={busy}
                  onClick={() => onBeginTitleEdit(todo)}
                >
                  {todo.title}
                </button>
              </h2>
            )}
          </div>
          <div className="project-todo-detail-header-actions">
            <ProjectTodoCreateChildButton
              busy={busy}
              className="project-todo-detail-icon-button project-todo-create-child-button"
              todo={todo}
              onCreateChild={onCreateChild}
            />
            <button
              type="button"
              className="project-todo-detail-icon-button project-todo-detail-delete"
              aria-label={t("projectTodo.detail.delete")}
              title={t("common.delete")}
              disabled={busy}
              onClick={() => onDelete(todo)}
            >
              <UiIcon name="trash" />
            </button>
            <button
              type="button"
              className="project-todo-detail-icon-button project-todo-detail-close"
              aria-label={t("projectTodo.detail.close")}
              title={t("common.close")}
              onClick={onClose}
            >
              <UiIcon name="x" />
            </button>
          </div>
        </header>

        <div className="project-todo-detail-body">
          <div className="project-todo-detail-main">
            {descriptionEditing ? (
              <ProjectTodoDescriptionEditForm
                busy={busy}
                editDescription={editDescription}
                todos={todos}
                todoId={todo.id}
                onCancelEdit={onCancelEdit}
                onEditDescriptionChange={onEditDescriptionChange}
                onSaveEdit={() => onSaveDescriptionEdit(todo)}
              />
            ) : (
              <ProjectTodoDescriptionPanel
                busy={busy}
                todo={todo}
                descriptionEditable={detailLoaded}
                onBeginEdit={() => {
                  if (detailLoaded) {
                    onBeginDescriptionEdit(todo);
                  }
                }}
                onOpenTodo={onOpenTodo}
              />
            )}
            <ProjectTodoExecutionTerminals
              clientId={clientId}
              projectPath={projectPath}
              todo={todo}
              onSelectWindow={onSelectWindow}
            />
            {todo.review_window_id && (
              <section className="project-todo-review-record" aria-label={t("projectTodo.detail.reviewRecord")}>
                <ProjectTodoAgentRecord
                  clientId={clientId}
                  projectPath={projectPath}
                  windowId={todo.review_window_id}
                  title={t("projectTodo.detail.reviewRecord")}
                />
              </section>
            )}
            <ProjectTodoAttachmentsPanel
              busy={busy}
              error={attachmentOpenError}
              deletingAttachmentIds={deletingAttachmentIds}
              todo={todo}
              uploading={uploadingAttachment}
              onDelete={onDeleteAttachment}
              onOpen={onOpenAttachment}
              onUpload={onUploadAttachment}
            />
            <ProjectTodoArtifactAgentsPanel artifacts={todo.artifacts} onOpenArtifact={onOpenArtifact} />
            <ProjectTodoRequestedArtifactsPanel
              artifactPlugins={artifactPlugins}
              busy={busy}
              todo={todo}
              onSaveArtifactKinds={onSaveArtifactKinds}
            />
            <ProjectTodoChildCardsPanel
              clientId={clientId}
              projectPath={projectPath}
              todo={todo}
              onOpenArtifact={onOpenArtifact}
              onOpenTodo={onOpenTodo}
              onSelectWindow={onSelectWindow}
            />
            <ProjectTodoRelations todo={todo} onOpenTodo={onOpenTodo} />
            <ProjectTodoReviewContext
              clientId={clientId}
              todo={todo}
              onOpenArtifact={onOpenArtifact}
            />
          </div>
          <aside className="project-todo-detail-side" aria-label={t("projectTodo.detail.metadataLabel")}>
            <ProjectTodoMetadataPanel
              busy={busy}
              canEditParent={canEditParent}
              canEditTodoType={canEditTodoType}
              clientId={clientId}
              editableTodoTypes={editableTodoTypes}
              projectPath={projectPath}
              todos={todos}
              todo={todo}
              todoTypeLabel={todoTypeLabel}
              todoTypesLoading={todoTypesQuery.isLoading}
              onSaveInputArtifactIds={onSaveInputArtifactIds}
              onSaveParentTodo={onSaveParentTodo}
              onSaveTodoType={onSaveTodoType}
            />
            <ProjectTodoTerminalActions
              todo={todo}
              projectPath={projectPath}
              busy={busy}
              commenting={commenting}
              commentDispatching={projectTodoDispatchStageActive(todo)}
              onComment={() => onComment(todo)}
              onSelectWindow={onSelectWindow}
            />
            <ProjectTodoHistoryPanel
              busy={busy}
              clientId={clientId}
              projectPath={projectPath}
              todo={todo}
            />
            <ProjectTodoActionRail
              artifactPlugins={artifactPlugins}
              projects={projects}
              todo={todo}
              busy={busy}
              dispatching={dispatching}
              generatingArtifact={generatingArtifact}
              onDispatch={() => onDispatch(todo)}
              onGenerateArtifact={(artifactOption) => onGenerateArtifact(todo, artifactOption)}
              onMoveToColumn={(status) => onMoveToColumn(todo.id, status)}
              onMoveToProject={(targetProjectPath) => onMoveToProject(todo, targetProjectPath)}
              onStatus={(status) => onStatus(todo, status)}
            />
            <ProjectTodoSchedulePanel busy={busy} todo={todo} onSaveSchedule={onSaveSchedule} />
          </aside>
        </div>
      </section>
    </div>
  );
}

function todoTypesForSelection(currentTodoType: ProjectTodoType, todoTypes: ProjectTodoType[]): ProjectTodoType[] {
  if (todoTypes.some((todoType) => todoType.id === currentTodoType.id)) {
    return todoTypes;
  }
  return [currentTodoType, ...todoTypes];
}
