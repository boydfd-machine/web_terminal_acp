import type { Dispatch, MutableRefObject, SetStateAction } from "react";
import type { ITheme, Terminal } from "@xterm/xterm";

import type { TerminalConnectionStatus, TerminalPaneProps } from "./TerminalPaneTypes";

export type UseTerminalPaneSessionArgs = {
  activeWindowIdRef: MutableRefObject<string | null>;
  allowMissingWindowRecreateRef: MutableRefObject<boolean>;
  autoFocusRef: MutableRefObject<boolean>;
  claimActiveTerminalViewRef: MutableRefObject<(() => void) | null>;
  clearScheduledFits: () => void;
  clientId: string | null;
  connectionStatusRef: MutableRefObject<TerminalConnectionStatus>;
  containerRef: MutableRefObject<HTMLDivElement | null>;
  fitAndNotifyResizeRef: MutableRefObject<(() => void) | null>;
  initialWindowIdRef: MutableRefObject<string | null>;
  onTerminalSelectionRef: MutableRefObject<TerminalPaneProps["onTerminalSelection"]>;
  pendingExplicitWindowIdRef: MutableRefObject<string | null>;
  priorityEnabled: boolean;
  scheduleFitAndNotifyResize: () => void;
  selectionEnabled: boolean;
  terminalSwitchingEnabled: boolean;
  setPendingClipboardText: Dispatch<SetStateAction<string | null>>;
  sendTerminalInputRef: MutableRefObject<((data: string) => void) | null>;
  socketOpenRef: MutableRefObject<boolean>;
  socketWorkerRef: MutableRefObject<Worker | null>;
  stageRef: MutableRefObject<HTMLDivElement | null>;
  terminalRef: MutableRefObject<Terminal | null>;
  theme?: ITheme;
  updateConnectionStatus: (status: TerminalConnectionStatus) => void;
  viewIdRef: MutableRefObject<string>;
  webSocketUrl: NonNullable<TerminalPaneProps["webSocketUrl"]>;
  sessionWindowId: string | null;
  xtermHostRef: MutableRefObject<HTMLDivElement | null>;
};
