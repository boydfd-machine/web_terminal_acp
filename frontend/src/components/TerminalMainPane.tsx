import { useEffect, useState, type MutableRefObject } from "react";
import type { ITheme } from "@xterm/xterm";

import { ProjectFilePreviewPanel } from "./ProjectFilesView";
import { ProjectTodoCreationPendingDialog } from "./ProjectTodoCreationPendingDialog";
import { ProjectTodoPanel } from "./ProjectTodoPanel";
import {
  TerminalPane,
  type TerminalConnectionStatus,
  type TerminalPaneHandle,
} from "./TerminalPane";
import { useI18n } from "../i18n";
import type { ProjectTodoDateFilter } from "../features/projectTodos/projectTodoDateFilter";
import type { CustomQuickKey } from "../terminalQuickKeys";
import type { Project, ProjectFileEntry, ProjectTodoArtifact } from "../types";
import type {
  ProjectTodoCreationPendingRequest,
  ProjectTodoFocusRequest,
  TerminalViewportMode,
  WorkspaceMode
} from "../appState";

type PendingTerminalCreate = {
  title: string;
};

export type TerminalMainPaneProps = {
  cloneTerminalStatus: "idle" | "success";
  customQuickKeys: CustomQuickKey[];
  detailPanelCollapsed: boolean;
  detailPanelOpen: boolean;
  mobileTerminalActive: boolean;
  pendingTerminalCreate: PendingTerminalCreate | null;
  projects: Project[];
  projectPath: string | null;
  projectFilePreviewMode: "edit" | "preview";
  projectTodoCreationPendingRequest: ProjectTodoCreationPendingRequest | null;
  projectTodoDateFilter: ProjectTodoDateFilter;
  projectTodoFocusRequest: ProjectTodoFocusRequest | null;
  selectedClientId: string | null;
  selectedProjectBrowseRoot: string | null;
  selectedProjectFile: ProjectFileEntry | null;
  selectedProjectFileLine: number | null;
  selectedWindowId: string | null;
  allowMissingWindowRecreate: boolean;
  terminalCloneBusy: boolean;
  terminalImmersive: boolean;
  terminalPaneRef: MutableRefObject<TerminalPaneHandle | null>;
  terminalTheme?: ITheme;
  terminalViewportMode: TerminalViewportMode;
  virtualKeysVisible: boolean;
  workspaceMode: WorkspaceMode;
  onCustomQuickKeySubmit: (quickKey: CustomQuickKey) => boolean;
  onQuickInputDraftChange: (draft: string) => void;
  onQuickInputOpenChange: (open: boolean) => void;
  onSetProjectFilePreviewMode: (mode: "edit" | "preview") => void;
  onOpenProjectTodoArtifact: (artifact: ProjectTodoArtifact, projectPath?: string | null) => void;
  onOpenProjectTodoTerminalWindow: (windowId: string, projectPath: string, title?: string | null) => void;
  onSelectProjectWindow: (windowId: string, projectPath: string) => void;
  onTerminalConnectionStatusChange: (status: TerminalConnectionStatus) => void;
  onTerminalSelection: (windowId: string) => void;
};

