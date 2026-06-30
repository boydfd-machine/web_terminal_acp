import { useEffect, useState } from "react";

import { ClientList } from "./ClientList";
import { FolderTree } from "./FolderTree";
import { ProjectCardRow, projectFallbackLabel } from "./FolderTreeNodes";
import { NotificationBellButton } from "./NotificationCenter";
import { ProjectFileTreePanel } from "./ProjectFilesView";
import { ProjectTodoSidebarControls } from "./ProjectTodoSidebarControls";
import { TERMINAL_TIME_RANGE_OPTIONS, isTerminalTimeRange } from "../terminalTimeRange";
import { terminalStatusLabel, type WorkspaceMode } from "../appState";
import type { AddClientMode } from "../appTypes";
import { useI18n } from "../i18n";
import type { ProjectTodoDateFilter } from "../features/projectTodos/projectTodoDateFilter";
import type {
  Client,
  Project,
  ProjectFileEntry,
  TerminalProject,
  TreeFolder,
} from "../types";
import type { SummaryOutputLanguage, TerminalGroupingMode, TerminalTimeRange } from "../userPreferences";

export type AppSidebarProps = {
  addClientPending: boolean;
  clients: Client[] | undefined;
  clientsCollapsed: boolean;
  clientsError: boolean;
  clientsLoading: boolean;
  createErrorMessage: string;
  createTerminalBusy: boolean;
  createError: boolean;
  cloneError: boolean;
  cloneErrorMessage: string;
  deleteClientError: boolean;
  deleteClientErrorMessage: string;
  deleteClientId: string | null;
  deleteError: boolean;
  deleteErrorMessage: string;
  deletingWindowId: string | null;
  generateTraceError: boolean;
  generateTraceErrorMessage: string;
  hasUnreadNotification: (windowId: string) => boolean;
  loadingSelectedProject: boolean;
  loadingTerminalProjects: boolean;
  notificationCenterOpen: boolean;
  projectListCollapsed: boolean;
  projectTodoDateFilter: ProjectTodoDateFilter;
  projects: Project[];
  selectedClientId: string | null;
  selectedClientOffline: boolean;
  selectedProjectFile: ProjectFileEntry | null;
  selectedProjectBrowseRoot: string | null;
  selectedProjectPath: string | null;
  selectedWindowId: string | null;
  summaryOutputLanguage: SummaryOutputLanguage;
  terminalGroupingMode: TerminalGroupingMode;
  terminalListLocateSignal: number;
  terminalProjects: TerminalProject[];
  terminalProjectsError: boolean;
  terminalTimeRange: TerminalTimeRange;
  treeError: boolean;
  treeFolders: TreeFolder[] | undefined;
  unreadNotificationCount: number;
  updateFailed: boolean;
  updateMessage: string | null;
  updatingClientId: string | null;
  reregisteringClientId: string | null;
  workspaceMode: WorkspaceMode;
  onCreateTerminalAtGroup: Parameters<typeof FolderTree>[0]["onCreateTerminalAtGroup"];
  onConfigureTerminalAtGroup: Parameters<typeof FolderTree>[0]["onConfigureTerminalAtGroup"];
  onDeleteClient: (client: Client) => void;
  onDeleteWindow: (windowId: string, title: string) => void;
  onEnterTerminal: () => void;
  onOpenAddClient: (mode: AddClientMode) => void;
  onOpenProjectDetail: (projectPath: string) => void;
  onSelectClient: (clientId: string) => void;
  onSelectProject: (projectPath: string) => void;
  onSelectProjectFile: (entry: ProjectFileEntry | null) => void;
  onSelectWindow: (windowId: string) => void;
  onSetClientsCollapsed: (updater: (collapsed: boolean) => boolean) => void;
  onSetProjectListCollapsed: (updater: (collapsed: boolean) => boolean) => void;
  onSetProjectTodoDateFilter: (filter: ProjectTodoDateFilter) => void;
  onSetTerminalTimeRange: (range: TerminalTimeRange) => void;
  onToggleNotificationCenter: () => void;
  onTriggerNewTerminal: () => void;
  onUpdateClient: (clientId: string) => void;
  onReregisterClient: (client: Client) => void;
  newTerminalShortcutLabel: string;
};

