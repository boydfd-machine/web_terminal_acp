import { useRef } from "react";

import { useI18n } from "../i18n";
import type { AgentClient, ProjectAgentPreference, ProjectTodo, ProjectTodoListItem } from "../types";
import { ProjectTodoCreateForm, type ProjectTodoCreateAction } from "./ProjectTodoCreateForm";
import { useOverlayFocus } from "./useOverlayFocus";

type ProjectTodoCreateDialogProps = {
  clientId: string;
  directDispatch?: boolean;
  isOpen: boolean;
  parentTodoId?: string | null;
  agentClients?: AgentClient[];
  projectPreference?: ProjectAgentPreference | null;
  projectPath: string;
  todos: ProjectTodoListItem[];
  creating: boolean;
  onClose: () => void;
  onCreated: (todo: ProjectTodo, action: ProjectTodoCreateAction) => void;
  onPendingChange: (pending: boolean) => void;
};

export function ProjectTodoCreateDialog({
  clientId,
  directDispatch = false,
  isOpen,
  parentTodoId = null,
  agentClients,
  projectPreference = null,
  projectPath,
  todos,
  creating,
  onClose,
  onCreated,
  onPendingChange
}: ProjectTodoCreateDialogProps) {
  const { t } = useI18n();
  const panelRef = useRef<HTMLElement | null>(null);
  useOverlayFocus({
    isOpen,
    ref: panelRef,
    onEscape: () => {
      if (!creating) {
        onClose();
      }
    },
    initialFocusSelector: "input"
  });

  if (!isOpen) {
    return null;
  }

  return (
    <div
      className="project-todo-create-dialog-backdrop"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget && !creating) {
          onClose();
        }
      }}
    >
      <section
        ref={panelRef}
        className="project-todo-create-dialog"
        role="dialog"
        aria-modal="true"
        aria-label={t("projectTodo.create.title")}
      >
        <header>
          <div>
            <h2>{t("projectTodo.create.title")}</h2>
            <p>{t("projectTodo.create.subtitle")}</p>
          </div>
          <button
            type="button"
            className="project-todo-detail-icon-button"
            aria-label={t("projectTodo.create.close")}
            title={t("common.close")}
            disabled={creating}
            onClick={onClose}
          >
            <CloseIcon />
          </button>
        </header>
        <ProjectTodoCreateForm
          clientId={clientId}
          directDispatch={directDispatch}
          mode="full"
          parentTodoId={parentTodoId}
          agentClients={agentClients}
          projectPreference={projectPreference}
          projectPath={projectPath}
          todos={todos}
          onCreated={onCreated}
          onPendingChange={onPendingChange}
        />
      </section>
    </div>
  );
}

function CloseIcon() {
  return (
    <svg
      aria-hidden="true"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d="m6 6 12 12" />
      <path d="m18 6-12 12" />
    </svg>
  );
}
