import type { AgentRecordDataState } from "../hooks/useAgentRecordData";
import type { ProjectFileLinkContext } from "../projectFileLinks";
import { AgentRecordModal } from "./AgentRecordViewer";

type AgentRecordStateModalProps = {
  agentRecord: AgentRecordDataState;
  canSendQuickInput?: boolean;
  onClose?: () => void;
  open: boolean;
  projectFileContext?: ProjectFileLinkContext | null;
  quickInputDraft?: string;
  terminalStatusLabel?: string;
  terminalStatusTone?: "connected" | "connecting" | "reconnecting" | "unavailable" | "error";
  onQuickInputDraftChange?: (draft: string) => void;
  onQuickInputSubmit?: (draft: string) => boolean;
};

export function AgentRecordStateModal({
  agentRecord,
  canSendQuickInput,
  onClose,
  open,
  projectFileContext = null,
  quickInputDraft,
  terminalStatusLabel,
  terminalStatusTone,
  onQuickInputDraftChange,
  onQuickInputSubmit
}: AgentRecordStateModalProps) {
  const close = () => {
    agentRecord.setExpanded(false);
    agentRecord.setJumpRequest(null);
    agentRecord.setSelectedSessionId(null);
    onClose?.();
  };

  return (
    <AgentRecordModal
      open={open}
      mode={agentRecord.mode}
      chatRoleFilter={agentRecord.chatRoleFilter}
      chatRecord={agentRecord.chatRecord}
      detailRecord={agentRecord.detailRecord}
      sessions={agentRecord.sessions}
      isLoading={agentRecord.isLoading}
      isError={agentRecord.isError}
      isFetching={agentRecord.isFetching}
      projectFileContext={projectFileContext}
      terminalStatusLabel={terminalStatusLabel}
      terminalStatusTone={terminalStatusTone}
      quickInputDraft={quickInputDraft}
      canSendQuickInput={canSendQuickInput}
      onQuickInputDraftChange={onQuickInputDraftChange}
      onQuickInputSubmit={onQuickInputSubmit}
      onModeChange={agentRecord.setMode}
      onChatRoleFilterChange={agentRecord.setChatRoleFilter}
      jumpRequest={agentRecord.jumpRequest}
      onClose={close}
      onSessionChange={agentRecord.setSelectedSessionId}
      onPreviousPage={agentRecord.previousPage}
      onNextPage={agentRecord.nextPage}
    />
  );
}
