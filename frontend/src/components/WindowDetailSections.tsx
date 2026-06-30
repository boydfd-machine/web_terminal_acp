import type { Dispatch, SetStateAction } from "react";

import type { useAgentConfigData } from "../hooks/useAgentConfigData";
import type { ProjectFileLinkContext } from "../projectFileLinks";
import { useI18n } from "../i18n";
import { AgentConfigViewer } from "./AgentConfigViewer";
import { AgentRecordStateModal } from "./AgentRecordStateModal";
import { AgentRecordViewer } from "./AgentRecordViewer";
import { CommandHistoryViewer } from "./CommandHistoryViewer";
import { TitleHistoryViewer } from "./TitleHistoryViewer";
import type { AgentDetailTab, HistoryDetailTab } from "./windowDetailData";

type WindowAgentSectionProps = {
  agentConfig: ReturnType<typeof useAgentConfigData>;
  agentDetailTab: AgentDetailTab;
  agentRecord: any;
  agentRecordShortcutLabel: string;
  canSendQuickInput?: boolean;
  onQuickInputDraftChange?: (draft: string) => void;
  onQuickInputSubmit?: (draft: string) => boolean;
  projectFileContext?: ProjectFileLinkContext | null;
  quickInputDraft?: string;
  setAgentDetailTab: Dispatch<SetStateAction<AgentDetailTab>>;
  terminalStatusLabel?: string;
  terminalStatusTone?: "connected" | "connecting" | "reconnecting" | "unavailable" | "error";
};

export function WindowAgentSection({
  agentConfig,
  agentDetailTab,
  agentRecord,
  agentRecordShortcutLabel,
  canSendQuickInput,
  onQuickInputDraftChange,
  onQuickInputSubmit,
  projectFileContext = null,
  quickInputDraft,
  setAgentDetailTab,
  terminalStatusLabel,
  terminalStatusTone
}: WindowAgentSectionProps) {
  const { t } = useI18n();

  return (
    <>
      <div className="agent-detail-tabs" role="tablist" aria-label={t("detail.tabs.agent")}>
        <button type="button" role="tab" aria-selected={agentDetailTab === "record"} className={agentDetailTab === "record" ? "selected" : undefined} onClick={() => setAgentDetailTab("record")}>{t("detail.tabs.record")}</button>
        <button type="button" role="tab" aria-selected={agentDetailTab === "config"} className={agentDetailTab === "config" ? "selected" : undefined} onClick={() => setAgentDetailTab("config")}>{t("detail.tabs.config")}</button>
      </div>
      {agentDetailTab === "record" ? (
        <>
          <AgentRecordViewer
            mode={agentRecord.mode}
            chatRoleFilter={agentRecord.chatRoleFilter}
            chatRecord={agentRecord.chatRecord}
            detailRecord={agentRecord.detailRecord}
            sessions={agentRecord.sessions}
            isLoading={agentRecord.isLoading}
            isError={agentRecord.isError}
            isFetching={agentRecord.isFetching}
            projectFileContext={projectFileContext}
            onModeChange={agentRecord.setMode}
            onChatRoleFilterChange={agentRecord.setChatRoleFilter}
            onOpenSubagent={(sessionId, originMessageId) => {
              agentRecord.setJumpRequest({ sessionId, originMessageId });
              agentRecord.setExpanded(true);
            }}
            onExpand={() => agentRecord.setExpanded(true)}
            expandShortcutLabel={agentRecordShortcutLabel}
            onSessionChange={agentRecord.setSelectedSessionId}
            onPreviousPage={agentRecord.previousPage}
            onNextPage={agentRecord.nextPage}
            searchDraft={agentRecord.searchDraft}
            searchQuery={agentRecord.searchQuery}
            searchRecord={agentRecord.searchRecord}
            searchIsLoading={agentRecord.searchIsLoading}
            searchIsError={agentRecord.searchIsError}
            searchIsFetching={agentRecord.searchIsFetching}
            onSearchDraftChange={agentRecord.setSearchDraft}
            onSearchSubmit={agentRecord.submitSearch}
            onSearchClear={agentRecord.clearSearch}
            onPreviousSearchPage={agentRecord.previousSearchPage}
            onNextSearchPage={agentRecord.nextSearchPage}
            quickInputDraft={quickInputDraft}
            canSendQuickInput={canSendQuickInput}
            onQuickInputDraftChange={onQuickInputDraftChange}
            onQuickInputSubmit={onQuickInputSubmit}
          />
          <AgentRecordStateModal
            agentRecord={agentRecord}
            open={agentRecord.expanded}
            projectFileContext={projectFileContext}
            terminalStatusLabel={terminalStatusLabel}
            terminalStatusTone={terminalStatusTone}
            quickInputDraft={quickInputDraft}
            canSendQuickInput={canSendQuickInput}
            onQuickInputDraftChange={onQuickInputDraftChange}
            onQuickInputSubmit={onQuickInputSubmit}
          />
        </>
      ) : (
        <AgentConfigViewer
          config={agentConfig.config}
          isLoading={agentConfig.isLoading}
          isError={agentConfig.isError}
          isFetching={agentConfig.isFetching}
          pendingItemId={agentConfig.pendingItemId}
          isToggling={agentConfig.isToggling}
          toggleError={agentConfig.toggleError}
          onToggleItem={agentConfig.toggleItem}
          onUpdateModel={agentConfig.updateModel}
          isUpdatingModel={agentConfig.isUpdatingModel}
          modelUpdateError={agentConfig.modelUpdateError}
        />
      )}
    </>
  );
}

