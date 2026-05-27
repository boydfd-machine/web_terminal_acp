export function applyElectronDocumentClass(): void {
  if (window.electronAPI?.isElectron) {
    document.documentElement.classList.add("electron-app");
  }
}
