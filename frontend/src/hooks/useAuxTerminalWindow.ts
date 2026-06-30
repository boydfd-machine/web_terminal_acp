import {
  useCallback,
  useEffect,
  useLayoutEffect,
  useMemo,
  useRef,
  useState,
  type CSSProperties,
  type PointerEvent as ReactPointerEvent,
  type RefObject,
} from "react";

import {
  type AuxTerminalWindowDragState,
  calculateAuxTerminalDefaultWindowLayout,
  clampAuxTerminalWindowPosition,
  initialAuxTerminalWindowLayout,
  readAuxTerminalWindowPosition,
  writeAuxTerminalWindowPosition,
} from "../auxTerminalLayout";

type UseAuxTerminalWindowArgs = {
  detailPanelCollapsed: boolean;
  detailPanelOpen: boolean;
  mobileTerminalActive: boolean;
  terminalImmersive: boolean;
  workspaceRef: RefObject<HTMLElement | null>;
};

export function useAuxTerminalWindow({
  detailPanelCollapsed,
  detailPanelOpen,
  mobileTerminalActive,
  terminalImmersive,
  workspaceRef,
}: UseAuxTerminalWindowArgs) {
  const [layout, setLayout] = useState(initialAuxTerminalWindowLayout);
  const [dragActive, setDragActive] = useState(false);
  const draggedRef = useRef(readAuxTerminalWindowPosition() !== null);
  const dragRef = useRef<AuxTerminalWindowDragState | null>(null);

  const syncLayout = useCallback(() => {
    setLayout((currentLayout) => {
      const nextDefaultLayout = calculateAuxTerminalDefaultWindowLayout(workspaceRef.current);
      const nextPosition = draggedRef.current
        ? clampAuxTerminalWindowPosition(currentLayout.position, nextDefaultLayout.metrics)
        : nextDefaultLayout.position;
      if (
        currentLayout.metrics.width === nextDefaultLayout.metrics.width
        && currentLayout.metrics.height === nextDefaultLayout.metrics.height
        && currentLayout.metrics.minHeight === nextDefaultLayout.metrics.minHeight
        && currentLayout.position.x === nextPosition.x
        && currentLayout.position.y === nextPosition.y
      ) {
        return currentLayout;
      }

      return {
        metrics: nextDefaultLayout.metrics,
        position: nextPosition,
      };
    });
  }, [workspaceRef]);

  useLayoutEffect(() => {
    syncLayout();
  }, [detailPanelCollapsed, detailPanelOpen, mobileTerminalActive, syncLayout, terminalImmersive]);

  useEffect(() => {
    let frame: number | null = null;
    const scheduleSync = () => {
      if (frame !== null) {
        return;
      }
      frame = window.requestAnimationFrame(() => {
        frame = null;
        syncLayout();
      });
    };

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
    };
  }, [syncLayout]);

  const handlePointerDown = useCallback((event: ReactPointerEvent<HTMLElement>) => {
    if (event.button !== 0) {
      return;
    }

    const target = event.target;
    if (target instanceof HTMLElement && target.closest("button, a, input, textarea, select, [role='button']")) {
      return;
    }

    dragRef.current = {
      pointerId: event.pointerId,
      startPointerX: event.clientX,
      startPointerY: event.clientY,
      startPosition: layout.position,
    };
    setDragActive(true);
    if (typeof event.currentTarget.setPointerCapture === "function") {
      event.currentTarget.setPointerCapture(event.pointerId);
    }
    event.preventDefault();
  }, [layout.position]);

  const handlePointerMove = useCallback((event: ReactPointerEvent<HTMLElement>) => {
    const dragState = dragRef.current;
    if (dragState === null || dragState.pointerId !== event.pointerId) {
      return;
    }

    const nextPosition = clampAuxTerminalWindowPosition({
      x: dragState.startPosition.x + event.clientX - dragState.startPointerX,
      y: dragState.startPosition.y + event.clientY - dragState.startPointerY,
    }, layout.metrics);
    setLayout((currentLayout) => (
      currentLayout.position.x === nextPosition.x && currentLayout.position.y === nextPosition.y
        ? currentLayout
        : { ...currentLayout, position: nextPosition }
    ));
    event.preventDefault();
  }, [layout.metrics]);

  const finishDrag = useCallback((event: ReactPointerEvent<HTMLElement>) => {
    const dragState = dragRef.current;
    if (dragState === null || dragState.pointerId !== event.pointerId) {
      return;
    }

    const nextPosition = clampAuxTerminalWindowPosition({
      x: dragState.startPosition.x + event.clientX - dragState.startPointerX,
      y: dragState.startPosition.y + event.clientY - dragState.startPointerY,
    }, layout.metrics);
    const positionChanged = nextPosition.x !== dragState.startPosition.x || nextPosition.y !== dragState.startPosition.y;
    dragRef.current = null;
    setDragActive(false);
    if (positionChanged) {
      draggedRef.current = true;
      setLayout((currentLayout) => (
        currentLayout.position.x === nextPosition.x && currentLayout.position.y === nextPosition.y
          ? currentLayout
          : { ...currentLayout, position: nextPosition }
      ));
      writeAuxTerminalWindowPosition(nextPosition);
    }
    if (
      typeof event.currentTarget.hasPointerCapture === "function"
      && event.currentTarget.hasPointerCapture(event.pointerId)
      && typeof event.currentTarget.releasePointerCapture === "function"
    ) {
      event.currentTarget.releasePointerCapture(event.pointerId);
    }
    event.preventDefault();
  }, [layout.metrics]);

  const style = useMemo<CSSProperties>(() => ({
    left: `${layout.position.x}px`,
    top: `${layout.position.y}px`,
    width: `${layout.metrics.width}px`,
    height: `${layout.metrics.height}px`,
    minHeight: `${layout.metrics.minHeight}px`,
  }), [layout]);

  return {
    dragActive,
    finishDrag,
    handlePointerDown,
    handlePointerMove,
    layout,
    style,
  };
}