export function AppSidebar({
  addClientPending,
  clients,
  clientsCollapsed,
  clientsError,
  clientsLoading,
  cloneError,
  cloneErrorMessage,
  createError,
  createErrorMessage,
  createTerminalBusy,
  deleteClientError,
  deleteClientErrorMessage,
  deleteClientId,
  deleteError,
  deleteErrorMessage,
  deletingWindowId,
  generateTraceError,
  generateTraceErrorMessage,
  hasUnreadNotification,
  loadingSelectedProject,
  loadingTerminalProjects,
  notificationCenterOpen,
  projectListCollapsed,
  projectTodoDateFilter,
  projects,
  selectedClientId,
  selectedClientOffline,
  selectedProjectFile,
  selectedProjectBrowseRoot,
  selectedProjectPath,
  selectedWindowId,
  summaryOutputLanguage,
  terminalGroupingMode,
  terminalListLocateSignal,
  terminalProjects,
  terminalProjectsError,
  terminalTimeRange,
  treeError,
  treeFolders,
  unreadNotificationCount,
  updateFailed,
  updateMessage,
  updatingClientId,
  reregisteringClientId,
  workspaceMode,
  onCreateTerminalAtGroup,
  onConfigureTerminalAtGroup,
  onDeleteClient,
  onDeleteWindow,
  onEnterTerminal,
  onOpenAddClient,
  onOpenProjectDetail,
  onSelectClient,
  onSelectProject,
  onSelectProjectFile,
  onSelectWindow,
  onSetClientsCollapsed,
  onSetProjectListCollapsed,
  onSetProjectTodoDateFilter,
  onSetTerminalTimeRange,
  onToggleNotificationCenter,
  onTriggerNewTerminal,
  onUpdateClient,
  onReregisterClient,
  newTerminalShortcutLabel,
}: AppSidebarProps) {
  const { t } = useI18n();
  const [hasVisitedFilesMode, setHasVisitedFilesMode] = useState(workspaceMode === "files");

  useEffect(() => {
    if (workspaceMode === "files") {
      setHasVisitedFilesMode(true);
    }
  }, [workspaceMode]);

  const filesTreeMounted = hasVisitedFilesMode || workspaceMode === "files";
  const projectSidebarVisible = selectedClientId !== null && workspaceMode !== "terminal";
  const projectSidebarMounted = selectedClientId !== null && (projectSidebarVisible || filesTreeMounted);
  const selectedProjectPreference = projects.find((project) => project.path === selectedProjectPath)?.agent_preference ?? null;

  return (
    <aside className="sidebar">
      <div className="sidebar-header">
        <div className="sidebar-title-row">
          <h1>Web Terminal ACP</h1>
          <div className="notification-bell-anchor">
            <NotificationBellButton
              unreadCount={unreadNotificationCount}
              isOpen={notificationCenterOpen}
              onClick={onToggleNotificationCenter}
            />
          </div>
        </div>
      </div>
      {clientsLoading && <p className="muted">{t("sidebar.clients.loading")}</p>}
      {clientsError && <p className="error" role="alert">{t("sidebar.clients.loadFailed")}</p>}
      {clients && (
        <section
          className={clientsCollapsed ? "client-list collapsible-section collapsed" : "client-list collapsible-section"}
          aria-labelledby="client-list-heading"
          data-onboarding-id="client-list"
        >
          <div className="section-header">
            <button
              type="button"
              className="section-collapse-button"
              aria-expanded={!clientsCollapsed}
              onClick={() => onSetClientsCollapsed((collapsed) => !collapsed)}
            >
              <span aria-hidden="true">{clientsCollapsed ? "▸" : "▾"}</span>
              <h2 id="client-list-heading">{t("sidebar.clients.title")}</h2>
            </button>
            <button
              type="button"
              className="section-header-action"
              data-onboarding-id="add-client-button"
              disabled={addClientPending}
              onClick={() => onOpenAddClient("bootstrap")}
            >
              {t("sidebar.clients.add")}
            </button>
          </div>
          {!clientsCollapsed && (
            <ClientList
              clients={clients}
              selectedClientId={selectedClientId}
              updatingClientId={updatingClientId}
              reregisteringClientId={reregisteringClientId}
              deletingClientId={deleteClientId}
              onSelectClient={onSelectClient}
              onUpdateClient={onUpdateClient}
              onReregisterClient={onReregisterClient}
              onDeleteClient={onDeleteClient}
            />
          )}
        </section>
      )}
      {updateMessage && <p className="muted">{updateMessage}</p>}
      {updateFailed && <p className="error" role="alert">{t("sidebar.clients.updateFailed")}</p>}
      {deleteClientError && <p className="error" role="alert">{deleteClientErrorMessage}</p>}
      {selectedClientOffline && <p className="muted">{t("sidebar.clients.offline")}</p>}
      {createError && <p className="error" role="alert">{createErrorMessage}</p>}
      {cloneError && <p className="error" role="alert">{cloneErrorMessage}</p>}
      {deleteError && <p className="error" role="alert">{deleteErrorMessage}</p>}
      {generateTraceError && <p className="error" role="alert">{generateTraceErrorMessage}</p>}
      {selectedClientId !== null && terminalProjectsError && (
        <p className="error" role="alert">{t("sidebar.projects.loadFailed")}</p>
      )}
      {selectedClientId !== null && treeError && <p className="error" role="alert">{t("sidebar.tree.loadFailed")}</p>}
      {selectedClientId !== null && workspaceMode === "terminal" && (
        <FolderTree
          clientId={selectedClientId}
          folders={treeFolders ?? []}
          projects={terminalProjects}
          selectedProjectPath={selectedProjectPath}
          loadingProjects={loadingTerminalProjects}
          loadingSelectedProject={loadingSelectedProject}
          groupingMode={terminalGroupingMode}
          timeRange={terminalTimeRange}
          timeRangeOptions={TERMINAL_TIME_RANGE_OPTIONS}
          summaryOutputLanguage={summaryOutputLanguage}
          selectedWindowId={selectedWindowId}
          locateSelectedWindowSignal={terminalListLocateSignal}
          deletingWindowId={deletingWindowId}
          hasUnreadNotification={hasUnreadNotification}
          onOpenProjectDetail={onOpenProjectDetail}
          onSelectProject={onSelectProject}
          onSelectWindow={(window) => onSelectWindow(window.id)}
          onDeleteWindow={(window) => onDeleteWindow(window.id, window.title)}
          onTimeRangeChange={(range) => {
            if (isTerminalTimeRange(range)) {
              onSetTerminalTimeRange(range);
            }
          }}
          onCreateTerminalAtGroup={onCreateTerminalAtGroup}
          onConfigureTerminalAtGroup={onConfigureTerminalAtGroup}
          renderHeaderAction={() => (
            <button
              type="button"
              className="section-header-action"
              data-onboarding-id="new-terminal-button"
              title={newTerminalShortcutLabel}
              disabled={selectedClientId === null || createTerminalBusy || selectedClientOffline}
              onClick={onTriggerNewTerminal}
            >
              {t("sidebar.terminal.new")}
            </button>
          )}
          creatingTerminal={createTerminalBusy}
          createTerminalDisabled={selectedClientOffline}
        />
      )}
      {projectSidebarMounted && (
        <section
          className="project-file-mode-sidebar"
          aria-label={workspaceMode === "files" ? t("sidebar.projects.fileMode") : t("sidebar.projects.kanbanMode")}
          hidden={!projectSidebarVisible}
        >
          <div className="tree-header">
            <button
              type="button"
              className="section-collapse-button"
              aria-expanded={!projectListCollapsed}
              onClick={() => onSetProjectListCollapsed((collapsed) => !collapsed)}
            >
              <span aria-hidden="true">{projectListCollapsed ? "▸" : "▾"}</span>
              <h2>{t("sidebar.projects.title")}</h2>
            </button>
          </div>
          {!projectListCollapsed && (
            <div className="terminal-project-cards" aria-label={t("sidebar.projects.title")}>
              {projects.map((project) => {
                const isSelected = project.path === selectedProjectPath;
                const label = project.display_name?.trim() || projectFallbackLabel(project.path);
                return (
                  <ProjectCardRow
                    key={project.path}
                    count={project.window_count}
                    isSelected={isSelected}
                    label={label}
                    projectPath={project.path}
                    onOpenDetail={onOpenProjectDetail}
                    onSelectProject={onSelectProject}
                  />
                );
              })}
            </div>
          )}
          {!projectListCollapsed && workspaceMode === "kanban" && selectedProjectPath !== null && (
            <ProjectTodoSidebarControls
              clientId={selectedClientId}
              dateFilter={projectTodoDateFilter}
              projectPreference={selectedProjectPreference}
              projectPath={selectedProjectPath}
              onDateFilterChange={onSetProjectTodoDateFilter}
            />
          )}
          {filesTreeMounted && (
            <div className="project-file-tree-slot" hidden={workspaceMode !== "files"}>
              <ProjectFileTreePanel
                active={workspaceMode === "files"}
                browseRoot={selectedProjectBrowseRoot}
                clientId={selectedClientId}
                projectPath={selectedProjectPath}
                selectedPath={selectedProjectFile?.path ?? null}
                onSelectEntry={onSelectProjectFile}
              />
            </div>
          )}
        </section>
      )}
      <div className="mobile-enter-terminal">
        <button
          type="button"
          disabled={selectedClientId === null || selectedWindowId === null}
          onClick={onEnterTerminal}
        >
          {t("sidebar.mobile.enterTerminal")}
        </button>
      </div>
    </aside>
  );
}
