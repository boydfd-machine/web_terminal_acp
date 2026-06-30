import type { Dispatch, SetStateAction } from "react";

import { useI18n } from "../i18n";
import type { GlobalTerminalRecent, ProjectSummary, TerminalRecent, TreeFolder, TreeWindow } from "../types";
import { TerminalUnreadDot } from "./NotificationCenter";
import { SwitcherWindowTitle, switcherWindowTitle } from "./SwitcherWindowTitle";
import { TerminalWindowMeta } from "./TerminalSwitcherTree";
import { WorkStatusDot } from "./WorkStatusBadge";
import {
  RECENT_PROJECT_ALL_KEY,
  findWindowInTree,
  isGlobalTerminalRecent,
  relatedRecentItemKey,
  scopedRecentItemKey,
  terminalMeta
} from "./terminalSwitcherData";

type TerminalSwitcherRecentListProps = {
  activeKey: string | null;
  activeRecentProjectKey: string;
  clientId: string | null;
  folders: TreeFolder[];
  hasUnreadNotification?: (windowId: string) => boolean;
  isGlobalRecentMode: boolean;
  isRelatedRecentMode: boolean;
  normalizedQuery: string;
  projectSummaryLookup: Map<string, ProjectSummary>;
  recentError: boolean;
  recentItems: Array<TerminalRecent | GlobalTerminalRecent>;
  recentLoading: boolean;
  recentMatchCount: number;
  recentPage: number;
  recentTotalPages: number;
  relatedLoading: boolean;
  relatedRecentVisibleItems: TreeWindow[];
  selectedWindowId: string | null;
  onSelectRecent: (item: TerminalRecent | GlobalTerminalRecent) => void;
  onSelectRelatedRecent: (window: TreeWindow) => void;
  setRecentPage: Dispatch<SetStateAction<number>>;
};

