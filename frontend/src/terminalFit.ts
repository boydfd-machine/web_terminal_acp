import type { Terminal } from "@xterm/xterm";

type TerminalCore = {
  _renderService?: {
    dimensions?: {
      css: {
        cell?: { width: number; height: number };
      };
    };
  };
  viewport?: { scrollBarWidth: number };
};

type RendererSyncAttempt = {
  container: HTMLElement;
  cols: number;
  rows: number;
  contentWidth: number;
  contentHeight: number;
  renderedHeight: number;
};

type StableFitSize = {
  container: HTMLElement;
  contentWidth: number;
  contentHeight: number;
  cellWidth: number;
  cellHeight: number;
  scrollBarWidth: number;
  cols: number;
  rows: number;
};

const rendererSyncAttempts = new WeakMap<Terminal, RendererSyncAttempt>();
const stableFitSizes = new WeakMap<Terminal, StableFitSize>();

function readTerminalCore(terminal: Terminal): TerminalCore {
  return (terminal as unknown as { _core?: TerminalCore })._core ?? {};
}

export function readContainerContentSize(container: HTMLElement): { width: number; height: number } | null {
  const rect = container.getBoundingClientRect();
  if (rect.width <= 0 || rect.height <= 0) {
    return null;
  }

  const style = window.getComputedStyle(container);
  const paddingX = parseFloat(style.paddingLeft) + parseFloat(style.paddingRight);
  const paddingY = parseFloat(style.paddingTop) + parseFloat(style.paddingBottom);
  const width = container.clientWidth - paddingX;
  const height = container.clientHeight - paddingY;
  if (width <= 0 || height <= 0) {
    return null;
  }

  return { width, height };
}

export function readTerminalCanvas(terminal: Terminal): HTMLElement | null {
  const canvas = terminal.element?.querySelector(".xterm-screen canvas");
  return canvas instanceof HTMLElement ? canvas : null;
}

export function readTerminalRenderedHeight(terminal: Terminal): number {
  const canvas = readTerminalCanvas(terminal);
  if (canvas !== null) {
    const canvasHeight = canvas.getBoundingClientRect().height;
    if (canvasHeight > 0) {
      return canvasHeight;
    }
  }

  const rowsElement = terminal.element?.querySelector(".xterm-rows");
  if (!(rowsElement instanceof HTMLElement)) {
    return 0;
  }

  const lineElements = rowsElement.querySelectorAll("div");
  if (lineElements.length > 0) {
    const first = lineElements[0].getBoundingClientRect();
    const last = lineElements[lineElements.length - 1].getBoundingClientRect();
    const span = last.bottom - first.top;
    if (span > 0) {
      return span;
    }
  }

  return rowsElement.getBoundingClientRect().height;
}

function readTerminalCellSize(terminal: Terminal): { width: number; height: number } | null {
  const cell = readTerminalCore(terminal)._renderService?.dimensions?.css.cell;
  if (cell === undefined || cell.width <= 0 || cell.height <= 0) {
    return null;
  }

  return cell;
}

/**
 * Compute the expected terminal grid height based on the current row count
 * and cell dimensions. Unlike readTerminalRenderedHeight, this value is
 * available synchronously after terminal.resize() and does not depend on
 * the async canvas/DOM render cycle.
 */
function expectedGridHeight(terminal: Terminal): number {
  const cell = readTerminalCellSize(terminal);
  if (cell === null) {
    return 0;
  }
  return terminal.rows * cell.height;
}

