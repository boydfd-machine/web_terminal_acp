import { useRef, type ChangeEvent } from "react";

import { useI18n } from "../i18n";
import type { ProjectTodo, ProjectTodoAttachment, ProjectTodoListItem } from "../types";
import { UiIcon } from "./UiIcon";
import { useOverlayFocus } from "./useOverlayFocus";

type TodoWithAttachments = ProjectTodo | ProjectTodoListItem;
type ProjectTodoAttachmentPreview = {
  attachment: ProjectTodoAttachment;
  downloadUrl: string;
};

export function ProjectTodoAttachmentUploadButton<TTodo extends TodoWithAttachments>({
  busy,
  className,
  todo,
  uploading,
  onUpload
}: {
  busy: boolean;
  className: string;
  todo: TTodo;
  uploading: boolean;
  onUpload: (todo: TTodo, files: FileList | File[]) => void;
}) {
  const { t } = useI18n();
  const inputRef = useRef<HTMLInputElement | null>(null);
  const disabled = busy || uploading;
  const label = uploading
    ? t("projectTodo.attachments.uploadingNamed", { title: todo.title })
    : t("projectTodo.attachments.uploadNamed", { title: todo.title });
  return (
    <>
      <button
        type="button"
        className={className}
        aria-label={label}
        title={t("projectTodo.attachments.upload")}
        disabled={disabled}
        onClick={(event) => {
          event.stopPropagation();
          inputRef.current?.click();
        }}
      >
        {uploading ? (
          <span className="terminal-create-progress-spinner project-todo-card-action-spinner blue" aria-hidden="true" />
        ) : (
          <UiIcon name="upload" />
        )}
      </button>
      <input
        ref={inputRef}
        className="project-todo-attachment-file-input"
        type="file"
        multiple
        onChange={(event: ChangeEvent<HTMLInputElement>) => {
          if (event.target.files !== null) {
            onUpload(todo, event.target.files);
          }
          event.target.value = "";
        }}
      />
    </>
  );
}

export function ProjectTodoAttachmentCount({ todo }: { todo: TodoWithAttachments }) {
  const { t } = useI18n();
  const count = attachmentList(todo).filter((attachment) => attachment.status === "uploaded").length;
  if (count === 0) {
    return null;
  }
  return (
    <span className="project-todo-attachment-chip" title={t("projectTodo.attachments.count", { count })}>
      <UiIcon name="file" />
      <span>{count}</span>
    </span>
  );
}

export function ProjectTodoAttachmentsPanel({
  busy,
  deletingAttachmentIds,
  error,
  todo,
  uploading,
  onDelete,
  onOpen,
  onUpload
}: {
  busy: boolean;
  deletingAttachmentIds: Set<string>;
  error: string | null;
  todo: ProjectTodo;
  uploading: boolean;
  onDelete: (todo: ProjectTodo, attachment: ProjectTodoAttachment) => void;
  onOpen: (todo: ProjectTodo, attachment: ProjectTodoAttachment) => void;
  onUpload: (todo: ProjectTodo, files: FileList | File[]) => void;
}) {
  const { t } = useI18n();
  const uploaded = attachmentList(todo).filter((attachment) => attachment.status === "uploaded");
  return (
    <section className="project-todo-attachments-panel" aria-label={t("projectTodo.attachments.label")}>
      <header>
        <strong>{t("projectTodo.attachments.label")}</strong>
        <ProjectTodoAttachmentUploadButton
          busy={busy}
          className="project-todo-detail-icon-button"
          todo={todo}
          uploading={uploading}
          onUpload={onUpload}
        />
      </header>
      {uploaded.length === 0 ? (
        <p className="muted">{t("projectTodo.attachments.empty")}</p>
      ) : (
        <ul>
          {uploaded.map((attachment) => (
            <li key={attachment.id}>
              <button
                type="button"
                className="project-todo-attachment-open"
                onClick={() => onOpen(todo, attachment)}
              >
                <UiIcon name="file" />
                <span>{attachment.filename}</span>
                <small>{attachmentSizeLabel(attachment)}</small>
              </button>
              <button
                type="button"
                className="project-todo-detail-icon-button"
                aria-label={t("projectTodo.attachments.deleteNamed", { filename: attachment.filename })}
                title={t("common.delete")}
                disabled={busy || deletingAttachmentIds.has(attachment.id)}
                onClick={() => onDelete(todo, attachment)}
              >
                {deletingAttachmentIds.has(attachment.id) ? (
                  <span className="terminal-create-progress-spinner project-todo-card-action-spinner red" aria-hidden="true" />
                ) : (
                  <UiIcon name="trash" />
                )}
              </button>
            </li>
          ))}
        </ul>
      )}
      {error !== null && <p className="error project-todo-attachment-error" role="alert">{error}</p>}
    </section>
  );
}

export function ProjectTodoAttachmentPreviewDialog({
  preview,
  onClose
}: {
  preview: ProjectTodoAttachmentPreview | null;
  onClose: () => void;
}) {
  const { t } = useI18n();
  const dialogRef = useRef<HTMLElement | null>(null);
  useOverlayFocus({
    isOpen: preview !== null,
    ref: dialogRef,
    onEscape: onClose,
    initialFocusSelector: ".project-todo-attachment-preview-close"
  });

  if (preview === null) {
    return null;
  }

  const isImage = preview.attachment.content_type.toLowerCase().startsWith("image/");
  return (
    <div
      className="project-todo-attachment-preview-backdrop"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) {
          onClose();
        }
      }}
    >
      <section
        ref={dialogRef}
        className="project-todo-attachment-preview-dialog"
        role="dialog"
        aria-modal="true"
        aria-label={t("projectTodo.attachments.previewTitle")}
      >
        <header className="project-todo-attachment-preview-header">
          <div>
            <strong>{preview.attachment.filename}</strong>
            <small>{attachmentSizeLabel(preview.attachment)}</small>
          </div>
          <button
            type="button"
            className="project-todo-detail-icon-button project-todo-attachment-preview-close"
            aria-label={t("projectTodo.attachments.closePreview")}
            title={t("common.close")}
            onClick={onClose}
          >
            <UiIcon name="x" />
          </button>
        </header>
        <div className="project-todo-attachment-preview-body">
          {isImage ? (
            <img src={preview.downloadUrl} alt={preview.attachment.filename} referrerPolicy="no-referrer" />
          ) : (
            <iframe
              src={preview.downloadUrl}
              title={preview.attachment.filename}
              sandbox=""
              referrerPolicy="no-referrer"
            />
          )}
        </div>
      </section>
    </div>
  );
}

function attachmentSizeLabel(attachment: ProjectTodoAttachment): string {
  if (attachment.size_bytes === null) {
    return attachment.content_type;
  }
  const size = attachment.size_bytes >= 1024 * 1024
    ? `${(attachment.size_bytes / (1024 * 1024)).toFixed(1)} MB`
    : `${Math.max(1, Math.round(attachment.size_bytes / 1024))} KB`;
  return `${attachment.content_type} - ${size}`;
}

function attachmentList(todo: TodoWithAttachments): ProjectTodoAttachment[] {
  return todo.attachments ?? [];
}
