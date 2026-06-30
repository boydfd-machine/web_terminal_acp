import { useEffect, useState } from "react";

import { useI18n } from "../i18n";
import type { AgentChatMessage, AgentChatRecord, SearchMatch } from "../types";
import type { ProjectFileLinkContext } from "../projectFileLinks";
import {
  AgentChatMessageCard,
  AgentChatMessageGroup,
  AgentChatMessageOverlay
} from "./AgentRecordContent";

type AgentChatMessageEntry =
  | { kind: "single"; message: AgentChatMessage }
  | { kind: "agent-group"; id: string; messages: AgentChatMessage[] };

function groupedAgentChatMessages(messages: AgentChatMessage[]): AgentChatMessageEntry[] {
  const entries: AgentChatMessageEntry[] = [];
  let pendingAgentMessages: AgentChatMessage[] = [];

  const appendPendingAgentMessages = () => {
    if (pendingAgentMessages.length === 0) {
      return;
    }
    if (pendingAgentMessages.length === 1) {
      entries.push({ kind: "single", message: pendingAgentMessages[0] });
      pendingAgentMessages = [];
      return;
    }
    const first = pendingAgentMessages[0];
    const last = pendingAgentMessages[pendingAgentMessages.length - 1];
    entries.push({
      kind: "agent-group",
      id: `agent-group-${first.id}-${last.id}`,
      messages: pendingAgentMessages
    });
    pendingAgentMessages = [];
  };

  for (const message of messages) {
    if (message.role === "agent") {
      pendingAgentMessages.push(message);
      continue;
    }
    appendPendingAgentMessages();
    entries.push({ kind: "single", message });
  }

  appendPendingAgentMessages();
  return entries;
}

export function AgentChatContent({
  record,
  highlightedMessageId,
  highlightMatchesByMessageId,
  projectFileContext,
  onOpenSubagent
}: {
  record: AgentChatRecord;
  highlightedMessageId?: string | null;
  highlightMatchesByMessageId?: Map<string, SearchMatch[]>;
  projectFileContext?: ProjectFileLinkContext | null;
  onOpenSubagent?: (message: AgentChatMessage) => void;
}) {
  const { t } = useI18n();
  const [expandedMessageId, setExpandedMessageId] = useState<string | null>(null);
  const expandedMessage = expandedMessageId === null
    ? null
    : record.messages.find((message) => message.id === expandedMessageId) ?? null;
  const messageEntries = groupedAgentChatMessages(record.messages);

  useEffect(() => {
    if (expandedMessageId !== null && expandedMessage === null) {
      setExpandedMessageId(null);
    }
  }, [expandedMessage, expandedMessageId]);

  if (record.messages_total === 0) {
    return <p className="muted">{t("agentRecord.empty")}</p>;
  }
  if (record.messages.length === 0) {
    return <p className="muted">{t("agentRecord.emptyPage")}</p>;
  }

  return (
    <>
      <div className="agent-chat-events">
        {messageEntries.map((entry) => {
          if (entry.kind === "agent-group") {
            return (
              <AgentChatMessageGroup
                key={entry.id}
                messages={entry.messages}
                highlightedMessageId={highlightedMessageId}
                highlightMatchesByMessageId={highlightMatchesByMessageId}
                projectFileContext={projectFileContext}
                onOpenSubagent={onOpenSubagent}
                onExpand={setExpandedMessageId}
              />
            );
          }

          const message = entry.message;
          return (
            <AgentChatMessageCard
              key={message.id}
              message={message}
              highlightMatches={highlightMatchesByMessageId?.get(message.id) ?? []}
              projectFileContext={projectFileContext}
              articleRef={highlightedMessageId === message.id ? (element) => element?.scrollIntoView({ block: "center" }) : undefined}
              onOpenSubagent={onOpenSubagent}
              onExpand={() => setExpandedMessageId(message.id)}
            />
          );
        })}
      </div>
      {expandedMessage && (
        <AgentChatMessageOverlay
          message={expandedMessage}
          projectFileContext={projectFileContext}
          onClose={() => setExpandedMessageId(null)}
        />
      )}
    </>
  );
}
