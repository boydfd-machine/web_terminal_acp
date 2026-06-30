import { useEffect, useRef, type RefObject } from "react";

type OverlayFocusOptions<T extends HTMLElement> = {
  isOpen: boolean;
  ref: RefObject<T>;
  onEscape?: (event: KeyboardEvent) => void;
  initialFocusSelector?: string;
  preserveExistingFocus?: boolean;
};

const overlayEscapeStack: object[] = [];

function containsActiveElement(element: HTMLElement): boolean {
  const activeElement = document.activeElement;
  return activeElement instanceof Node && element.contains(activeElement);
}

function focusOverlayElement<T extends HTMLElement>(
  element: T,
  initialFocusSelector: string | undefined
): void {
  const target = initialFocusSelector === undefined
    ? null
    : element.querySelector<HTMLElement>(initialFocusSelector);

  if (!element.hasAttribute("tabindex")) {
    element.tabIndex = -1;
  }
  (target ?? element).focus({ preventScroll: true });
}

export function useOverlayFocus<T extends HTMLElement>({
  isOpen,
  ref,
  onEscape,
  initialFocusSelector,
  preserveExistingFocus = false
}: OverlayFocusOptions<T>): void {
  const onEscapeRef = useRef(onEscape);

  useEffect(() => {
    onEscapeRef.current = onEscape;
  }, [onEscape]);

  useEffect(() => {
    if (!isOpen) {
      return;
    }

    const frame = window.requestAnimationFrame(() => {
      const element = ref.current;
      if (element === null) {
        return;
      }
      if (preserveExistingFocus && containsActiveElement(element)) {
        return;
      }
      focusOverlayElement(element, initialFocusSelector);
    });

    return () => window.cancelAnimationFrame(frame);
  }, [initialFocusSelector, isOpen, preserveExistingFocus, ref]);

  useEffect(() => {
    if (!isOpen) {
      return;
    }

    const stackEntry = {};
    overlayEscapeStack.push(stackEntry);

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key !== "Escape") {
        return;
      }

      if (overlayEscapeStack[overlayEscapeStack.length - 1] !== stackEntry) {
        return;
      }

      event.preventDefault();
      event.stopPropagation();
      onEscapeRef.current?.(event);
    };

    window.addEventListener("keydown", handleKeyDown, { capture: true });
    return () => {
      window.removeEventListener("keydown", handleKeyDown, { capture: true });
      const index = overlayEscapeStack.indexOf(stackEntry);
      if (index >= 0) {
        overlayEscapeStack.splice(index, 1);
      }
    };
  }, [isOpen]);
}
