import type { MutableRefObject } from "react";

import { ProjectDetail } from "./ProjectDetail";
import { WindowDetail } from "./WindowDetail";
import type { TerminalConnectionStatus, TerminalPaneHandle } from "./TerminalPane";
import {
  terminalStatusLabel,
  type DetailContext,
  type ProjectTodoFocusRequest,
  type WorkspaceMode
} from "../appState";
import type { ProjectFileLinkContext } from "../projectFileLinks";
import type { Project, ProjectTodoArtifact, TerminalArtifact, TreeWindow } from "../types";
import type { TerminalTimeRange } from "../userPreferences";
import { UiIcon } from "./UiIcon";
import { useI18n } from "../i18n";

export type AppDetailPanelProps = {
  agentPreviewCanSendQuickInput: boolean;
  agentRecordShortcutLabel: string;
  detailContext: DetailContext;
  project: Project | null;
  projects: Project[];
  projectPath: string | null;
  projectFileContext?: ProjectFileLinkContext | null;
  projectTodoFocusRequest: ProjectTodoFocusRequest | null;
  quickInputDraft: string;
  selectedClientId: string | null;
  selectedProjectPath: string | null;
  selectedTreeWindow: TreeWindow | null | undefined;
  selectedWindowId: string | null;
  terminalConnectionStatus: TerminalConnectionStatus;
  terminalPaneRef: MutableRefObject<TerminalPaneHandle | null>;
  terminalTimeRange: TerminalTimeRange;
  workspaceMode: WorkspaceMode;
  onCollapseDetails: () => void;
  onCloseDetails: () => void;
  onOpenArtifactTerminal: (artifact: TerminalArtifact) => void;
  onOpenProjectTodoArtifact: (artifact: ProjectTodoArtifact, projectPath?: string | null) => void;
  onQuickInputSubmit: (draft: string) => boolean;
  onFocusProjectTodo: (projectPath: string, todoId: string) => void;
  onSelectProjectWindow: (windowId: string, projectPath: string) => void;
  onSelectWindow: (windowId: string) => void;
};

export function AppDetailPanel({
  agentPreviewCanSendQuickInput,
  agentRecordShortcutLabel,
  detailContext,
  project,
  projects,
  projectPath,
  projectFileContext = null,
  projectTodoFocusRequest,
  quickInputDraft,
  selectedClientId,
  selectedProjectPath,
  selectedTreeWindow,
  selectedWindowId,
  terminalConnectionStatus,
  terminalPaneRef,
  terminalTimeRange,
  workspaceMode,
  onCollapseDetails,
  onCloseDetails,
  onFocusProjectTodo,
  onOpenArtifactTerminal,
  onOpenProjectTodoArtifact,
  onQuickInputSubmit,
  onSelectProjectWindow,
  onSelectWindow,
}: AppDetailPanelProps) {
  const { t } = useI18n();

  return (
    <aside className="detail-panel" data-onboarding-id="detail-panel">
      <div className="detail-panel-desktop-header">
        <strong>{t("detail.panel.title")}</strong>
        <button
          type="button"
          className="detail-panel-collapse-button ui-icon-button"
          aria-label={t("detail.panel.collapse")}
          title={t("detail.panel.collapse")}
          onClick={onCollapseDetails}
        >
          <UiIcon name="chevron-right" />
        </button>
      </div>
      <div className="detail-panel-mobile-header">
        <strong>{t("detail.panel.title")}</strong>
        <button
          type="button"
          className="ui-icon-button"
          aria-label={t("detail.panel.close")}
          title={t("common.close")}
          onClick={onCloseDetails}
        >
          <UiIcon name="x" />
        </button>
      </div>
      {workspaceMode === "files" || detailContext === "project" ? (
        <ProjectDetail
          clientId={selectedClientId}
          projectPath={selectedProjectPath}
          project={project}
          projects={projects}
          todoFocusRequest={projectTodoFocusRequest}
          timeRange={terminalTimeRange}
          workspaceMode={workspaceMode}
          onOpenArtifact={onOpenProjectTodoArtifact}
          onSelectWindow={onSelectProjectWindow}
        />
      ) : (
        <WindowDetail
          clientId={selectedClientId}
          windowId={selectedWindowId}
          gitWorktree={selectedTreeWindow?.git_worktree ?? null}
          projectFileContext={projectFileContext}
          terminalStatusLabel={terminalStatusLabel(terminalConnectionStatus)}
          terminalStatusTone={terminalConnectionStatus}
          quickInputDraft={quickInputDraft}
          canSendQuickInput={agentPreviewCanSendQuickInput}
          agentRecordShortcutLabel={agentRecordShortcutLabel}
          onQuickInputDraftChange={(draft) => terminalPaneRef.current?.setQuickInputDraft(draft)}
          onQuickInputSubmit={onQuickInputSubmit}
          onFocusProjectTodo={onFocusProjectTodo}
          onOpenArtifactTerminal={onOpenArtifactTerminal}
        />
      )}
    </aside>
  );
}