export function proposeTerminalGridSize(
  terminal: Terminal,
  container: HTMLElement,
): { cols: number; rows: number } | null {
  const content = readContainerContentSize(container);
  if (content === null) {
    return null;
  }

  const core = readTerminalCore(terminal);
  const cell = readTerminalCellSize(terminal);
  if (cell === null) {
    return null;
  }

  const scrollBarWidth = terminal.options.scrollback === 0 ? 0 : core.viewport?.scrollBarWidth ?? 0;
  const rowRatio = content.height / cell.height;
  const floorRows = Math.max(1, Math.floor(rowRatio));

  // Keep the rounded grid size stable while the measured container and cell
  // dimensions are unchanged. Otherwise a one-time fill resize can be followed
  // by a floor resize on the next observer tick, which makes the PTY alternate
  // between two row counts.
  const previous = stableFitSizes.get(terminal);
  if (
    previous?.container === container &&
    previous.contentWidth === content.width &&
    previous.contentHeight === content.height &&
    previous.cellWidth === cell.width &&
    previous.cellHeight === cell.height &&
    previous.scrollBarWidth === scrollBarWidth
  ) {
    return { cols: previous.cols, rows: previous.rows };
  }

  const rows = floorRows;
  const cols = Math.max(2, Math.floor((content.width - scrollBarWidth) / cell.width));
  stableFitSizes.set(terminal, {
    container,
    contentWidth: content.width,
    contentHeight: content.height,
    cellWidth: cell.width,
    cellHeight: cell.height,
    scrollBarWidth,
    cols,
    rows,
  });

  return {
    cols,
    rows,
  };
}

export function isTerminalGridMeasurable(terminal: Terminal): boolean {
  return readTerminalCellSize(terminal) !== null;
}

/**
 * Determine whether the terminal grid and the visible renderer both fill the
 * container viewport.  xterm updates rows synchronously, but the DOM/canvas
 * renderer can lag a frame or stay at an old height after a same-size refit.
 */
export function isTerminalViewportFilled(terminal: Terminal, container: HTMLElement): boolean {
  if (!isTerminalGridMeasurable(terminal)) {
    return false;
  }

  const content = readContainerContentSize(container);
  if (content === null) {
    return false;
  }

  const gridHeight = expectedGridHeight(terminal);
  if (gridHeight <= 0 || gridHeight < content.height * 0.92) {
    return false;
  }

  const renderedHeight = readTerminalRenderedHeight(terminal);
  if (renderedHeight <= 0) {
    return false;
  }

  return renderedHeight >= content.height * 0.92;
}

function syncTerminalRendererToGrid(terminal: Terminal, cols: number, rows: number): void {
  if (terminal.cols !== cols || terminal.rows !== rows) {
    terminal.resize(cols, rows);
    return;
  }

  if (rows > 1) {
    terminal.resize(cols, rows - 1);
  }
  terminal.resize(cols, rows);
  terminal.clearTextureAtlas();
  terminal.refresh(0, Math.max(0, rows - 1));
}

export function fitTerminalToContainer(terminal: Terminal, container: HTMLElement): boolean {
  const next = proposeTerminalGridSize(terminal, container);
  if (next === null) {
    return false;
  }

  const needsGridChange = terminal.cols !== next.cols || terminal.rows !== next.rows;

  // Check whether the rendered pixels actually fill the container.  Even when
  // the grid is the right size, the canvas/DOM render may not have caught up.
  const renderedHeight = readTerminalRenderedHeight(terminal);
  const content = readContainerContentSize(container);
  const needsRenderFix =
    content !== null &&
    renderedHeight > 0 &&
    renderedHeight < content.height * 0.92;

  if (!needsGridChange && !needsRenderFix) {
    rendererSyncAttempts.delete(terminal);
    return true;
  }

  if (needsGridChange) {
    rendererSyncAttempts.delete(terminal);
    terminal.resize(next.cols, next.rows);
  } else {
    if (content === null) {
      return true;
    }
    const previousSync = rendererSyncAttempts.get(terminal);
    if (
      previousSync?.container === container &&
      previousSync.cols === next.cols &&
      previousSync.rows === next.rows &&
      previousSync.contentWidth === content.width &&
      previousSync.contentHeight === content.height &&
      previousSync.renderedHeight === renderedHeight
    ) {
      return true;
    }
    rendererSyncAttempts.set(terminal, {
      container,
      cols: next.cols,
      rows: next.rows,
      contentWidth: content.width,
      contentHeight: content.height,
      renderedHeight,
    });
    syncTerminalRendererToGrid(terminal, next.cols, next.rows);
  }

  return true;
}

export function terminalViewportNeedsRefit(terminal: Terminal, container: HTMLElement): boolean {
  return !isTerminalViewportFilled(terminal, container);
}
