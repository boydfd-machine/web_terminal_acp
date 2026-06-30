import { useEffect, useRef, useState } from "react";

import { useI18n } from "../i18n";
import type { ArtifactPluginDescriptor, ProjectTodo, ProjectTodoListItem } from "../types";
import { ProjectTodoArtifactKindSelector } from "./ProjectTodoArtifactKindSelector";
import { ProjectTodoDescriptionMentionTextarea } from "./ProjectTodoDescriptionMentionTextarea";
import { UiIcon } from "./UiIcon";
import { useOverlayFocus } from "./useOverlayFocus";

type ProjectTodoCommentModalProps = {
  artifactPlugins: ArtifactPluginDescriptor[];
  isOpen: boolean;
  todo: ProjectTodo | null;
  todos: ProjectTodoListItem[];
  submitting: boolean;
  onClose: () => void;
  onSubmit: (comment: string, artifactKinds?: string[]) => void;
};

export function ProjectTodoCommentModal({
  artifactPlugins,
  isOpen,
  todo,
  todos,
  submitting,
  onClose,
  onSubmit
}: ProjectTodoCommentModalProps) {
  const { t } = useI18n();
  const [comment, setComment] = useState("");
  const [artifactKinds, setArtifactKinds] = useState<string[]>([]);
  const panelRef = useRef<HTMLElement | null>(null);
  const trimmedComment = comment.trim();

  useOverlayFocus({
    isOpen,
    ref: panelRef,
    onEscape: () => {
      if (!submitting) {
        onClose();
      }
    },
    initialFocusSelector: "textarea"
  });

  useEffect(() => {
    if (isOpen) {
      setComment("");
      setArtifactKinds(todo?.artifact_kinds ?? []);
    }
  }, [isOpen, todo?.id]);

  if (!isOpen || todo === null) {
    return null;
  }

  return (
    <div
      className="project-todo-comment-backdrop"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget && !submitting) {
          onClose();
        }
      }}
    >
      <section
        ref={panelRef}
        className="project-todo-comment-modal"
        role="dialog"
        aria-modal="true"
        aria-label={t("projectTodo.comment.onTodo")}
      >
        <header>
          <strong>{todo.title}</strong>
          <button
            type="button"
            className="project-todo-detail-icon-button"
            aria-label={t("projectTodo.comment.close")}
            title={t("common.close")}
            disabled={submitting}
            onClick={onClose}
          >
            <UiIcon name="x" />
          </button>
        </header>
        <form
          onSubmit={(event) => {
            event.preventDefault();
            if (trimmedComment.length > 0 && !submitting) {
              onSubmit(trimmedComment, artifactPlugins.length > 0 ? artifactKinds : undefined);
            }
          }}
        >
          <ProjectTodoDescriptionMentionTextarea
            value={comment}
            todos={todos}
            currentTodoId={todo.id}
            rows={6}
            maxLength={65536}
            ariaLabel={t("projectTodo.comment.label")}
            disabled={submitting}
            onChange={setComment}
          />
          <ProjectTodoArtifactKindSelector
            artifactPlugins={artifactPlugins}
            selectedKinds={artifactKinds}
            className="project-todo-comment-artifacts"
            disabled={submitting}
            legend={t("projectTodo.comment.artifacts")}
            onSelectionChange={setArtifactKinds}
          />
          <div className="project-todo-comment-actions">
            <button
              type="button"
              className="ui-icon-button"
              disabled={submitting}
              aria-label={t("projectTodo.comment.cancel")}
              title={t("common.cancel")}
              onClick={onClose}
            >
              <UiIcon name="x" />
            </button>
            <button type="submit" disabled={submitting || trimmedComment.length === 0}>
              {submitting && <span className="terminal-create-progress-spinner" aria-hidden="true" />}
              <span>{submitting ? t("projectTodo.comment.sending") : t("projectTodo.comment.send")}</span>
            </button>
          </div>
        </form>
      </section>
    </div>
  );
}
