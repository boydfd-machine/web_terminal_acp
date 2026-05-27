export type ElectronAPI = {
  isElectron: boolean;
  platform: NodeJS.Platform;
};

declare global {
  interface Window {
    electronAPI?: ElectronAPI;
  }
}

export {};
