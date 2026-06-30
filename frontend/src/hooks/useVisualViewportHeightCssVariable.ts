import { useEffect } from "react";

export function useVisualViewportHeightCssVariable(): void {
  useEffect(() => {
    const root = document.documentElement;
    let frame: number | null = null;
    let lastHeight = "";

    const sync = () => {
      frame = null;
      const viewportHeight = window.visualViewport?.height ?? window.innerHeight;
      if (viewportHeight <= 0) {
        return;
      }

      const nextHeight = `${Math.round(viewportHeight)}px`;
      if (nextHeight === lastHeight) {
        return;
      }

      lastHeight = nextHeight;
      root.style.setProperty("--web-terminal-viewport-height", nextHeight);
    };

    const scheduleSync = () => {
      if (frame !== null) {
        return;
      }
      frame = window.requestAnimationFrame(sync);
    };

    sync();
    window.visualViewport?.addEventListener("resize", scheduleSync);
    window.visualViewport?.addEventListener("scroll", scheduleSync);
    window.addEventListener("resize", scheduleSync);
    window.addEventListener("orientationchange", scheduleSync);
    return () => {
      if (frame !== null) {
        window.cancelAnimationFrame(frame);
      }
      window.visualViewport?.removeEventListener("resize", scheduleSync);
      window.visualViewport?.removeEventListener("scroll", scheduleSync);
      window.removeEventListener("resize", scheduleSync);
      window.removeEventListener("orientationchange", scheduleSync);
      root.style.removeProperty("--web-terminal-viewport-height");
    };
  }, []);
}
