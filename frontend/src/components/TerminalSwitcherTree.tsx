import { canCreateWindowAtGroupNode, type SwitcherGroupNode, type SwitcherNode } from "../terminalGrouping";
import { useI18n } from "../i18n";
import type { ProjectSummary } from "../types";
import { TerminalUnreadDot } from "./NotificationCenter";
import { SwitcherWindowTitle } from "./SwitcherWindowTitle";
import { WorkStatusDot } from "./WorkStatusBadge";
import { terminalMeta, type TerminalEntry, type TerminalMeta } from "./terminalSwitcherData";

export function TerminalWindowMeta({ meta }: { meta: TerminalMeta }) {
  const { t } = useI18n();

  return (
    <span className="switcher-window-meta" aria-label={t("terminal.switcher.metadata")}>
      <span className="switcher-window-tag agent" title={t("terminal.switcher.agentTitle", { agent: meta.agentLabel })}>{meta.agentLabel}</span>
      <time className="switcher-window-meta-text switcher-window-meta-time" dateTime={meta.timeValue} title={t("terminal.switcher.createdTitle", { time: meta.timeTitle })}>
        {meta.timeLabel}
      </time>
      {meta.projectLabel !== null && (
        <span className="switcher-window-meta-text switcher-window-meta-project" title={meta.projectPath ?? meta.projectLabel}>
          {meta.projectLabel}
        </span>
      )}
    </span>
  );
}

export function SwitcherTreeNode({
  node,
  activeKey,
  expandedKeys,
  selectedWindowId,
  projectSummaryLookup,
  summarizingProjectPath,
  hasUnreadNotification,
  onSelectEntry,
  onToggleGroup,
  onSummarizeProject,
  onCreateTerminalAtGroup,
  onConfigureTerminalAtGroup,
  creatingTerminal,
  createTerminalDisabled
}: {
  node: SwitcherNode;
  activeKey: string | null;
  expandedKeys: Set<string>;
  selectedWindowId: string | null;
  projectSummaryLookup: Map<string, ProjectSummary>;
  summarizingProjectPath: string | null;
  hasUnreadNotification?: (windowId: string) => boolean;
  onSelectEntry: (entry: TerminalEntry) => void;
  onToggleGroup: (key: string) => void;
  onSummarizeProject?: (projectPath: string) => void;
  onCreateTerminalAtGroup?: (node: SwitcherGroupNode) => void;
  onConfigureTerminalAtGroup?: (node: SwitcherGroupNode) => void;
  creatingTerminal?: boolean;
  createTerminalDisabled?: boolean;
}) {
  const { t } = useI18n();

  if (node.type === "window") {
    const isActive = node.key === activeKey;
    const isSelected = node.window.id === selectedWindowId;
    const showUnreadDot = hasUnreadNotification?.(node.window.id) ?? false;
    const meta = terminalMeta(node.window, projectSummaryLookup, t);

    return (
      <li>
        <button
          type="button"
          aria-current={isSelected ? "true" : undefined}
          aria-selected={isActive}
          className={isActive ? "switcher-window with-meta active" : "switcher-window with-meta"}
          onClick={() => onSelectEntry({ window: node.window, topicPath: node.topicPath })}
          role="treeitem"
          title={`${node.window.work_status.label}: ${node.window.title}`}
        >
          <WorkStatusDot status={node.window.work_status} />
          <SwitcherWindowTitle active={isActive} title={node.window.title} todoTitle={node.window.todo_title} />
          <TerminalWindowMeta meta={meta} />
          <TerminalUnreadDot visible={showUnreadDot} />
        </button>
      </li>
    );
  }

  const isExpanded = expandedKeys.has(node.key);
  const isActive = node.key === activeKey;
  const showSummarize = node.projectPath !== undefined && !node.topicPath && onSummarizeProject !== undefined;
  const isSummarizing = showSummarize && summarizingProjectPath === node.projectPath;
  const showCreateTerminal = onCreateTerminalAtGroup !== undefined && canCreateWindowAtGroupNode(node);
  const createLabel = node.projectPath ?? node.label;

  return (
    <li className="switcher-folder-node" role="none">
      <div className="switcher-folder-row">
        <button
          type="button"
          className={isActive ? "switcher-folder-button active" : "switcher-folder-button"}
          aria-selected={isActive}
          aria-expanded={isExpanded}
          onClick={() => onToggleGroup(node.key)}
          role="treeitem"
          title={node.projectPath ?? node.topicPath ?? node.label}
        >
          <span className="disclosure" aria-hidden="true">{isExpanded ? "▾" : "▸"}</span>
          <span>{node.label}</span>
          <span className="count">{node.count}</span>
        </button>
        {showSummarize && (
          <button
            type="button"
            className="switcher-summarize-button"
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
            className="switcher-create-terminal-button"
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
            className="switcher-configure-terminal-button"
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
        <ul role="group">
          {node.children.map((child) => (
            <SwitcherTreeNode
              key={child.key}
              node={child}
              activeKey={activeKey}
              expandedKeys={expandedKeys}
              selectedWindowId={selectedWindowId}
              projectSummaryLookup={projectSummaryLookup}
              summarizingProjectPath={summarizingProjectPath}
              hasUnreadNotification={hasUnreadNotification}
              onSelectEntry={onSelectEntry}
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
