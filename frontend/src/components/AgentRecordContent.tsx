import { useRef, type ReactNode, type Ref, type SyntheticEvent } from "react";
import { createPortal } from "react-dom";

import { useI18n } from "../i18n";
import type { AgentChatMessage, AgentRecord, SearchMatch } from "../types";
import type { ProjectFileLinkContext } from "../projectFileLinks";
import {
  buildAgentTree,
  chatMessageClass,
  chatSpeakerLabel,
  defaultAgentMessageType,
  eventView,
  formatDateTime,
  json,
  sessionLabel,
  type AgentNode
} from "./AgentRecordData";
import { MarkdownText } from "./AgentRecordMarkdown";
import { highlightedText } from "./SearchHighlights";
import { useOverlayFocus } from "./useOverlayFocus";

export function AgentTree({ nodes }: { nodes: AgentNode[] }) {
  return (
    <ul className="agent-tree">
      {nodes.map((node) => (
        <li key={node.id}>
          <div><strong>{node.label}</strong><small>{node.meta}</small></div>
          {node.children.length > 0 && <AgentTree nodes={node.children} />}
        </li>
      ))}
    </ul>
  );
}

function AgentChatMessageBody({
  message,
  highlightMatches = [],
  projectFileContext
}: {
  message: AgentChatMessage;
  highlightMatches?: SearchMatch[];
  projectFileContext?: ProjectFileLinkContext | null;
}) {
  return (
    <div className="agent-chat-message-body">
      {highlightMatches.length > 0
        ? <p className="agent-chat-highlighted-body">{highlightedText(message.body, highlightMatches)}</p>
        : message.body_format === "json"
        ? <pre className="agent-event-json">{message.body}</pre>
        : <MarkdownText text={message.body} projectFileContext={projectFileContext} />}
    </div>
  );
}

export function AgentChatMessageCard({
  message,
  fullscreen = false,
  projectFileContext,
  onExpand,
  onCollapse,
  onOpenSubagent,
  articleRef,
  highlightMatches = [],
  detailActions = null
}: {
  message: AgentChatMessage;
  fullscreen?: boolean;
  projectFileContext?: ProjectFileLinkContext | null;
  onExpand?: () => void;
  onCollapse?: () => void;
  onOpenSubagent?: (message: AgentChatMessage) => void;
  articleRef?: Ref<HTMLElement>;
  highlightMatches?: SearchMatch[];
  detailActions?: ReactNode;
}) {
  const { t } = useI18n();
  const translatedSpeakerLabel = chatSpeakerLabel(message, t);
  const actionLabel = fullscreen ? t("agentRecord.collapse") : t("agentRecord.expand");
  const canOpenSubagent = message.target_session_id !== null && onOpenSubagent !== undefined && !fullscreen;

  return (
    <article
      ref={articleRef}
      className={[
        "agent-chat-message",
        chatMessageClass(message),
        fullscreen ? "agent-chat-message-fullscreen" : ""
      ].filter(Boolean).join(" ")}
    >
      <AgentChatAvatar message={message} />
      <div className="agent-chat-message-content" aria-label={t("agentRecord.speakerMessage", { speaker: translatedSpeakerLabel })}>
        <button
          type="button"
          className="agent-chat-message-zoom-button"
          aria-label={fullscreen
            ? t("agentRecord.collapseSpeakerMessage", { speaker: translatedSpeakerLabel })
            : t("agentRecord.expandSpeakerMessage", { speaker: translatedSpeakerLabel })}
          title={actionLabel}
          onClick={fullscreen ? onCollapse : onExpand}
        >
          <AgentMessageExpandIcon expanded={fullscreen} />
        </button>
        {fullscreen && (
          <header className="agent-chat-message-detail-header">
            <time dateTime={message.created_at}>{formatDateTime(message.created_at)}</time>
            {detailActions}
          </header>
        )}
        <AgentChatMessageBody
          message={message}
          highlightMatches={highlightMatches}
          projectFileContext={projectFileContext}
        />
        {canOpenSubagent && (
          <button
            type="button"
            className="agent-chat-message-subagent-button"
            onClick={() => onOpenSubagent?.(message)}
          >
            {t("agentRecord.openSubagent")}
          </button>
        )}
      </div>
    </article>
  );
}

