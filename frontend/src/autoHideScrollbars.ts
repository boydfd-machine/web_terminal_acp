export const AUTO_HIDE_SCROLLBAR_ACTIVE_CLASS = "scrollbars-active";
export const AUTO_HIDE_SCROLLBAR_IDLE_MS = 900;

type AutoHideScrollbarsOptions = {
  doc?: Document;
  idleMs?: number;
  win?: Window;
};

export function installAutoHideScrollbars({
  doc = document,
  idleMs = AUTO_HIDE_SCROLLBAR_IDLE_MS,
  win = window
}: AutoHideScrollbarsOptions = {}): () => void {
  let activeElement: Element | null = null;
  let hideTimeout: ReturnType<Window["setTimeout"]> | null = null;

  const setInactive = () => {
    activeElement?.classList.remove(AUTO_HIDE_SCROLLBAR_ACTIVE_CLASS);
    activeElement = null;
    hideTimeout = null;
  };

  const targetElement = (target: EventTarget | null): Element | null => {
    const elementConstructor = doc.defaultView?.Element;
    if (elementConstructor !== undefined && target instanceof elementConstructor) {
      return target;
    }
    if (target === doc) {
      return doc.scrollingElement ?? doc.documentElement;
    }
    return null;
  };

  const handleScroll = (event: Event) => {
    const nextActiveElement = targetElement(event.target);
    if (nextActiveElement === null) {
      return;
    }
    if (activeElement !== null && activeElement !== nextActiveElement) {
      activeElement.classList.remove(AUTO_HIDE_SCROLLBAR_ACTIVE_CLASS);
    }
    activeElement = nextActiveElement;
    activeElement.classList.add(AUTO_HIDE_SCROLLBAR_ACTIVE_CLASS);
    if (hideTimeout !== null) {
      win.clearTimeout(hideTimeout);
    }
    hideTimeout = win.setTimeout(setInactive, idleMs);
  };

  doc.addEventListener("scroll", handleScroll, { capture: true, passive: true });

  return () => {
    doc.removeEventListener("scroll", handleScroll, { capture: true });
    if (hideTimeout !== null) {
      win.clearTimeout(hideTimeout);
    }
    activeElement?.classList.remove(AUTO_HIDE_SCROLLBAR_ACTIVE_CLASS);
    activeElement = null;
  };
}
