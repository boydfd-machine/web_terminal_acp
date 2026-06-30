import { useCallback } from "react";

import {
  canCreateWindowAtGroupNode,
  type SwitcherGroupNode,
  type SwitcherNode
} from "../terminalGrouping";
import { useI18n } from "../i18n";
import type { ProjectSummary, TerminalProject, TreeWindow } from "../types";
import { TerminalUnreadDot } from "./NotificationCenter";
import { WorkStatusDot } from "./WorkStatusBadge";

export function projectFallbackLabel(projectPath: string): string {
  const segments = projectPath.split("/").filter(Boolean);
  return segments[segments.length - 1] ?? projectPath;
}

export function ProjectCardList({
  projects,
  selectedProjectPath,
  projectSummaryLookup,
  loadingProjects,
  onSelectProject,
  onOpenProjectDetail
}: {
  projects: TerminalProject[];
  selectedProjectPath: string | null;
  projectSummaryLookup: Map<string, ProjectSummary>;
  loadingProjects?: boolean;
  onSelectProject: (projectPath: string) => void;
  onOpenProjectDetail: (projectPath: string) => void;
}) {
  const { t } = useI18n();

  if (loadingProjects && projects.length === 0) {
    return (
      <div className="terminal-project-loading" role="status" aria-live="polite">
        <span className="terminal-project-spinner" aria-hidden="true" />
        <span>{t("terminal.tree.loadingProjects")}</span>
      </div>
    );
  }

  if (projects.length === 0) {
    return <p className="muted terminal-project-empty">{t("terminal.tree.noProjectsInRange")}</p>;
  }

  return (
    <div className="terminal-project-cards" aria-label={t("terminal.switcher.projects")}>
      {projects.map((project) => {
        const isSelected = project.project_path === selectedProjectPath;
        const summary = projectSummaryLookup.get(project.project_path);
        const label = summary?.display_name?.trim() || projectFallbackLabel(project.project_path);

        return (
          <ProjectCardRow
            key={project.project_path}
            count={project.window_count}
            isSelected={isSelected}
            label={label}
            projectPath={project.project_path}
            onOpenDetail={onOpenProjectDetail}
            onSelectProject={onSelectProject}
          />
        );
      })}
    </div>
  );
}

export function ProjectCardRow({
  count,
  isSelected,
  label,
  projectPath,
  onOpenDetail,
  onSelectProject
}: {
  count: number;
  isSelected: boolean;
  label: string;
  projectPath: string;
  onOpenDetail: (projectPath: string) => void;
  onSelectProject: (projectPath: string) => void;
}) {
  const { t } = useI18n();

  return (
    <div className="terminal-project-card-row">
      <button
        type="button"
        aria-current={isSelected ? "true" : undefined}
        className={isSelected ? "terminal-project-card selected" : "terminal-project-card"}
        onClick={() => onSelectProject(projectPath)}
        title={projectPath}
      >
        <span className="terminal-project-card-main">
          <strong>{label}</strong>
          {label !== projectPath && (
            <span>{projectPath}</span>
          )}
        </span>
        <span className="terminal-project-card-count">{count}</span>
      </button>
      <button
        type="button"
        className="terminal-project-detail-button"
        aria-label={t("terminal.tree.openProjectDetails", { label })}
        title={t("terminal.tree.openProjectDetailsTitle", { path: projectPath })}
        onClick={() => onOpenDetail(projectPath)}
      >
        {t("terminal.tree.detail")}
      </button>
    </div>
  );
}

function WindowNode({
  window,
  selectedWindowId,
  locatingWindowId,
  registerWindowButton,
  deletingWindowId,
  hasUnreadNotification,
  onSelectWindow,
  onDeleteWindow
}: {
  window: TreeWindow;
  selectedWindowId: string | null;
  locatingWindowId: string | null;
  registerWindowButton: (windowId: string, element: HTMLButtonElement | null) => void;
  deletingWindowId?: string | null;
  hasUnreadNotification?: (windowId: string) => boolean;
  onSelectWindow: (window: TreeWindow) => void;
  onDeleteWindow: (window: TreeWindow) => void;
}) {
  const { t } = useI18n();
  const isSelected = window.id === selectedWindowId;
  const isLocating = window.id === locatingWindowId;
  const isDeleting = deletingWindowId === window.id;
  const showUnreadDot = hasUnreadNotification?.(window.id) ?? false;
  const handleWindowButtonRef = useCallback((element: HTMLButtonElement | null) => {
    registerWindowButton(window.id, element);
  }, [registerWindowButton, window.id]);

  return (
    <li className="tree-window-row">
      <button
        type="button"
        ref={handleWindowButtonRef}
        aria-current={isSelected ? "true" : undefined}
        className={[
          "tree-window",
          isSelected ? "selected" : "",
          isLocating ? "locating" : ""
        ].filter(Boolean).join(" ")}
        onClick={() => onSelectWindow(window)}
        title={`${window.work_status.label}: ${window.title}`}
      >
        <span className="tree-window-line">
          <WorkStatusDot status={window.work_status} />
          <span className="tree-window-title">{window.title}</span>
          <TerminalUnreadDot visible={showUnreadDot} />
        </span>
      </button>
      <button
        type="button"
        className="tree-window-delete"
        aria-label={t("terminal.tree.deleteWindow", { title: window.title })}
        disabled={isDeleting}
        onClick={(event) => {
          event.stopPropagation();
          onDeleteWindow(window);
        }}
      >
        ×
      </button>
    </li>
  );
}

