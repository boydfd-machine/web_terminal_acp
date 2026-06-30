import { useCallback, useEffect, useRef, type MutableRefObject } from "react";

import type { TerminalPaneHandle } from "../components/TerminalPane";
import {
  CODEX_COMPOSER_FOLLOWUP_SUBMIT_INTERVAL_MS,
  agentDirectSubmitFollowupInputs,
} from "../terminalQuickKeys";

type UseAgentPreviewFollowupsArgs = {
  terminalPaneRef: MutableRefObject<TerminalPaneHandle | null>;
};

export function useAgentPreviewFollowups({
  terminalPaneRef,
}: UseAgentPreviewFollowupsArgs) {
  const timersRef = useRef<number[]>([]);

  const clearAgentPreviewFollowupSubmits = useCallback(() => {
    for (const timer of timersRef.current) {
      window.clearTimeout(timer);
    }
    timersRef.current = [];
  }, []);

  const scheduleAgentPreviewFollowupSubmits = useCallback((runtimeTags: string[] | null | undefined) => {
    clearAgentPreviewFollowupSubmits();
    const inputs = agentDirectSubmitFollowupInputs(runtimeTags);
    if (inputs.length === 0) {
      return;
    }
    timersRef.current = inputs.map((input, index) => window.setTimeout(() => {
      terminalPaneRef.current?.submitQuickInput(input);
    }, CODEX_COMPOSER_FOLLOWUP_SUBMIT_INTERVAL_MS * (index + 1)));
  }, [clearAgentPreviewFollowupSubmits, terminalPaneRef]);

  useEffect(() => clearAgentPreviewFollowupSubmits, [clearAgentPreviewFollowupSubmits]);

  return {
    clearAgentPreviewFollowupSubmits,
    scheduleAgentPreviewFollowupSubmits,
  };
}
