import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { useI18n } from "../i18n";
import type {
  AgentChatMessage,
  AgentChatRecord,
  AgentChatRoleFilter,
  AgentRecord,
  AgentRecordDisplayMode,
  AgentSession
} from "../types";
import { TerminalQuickInput } from "./TerminalQuickInput";
import { useOverlayFocus } from "./useOverlayFocus";
import { AgentChatContent } from "./AgentChatContent";
import { AgentMessageExpandIcon, AgentRecordContent } from "./AgentRecordContent";
import { AgentRecordScopedSearch } from "./AgentRecordScopedSearch";
import {
  AgentChatRoleFilterToggle,
  AgentRecordModeToggle,
  AgentRecordPagination,
  AgentRecordReturnButton,
  AgentRecordSessionTabs
} from "./AgentRecordControls";
import {
  pickInitialSessionId,
  recordMeta,
  pageInfo,
  hasSubagentSessionNavigation,
  sortSessionsByCreation,
  type AgentRecordJumpRequest,
  type AgentRecordPageOffset,
  type AgentRecordViewProps,
  type AgentRecordViewerProps,
  type AgentRecordModalProps
} from "./AgentRecordData";

export function AgentRecordViewer({
  mode,
  chatRoleFilter,
  chatRecord,
  detailRecord,
  sessions,
  isLoading = false,
  isError = false,
  isFetching = false,
  projectFileContext = null,
  onModeChange,
  onChatRoleFilterChange,
  onOpenSubagent,
  onSessionChange,
  onPreviousPage,
  onNextPage,
  searchDraft = "",
  searchQuery = "",
  searchRecord = null,
  searchIsLoading = false,
  searchIsError = false,
  searchIsFetching = false,
  onSearchDraftChange,
  onSearchSubmit,
  onSearchClear,
  onPreviousSearchPage,
  onNextSearchPage,
  onExpand,
  expandShortcutLabel = "Expand",
  quickInputDraft = "",
  canSendQuickInput = false,
  onQuickInputDraftChange,
  onQuickInputSubmit
}: AgentRecordViewerProps) {
  const { t } = useI18n();
  const activeRecord = mode === "chat" ? chatRecord : detailRecord;
  const canExpand = activeRecord !== null && !isLoading && !isError;
  const searchActive = searchQuery.trim().length > 0;
  const activePageInfo = pageInfo(mode, chatRecord, detailRecord);
  const canUseQuickInput = onQuickInputDraftChange !== undefined && onQuickInputSubmit !== undefined;
  const content = isLoading
    ? <p className="muted">{t("agentRecord.loading")}</p>
    : isError || activeRecord === null
      ? <p className="error" role="alert">{t("agentRecord.loadFailed")}</p>
      : mode === "chat"
        ? (
          <AgentChatContent
            record={activeRecord as AgentChatRecord}
            projectFileContext={projectFileContext}
            onOpenSubagent={(message) => {
              if (message.target_session_id) {
                onOpenSubagent?.(message.target_session_id, message.id);
              }
            }}
          />
        )
        : (
          <AgentRecordContent
            record={activeRecord as AgentRecord}
            projectFileContext={projectFileContext}
            onOpenSubagent={(sessionId) => {
              onOpenSubagent?.(sessionId);
            }}
          />
        );
  const meta = recordMeta(mode, chatRoleFilter, chatRecord, detailRecord, isLoading, isError, t);

  const openExpanded = () => {
    onExpand();
  };
  const submitQuickInput = (draft: string) => {
    if (!canUseQuickInput) {
      return false;
    }
    return onQuickInputSubmit(draft);
  };

  return (
    <section className="agent-record-viewer">
      <div className="agent-record-header">
        <div>
          <h3>{t("agentRecord.title")}</h3>
          <small>{meta}</small>
        </div>
        <div className="agent-record-actions">
          <AgentRecordModeToggle mode={mode} onModeChange={onModeChange} disabled={isLoading} />
          {mode === "chat" && (
            <AgentChatRoleFilterToggle
              value={chatRoleFilter}
              onChange={onChatRoleFilterChange}
              disabled={isLoading}
            />
          )}
          <button
            type="button"
            className="agent-record-icon-button"
            disabled={!canExpand}
            onClick={openExpanded}
            aria-label={t("agentRecord.expandRecord")}
            title={t("agentRecord.expandRecordWithShortcut", { shortcut: expandShortcutLabel })}
          >
            <AgentMessageExpandIcon />
          </button>
        </div>
      </div>
      <AgentRecordPagination info={activePageInfo} isFetching={isFetching && !isLoading} onPreviousPage={onPreviousPage} onNextPage={onNextPage} />
      <AgentRecordScopedSearch
        draft={searchDraft}
        query={searchQuery}
        record={searchRecord}
        isLoading={searchIsLoading}
        isError={searchIsError}
        isFetching={searchIsFetching}
        onDraftChange={onSearchDraftChange}
        onSubmit={onSearchSubmit}
        onClear={onSearchClear}
        onPreviousPage={onPreviousSearchPage}
        onNextPage={onNextSearchPage}
      />
      <div className="agent-record-body">
        {searchActive ? null : content}
      </div>
      {canUseQuickInput && (
        <TerminalQuickInput
          className="agent-record-quick-input"
          value={quickInputDraft}
          canSend={canSendQuickInput}
          onValueChange={onQuickInputDraftChange}
          onSubmit={submitQuickInput}
          placeholder={t("agentRecord.quickInputPlaceholder")}
          submitOnEnter
        />
      )}
    </section>
  );
}

