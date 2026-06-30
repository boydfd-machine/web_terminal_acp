export type AuxTerminalWindowPosition = {
  x: number;
  y: number;
};

export type AuxTerminalWindowMetrics = {
  width: number;
  height: number;
  minHeight: number;
};

export type AuxTerminalWindowLayout = {
  metrics: AuxTerminalWindowMetrics;
  position: AuxTerminalWindowPosition;
};

export type AuxTerminalWindowDragState = {
  pointerId: number;
  startPointerX: number;
  startPointerY: number;
  startPosition: AuxTerminalWindowPosition;
};

export const AUX_TERMINAL_WINDOW_POSITION_STORAGE_KEY = "web-terminal-acp:aux-terminal-window-position";

const AUX_TERMINAL_MIN_WIDTH = 320;
const AUX_TERMINAL_DESKTOP_MIN_HEIGHT = 220;
const AUX_TERMINAL_MOBILE_MIN_HEIGHT = 200;
const AUX_TERMINAL_MOBILE_BREAKPOINT = 760;

export function readAuxTerminalWindowPosition(): AuxTerminalWindowPosition | null {
  if (typeof window === "undefined") {
    return null;
  }

  try {
    const parsed = JSON.parse(window.localStorage.getItem(AUX_TERMINAL_WINDOW_POSITION_STORAGE_KEY) ?? "null");
    if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
      return null;
    }

    const record = parsed as Record<string, unknown>;
    return typeof record.x === "number" && Number.isFinite(record.x)
      && typeof record.y === "number" && Number.isFinite(record.y)
      ? { x: record.x, y: record.y }
      : null;
  } catch {
    return null;
  }
}

export function writeAuxTerminalWindowPosition(position: AuxTerminalWindowPosition): void {
  if (typeof window === "undefined") {
    return;
  }

  try {
    window.localStorage.setItem(AUX_TERMINAL_WINDOW_POSITION_STORAGE_KEY, JSON.stringify(position));
  } catch {
    return;
  }
}

export function auxTerminalViewportSize(): { width: number; height: number } {
  if (typeof window === "undefined") {
    return { width: 1024, height: 768 };
  }

  const root = document.documentElement;
  return {
    width: Math.max(0, Math.round(window.innerWidth || root.clientWidth || 0)),
    height: Math.max(0, Math.round(window.visualViewport?.height ?? window.innerHeight ?? root.clientHeight ?? 0))
  };
}

export function clampAuxTerminalWindowPosition(
  position: AuxTerminalWindowPosition,
  metrics: AuxTerminalWindowMetrics
): AuxTerminalWindowPosition {
  const viewport = auxTerminalViewportSize();
  const maxX = Math.max(0, viewport.width - metrics.width);
  const maxY = Math.max(0, viewport.height - metrics.height);
  return {
    x: Math.min(Math.max(0, Math.round(position.x)), maxX),
    y: Math.min(Math.max(0, Math.round(position.y)), maxY)
  };
}

export function calculateAuxTerminalDefaultWindowLayout(workspace: HTMLElement | null): AuxTerminalWindowLayout {
  const viewport = auxTerminalViewportSize();
  const rawMinHeight = viewport.width <= AUX_TERMINAL_MOBILE_BREAKPOINT
    ? AUX_TERMINAL_MOBILE_MIN_HEIGHT
    : AUX_TERMINAL_DESKTOP_MIN_HEIGHT;
  const minHeight = Math.min(rawMinHeight, Math.max(0, viewport.height));
  const workspaceRect = workspace?.getBoundingClientRect();
  const hasWorkspaceRect = workspaceRect !== undefined && workspaceRect.width > 0 && workspaceRect.height > 0;
  const rect = hasWorkspaceRect
    ? workspaceRect
    : {
      left: 0,
      right: viewport.width,
      top: 0,
      bottom: viewport.height,
      width: viewport.width,
      height: viewport.height
    };
  const width = Math.max(
    0,
    Math.min(
      Math.max(Math.round(rect.width), Math.min(AUX_TERMINAL_MIN_WIDTH, viewport.width)),
      viewport.width
    )
  );
  const halfHeight = Math.min(rect.height * 0.5, viewport.height * 0.5);
  const height = Math.max(minHeight, Math.min(Math.round(halfHeight), viewport.height));
  const metrics = { width, height, minHeight };
  const position = clampAuxTerminalWindowPosition({
    x: Math.round(rect.left),
    y: Math.round(rect.bottom - height)
  }, metrics);
  return { metrics, position };
}

export function initialAuxTerminalWindowLayout(): AuxTerminalWindowLayout {
  const layout = calculateAuxTerminalDefaultWindowLayout(null);
  const storedPosition = readAuxTerminalWindowPosition();
  return storedPosition === null
    ? layout
    : { metrics: layout.metrics, position: storedPosition };
}
