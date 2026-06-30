export function isXtermInput(element: EventTarget | null): boolean {
  if (!(element instanceof HTMLElement)) {
    return false;
  }

  return element.classList.contains("xterm-helper-textarea") || element.closest(".xterm") !== null;
}

export function isBlockingTextInput(element: EventTarget | null): boolean {
  if (!(element instanceof HTMLElement) || isXtermInput(element)) {
    return false;
  }

  const tag = element.tagName;
  return tag === "INPUT" || tag === "TEXTAREA" || element.isContentEditable;
}

export function isGlobalShortcutTextTarget(element: EventTarget | null): boolean {
  if (!(element instanceof HTMLElement) || isXtermInput(element)) {
    return false;
  }

  if (element.closest(".terminal-quick-input-panel") !== null) {
    return false;
  }

  return isBlockingTextInput(element);
}