type WindowHistorySectionProps = {
  commandHistoryQuery: any;
  historyDetailTab: HistoryDetailTab;
  setCommandHistoryPage: Dispatch<SetStateAction<number>>;
  setHistoryDetailTab: Dispatch<SetStateAction<HistoryDetailTab>>;
  setTitleHistoryPage: Dispatch<SetStateAction<number>>;
  titleHistoryQuery: any;
};

export function WindowHistorySection({
  commandHistoryQuery,
  historyDetailTab,
  setCommandHistoryPage,
  setHistoryDetailTab,
  setTitleHistoryPage,
  titleHistoryQuery
}: WindowHistorySectionProps) {
  const { t } = useI18n();

  return (
    <>
      <div className="history-detail-tabs" role="tablist" aria-label={t("detail.tabs.history")}>
        <button type="button" role="tab" aria-selected={historyDetailTab === "commands"} className={historyDetailTab === "commands" ? "selected" : undefined} onClick={() => setHistoryDetailTab("commands")}>{t("detail.tabs.commands")}</button>
        <button type="button" role="tab" aria-selected={historyDetailTab === "title"} className={historyDetailTab === "title" ? "selected" : undefined} onClick={() => setHistoryDetailTab("title")}>{t("detail.tabs.title")}</button>
      </div>
      {historyDetailTab === "commands" ? (
        <CommandHistoryViewer
          history={commandHistoryQuery.data ?? null}
          isLoading={commandHistoryQuery.isLoading}
          isError={commandHistoryQuery.isError}
          isFetching={commandHistoryQuery.isFetching}
          onPreviousPage={() => setCommandHistoryPage((page) => Math.max(0, page - 1))}
          onNextPage={() => setCommandHistoryPage((page) => page + 1)}
        />
      ) : (
        <TitleHistoryViewer
          history={titleHistoryQuery.data ?? null}
          isLoading={titleHistoryQuery.isLoading}
          isError={titleHistoryQuery.isError}
          isFetching={titleHistoryQuery.isFetching}
          onPreviousPage={() => setTitleHistoryPage((page) => Math.max(0, page - 1))}
          onNextPage={() => setTitleHistoryPage((page) => page + 1)}
        />
      )}
    </>
  );
}
