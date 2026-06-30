import type { AgentChatRoleFilter, AgentRecordDisplayMode, AgentSession } from "../types";
import { useI18n } from "../i18n";
import {
  CHAT_ROLE_FILTER_LABELS,
  chatRoleFilterLabel,
  pageRange,
  sessionLabel,
  sortSessionsByCreation,
  type PageInfo
} from "./AgentRecordData";
import { UiIcon } from "./UiIcon";

export function AgentRecordModeToggle({
  mode,
  onModeChange,
  disabled = false
}: {
  mode: AgentRecordDisplayMode;
  onModeChange: (mode: AgentRecordDisplayMode) => void;
  disabled?: boolean;
}) {
  const { t } = useI18n();
  return (
    <div className="agent-record-mode-toggle" role="group" aria-label={t("agentRecord.displayMode")}>
      <button
        type="button"
        className={mode === "chat" ? "selected" : undefined}
        aria-pressed={mode === "chat"}
        disabled={disabled}
        onClick={() => onModeChange("chat")}
      >
        {t("agentRecord.chat")}
      </button>
      <button
        type="button"
        className={mode === "detail" ? "selected" : undefined}
        aria-pressed={mode === "detail"}
        disabled={disabled}
        onClick={() => onModeChange("detail")}
      >
        {t("agentRecord.detail")}
      </button>
    </div>
  );
}

export function AgentChatRoleFilterToggle({
  value,
  onChange,
  disabled = false
}: {
  value: AgentChatRoleFilter;
  onChange: (role: AgentChatRoleFilter) => void;
  disabled?: boolean;
}) {
  const { t } = useI18n();
  return (
    <div className="agent-record-role-toggle" role="group" aria-label={t("agentRecord.messageType")}>
      {(Object.keys(CHAT_ROLE_FILTER_LABELS) as AgentChatRoleFilter[]).map((role) => (
        <button
          key={role}
          type="button"
          className={value === role ? "selected" : undefined}
          aria-pressed={value === role}
          disabled={disabled}
          onClick={() => onChange(role)}
        >
          {chatRoleFilterLabel(role, t)}
        </button>
      ))}
    </div>
  );
}


export function AgentRecordSessionTabs({
  sessions,
  selectedSessionId,
  onSelectSession
}: {
  sessions: AgentSession[];
  selectedSessionId: string;
  onSelectSession: (sessionId: string) => void;
}) {
  const { t } = useI18n();
  const orderedSessions = sortSessionsByCreation(sessions);
  return (
    <div className="agent-record-session-tabs" role="tablist" aria-label={t("agentRecord.sessions")}>
      {orderedSessions.map((session, index) => (
        <button
          key={session.id}
          type="button"
          role="tab"
          className={session.id === selectedSessionId ? "selected" : undefined}
          aria-selected={session.id === selectedSessionId}
          title={sessionLabel(session)}
          onClick={() => onSelectSession(session.id)}
        >
          {index === 0 ? t("agentRecord.mainSession") : t("agentRecord.subSession", { index })}
        </button>
      ))}
    </div>
  );
}

export function AgentRecordReturnButton({
  originMessageId,
  onReturn
}: {
  originMessageId: string | null;
  onReturn: () => void;
}) {
  const { t } = useI18n();
  if (originMessageId === null) {
    return null;
  }
  return (
    <button type="button" className="agent-record-return-button" onClick={onReturn}>
      {t("agentRecord.returnToCall")}
    </button>
  );
}

export function AgentRecordPagination({
  info,
  isFetching,
  onPreviousPage,
  onNextPage
}: {
  info: PageInfo | null;
  isFetching: boolean;
  onPreviousPage?: () => void;
  onNextPage?: () => void;
}) {
  const { t } = useI18n();
  if (info === null) return null;
  const canPrevious = info.offset > 0;
  const canNext = info.hasMore;
  return (
    <div className="agent-record-pagination">
      <span>{pageRange(info, t)}{isFetching ? ` · ${t("agentRecord.refreshing")}` : ""}</span>
      <div>
        <button
          type="button"
          className="ui-icon-button"
          disabled={!canPrevious || !onPreviousPage}
          aria-label={t("common.previous")}
          title={t("common.previous")}
          onClick={onPreviousPage}
        >
          <UiIcon name="chevron-left" />
        </button>
        <button
          type="button"
          className="ui-icon-button"
          disabled={!canNext || !onNextPage}
          aria-label={t("common.next")}
          title={t("common.next")}
          onClick={onNextPage}
        >
          <UiIcon name="chevron-right" />
        </button>
      </div>
    </div>
  );
}
