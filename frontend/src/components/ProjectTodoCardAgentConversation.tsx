import { useQuery } from "@tanstack/react-query";
import { useMemo, useRef, useState, type SyntheticEvent } from "react";

import { fetchAgentRecordChat } from "../api";
import { useAgentRecordData } from "../hooks/useAgentRecordData";
import { useI18n } from "../i18n";
import {
  projectFileLinkContextForWindow,
  type ProjectFileLinkContext
} from "../projectFileLinks";
import type { ProjectTodoAssignedTerminal, ProjectTodoListItem } from "../types";
import { AgentChatMessageOverlay } from "./AgentRecordContent";
import { AgentRecordStateModal } from "./AgentRecordStateModal";
import { UiIcon } from "./UiIcon";
import { useOverlayFocus } from "./useOverlayFocus";

type ProjectTodoCardAgentConversationButtonProps = {
  clientId: string;
  projectPath: string;
  terminal: Pick<ProjectTodoAssignedTerminal, "git_worktree" | "runtime_tags" | "title"> | null;
  todo: ProjectTodoListItem;
  windowId: string;
};

export function ProjectTodoCardAgentConversationButton({
  clientId,
  projectPath,
  terminal,
  todo,
  windowId
}: ProjectTodoCardAgentConversationButtonProps) {
  const { t } = useI18n();
  const [conversationOpen, setConversationOpen] = useState(false);
  const [previewOpen, setPreviewOpen] = useState(false);
  const agentRecord = useAgentRecordData({ clientId, windowId, enabled: previewOpen });
  const projectFileContext = useProjectFileContext(clientId, projectPath, terminal, windowId);
  const latestAgentQuery = useQuery({
    queryKey: ["project-todo-card-agent-conversation", "latest-agent", clientId, windowId],
    queryFn: () => fetchAgentRecordChat(clientId, windowId, 1, 0, "agent", null, "latest"),
    enabled: conversationOpen,
    refetchInterval: conversationOpen ? 10000 : false
  });
  const latestAgentMessage = latestAgentQuery.data?.messages[0] ?? null;
  const openPreview = () => {
    setConversationOpen(false);
    setPreviewOpen(true);
    agentRecord.setExpanded(true);
  };

  return (
    <>
      <button
        type="button"
        className="project-todo-card-action-button project-todo-agent-conversation-button"
        aria-label={t("projectTodo.agentRecord.openConversationFor", { title: todo.title })}
        title={t("projectTodo.agentRecord.openConversation")}
        onClick={(event) => {
          event.stopPropagation();
          setConversationOpen(true);
        }}
      >
        <UiIcon name="message-circle" />
      </button>
      {conversationOpen && latestAgentMessage === null ? (
        <ProjectTodoCardAgentConversationStatusDialog
          isError={latestAgentQuery.isError}
          isLoading={latestAgentQuery.isLoading}
          onClose={() => setConversationOpen(false)}
        />
      ) : null}
      {conversationOpen && latestAgentMessage !== null ? (
        <AgentChatMessageOverlay
          className="project-todo-card-agent-conversation-dialog"
          detailActions={(
            <button
              type="button"
              className="agent-chat-message-detail-action project-todo-card-agent-preview-button"
              aria-label={t("projectTodo.agentRecord.openPreviewFor", { title: t("projectTodo.execution.agentConversation") })}
              title={t("projectTodo.agentRecord.openPreview")}
              onClick={(event) => {
                event.stopPropagation();
                openPreview();
              }}
            >
              <UiIcon name="external-link" />
            </button>
          )}
          message={latestAgentMessage}
          portalContainer={documentBody()}
          projectFileContext={projectFileContext}
          onClose={() => setConversationOpen(false)}
        />
      ) : null}
      <AgentRecordStateModal
        agentRecord={agentRecord}
        open={previewOpen}
        projectFileContext={projectFileContext}
        terminalStatusLabel={t("projectTodo.agentRecord.terminal")}
        terminalStatusTone="connected"
        onClose={() => setPreviewOpen(false)}
      />
    </>
  );
}

function ProjectTodoCardAgentConversationStatusDialog({
  isError,
  isLoading,
  onClose
}: {
  isError: boolean;
  isLoading: boolean;
  onClose: () => void;
}) {
  const { t } = useI18n();
  const panelRef = useRef<HTMLElement | null>(null);
  useOverlayFocus({
    isOpen: true,
    ref: panelRef,
    onEscape: onClose,
    initialFocusSelector: ".project-todo-card-agent-conversation-close"
  });
  const message = isLoading
    ? t("projectTodo.agentRecord.loading")
    : isError
      ? t("projectTodo.agentRecord.loadFailed")
      : t("projectTodo.agentRecord.empty");

  return (
    <div
      className="agent-chat-message-overlay project-todo-card-agent-conversation-dialog"
      role="dialog"
      aria-modal="true"
      aria-label={t("projectTodo.execution.agentConversation")}
      onClick={stopOverlayPropagation}
      onDragStart={stopOverlayPropagation}
      onMouseDown={stopOverlayPropagation}
      onPointerDown={stopOverlayPropagation}
    >
      <button type="button" className="agent-chat-message-overlay-backdrop" aria-label={t("common.close")} onClick={onClose} />
      <section ref={panelRef} className="project-todo-card-agent-conversation-panel">
        <header>
          <strong>{t("projectTodo.execution.agentConversation")}</strong>
          <button
            type="button"
            className="project-todo-detail-icon-button project-todo-card-agent-conversation-close"
            aria-label={t("common.close")}
            title={t("common.close")}
            onClick={onClose}
          >
            <UiIcon name="x" />
          </button>
        </header>
        <p className={isError ? "error" : "muted"} role={isError ? "alert" : undefined}>{message}</p>
      </section>
    </div>
  );
}

function stopOverlayPropagation(event: SyntheticEvent): void {
  event.stopPropagation();
}

function documentBody(): HTMLElement | null {
  return typeof document === "undefined" ? null : document.body;
}

function useProjectFileContext(
  clientId: string,
  projectPath: string,
  terminal: Pick<ProjectTodoAssignedTerminal, "git_worktree" | "runtime_tags"> | null,
  windowId: string
): ProjectFileLinkContext {
  return useMemo(() => projectFileLinkContextForWindow({
    clientId,
    windowId,
    projectPath,
    window: terminal
      ? {
        git_worktree: terminal.git_worktree ?? null,
        runtime_tags: terminal.runtime_tags,
      }
      : null,
  }), [clientId, projectPath, terminal, windowId]);
}