export function AgentChatMessageGroup({
  messages,
  highlightedMessageId,
  projectFileContext,
  onOpenSubagent,
  onExpand,
  highlightMatchesByMessageId = new Map()
}: {
  messages: AgentChatMessage[];
  highlightedMessageId?: string | null;
  projectFileContext?: ProjectFileLinkContext | null;
  onOpenSubagent?: (message: AgentChatMessage) => void;
  onExpand: (messageId: string) => void;
  highlightMatchesByMessageId?: Map<string, SearchMatch[]>;
}) {
  const { t } = useI18n();
  const firstMessage = messages[0];
  if (!firstMessage) {
    return null;
  }

  return (
    <article className={["agent-chat-message", chatMessageClass(firstMessage), "agent-chat-message-agent-group"].join(" ")}>
      <AgentChatAvatar message={firstMessage} />
      <div className="agent-chat-message-content" aria-label={t("agentRecord.messageGroup", { count: messages.length })}>
        <div className="agent-chat-message-group-list" role="list">
          {messages.map((message) => {
            const messageType = defaultAgentMessageType(message);
            const speakerLabel = chatSpeakerLabel(message, t);
            const canOpenSubagent = message.target_session_id !== null && onOpenSubagent !== undefined;

            return (
              <div
                key={message.id}
                className={[
                  "agent-chat-message-group-item",
                  `agent-chat-message-group-item-${messageType.replace("_", "-")}`
                ].join(" ")}
                role="listitem"
                aria-label={t("agentRecord.speakerMessage", { speaker: speakerLabel })}
                ref={highlightedMessageId === message.id ? (element) => element?.scrollIntoView({ block: "center" }) : undefined}
              >
                <button
                  type="button"
                  className="agent-chat-message-zoom-button"
                  aria-label={t("agentRecord.expandSpeakerMessage", { speaker: speakerLabel })}
                  title={t("agentRecord.expand")}
                  onClick={() => onExpand(message.id)}
                >
                  <AgentMessageExpandIcon />
                </button>
                <AgentChatMessageBody
                  message={message}
                  highlightMatches={highlightMatchesByMessageId.get(message.id) ?? []}
                  projectFileContext={projectFileContext}
                />
                {canOpenSubagent && (
                  <button
                    type="button"
                    className="agent-chat-message-subagent-button"
                    onClick={() => onOpenSubagent?.(message)}
                  >
                    {t("agentRecord.openSubagent")}
                  </button>
                )}
              </div>
            );
          })}
        </div>
      </div>
    </article>
  );
}

export function AgentChatAvatar({
  message,
  className = ""
}: {
  message: AgentChatMessage;
  className?: string;
}) {
  const messageType = defaultAgentMessageType(message);
  return (
    <div
      className={[
        "agent-chat-avatar",
        `agent-chat-avatar-${messageType.replace("_", "-")}`,
        className
      ].filter(Boolean).join(" ")}
      aria-hidden="true"
    >
      <AgentChatAvatarIcon type={messageType} />
    </div>
  );
}

function AgentChatAvatarIcon({ type }: { type: ReturnType<typeof defaultAgentMessageType> }) {
  if (type === "user") {
    return (
      <svg viewBox="0 0 24 24" fill="none">
        <path d="M12 12.5a4 4 0 1 0 0-8 4 4 0 0 0 0 8Z" />
        <path d="M4.8 20.2a7.2 7.2 0 0 1 14.4 0" />
      </svg>
    );
  }
  if (type === "agent") {
    return (
      <svg viewBox="0 0 24 24" fill="none">
        <path d="M8 7.5h8a3 3 0 0 1 3 3v4a3 3 0 0 1-3 3H8a3 3 0 0 1-3-3v-4a3 3 0 0 1 3-3Z" />
        <path d="M12 4v3.5" />
        <path d="M9.2 12h.01M14.8 12h.01" />
        <path d="M10 15h4" />
      </svg>
    );
  }
  return (
    <svg viewBox="0 0 24 24" fill="none">
      <path d="M8 8h8a3 3 0 0 1 3 3v2.5a3 3 0 0 1-3 3H8a3 3 0 0 1-3-3V11a3 3 0 0 1 3-3Z" />
      <path d="M12 4v4M8 19l-3 2M16 19l3 2" />
      <path d="M9.3 12h.01M14.7 12h.01" />
    </svg>
  );
}

