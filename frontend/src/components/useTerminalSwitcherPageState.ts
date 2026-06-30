import { useEffect, type Dispatch, type SetStateAction } from "react";

import { RECENT_PROJECT_ALL_KEY } from "./terminalSwitcherData";

type UseTerminalSwitcherPageStateArgs = {
  activeRecentProjectKey: string;
  isOpen: boolean;
  isRecentMode: boolean;
  normalizedQuery: string;
  recentTotalPages: number;
  setActiveRecentProjectKey: Dispatch<SetStateAction<string>>;
  setRecentPage: Dispatch<SetStateAction<number>>;
};

export function useTerminalSwitcherPageState({
  activeRecentProjectKey,
  isOpen,
  isRecentMode,
  normalizedQuery,
  recentTotalPages,
  setActiveRecentProjectKey,
  setRecentPage
}: UseTerminalSwitcherPageStateArgs) {
  useEffect(() => {
    setRecentPage(1);
    setActiveRecentProjectKey(RECENT_PROJECT_ALL_KEY);
  }, [normalizedQuery, setActiveRecentProjectKey, setRecentPage]);

  useEffect(() => {
    setRecentPage(1);
  }, [activeRecentProjectKey, setRecentPage]);

  useEffect(() => {
    if (!isOpen || !isRecentMode || recentTotalPages <= 0) {
      return;
    }

    setRecentPage((page) => Math.min(Math.max(1, page), recentTotalPages));
  }, [isOpen, isRecentMode, recentTotalPages, setRecentPage]);
}
