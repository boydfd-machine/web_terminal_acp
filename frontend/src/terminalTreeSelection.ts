import { flattenTreeWindows } from "./terminalTree";
import type { TreeFolder } from "./types";

export function findTreeWindow(
  folders: TreeFolder[] | undefined,
  windowId: string | null
): TreeFolder["windows"][number] | null {
  if (!folders || windowId === null) {
    return null;
  }

  for (const folder of folders) {
    const window = folder.windows.find((candidate) => candidate.id === windowId);
    if (window) {
      return window;
    }

    const childWindow = findTreeWindow(folder.folders, windowId);
    if (childWindow) {
      return childWindow;
    }
  }

  return null;
}

export function findWindowTitle(folders: TreeFolder[] | undefined, windowId: string | null): string | null {
  if (!folders || windowId === null) {
    return null;
  }

  return findTreeWindow(folders, windowId)?.title ?? null;
}

export function pickWindowAfterDelete(folders: TreeFolder[] | undefined, deletedWindowId: string): string | null {
  const windows = flattenTreeWindows(folders);
  const index = windows.findIndex((window) => window.id === deletedWindowId);
  if (windows.length <= 1) {
    return null;
  }
  if (index === -1) {
    return windows[0]?.id ?? null;
  }
  const nextWindow = windows[index + 1] ?? windows[index - 1];
  return nextWindow?.id ?? null;
}

export function treeContainsWindow(folders: TreeFolder[] | undefined, windowId: string | null): boolean {
  if (!folders || windowId === null) {
    return false;
  }

  for (const folder of folders) {
    if (folder.windows.some((window) => window.id === windowId)) {
      return true;
    }

    if (treeContainsWindow(folder.folders, windowId)) {
      return true;
    }
  }

  return false;
}