export function AgentMessageExpandIcon({ expanded = false }: { expanded?: boolean }) {
  return (
    <svg
      aria-hidden="true"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      {expanded
        ? (
          <>
            <path d="M9 3v6H3" />
            <path d="M3 9l7-7" />
            <path d="M15 21v-6h6" />
            <path d="M21 15l-7 7" />
          </>
        )
        : (
          <>
            <path d="M8 3H3v5" />
            <path d="M3 3l7 7" />
            <path d="M16 21h5v-5" />
            <path d="M21 21l-7-7" />
          </>
        )}
    </svg>
  );
}

export function AgentChatMessageOverlay({
  className = "",
  detailActions = null,
  message,
  portalContainer = null,
  projectFileContext,
  onClose
}: {
  className?: string;
  detailActions?: ReactNode;
  message: AgentChatMessage;
  portalContainer?: Element | DocumentFragment | null;
  projectFileContext?: ProjectFileLinkContext | null;
  onClose: () => void;
}) {
  const panelRef = useRef<HTMLElement | null>(null);
  const { t } = useI18n();
  const speakerLabel = chatSpeakerLabel(message, t);

  useOverlayFocus({
    isOpen: true,
    ref: panelRef,
    onEscape: onClose,
    initialFocusSelector: ".agent-chat-message-zoom-button"
  });

  const overlay = (
    <div
      className={["agent-chat-message-overlay", className].filter(Boolean).join(" ")}
      role="dialog"
      aria-modal="true"
      aria-label={t("agentRecord.expandedSpeakerMessage", { speaker: speakerLabel })}
      onClick={stopOverlayPropagation}
      onDragStart={stopOverlayPropagation}
      onMouseDown={stopOverlayPropagation}
      onPointerDown={stopOverlayPropagation}
    >
      <button type="button" className="agent-chat-message-overlay-backdrop" aria-label={t("agentRecord.collapseSpeakerMessage", { speaker: speakerLabel })} onClick={onClose} />
      <AgentChatMessageCard
        message={message}
        fullscreen
        projectFileContext={projectFileContext}
        onCollapse={onClose}
        articleRef={panelRef}
        detailActions={detailActions}
      />
    </div>
  );

  return portalContainer === null ? overlay : createPortal(overlay, portalContainer);
}

function stopOverlayPropagation(event: SyntheticEvent): void {
  event.stopPropagation();
}

export function AgentRecordContent({
  record,
  projectFileContext,
  onOpenSubagent
}: {
  record: AgentRecord;
  projectFileContext?: ProjectFileLinkContext | null;
  onOpenSubagent?: (sessionId: string) => void;
}) {
  const { t } = useI18n();
  if (record.sessions.length === 0 && record.events.length === 0) {
    return <p className="muted">{t("agentRecord.empty")}</p>;
  }
  const sessions = new Map(record.sessions.map((session) => [session.id, session]));

  return (
    <>
      <h4>{t("agentRecord.agents")}</h4>
      <AgentTree nodes={buildAgentTree(record, t)} />
      <h4>{t("agentRecord.recordEvents")}</h4>
      <div className="agent-events">
        {record.events.map((event) => {
          const view = eventView(event, t);
          const session = event.ai_session_id ? sessions.get(event.ai_session_id) : undefined;
          return (
            <article key={event.id} className={`agent-event agent-event-${view.tone}`}>
              <header>
                <div className="agent-event-title">
                  <span>{view.label}</span>
                  {view.subtype && <code>{view.subtype}</code>}
                </div>
                <time dateTime={event.created_at}>{formatDateTime(event.created_at)}</time>
              </header>
              <small>{session ? `${session.provider} · ${sessionLabel(session)}` : `${event.source_type} · ${event.source_id}`}</small>
              {view.bodyFormat === "json"
                ? <pre className="agent-event-json">{view.body}</pre>
                : <MarkdownText text={view.body} projectFileContext={projectFileContext} />}
              {view.targetSessionId && onOpenSubagent && (
                <button
                  type="button"
                  className="agent-event-subagent-button"
                  onClick={() => onOpenSubagent(view.targetSessionId as string)}
                >
                  {t("agentRecord.openSubagent")}
                </button>
              )}
              <details className="agent-event-raw"><summary>{t("agentRecord.rawEvent")}</summary><pre>{json(event)}</pre></details>
            </article>
          );
        })}
      </div>
    </>
  );
}