export function DisplayTreeNode({
  node,
  collapsedKeys,
  selectedPathKeys,
  selectedWindowId,
  locatingWindowId,
  registerWindowButton,
  deletingWindowId,
  summarizingProjectPath,
  hasUnreadNotification,
  onSelectWindow,
  onDeleteWindow,
  onToggleGroup,
  onSummarizeProject,
  onCreateTerminalAtGroup,
  onConfigureTerminalAtGroup,
  creatingTerminal,
  createTerminalDisabled
}: {
  node: SwitcherNode;
  collapsedKeys: Set<string>;
  selectedPathKeys: Set<string>;
  selectedWindowId: string | null;
  locatingWindowId: string | null;
  registerWindowButton: (windowId: string, element: HTMLButtonElement | null) => void;
  deletingWindowId?: string | null;
  summarizingProjectPath: string | null;
  hasUnreadNotification?: (windowId: string) => boolean;
  onSelectWindow: (window: TreeWindow) => void;
  onDeleteWindow: (window: TreeWindow) => void;
  onToggleGroup: (key: string) => void;
  onSummarizeProject?: (projectPath: string) => void;
  onCreateTerminalAtGroup?: (node: SwitcherGroupNode) => void;
  onConfigureTerminalAtGroup?: (node: SwitcherGroupNode) => void;
  creatingTerminal?: boolean;
  createTerminalDisabled?: boolean;
}) {
  const { t } = useI18n();

  if (node.type === "window") {
    return (
      <WindowNode
        window={node.window}
        selectedWindowId={selectedWindowId}
        locatingWindowId={locatingWindowId}
        registerWindowButton={registerWindowButton}
        deletingWindowId={deletingWindowId}
        hasUnreadNotification={hasUnreadNotification}
        onSelectWindow={onSelectWindow}
        onDeleteWindow={onDeleteWindow}
      />
    );
  }

  const isExpanded = selectedPathKeys.has(node.key) || !collapsedKeys.has(node.key);
  const showSummarize = node.projectPath !== undefined && !node.topicPath && onSummarizeProject !== undefined;
  const isSummarizing = showSummarize && summarizingProjectPath === node.projectPath;
  const showCreateTerminal = onCreateTerminalAtGroup !== undefined && canCreateWindowAtGroupNode(node);
  const createLabel = node.projectPath ?? node.label;

  return (
    <li className="folder-node">
      <div className="switcher-folder-row tree-folder-row">
        <button
          type="button"
          className="folder-label-button"
          aria-expanded={isExpanded}
          onClick={() => onToggleGroup(node.key)}
          title={node.projectPath ?? node.topicPath ?? node.label}
        >
          <span className="disclosure" aria-hidden="true">{isExpanded ? "▾" : "▸"}</span>
          <span>{node.label}</span>
          <span className="count">{node.count}</span>
        </button>
        {showSummarize && (
          <button
            type="button"
            className="switcher-summarize-button tree-summarize-button"
            disabled={isSummarizing}
            aria-label={t("terminal.switcher.summarizeProject", { label: node.label })}
            title={t("terminal.switcher.summarizeTitle")}
            onClick={(event) => {
              event.stopPropagation();
              onSummarizeProject(node.projectPath as string);
            }}
          >
            {isSummarizing ? "…" : t("terminal.switcher.summarize")}
          </button>
        )}
        {showCreateTerminal && (
          <button
            type="button"
            className="switcher-create-terminal-button tree-create-terminal-button"
            disabled={creatingTerminal || createTerminalDisabled}
            aria-label={t("terminal.switcher.createAt", { label: createLabel })}
            title={t("terminal.switcher.createAt", { label: createLabel })}
            onClick={(event) => {
              event.stopPropagation();
              onCreateTerminalAtGroup(node);
            }}
          >
            +
          </button>
        )}
        {showCreateTerminal && onConfigureTerminalAtGroup && (
          <button
            type="button"
            className="switcher-configure-terminal-button tree-configure-terminal-button"
            disabled={creatingTerminal || createTerminalDisabled}
            aria-label={t("terminal.switcher.configureAt", { label: createLabel })}
            title={t("terminal.switcher.configureAt", { label: createLabel })}
            onClick={(event) => {
              event.stopPropagation();
              onConfigureTerminalAtGroup(node);
            }}
          >
            {t("terminal.switcher.configure")}
          </button>
        )}
      </div>
      {isExpanded && (
        <ul>
          {node.children.map((child) => (
            <DisplayTreeNode
              key={child.key}
              node={child}
              collapsedKeys={collapsedKeys}
              selectedPathKeys={selectedPathKeys}
              selectedWindowId={selectedWindowId}
              locatingWindowId={locatingWindowId}
              registerWindowButton={registerWindowButton}
              deletingWindowId={deletingWindowId}
              summarizingProjectPath={summarizingProjectPath}
              hasUnreadNotification={hasUnreadNotification}
              onSelectWindow={onSelectWindow}
              onDeleteWindow={onDeleteWindow}
              onToggleGroup={onToggleGroup}
              onSummarizeProject={onSummarizeProject}
              onCreateTerminalAtGroup={onCreateTerminalAtGroup}
              onConfigureTerminalAtGroup={onConfigureTerminalAtGroup}
              creatingTerminal={creatingTerminal}
              createTerminalDisabled={createTerminalDisabled}
            />
          ))}
        </ul>
      )}
    </li>
  );
}