export function TerminalSwitcherRecentList({
  activeKey,
  activeRecentProjectKey,
  clientId,
  folders,
  hasUnreadNotification,
  isGlobalRecentMode,
  isRelatedRecentMode,
  normalizedQuery,
  projectSummaryLookup,
  recentError,
  recentItems,
  recentLoading,
  recentMatchCount,
  recentPage,
  recentTotalPages,
  relatedLoading,
  relatedRecentVisibleItems,
  selectedWindowId,
  onSelectRecent,
  onSelectRelatedRecent,
  setRecentPage
}: TerminalSwitcherRecentListProps) {
  const { t } = useI18n();

  return (
    <>
      {recentLoading && <p className="terminal-switcher-empty">{t("terminal.switcher.loadingRecent")}</p>}
      {recentError && <p className="terminal-switcher-empty">{t("terminal.switcher.loadRecentFailed")}</p>}
      {isRelatedRecentMode && relatedLoading && relatedRecentVisibleItems.length === 0 && (
        <p className="terminal-switcher-empty">{t("terminal.switcher.loadingRelated")}</p>
      )}
      {isRelatedRecentMode && !relatedLoading && relatedRecentVisibleItems.length === 0 && (
        <p className="terminal-switcher-empty">
          {activeRecentProjectKey !== RECENT_PROJECT_ALL_KEY
            ? t("terminal.switcher.noRelatedProject")
            : normalizedQuery
            ? t("terminal.switcher.noMatchingRelated")
            : t("terminal.switcher.noRelated")}
        </p>
      )}
      {!isRelatedRecentMode && !recentLoading && !recentError && recentItems.length === 0 && (
        <p className="terminal-switcher-empty">
          {activeRecentProjectKey !== RECENT_PROJECT_ALL_KEY
            ? t("terminal.switcher.noRecentProject")
            : normalizedQuery
            ? t("terminal.switcher.noMatchingRecent")
            : t("terminal.switcher.noRecent")}
        </p>
      )}
      {isRelatedRecentMode && relatedRecentVisibleItems.length > 0 && (
        <ul className="terminal-switcher-results terminal-switcher-recents" role="listbox" aria-label={t("terminal.switcher.relatedList")}>
          {relatedRecentVisibleItems.map((window) => {
            const key = relatedRecentItemKey(window);
            const isActive = key === activeKey;
            const isSelected = window.id === selectedWindowId;
            const showUnreadDot = hasUnreadNotification?.(window.id) ?? false;
            const meta = terminalMeta(window, projectSummaryLookup, t);
            return (
              <li key={key}>
                <button
                  type="button"
                  aria-selected={isActive}
                  aria-current={isSelected ? "true" : undefined}
                  className={isActive ? "switcher-window with-meta active" : "switcher-window with-meta"}
                  onClick={() => onSelectRelatedRecent(window)}
                  role="option"
                  title={switcherWindowTitle(window.title, window.todo_title)}
                >
                  <WorkStatusDot status={window.work_status} />
                  <SwitcherWindowTitle active={isActive} title={window.title} todoTitle={window.todo_title} />
                  <TerminalWindowMeta meta={meta} />
                  <TerminalUnreadDot visible={showUnreadDot} />
                </button>
              </li>
            );
          })}
        </ul>
      )}
      {!isRelatedRecentMode && !recentLoading && !recentError && recentItems.length > 0 && (
        <ul className="terminal-switcher-results terminal-switcher-recents" role="listbox" aria-label={t("terminal.switcher.recentList")}>
          {recentItems.map((item) => {
            const key = scopedRecentItemKey(item, isGlobalRecentMode);
            const treeWindow = findWindowInTree(folders, item.window_id);
            const isActive = key === activeKey;
            const isSelected = item.window_id === selectedWindowId
              && (!isGlobalTerminalRecent(item) || item.client_id === clientId);
            const showUnreadDot = hasUnreadNotification?.(item.window_id) ?? false;
            const meta = treeWindow ? terminalMeta(treeWindow, projectSummaryLookup, t) : null;
            const clientName = isGlobalTerminalRecent(item) ? item.client_name : null;
            const todoTitle = item.todo_title ?? treeWindow?.todo_title;
            const buttonClassName = [
              "switcher-window",
              isActive ? "active" : null,
              meta !== null ? "with-meta" : null,
              clientName !== null ? "with-client-name" : null
            ].filter(Boolean).join(" ");
            return (
              <li key={key}>
                <button
                  type="button"
                  aria-selected={isActive}
                  aria-current={isSelected ? "true" : undefined}
                  className={buttonClassName}
                  onClick={() => onSelectRecent(item)}
                  role="option"
                  title={switcherWindowTitle(item.title, todoTitle)}
                >
                  {treeWindow ? <WorkStatusDot status={treeWindow.work_status} /> : <span className="switcher-window-placeholder" aria-hidden="true" />}
                  <SwitcherWindowTitle active={isActive} title={item.title} todoTitle={todoTitle} />
                  {clientName !== null && <span className="switcher-client-name">{clientName}</span>}
                  {meta !== null && <TerminalWindowMeta meta={meta} />}
                  <TerminalUnreadDot visible={showUnreadDot} />
                </button>
              </li>
            );
          })}
        </ul>
      )}
      {!recentLoading && !recentError && recentTotalPages > 1 && (
        <div className="terminal-switcher-pagination">
          <button type="button" disabled={recentPage <= 1} onClick={() => setRecentPage((page) => Math.max(1, page - 1))}>
            {t("terminal.switcher.previous")}
          </button>
          <span>
            {normalizedQuery
              ? t("terminal.switcher.pageWithMatches", { page: recentPage, total: recentTotalPages, count: recentMatchCount })
              : t("terminal.switcher.page", { page: recentPage, total: recentTotalPages })}
          </span>
          <button type="button" disabled={recentPage >= recentTotalPages} onClick={() => setRecentPage((page) => page + 1)}>
            {t("terminal.switcher.next")}
          </button>
        </div>
      )}
    </>
  );
}
