import { useQuery } from "@tanstack/react-query";
import { useEffect, useMemo, useState } from "react";

import { fetchAgentRecordChat } from "../api";
import { useI18n } from "../i18n";
import {
  projectFileLinkContextForWindow,
  type ProjectFileLinkContext
} from "../projectFileLinks";
import type { AgentChatMessage, AgentChatRecord, ProjectTodoAssignedTerminal } from "../types";
import { AgentChatAvatar, AgentChatMessageOverlay, AgentMessageExpandIcon } from "./AgentRecordContent";
import { chatSpeakerLabel, defaultAgentMessageType, formatTimeRange, timeRangeFromDates } from "./AgentRecordData";
import { AgentRecordStateModal } from "./AgentRecordStateModal";
import { useAgentRecordData } from "../hooks/useAgentRecordData";

type ProjectTodoAgentRecordProps = {
  clientId: string;
  projectPath?: string | null;
  terminal?: Pick<ProjectTodoAssignedTerminal, "git_worktree" | "runtime_tags"> | null;
  windowId: string | null;
  title?: string;
};

const INLINE_CHAT_PAGE_SIZE = 30;

function messagePreview(message: AgentChatMessage): string {
  const body = message.body.trim();
  return body.length > 520 ? `${body.slice(0, 520)}...` : body;
}

function projectTodoMessageClass(message: AgentChatMessage): string {
  return `project-todo-agent-record-item-${defaultAgentMessageType(message).replace("_", "-")}`;
}

function appendAgentMessage(visible: AgentChatMessage[], message: AgentChatMessage | null): void {
  if (message !== null) {
    visible.push(message);
  }
}

function compactMessages(messages: AgentChatMessage[]): AgentChatMessage[] {
  let pendingAgent: AgentChatMessage | null = null;
  let visible: AgentChatMessage[] = [];

  for (const message of messages) {
    if (message.role === "agent") {
      pendingAgent = message;
      continue;
    }
    appendAgentMessage(visible, pendingAgent);
    pendingAgent = null;
    visible.push(message);
  }

  appendAgentMessage(visible, pendingAgent);
  return visible;
}

async function fetchInlineAgentChat(clientId: string, windowId: string): Promise<AgentChatRecord> {
  return fetchAgentRecordChat(clientId, windowId, INLINE_CHAT_PAGE_SIZE, 0, "all", null, "latest");
}

export function ProjectTodoAgentRecord({
  clientId,
  projectPath = null,
  terminal = null,
  windowId,
  title
}: ProjectTodoAgentRecordProps) {
  const { t } = useI18n();
  const enabled = windowId !== null;
  const displayTitle = title ?? t("projectTodo.execution.agentConversation");
  const [previewOpen, setPreviewOpen] = useState(false);
  const [expandedMessageId, setExpandedMessageId] = useState<string | null>(null);
  const agentRecord = useAgentRecordData({ clientId, windowId, enabled: enabled && previewOpen });
  const projectFileContext = useMemo<ProjectFileLinkContext | null>(() => (
    projectPath === null
      ? null
      : projectFileLinkContextForWindow({
        clientId,
        windowId,
        projectPath,
        window: terminal
          ? {
            git_worktree: terminal.git_worktree ?? null,
            runtime_tags: terminal.runtime_tags,
          }
          : null,
      })
  ), [clientId, projectPath, terminal, windowId]);

  useEffect(() => {
    setPreviewOpen(false);
    setExpandedMessageId(null);
  }, [clientId, windowId]);
  const chatQuery = useQuery({
    queryKey: ["project-todo-agent-record", "chat", clientId, windowId],
    queryFn: () => fetchInlineAgentChat(clientId, windowId as string),
    enabled,
    refetchInterval: 10000
  });

  useEffect(() => {
    setExpandedMessageId((current) => {
      if (current === null) {
        return null;
      }
      return compactMessages(chatQuery.data?.messages ?? []).some((message) => message.id === current)
        ? current
        : null;
    });
  }, [chatQuery.data]);

  if (!enabled) {
    return <p className="muted">{t("projectTodo.agentRecord.noTerminal")}</p>;
  }

  if (chatQuery.isLoading) {
    return <p className="muted">{t("projectTodo.agentRecord.loading")}</p>;
  }

  if (chatQuery.isError) {
    return <p className="error" role="alert">{t("projectTodo.agentRecord.loadFailed")}</p>;
  }

  const record = chatQuery.data ?? null;
  const messages = compactMessages(record?.messages ?? []);
  const expandedMessage = expandedMessageId === null
    ? null
    : messages.find((message) => message.id === expandedMessageId) ?? null;
  const canExpand = record !== null;
  const total = record?.messages_total ?? 0;
  const timeRange = timeRangeFromDates(messages.map((message) => message.created_at));

  return (
    <div className="project-todo-agent-record">
      <header className="project-todo-agent-record-header">
        <strong>{displayTitle}</strong>
        <button
          type="button"
          className="project-todo-detail-icon-button project-todo-agent-record-preview-button"
          aria-label={t("projectTodo.agentRecord.openPreviewFor", { title: displayTitle })}
          title={t("projectTodo.agentRecord.openPreview")}
          disabled={!canExpand}
          onClick={() => {
            setPreviewOpen(true);
            agentRecord.setExpanded(true);
          }}
        >
          <AgentMessageExpandIcon />
        </button>
      </header>
      <div className="project-todo-agent-record-stats">
        <span>{t("projectTodo.agentRecord.messagesCount", { count: total })}</span>
        {record?.messages_has_more && <span>{t("projectTodo.agentRecord.showingFirst", { count: record.messages.length })}</span>}
        {timeRange && (
          <span>{formatTimeRange(timeRange)}</span>
        )}
      </div>
      {messages.length > 0 && (
        <div className="project-todo-agent-record-list" aria-label={t("projectTodo.agentRecord.recentMessages")}>
          {messages.map((message) => {
            const speakerLabel = chatSpeakerLabel(message, t);
            return (
              <article key={message.id} className={projectTodoMessageClass(message)}>
                <AgentChatAvatar message={message} className="project-todo-agent-record-avatar" />
                <div className="project-todo-agent-record-message-content" aria-label={t("projectTodo.agentRecord.speakerMessage", { speaker: speakerLabel })}>
                  <button
                    type="button"
                    className="project-todo-agent-record-message-expand"
                    aria-label={t("projectTodo.agentRecord.expandMessage", { role: speakerLabel })}
                    title={t("projectTodo.agentRecord.expand")}
                    onClick={() => setExpandedMessageId(message.id)}
                  >
                    <AgentMessageExpandIcon />
                  </button>
                  <p>{messagePreview(message)}</p>
                </div>
              </article>
            );
          })}
        </div>
      )}
      {messages.length === 0 && (
        <p className="muted">{t("projectTodo.agentRecord.empty")}</p>
      )}
      <AgentRecordStateModal
        agentRecord={agentRecord}
        open={previewOpen}
        projectFileContext={projectFileContext}
        terminalStatusLabel={t("projectTodo.agentRecord.terminal")}
        terminalStatusTone="connected"
        onClose={() => setPreviewOpen(false)}
      />
      {expandedMessage && (
        <AgentChatMessageOverlay
          message={expandedMessage}
          projectFileContext={projectFileContext}
          onClose={() => setExpandedMessageId(null)}
        />
      )}
    </div>
  );
}
