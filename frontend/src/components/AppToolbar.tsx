import { useState, type RefObject } from "react";
import { useQuery } from "@tanstack/react-query";

import { fetchProjectFileContent } from "../api";
import { isBinaryPreviewError } from "./projectFilesUtils";
import type { KeyboardShortcutBindings } from "../keyboardShortcuts";
import { effectiveKeyboardShortcut, keyboardShortcutLabel } from "../keyboardShortcuts";
import type { TerminalViewportMode, WorkspaceMode } from "../appState";
import { useI18n } from "../i18n";
import type { ProjectBrowseRootOption } from "../projectBrowseRoots";
import type { ProjectFileEntry } from "../types";
import { GlobalSearchModal } from "./GlobalSearchModal";
import { ProjectBrowseRootSelector } from "./ProjectBrowseRootSelector";
import { UiIcon } from "./UiIcon";

export type AppToolbarProps = {
  auxTerminalOpen: boolean;
  auxTerminalShortcutLabel: string;
  cloneTerminalShortcutLabel: string;
  deletePending: boolean;
  detailPanelCollapsed: boolean;
  generateTracePending: boolean;
  gitDiffShortcutLabel: string;
  keyboardShortcutBindings: KeyboardShortcutBindings;
  quickInputShortcutLabel: string;
  projectBrowseRootOptions: ProjectBrowseRootOption[];
  projectFilePreviewMode: "edit" | "preview";
  relatedTerminalShortcutLabel: string;
  selectedClientId: string | null;
  selectedClientOffline: boolean;
  selectedProjectBrowseRoot: string | null;
  selectedProjectFile: ProjectFileEntry | null;
  selectedProjectPath: string | null;
  selectedWindowId: string | null;
  settingsShortcutLabel: string;
  terminalCloneBusy: boolean;
  terminalControlsOpen: boolean;
  terminalControlsRef: RefObject<HTMLDivElement>;
  terminalCreateBusy: boolean;
  terminalQuickInputOpen: boolean;
  terminalViewportMode: TerminalViewportMode;
  toolbarSubtitle: string;
  toolbarTitle: string;
  virtualKeysVisible: boolean;
  workspaceMode: WorkspaceMode;
  workspaceModeShortcutLabel: string;
  onConfirmDeleteTerminal: () => void;
  onGenerateTrace: () => void;
  onSetDetailPanelCollapsed: (collapsed: boolean) => void;
  onSetDetailPanelOpen: (open: boolean) => void;
  onSetMobileTerminalActive: (active: boolean) => void;
  onSetSettingsOpen: (open: boolean) => void;
  onSetTerminalControlsOpen: (open: boolean | ((open: boolean) => boolean)) => void;
  onSetTerminalImmersive: (open: boolean) => void;
  onSetTerminalSwitcherOpen: (open: boolean) => void;
  onSetTerminalViewportMode: (mode: TerminalViewportMode) => void;
  onSelectProjectBrowseRoot: (option: ProjectBrowseRootOption) => void;
  onSelectWorkspaceMode: (mode: WorkspaceMode) => void;
  onSetProjectFilePreviewMode: (mode: "edit" | "preview") => void;
  onFocusProjectTodo: (projectPath: string, todoId: string) => void;
  onOpenProjectTodoBoard: () => void;
  onSelectGlobalSearchWindow: (windowId: string, clientId?: string | null) => void;
  onToggleAuxTerminal: () => void;
  onToggleVirtualKeysVisibility: () => void;
  onToggleWorkspaceMode: () => void;
  onTriggerAgentRecordExpand: () => void;
  onTriggerCloneTerminal: () => void;
  onTriggerGitDiffBrowser: () => void;
  onTriggerQuickInput: () => void;
  onTriggerRelatedTerminalSwitch: () => void;
};