export function TerminalMainPane({
  cloneTerminalStatus,
  customQuickKeys,
  detailPanelCollapsed,
  detailPanelOpen,
  mobileTerminalActive,
  pendingTerminalCreate,
  projects,
  projectPath,
  projectFilePreviewMode,
  projectTodoCreationPendingRequest,
  projectTodoDateFilter,
  projectTodoFocusRequest,
  selectedClientId,
  selectedProjectBrowseRoot,
  selectedProjectFile,
  selectedProjectFileLine,
  selectedWindowId,
  allowMissingWindowRecreate,
  terminalCloneBusy,
  terminalImmersive,
  terminalPaneRef,
  terminalTheme,
  terminalViewportMode,
  virtualKeysVisible,
  workspaceMode,
  onCustomQuickKeySubmit,
  onQuickInputDraftChange,
  onQuickInputOpenChange,
  onSetProjectFilePreviewMode,
  onOpenProjectTodoArtifact,
  onOpenProjectTodoTerminalWindow,
  onSelectProjectWindow,
  onTerminalConnectionStatusChange,
  onTerminalSelection,
}: TerminalMainPaneProps) {
  const { t } = useI18n();
  const terminalActive = workspaceMode === "terminal";
  const filesActive = workspaceMode === "files";
  const kanbanActive = workspaceMode === "kanban";
  const [mountedModes, setMountedModes] = useState<Record<WorkspaceMode, boolean>>(() => ({
    terminal: terminalActive,
    files: filesActive,
    kanban: kanbanActive,
  }));
  const terminalMounted = terminalActive || mountedModes.terminal;
  const filesMounted = filesActive || mountedModes.files;
  const kanbanMounted = kanbanActive || mountedModes.kanban;
  const matchingProjectTodoCreationPendingRequest = projectTodoCreationPendingRequest !== null
    && selectedClientId !== null
    && projectPath !== null
    && projectTodoCreationPendingRequest.clientId === selectedClientId
    && projectTodoCreationPendingRequest.projectPath === projectPath
      ? projectTodoCreationPendingRequest
      : null;

  useEffect(() => {
    setMountedModes((current) => (
      current[workspaceMode] ? current : { ...current, [workspaceMode]: true }
    ));
  }, [workspaceMode]);

  return (
    <>
      <div className="workspace-mode-pane" data-debug-id="workspace-mode-terminal" hidden={!terminalActive}>
        {terminalMounted && (
          <TerminalPane
            ref={terminalPaneRef}
            clientId={selectedClientId}
            windowId={selectedWindowId}
            allowMissingWindowRecreate={terminalActive && allowMissingWindowRecreate}
            viewportMode={terminalViewportMode}
            onQuickInputOpenChange={onQuickInputOpenChange}
            onQuickInputDraftChange={onQuickInputDraftChange}
            onTerminalConnectionStatusChange={onTerminalConnectionStatusChange}
            customQuickKeys={customQuickKeys}
            onCustomQuickKeySubmit={onCustomQuickKeySubmit}
            theme={terminalTheme}
            layoutVersion={
              (mobileTerminalActive ? 1 : 0)
              + (terminalImmersive ? 2 : 0)
              + (detailPanelOpen ? 4 : 0)
              + (detailPanelCollapsed ? 8 : 0)
            }
            onTerminalSelection={terminalActive ? onTerminalSelection : undefined}
            virtualKeysVisible={virtualKeysVisible}
          />
        )}
      </div>
      <div className="workspace-mode-pane" data-debug-id="workspace-mode-files" hidden={!filesActive}>
        {filesMounted && (
          <ProjectFilePreviewPanel
            browseRoot={selectedProjectBrowseRoot}
            clientId={selectedClientId}
            projectPath={projectPath}
            entry={selectedProjectFile}
            targetLine={selectedProjectFileLine}
            mode={projectFilePreviewMode}
            onModeChange={onSetProjectFilePreviewMode}
          />
        )}
      </div>
      <div className="workspace-mode-pane" data-debug-id="workspace-mode-kanban" hidden={!kanbanActive}>
        {kanbanMounted && (
          selectedClientId === null || projectPath === null ? (
            <div className="project-kanban-empty" role="status">
              <strong>{t("terminal.kanban.selectProject")}</strong>
            </div>
          ) : (
            <section className="project-kanban-workspace" data-debug-id="project-kanban-workspace" aria-label={t("terminal.kanban.region")}>
              <ProjectTodoPanel
                clientId={selectedClientId}
                dateFilter={projectTodoDateFilter}
                focusRequest={projectTodoFocusRequest}
                projects={projects}
                projectPath={projectPath}
                routeWindowId={selectedWindowId}
                viewMode="board"
                onOpenArtifact={onOpenProjectTodoArtifact}
                onOpenTerminalWindow={onOpenProjectTodoTerminalWindow}
                onSelectWindow={onSelectProjectWindow}
              />
              <ProjectTodoCreationPendingDialog request={matchingProjectTodoCreationPendingRequest} />
            </section>
          )
        )}
      </div>
      {terminalActive && pendingTerminalCreate !== null && (
        <div className="terminal-create-progress" role="status" aria-live="polite">
          <span className="terminal-create-progress-spinner" aria-hidden="true" />
          <span>{t("terminal.create.progress", { title: pendingTerminalCreate.title })}</span>
        </div>
      )}
      {terminalActive && (terminalCloneBusy || cloneTerminalStatus === "success") && (
        <div
          className={terminalCloneBusy ? "terminal-clone-progress" : "terminal-clone-progress success"}
          role="status"
          aria-live="polite"
        >
          {terminalCloneBusy && <span className="terminal-create-progress-spinner" aria-hidden="true" />}
          <span>{terminalCloneBusy ? t("terminal.clone.progress") : t("terminal.clone.done")}</span>
        </div>
      )}
    </>
  );
}