export function AgentRecordModal({
  open,
  mode,
  chatRoleFilter,
  chatRecord,
  detailRecord,
  sessions,
  isLoading = false,
  isError = false,
  isFetching = false,
  projectFileContext = null,
  terminalStatusLabel = "Terminal unavailable",
  terminalStatusTone = "unavailable",
  quickInputDraft = "",
  canSendQuickInput = false,
  onQuickInputDraftChange,
  onQuickInputSubmit,
  onModeChange,
  onChatRoleFilterChange,
  jumpRequest = null,
  onSessionChange,
  onPreviousPage,
  onNextPage,
  onClose
}: AgentRecordModalProps) {
  const { t } = useI18n();
  const [selectedSessionId, setSelectedSessionId] = useState<string | null>(null);
  const [returnTarget, setReturnTarget] = useState<{
    sessionId: string | null;
    messageId: string;
    pageOffset: AgentRecordPageOffset;
  } | null>(null);
  const [highlightedMessageId, setHighlightedMessageId] = useState<string | null>(null);
  const panelRef = useRef<HTMLElement | null>(null);
  const lastJumpKeyRef = useRef<string | null>(null);
  const sortedSessions = useMemo(() => sortSessionsByCreation(sessions), [sessions]);
  const hasSessionNavigation = hasSubagentSessionNavigation(sortedSessions, chatRecord, detailRecord);
  const activeSessionId = hasSessionNavigation ? selectedSessionId ?? pickInitialSessionId(sortedSessions) : null;
  const activeRecord = mode === "chat" ? chatRecord : detailRecord;
  const canRenderContent = activeRecord !== null && !isLoading && !isError;
  const expandedDisplayRecord = mode === "chat" ? chatRecord : detailRecord;
  const activePageInfo = pageInfo(mode, chatRecord, detailRecord);
  const canUseQuickInput = onQuickInputDraftChange !== undefined && onQuickInputSubmit !== undefined;
  const currentPageOffset = (): AgentRecordPageOffset => {
    if (mode === "chat") {
      return { chatOffset: chatRecord?.messages_offset ?? 0 };
    }
    return { detailOffset: detailRecord?.events_offset ?? 0 };
  };

  const selectSession = (sessionId: string) => {
    setReturnTarget(null);
    setSelectedSessionId(sessionId);
    onSessionChange?.(sessionId);
  };

  const openSubagentFromMessage = (message: AgentChatMessage) => {
    if (!message.target_session_id) {
      return;
    }
    setReturnTarget({ sessionId: activeSessionId, messageId: message.id, pageOffset: currentPageOffset() });
    setSelectedSessionId(message.target_session_id);
    onSessionChange?.(message.target_session_id);
  };

  const openSubagentSession = (sessionId: string) => {
    setReturnTarget(null);
    setSelectedSessionId(sessionId);
    onSessionChange?.(sessionId);
  };

  const returnToCall = () => {
    if (returnTarget === null) {
      return;
    }
    setSelectedSessionId(returnTarget.sessionId);
    setHighlightedMessageId(returnTarget.messageId);
    onSessionChange?.(returnTarget.sessionId, returnTarget.pageOffset);
    setReturnTarget(null);
  };

  useEffect(() => {
    if (highlightedMessageId === null) {
      return;
    }
    const timeout = window.setTimeout(() => setHighlightedMessageId(null), 1600);
    return () => window.clearTimeout(timeout);
  }, [highlightedMessageId]);

  useEffect(() => {
    if (!open || jumpRequest === null) {
      return;
    }
    const jumpKey = `${jumpRequest.sessionId}:${jumpRequest.originMessageId ?? ""}`;
    if (lastJumpKeyRef.current === jumpKey) {
      return;
    }
    lastJumpKeyRef.current = jumpKey;
    const previousSessionId = selectedSessionId ?? pickInitialSessionId(sortedSessions);
    setReturnTarget(jumpRequest.originMessageId
      ? { sessionId: previousSessionId, messageId: jumpRequest.originMessageId, pageOffset: currentPageOffset() }
      : null);
    setSelectedSessionId(jumpRequest.sessionId);
    onSessionChange?.(jumpRequest.sessionId);
  }, [
    chatRecord?.messages_offset,
    detailRecord?.events_offset,
    jumpRequest,
    mode,
    onSessionChange,
    open,
    selectedSessionId,
    sortedSessions
  ]);

  useEffect(() => {
    if (!open) {
      setSelectedSessionId(null);
      setReturnTarget(null);
      setHighlightedMessageId(null);
      lastJumpKeyRef.current = null;
      return;
    }
  }, [open]);

  useEffect(() => {
    if (!open) {
      return;
    }
    if (sortedSessions.length === 0 || !hasSessionNavigation) {
      if (jumpRequest === null) {
        setSelectedSessionId(null);
      }
      return;
    }
    if (
      selectedSessionId !== null
      && (
        sortedSessions.some((session) => session.id === selectedSessionId)
        || (jumpRequest !== null && selectedSessionId === jumpRequest.sessionId)
      )
    ) {
      return;
    }
    setSelectedSessionId(pickInitialSessionId(sortedSessions));
  }, [hasSessionNavigation, jumpRequest, open, selectedSessionId, sortedSessions]);

  const handleEscape = useCallback(() => {
    if (panelRef.current?.querySelector(".agent-chat-message-overlay")) {
      return;
    }
    onClose();
  }, [onClose]);

  useOverlayFocus({
    isOpen: open,
    ref: panelRef,
    onEscape: handleEscape,
    preserveExistingFocus: true
  });

  const sessionTabs = hasSessionNavigation && activeSessionId
    ? (
      <AgentRecordSessionTabs
        sessions={sortedSessions}
        selectedSessionId={activeSessionId}
        onSelectSession={selectSession}
      />
    )
    : null;

  if (!open) {
    return null;
  }

  const pendingJumpTarget = jumpRequest !== null && !sortedSessions.some((session) => session.id === jumpRequest.sessionId);

  const submitQuickInput = (draft: string) => {
    if (!canUseQuickInput) {
      return false;
    }
    return onQuickInputSubmit(draft);
  };

  return (
    <div className="agent-record-modal" role="dialog" aria-modal="true" aria-label={t("agentRecord.title")}>
      <button type="button" className="agent-record-modal-backdrop" aria-label={t("agentRecord.collapseRecord")} onClick={onClose} />
      <section ref={panelRef} className="agent-record-modal-panel">
        <div className="agent-record-header">
          <div>
            <h3>{t("agentRecord.title")}</h3>
            <small>{recordMeta(mode, chatRoleFilter, chatRecord, detailRecord, isLoading, isError, t)}</small>
          </div>
          <div className="agent-record-actions">
            <span className={`agent-record-terminal-status ${terminalStatusTone}`} role="status">
              {terminalStatusLabel}
            </span>
            <AgentRecordModeToggle mode={mode} onModeChange={onModeChange} disabled={isLoading} />
            {mode === "chat" && (
              <AgentChatRoleFilterToggle
                value={chatRoleFilter}
                onChange={onChatRoleFilterChange}
                disabled={isLoading}
              />
            )}
            <button
              type="button"
              className="agent-record-icon-button"
              onClick={onClose}
              aria-label={t("agentRecord.collapseRecord")}
              title={t("agentRecord.collapseRecord")}
            >
              <AgentMessageExpandIcon expanded />
            </button>
          </div>
        </div>
        <div className="agent-record-modal-scroll">
          {sessionTabs}
          <AgentRecordReturnButton originMessageId={returnTarget?.messageId ?? null} onReturn={returnToCall} />
          <AgentRecordPagination info={activePageInfo} isFetching={isFetching} onPreviousPage={onPreviousPage} onNextPage={onNextPage} />
          {isLoading
            ? <p className="muted">{t("agentRecord.loading")}</p>
            : pendingJumpTarget
              ? <p className="muted">{t("agentRecord.loadingSubagent")}</p>
            : isError
              ? <p className="error" role="alert">{t("agentRecord.loadFailed")}</p>
              : canRenderContent && expandedDisplayRecord
                ? mode === "chat"
                  ? (
                    <AgentChatContent
                      record={expandedDisplayRecord as AgentChatRecord}
                      highlightedMessageId={highlightedMessageId}
                      projectFileContext={projectFileContext}
                      onOpenSubagent={openSubagentFromMessage}
                    />
                  )
                  : (
                    <AgentRecordContent
                      record={expandedDisplayRecord as AgentRecord}
                      projectFileContext={projectFileContext}
                      onOpenSubagent={openSubagentSession}
                    />
                  )
                : <p className="muted">{t("agentRecord.empty")}</p>}
        </div>
        {canUseQuickInput && (
          <TerminalQuickInput
            className="agent-record-quick-input"
            value={quickInputDraft}
            canSend={canSendQuickInput}
            onValueChange={onQuickInputDraftChange}
            onSubmit={submitQuickInput}
            autoFocus
            placeholder={t("agentRecord.quickInputPlaceholder")}
            submitOnEnter
          />
        )}
      </section>
    </div>
  );
}
