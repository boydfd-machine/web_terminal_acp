import { useCallback, useEffect, useRef, useState } from "react";

import { readMobileLayout } from "./useMobileLayout";
import type { TerminalViewportMode } from "../appState";

export function useTerminalVirtualKeysPreference(
  isMobileLayout: boolean,
  terminalViewportMode: TerminalViewportMode,
) {
  const preferenceTouchedRef = useRef(false);
  const [virtualKeysVisible, setVirtualKeysVisible] = useState(
    () => readMobileLayout() || terminalViewportMode === "phone",
  );

  useEffect(() => {
    if (preferenceTouchedRef.current) {
      return;
    }

    setVirtualKeysVisible(isMobileLayout || terminalViewportMode === "phone");
  }, [isMobileLayout, terminalViewportMode]);

  const toggleVirtualKeysVisibility = useCallback(() => {
    preferenceTouchedRef.current = true;
    setVirtualKeysVisible((isVisible) => !isVisible);
  }, []);

  return {
    toggleVirtualKeysVisibility,
    virtualKeysVisible,
  };
}
