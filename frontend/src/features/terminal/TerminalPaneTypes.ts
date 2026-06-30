import type { ITheme } from "@xterm/xterm";

import type { CustomQuickKey } from "../../terminalQuickKeys";

export type TerminalViewportMode = "desktop" | "phone" | "fixed";
export type TerminalConnectionStatus = "connecting" | "connected" | "reconnecting" | "unavailable" | "error";

export type TerminalPaneProps = {
  clientId: string | null;
  windowId: string | null;
  viewportMode?: TerminalViewportMode;
  layoutVersion?: number | string;
  virtualKeysVisible?: boolean;
  onTerminalSelection?: (windowId: string) => void;
  onQuickInputOpenChange?: (open: boolean) => void;
  onQuickInputDraftChange?: (draft: string) => void;
  customQuickKeys?: CustomQuickKey[];
  onCustomQuickKeySubmit?: (quickKey: CustomQuickKey) => boolean;
  onTerminalConnectionStatusChange?: (status: TerminalConnectionStatus) => void;
  webSocketUrl?: (
    clientId: string,
    windowId: string,
    viewId: string,
    options?: { allowMissingWindowRecreate?: boolean },
  ) => string;
  selectionEnabled?: boolean;
  terminalSwitchingEnabled?: boolean;
  priorityEnabled?: boolean;
  autoFocus?: boolean;
  allowMissingWindowRecreate?: boolean;
  theme?: ITheme;
};

export type TerminalPaneHandle = {
  focus: () => void;
  refit: () => void;
  openQuickInput: () => void;
  setQuickInputDraft: (draft: string) => void;
  submitQuickInput: (draft?: string) => boolean;
  connectionStatus: () => TerminalConnectionStatus;
};

export type TouchScrollGesture = {
  pointerId: number;
  startX: number;
  startY: number;
  lastY: number;
  accumulatedY: number;
  scrolling: boolean;
};

export type RecentNativeFallbackInput = {
  data: string;
  inputEventSerial: number;
  sentAt: number;
};

export type RecentXtermInput = {
  data: string;
  seenAt: number;
};
