import { useEffect, type MutableRefObject } from "react";

import {
  TERMINAL_VIEWPORT_STORAGE_KEY,
  WORKSPACE_MODE_STORAGE_KEY,
  type TerminalViewportMode,
  type WorkspaceMode,
} from "../appState";
import { writeProjectTodoDateFilter, type ProjectTodoDateFilter } from "../features/projectTodos/projectTodoDateFilter";
import { writeTerminalTimeRange, type TerminalTimeRange } from "../userPreferences";
import type { TerminalArtifact } from "../types";
import type { TerminalCreateContext } from "../components/TerminalCreateModal";
import type { TerminalPaneHandle } from "../components/TerminalPane";

type UseAppLifecycleEffectsArgs = {
  focusSelectedTerminal: () => void;
  projectTodoDateFilter: ProjectTodoDateFilter;
  selectedClientId: string | null;
  selectedWindowId: string | null;
  terminalControlsOpen: boolean;
  terminalControlsRef: MutableRefObject<HTMLDivElement | null>;
  terminalPaneRef: MutableRefObject<TerminalPaneHandle | null>;
  terminalTimeRange: TerminalTimeRange;
  terminalViewportMode: TerminalViewportMode;
  treeQuerySuccess: boolean;
  workspaceMode: WorkspaceMode;
  setAgentRecordModalOpen: (open: boolean) => void;
  setArtifactQuickOpenOpen: (open: boolean) => void;
  setArtifactResultViewerArtifact: (artifact: TerminalArtifact | null) => void;
  setClientSwitcherOpen: (open: boolean) => void;
  setGitDiffBrowserOpen: (open: boolean) => void;
  setNotificationCenterOpen: (open: boolean) => void;
  setProjectTerminalPickerOpen: (open: boolean) => void;
  setTerminalControlsOpen: (open: boolean) => void;
  setTerminalCreateContext: (context: TerminalCreateContext | null) => void;
  setTerminalImmersive: (immersive: boolean) => void;
  setTerminalSwitcherOpen: (open: boolean) => void;
};

export function useAppLifecycleEffects({
  focusSelectedTerminal,
  projectTodoDateFilter,
  selectedClientId,
  selectedWindowId,
  terminalControlsOpen,
  terminalControlsRef,
  terminalPaneRef,
  terminalTimeRange,
  terminalViewportMode,
  treeQuerySuccess,
  workspaceMode,
  setAgentRecordModalOpen,
  setArtifactQuickOpenOpen,
  setArtifactResultViewerArtifact,
  setClientSwitcherOpen,
  setGitDiffBrowserOpen,
  setNotificationCenterOpen,
  setProjectTerminalPickerOpen,
  setTerminalControlsOpen,
  setTerminalCreateContext,
  setTerminalImmersive,
  setTerminalSwitcherOpen,
}: UseAppLifecycleEffectsArgs) {
  useEffect(() => {
    setTerminalSwitcherOpen(false);
    setClientSwitcherOpen(false);
    setProjectTerminalPickerOpen(false);
    setTerminalControlsOpen(false);
    setTerminalImmersive(false);
    setNotificationCenterOpen(false);
    setGitDiffBrowserOpen(false);
    setAgentRecordModalOpen(false);
    setArtifactQuickOpenOpen(false);
    setArtifactResultViewerArtifact(null);
    setTerminalCreateContext(null);
  }, [
    selectedClientId,
    setAgentRecordModalOpen,
    setArtifactQuickOpenOpen,
    setArtifactResultViewerArtifact,
    setClientSwitcherOpen,
    setGitDiffBrowserOpen,
    setNotificationCenterOpen,
    setProjectTerminalPickerOpen,
    setTerminalControlsOpen,
    setTerminalCreateContext,
    setTerminalImmersive,
    setTerminalSwitcherOpen,
  ]);

  useEffect(() => {
    window.localStorage.setItem(TERMINAL_VIEWPORT_STORAGE_KEY, terminalViewportMode);
  }, [terminalViewportMode]);

  useEffect(() => {
    window.localStorage.setItem(WORKSPACE_MODE_STORAGE_KEY, workspaceMode);
  }, [workspaceMode]);

  useEffect(() => {
    if (workspaceMode !== "terminal" || selectedWindowId === null) {
      return;
    }
    focusSelectedTerminal();
  }, [focusSelectedTerminal, selectedWindowId, workspaceMode]);

  useEffect(() => {
    writeTerminalTimeRange(terminalTimeRange);
  }, [terminalTimeRange]);

  useEffect(() => {
    writeProjectTodoDateFilter(projectTodoDateFilter);
  }, [projectTodoDateFilter]);

  useEffect(() => {
    if (selectedWindowId === null || !treeQuerySuccess) {
      return;
    }

    const frame = window.requestAnimationFrame(() => {
      terminalPaneRef.current?.refit();
    });
    return () => window.cancelAnimationFrame(frame);
  }, [selectedWindowId, terminalPaneRef, treeQuerySuccess]);

  useEffect(() => {
    if (!terminalControlsOpen) {
      return;
    }

    const handlePointerDown = (event: PointerEvent) => {
      const target = event.target;
      if (!(target instanceof Node) || !terminalControlsRef.current?.contains(target)) {
        setTerminalControlsOpen(false);
      }
    };
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setTerminalControlsOpen(false);
        focusSelectedTerminal();
      }
    };

    window.addEventListener("pointerdown", handlePointerDown);
    window.addEventListener("keydown", handleKeyDown);
    return () => {
      window.removeEventListener("pointerdown", handlePointerDown);
      window.removeEventListener("keydown", handleKeyDown);
    };
  }, [focusSelectedTerminal, setTerminalControlsOpen, terminalControlsOpen, terminalControlsRef]);
}
