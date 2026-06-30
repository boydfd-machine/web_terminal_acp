import type { SwitcherGroupNode, SwitcherNode } from "../terminalGrouping";
import { terminalGroupingModeHasProjectRoot } from "../terminalGrouping";
import { useI18n } from "../i18n";
import type { TerminalGroupingMode } from "../userPreferences";
import type { ProjectSummary } from "../types";
import { SwitcherTreeNode } from "./TerminalSwitcherTree";
import type { TerminalEntry } from "./terminalSwitcherData";

type TerminalSwitcherTreeListProps = {
  activeKey: string | null;
  clientId: string | null;
  createTerminalDisabled?: boolean;
  creatingTerminal?: boolean;
  entriesLength: number;
  expandedKeys: Set<string>;
  hasUnreadNotification?: (windowId: string) => boolean;
  projectSummaryLookup: Map<string, ProjectSummary>;
  selectedWindowId: string | null;
  summarizingProjectPath: string | null;
  terminalGroupingMode: TerminalGroupingMode;
  treeNodes: SwitcherNode[];
  onConfigureTerminalAtGroup?: (node: SwitcherGroupNode) => void;
  onCreateTerminalAtGroup?: (node: SwitcherGroupNode) => void;
  onSelectEntry: (entry: TerminalEntry) => void;
  onSummarizeProject: (projectPath: string) => void;
  onToggleGroup: (key: string) => void;
};

export function TerminalSwitcherTreeList({
  activeKey,
  clientId,
  createTerminalDisabled,
  creatingTerminal,
  entriesLength,
  expandedKeys,
  hasUnreadNotification,
  projectSummaryLookup,
  selectedWindowId,
  summarizingProjectPath,
  terminalGroupingMode,
  treeNodes,
  onConfigureTerminalAtGroup,
  onCreateTerminalAtGroup,
  onSelectEntry,
  onSummarizeProject,
  onToggleGroup
}: TerminalSwitcherTreeListProps) {
  const { t } = useI18n();

  if (clientId === null || entriesLength === 0) {
    return null;
  }
  if (treeNodes.length === 0) {
    return <p className="terminal-switcher-empty">{t("terminal.switcher.noMatching")}</p>;
  }
  return (
    <ul className="terminal-switcher-results switcher-topic-tree" role="tree">
      {treeNodes.map((node) => (
        <SwitcherTreeNode
          key={node.key}
          node={node}
          activeKey={activeKey}
          expandedKeys={expandedKeys}
          selectedWindowId={selectedWindowId}
          projectSummaryLookup={projectSummaryLookup}
          summarizingProjectPath={summarizingProjectPath}
          hasUnreadNotification={hasUnreadNotification}
          onSelectEntry={onSelectEntry}
          onToggleGroup={onToggleGroup}
          onSummarizeProject={
            terminalGroupingModeHasProjectRoot(terminalGroupingMode) && clientId !== null
              ? onSummarizeProject
              : undefined
          }
          onCreateTerminalAtGroup={onCreateTerminalAtGroup}
          onConfigureTerminalAtGroup={onConfigureTerminalAtGroup}
          creatingTerminal={creatingTerminal}
          createTerminalDisabled={createTerminalDisabled}
        />
      ))}
    </ul>
  );
}