export function AppToolbar({
  auxTerminalOpen,
  auxTerminalShortcutLabel,
  cloneTerminalShortcutLabel,
  deletePending,
  detailPanelCollapsed,
  generateTracePending,
  gitDiffShortcutLabel,
  keyboardShortcutBindings,
  quickInputShortcutLabel,
  projectBrowseRootOptions,
  projectFilePreviewMode,
  relatedTerminalShortcutLabel,
  selectedClientId,
  selectedClientOffline,
  selectedProjectBrowseRoot,
  selectedProjectFile,
  selectedProjectPath,
  selectedWindowId,
  settingsShortcutLabel,
  terminalCloneBusy,
  terminalControlsOpen,
  terminalControlsRef,
  terminalCreateBusy,
  terminalQuickInputOpen,
  terminalViewportMode,
  toolbarSubtitle,
  toolbarTitle,
  virtualKeysVisible,
  workspaceMode,
  workspaceModeShortcutLabel,
  onConfirmDeleteTerminal,
  onGenerateTrace,
  onSetDetailPanelCollapsed,
  onSetDetailPanelOpen,
  onSetMobileTerminalActive,
  onSetSettingsOpen,
  onSetTerminalControlsOpen,
  onSetTerminalImmersive,
  onSetTerminalSwitcherOpen,
  onSetTerminalViewportMode,
  onSelectProjectBrowseRoot,
  onSelectWorkspaceMode,
  onSetProjectFilePreviewMode,
  onFocusProjectTodo,
  onOpenProjectTodoBoard,
  onSelectGlobalSearchWindow,
  onToggleAuxTerminal,
  onToggleVirtualKeysVisibility,
  onToggleWorkspaceMode,
  onTriggerAgentRecordExpand,
  onTriggerCloneTerminal,
  onTriggerGitDiffBrowser,
  onTriggerQuickInput,
  onTriggerRelatedTerminalSwitch,
}: AppToolbarProps) {
  const { t } = useI18n();
  const [globalSearchOpen, setGlobalSearchOpen] = useState(false);
  const terminalSelected = selectedClientId !== null && selectedWindowId !== null;
  const filesAvailable = selectedClientId !== null
    && (selectedProjectPath !== null || projectBrowseRootOptions.length > 0);
  const kanbanAvailable = selectedClientId !== null
    && (selectedProjectPath !== null || selectedWindowId !== null);
  const previewFileQuery = useQuery({
    queryKey: [
      "project-file-content",
      selectedClientId,
      selectedProjectPath,
      selectedProjectBrowseRoot ?? null,
      selectedProjectFile?.kind === "file" ? selectedProjectFile.path : null
    ],
    queryFn: () => fetchProjectFileContent(
      selectedClientId as string,
      selectedProjectPath as string,
      (selectedProjectFile as { path: string }).path,
      selectedProjectBrowseRoot
    ),
    enabled: workspaceMode === "files"
      && selectedClientId !== null
      && selectedProjectPath !== null
      && selectedProjectFile?.kind === "file",
    meta: { suppressApiErrorToast: true },
    retry: (failureCount, error) => !isBinaryPreviewError(error) && failureCount < 2,
    staleTime: 10000
  });
  const previewFileCanEdit = previewFileQuery.data !== undefined && !previewFileQuery.data.truncated;
  const previewFileModeVisible = workspaceMode === "files"
    && selectedClientId !== null
    && selectedProjectFile?.kind === "file";
  return (
    <div className="toolbar terminal-toolbar" data-debug-id="app-toolbar" aria-live="polite">
      <button type="button" className="mobile-back-button" onClick={() => onSetMobileTerminalActive(false)}>
        {t("toolbar.mobileBack")}
      </button>
      <div className="workspace-mode-toggle" role="group" aria-label={t("toolbar.workspaceMode")}>
        <button
          type="button"
          aria-pressed={workspaceMode === "terminal"}
          className={workspaceMode === "terminal" ? "active" : ""}
          disabled={selectedClientId === null}
          onClick={() => {
            if (workspaceMode !== "terminal") {
              onSelectWorkspaceMode("terminal");
            }
          }}
          title={workspaceModeShortcutLabel}
        >
          {t("toolbar.workspace.terminal")}
        </button>
        <button
          type="button"
          aria-pressed={workspaceMode === "files"}
          className={workspaceMode === "files" ? "active" : ""}
          disabled={!filesAvailable}
          onClick={() => {
            if (workspaceMode !== "files") {
              onSelectWorkspaceMode("files");
            }
          }}
          title={workspaceModeShortcutLabel}
        >
          {t("toolbar.workspace.files")}
        </button>
        <button
          type="button"
          aria-pressed={workspaceMode === "kanban"}
          className={workspaceMode === "kanban" ? "active" : ""}
          disabled={!kanbanAvailable}
          onClick={() => {
            onOpenProjectTodoBoard();
          }}
          title={keyboardShortcutLabel(effectiveKeyboardShortcut("open-project-todo-board", keyboardShortcutBindings))}
        >
          {t("toolbar.workspace.kanban")}
        </button>
      </div>
      {workspaceMode === "files" && (
        <ProjectBrowseRootSelector
          options={projectBrowseRootOptions}
          selectedBrowseRoot={selectedProjectBrowseRoot}
          selectedProjectPath={selectedProjectPath}
          onSelect={onSelectProjectBrowseRoot}
        />
      )}
      {previewFileModeVisible && (
        <div
          className="toolbar-file-preview-mode workspace-mode-toggle"
          role="group"
          aria-label={t("projectFiles.mode")}
        >
          <button
            type="button"
            aria-pressed={projectFilePreviewMode === "preview"}
            className={projectFilePreviewMode === "preview" ? "active" : ""}
            onClick={() => onSetProjectFilePreviewMode("preview")}
          >
            {t("projectFiles.preview")}
          </button>
          <button
            type="button"
            aria-pressed={projectFilePreviewMode === "edit"}
            className={projectFilePreviewMode === "edit" ? "active" : ""}
            disabled={!previewFileCanEdit}
            onClick={() => onSetProjectFilePreviewMode("edit")}
          >
            {t("projectFiles.edit")}
          </button>
        </div>
      )}
      <div className="terminal-toolbar-title">
        <strong title={toolbarTitle}>{toolbarTitle}</strong>
        <span>{toolbarSubtitle}</span>
      </div>
      <div className="terminal-actions" ref={terminalControlsRef}>
        {detailPanelCollapsed && (
          <button
            type="button"
            className="terminal-toolbar-action terminal-toolbar-detail-restore"
            onClick={() => {
              onSetDetailPanelCollapsed(false);
              onSetDetailPanelOpen(true);
            }}
          >
            {t("toolbar.details")}
          </button>
        )}
        <button
          type="button"
          className="terminal-toolbar-action terminal-toolbar-global-search ui-icon-button"
          disabled={selectedClientId === null}
          onClick={() => setGlobalSearchOpen(true)}
          aria-label={t("toolbar.globalSearch")}
          title={t("toolbar.globalSearch")}
        >
          <UiIcon name="search" />
        </button>
        <button
          type="button"
          className="terminal-toolbar-action terminal-toolbar-agent-preview mobile-agent-preview-button"
          disabled={workspaceMode !== "terminal" || !terminalSelected}
          onClick={onTriggerAgentRecordExpand}
        >
          {t("toolbar.agentPreview")}
        </button>
        <button
          type="button"
          className="terminal-toolbar-action terminal-toolbar-generate-trace"
          disabled={workspaceMode !== "terminal" || !terminalSelected || generateTracePending}
          onClick={onGenerateTrace}
        >
          {generateTracePending ? t("toolbar.generating") : t("toolbar.generateTrace")}
        </button>
        <button
          type="button"
          className="terminal-toolbar-action terminal-toolbar-aux-terminal"
          disabled={workspaceMode !== "terminal" || !terminalSelected}
          onClick={onToggleAuxTerminal}
        >
          {t("toolbar.auxTerminal")}
        </button>
        <button
          type="button"
          className="terminal-toolbar-action terminal-toolbar-quick-input"
          disabled={workspaceMode !== "terminal" || !terminalSelected}
          onClick={onTriggerQuickInput}
        >
          {t("toolbar.quickInput")}
        </button>
        <button
          type="button"
          className="terminal-menu-button"
          aria-expanded={terminalControlsOpen}
          aria-haspopup="menu"
          onClick={() => onSetTerminalControlsOpen((isOpen) => !isOpen)}
        >
          {t("toolbar.controls")}
        </button>
        {terminalControlsOpen && (
          <div className="terminal-controls-menu" role="menu" data-onboarding-id="terminal-controls-menu">
            <TerminalViewportControls
              terminalViewportMode={terminalViewportMode}
              onSetTerminalViewportMode={onSetTerminalViewportMode}
            />
            <button type="button" role="menuitem" className="terminal-controls-row" onClick={onToggleVirtualKeysVisibility}>
              <span>{t("toolbar.virtualKeys")}</span>
              <strong>{virtualKeysVisible ? t("toolbar.on") : t("toolbar.off")}</strong>
            </button>
            <button
              type="button"
              role="menuitem"
              className="terminal-controls-row"
              disabled={!terminalSelected}
              onClick={() => {
                onTriggerAgentRecordExpand();
                onSetTerminalControlsOpen(false);
              }}
            >
              <span>{t("toolbar.agentPreview")}</span>
              <strong>{keyboardShortcutLabel(effectiveKeyboardShortcut("expand-record", keyboardShortcutBindings))}</strong>
            </button>
            <button
              type="button"
              role="menuitem"
              className="terminal-controls-row"
              disabled={!terminalSelected || generateTracePending}
              onClick={() => {
                onGenerateTrace();
                onSetTerminalControlsOpen(false);
              }}
            >
              <span>{t("toolbar.generateTraceMenu")}</span>
              <strong>{generateTracePending ? t("toolbar.running") : t("toolbar.artifact")}</strong>
            </button>
            <button
              type="button"
              role="menuitem"
              className="terminal-controls-row"
              disabled={!terminalSelected}
              onClick={() => {
                onTriggerRelatedTerminalSwitch();
                onSetTerminalControlsOpen(false);
              }}
            >
              <span>{t("toolbar.relatedTerminals")}</span>
              <strong>{relatedTerminalShortcutLabel}</strong>
            </button>
            <button
              type="button"
              role="menuitem"
              className="terminal-controls-row"
              disabled={!terminalSelected || terminalCreateBusy || terminalCloneBusy || selectedClientOffline}
              onClick={onTriggerCloneTerminal}
            >
              <span>{t("toolbar.cloneTerminal")}</span>
              <strong>{terminalCloneBusy ? t("toolbar.cloning") : cloneTerminalShortcutLabel}</strong>
            </button>
            <button
              type="button"
              role="menuitem"
              className="terminal-controls-row"
              disabled={!terminalSelected}
              onClick={() => {
                onTriggerQuickInput();
                onSetTerminalControlsOpen(false);
              }}
            >
              <span>{t("toolbar.quickInput")}</span>
              <strong>{terminalQuickInputOpen ? t("toolbar.open") : quickInputShortcutLabel}</strong>
            </button>
            <button
              type="button"
              role="menuitem"
              className="terminal-controls-row"
              disabled={!terminalSelected}
              onClick={onToggleAuxTerminal}
            >
              <span>{t("toolbar.auxTerminal")}</span>
              <strong>{auxTerminalOpen ? t("toolbar.open") : auxTerminalShortcutLabel}</strong>
            </button>
            <button
              type="button"
              role="menuitem"
              className="terminal-controls-row"
              disabled={!terminalSelected}
              onClick={() => {
                onSetTerminalImmersive(true);
                onSetDetailPanelOpen(false);
                onSetTerminalControlsOpen(false);
                onSetTerminalSwitcherOpen(false);
              }}
            >
              <span>{t("toolbar.immersiveMode")}</span>
            </button>
            <button
              type="button"
              role="menuitem"
              className="terminal-controls-row"
              disabled={!terminalSelected}
              onClick={() => {
                onTriggerGitDiffBrowser();
                onSetTerminalControlsOpen(false);
              }}
            >
              <span>{t("toolbar.gitDiff")}</span>
              <strong>{gitDiffShortcutLabel}</strong>
            </button>
            <button
              type="button"
              role="menuitem"
              className="terminal-controls-row"
              disabled={workspaceMode === "terminal" && !filesAvailable}
              onClick={() => {
                onToggleWorkspaceMode();
                onSetTerminalControlsOpen(false);
              }}
            >
              <span>{workspaceMode === "terminal" ? t("toolbar.filesMode") : t("toolbar.terminalMode")}</span>
              <strong>{workspaceModeShortcutLabel}</strong>
            </button>
            <button
              type="button"
              role="menuitem"
              className="terminal-controls-row"
              disabled={selectedClientId === null || (selectedProjectPath === null && selectedWindowId === null)}
              onClick={() => {
                onOpenProjectTodoBoard();
                onSetTerminalControlsOpen(false);
              }}
            >
              <span>{t("toolbar.workspace.kanban")}</span>
              <strong>{keyboardShortcutLabel(effectiveKeyboardShortcut("open-project-todo-board", keyboardShortcutBindings))}</strong>
            </button>
            <button
              type="button"
              role="menuitem"
              className="terminal-controls-row"
              onClick={() => {
                onSetSettingsOpen(true);
                onSetTerminalControlsOpen(false);
              }}
            >
              <span>{t("app.settings")}</span>
              <strong>{settingsShortcutLabel}</strong>
            </button>
            <button
              type="button"
              role="menuitem"
              className="terminal-controls-row"
              onClick={() => {
                onSetDetailPanelCollapsed(false);
                onSetDetailPanelOpen(true);
                onSetTerminalControlsOpen(false);
              }}
            >
              <span>{t("toolbar.details")}</span>
            </button>
            <button
              type="button"
              role="menuitem"
              className="terminal-controls-row terminal-controls-row-danger"
              disabled={!terminalSelected || deletePending}
              onClick={onConfirmDeleteTerminal}
            >
              <span>{t("toolbar.deleteTerminal")}</span>
            </button>
          </div>
        )}
      </div>
      <GlobalSearchModal
        clientId={selectedClientId}
        open={globalSearchOpen}
        onClose={() => setGlobalSearchOpen(false)}
        onFocusProjectTodo={onFocusProjectTodo}
        onSelectWindow={onSelectGlobalSearchWindow}
      />
    </div>
  );
}

function TerminalViewportControls({
  terminalViewportMode,
  onSetTerminalViewportMode,
}: {
  terminalViewportMode: TerminalViewportMode;
  onSetTerminalViewportMode: (mode: TerminalViewportMode) => void;
}) {
  const { t } = useI18n();

  return (
    <div className="terminal-controls-section">
      <span>{t("toolbar.view")}</span>
      <div className="terminal-mode-toggle" role="group" aria-label={t("toolbar.viewportMode")}>
        {(["desktop", "phone", "fixed"] as const).map((mode) => (
          <button
            key={mode}
            type="button"
            aria-pressed={terminalViewportMode === mode}
            className={terminalViewportMode === mode ? "active" : ""}
            onClick={() => onSetTerminalViewportMode(mode)}
          >
            {mode === "desktop" ? t("toolbar.viewport.desktop") : mode === "phone" ? t("toolbar.viewport.phone") : "1920x1080"}
          </button>
        ))}
      </div>
    </div>
  );
}
