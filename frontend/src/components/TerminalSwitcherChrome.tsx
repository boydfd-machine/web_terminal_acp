import type { Dispatch, SetStateAction } from "react";

import type { TerminalGroupingMode } from "../userPreferences";
import { useI18n } from "../i18n";
import { UiIcon } from "./UiIcon";
import { RECENT_PROJECT_ALL_KEY, terminalGroupingDescription, type RecentProjectTab } from "./terminalSwitcherData";

type TerminalSwitcherChromeProps = {
  activeRecentProjectKey: string;
  isGlobalRecentMode: boolean;
  isRecentMode: boolean;
  isRelatedRecentMode: boolean;
  query: string;
  recentProjectTabs: RecentProjectTab[];
  showRecentProjectTabs: boolean;
  switchShortcutLabel: string;
  terminalGroupingMode: TerminalGroupingMode;
  onClose: () => void;
  setActiveKey: Dispatch<SetStateAction<string | null>>;
  setActiveRecentProjectKey: Dispatch<SetStateAction<string>>;
  setExpandedKeys: Dispatch<SetStateAction<Set<string>>>;
  setQuery: Dispatch<SetStateAction<string>>;
};

export function TerminalSwitcherChrome({
  activeRecentProjectKey,
  isGlobalRecentMode,
  isRecentMode,
  isRelatedRecentMode,
  query,
  recentProjectTabs,
  showRecentProjectTabs,
  switchShortcutLabel,
  terminalGroupingMode,
  onClose,
  setActiveKey,
  setActiveRecentProjectKey,
  setExpandedKeys,
  setQuery
}: TerminalSwitcherChromeProps) {
  const { t } = useI18n();
  const description = terminalGroupingDescription(terminalGroupingMode, t);
  const recentScope = isGlobalRecentMode ? t("terminal.switcher.globalRecent") : t("terminal.switcher.clientRecent");

  return (
    <>
      <div className="terminal-switcher-header">
        <div>
          <h2>{isRelatedRecentMode ? t("terminal.switcher.relatedTitle") : t("terminal.switcher.title")}</h2>
          <p className="muted">
            {isRelatedRecentMode
              ? t("terminal.switcher.relatedHint", { shortcut: switchShortcutLabel })
              : isRecentMode
              ? t("terminal.switcher.recentHint", { scope: recentScope, shortcut: switchShortcutLabel })
              : t("terminal.switcher.treeHint", { description, shortcut: switchShortcutLabel })}
          </p>
        </div>
        <button
          type="button"
          className="ui-icon-button"
          aria-label={t("terminal.switcher.close")}
          title={t("terminal.switcher.close")}
          onClick={onClose}
        >
          <UiIcon name="x" />
        </button>
      </div>
      {showRecentProjectTabs && recentProjectTabs.length > 1 && (
        <div className="terminal-switcher-project-tabs" role="tablist" aria-label={t("terminal.switcher.projects")}>
          {recentProjectTabs.map((tab) => {
            const isActive = tab.key === activeRecentProjectKey;
            const title = tab.key === RECENT_PROJECT_ALL_KEY ? t("terminal.switcher.allProjects") : tab.projectPath ?? t("terminal.switcher.noProject");
            return (
              <button
                key={tab.key}
                type="button"
                className={isActive ? "active" : undefined}
                role="tab"
                aria-selected={isActive}
                title={title}
                onClick={() => {
                  setActiveRecentProjectKey(tab.key);
                  setActiveKey(null);
                }}
              >
                <span>{tab.label}</span>
                <span className="terminal-switcher-project-count">{tab.count}</span>
              </button>
            );
          })}
        </div>
      )}
      <input
        aria-label={t("terminal.switcher.search")}
        value={query}
        onChange={(event) => {
          const nextQuery = event.target.value;
          setQuery(nextQuery);
          if (nextQuery.trim().length === 0) {
            setExpandedKeys(new Set());
          }
        }}
        placeholder={isRelatedRecentMode ? t("terminal.switcher.searchRelated") : isRecentMode ? t("terminal.switcher.searchRecent") : t("terminal.switcher.search")}
      />
    </>
  );
}
