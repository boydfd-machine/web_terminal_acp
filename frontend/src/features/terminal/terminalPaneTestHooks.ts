type TerminalWriteTestHook = (data: string | Uint8Array, parsedAt: number) => void;
type TerminalInteractiveOutputTestHook = (data: string | Uint8Array, receivedAt: number) => void;
type TerminalDataTestHook = (data: string, onDataAt: number) => void;

declare global {
  interface Window {
    __WEB_TERMINAL_TEST_ON_TERMINAL_WRITE__?: TerminalWriteTestHook;
    __WEB_TERMINAL_TEST_ON_INTERACTIVE_OUTPUT__?: TerminalInteractiveOutputTestHook;
    __WEB_TERMINAL_TEST_ON_TERMINAL_DATA__?: TerminalDataTestHook;
  }
}

export {};
