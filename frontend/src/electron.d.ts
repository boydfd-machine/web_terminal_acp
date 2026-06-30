export type ElectronAPI = {
  isElectron: boolean;
  platform: NodeJS.Platform;
  capturePageScreenshot?: (
    selection?: { left: number; top: number; width: number; height: number }
  ) => Promise<{
    dataUrl: string;
    width: number;
    height: number;
    capturedRect?: { left: number; top: number; width: number; height: number };
  }>;
  readClipboardText?: () => Promise<string>;
  writeClipboardText?: (text: string) => Promise<void>;
};

declare global {
  interface Window {
    electronAPI?: ElectronAPI;
  }
}

export {};
