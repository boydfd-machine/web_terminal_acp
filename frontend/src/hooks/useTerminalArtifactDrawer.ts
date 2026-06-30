import { useCallback, useEffect, useMemo, useRef, useState, type MutableRefObject } from "react";
import { useMutation, type QueryClient, type UseMutationResult, type UseQueryResult } from "@tanstack/react-query";

import { createTerminalArtifact } from "../api";
import {
  artifactTerminalCarrierStatusLabel,
  isActiveTerminalArtifact,
} from "../artifactTerminalCarrier";
import type { TerminalPaneHandle } from "../components/TerminalPane";
import type {
  TerminalArtifact,
  TerminalArtifactList,
} from "../types";

const ARTIFACT_MONITOR_PAGE_SIZE = 100;

type EnsureAuxTerminalReady = (variables: { clientId: string; windowId: string }) => void;

type FloatingTerminalWindow = {
  clientId: string;
  windowId: string;
  projectPath: string;
  title: string | null;
};

export type AuxTerminalDrawerTab = "terminal" | "todo";

type UseTerminalArtifactDrawerArgs = {
  artifactQuickOpenOpen: boolean;
  selectedArtifactTerminalId: string | null;
  artifactTerminalCarrier: TerminalArtifact | null;
  artifactTerminalMonitorQuery: UseQueryResult<TerminalArtifactList, Error>;
  auxTerminalPaneRef: MutableRefObject<TerminalPaneHandle | null>;
  auxTerminalWindowMetrics: {
    width: number;
    height: number;
    minHeight: number;
  };
  ensureAuxTerminalReady: EnsureAuxTerminalReady;
  focusSelectedTerminal: () => void;
  queryClient: QueryClient;
  selectedClientId: string | null;
  selectedWindowId: string | null;
  setAgentRecordModalOpen: (open: boolean) => void;
  setArtifactQuickOpenOpen: (open: boolean) => void;
  setClientSwitcherOpen: (open: boolean) => void;
  setGitDiffBrowserOpen: (open: boolean) => void;
  setNotificationCenterOpen: (open: boolean) => void;
  setProjectTerminalPickerOpen: (open: boolean) => void;
  setSettingsOpen: (open: boolean) => void;
  setTerminalControlsOpen: (open: boolean) => void;
  setTerminalSwitcherOpen: (open: boolean) => void;
  setSelectedArtifactTerminalId: (artifactId: string | null) => void;
};

type TerminalArtifactDrawerState = {
  artifactQuickOpenOpen: boolean;
  artifactResultViewerArtifact: TerminalArtifact | null;
  artifactTerminalStatus: string;
  artifactTerminalTitle: string;
  artifactTerminalWindowId: string | null;
  auxTerminalMounted: boolean;
  auxTerminalOpen: boolean;
  activeAuxTerminalTab: AuxTerminalDrawerTab;
  auxTerminalTabsVisible: boolean;
  generateTraceMutation: UseMutationResult<TerminalArtifact, Error, { clientId: string; windowId: string }>;
  selectedArtifactTerminalId: string | null;
  terminalWindowPaneRef: MutableRefObject<TerminalPaneHandle | null>;
  terminalDrawerMode: "artifact" | "aux" | "terminal";
  terminalDrawerMounted: boolean;
  terminalDrawerOpen: boolean;
  terminalWindowClientId: string | null;
  terminalWindowId: string | null;
  terminalWindowProjectPath: string | null;
  terminalWindowTitle: string | null;
  terminalPaneLayoutVersion: string;
  closeTerminalDrawer: () => void;
  openArtifactResult: (artifact: TerminalArtifact) => void;
  openArtifactTerminal: (artifact: TerminalArtifact) => void;
  openTerminalWindow: (target: FloatingTerminalWindow) => void;
  setArtifactResultViewerArtifact: (artifact: TerminalArtifact | null) => void;
  setAuxTerminalMounted: (mounted: boolean) => void;
  setAuxTerminalOpen: (open: boolean) => void;
  selectAuxTerminalTab: (tab: AuxTerminalDrawerTab) => void;
  switchAuxTerminalTab: (direction: "previous" | "next") => void;
  toggleAuxTerminal: () => void;
  triggerArtifactQuickOpen: () => void;
  triggerGenerateTrace: () => void;
};

export function useTerminalArtifactDrawer({
  artifactQuickOpenOpen,
  selectedArtifactTerminalId,
  artifactTerminalCarrier,
  artifactTerminalMonitorQuery,
  auxTerminalPaneRef,
  auxTerminalWindowMetrics,
  ensureAuxTerminalReady,
  focusSelectedTerminal,
  queryClient,
  selectedClientId,
  selectedWindowId,
  setAgentRecordModalOpen,
  setArtifactQuickOpenOpen,
  setClientSwitcherOpen,
  setGitDiffBrowserOpen,
  setNotificationCenterOpen,
  setProjectTerminalPickerOpen,
  setSettingsOpen,
  setTerminalControlsOpen,
  setTerminalSwitcherOpen,
  setSelectedArtifactTerminalId,
}: UseTerminalArtifactDrawerArgs): TerminalArtifactDrawerState {
  const [auxTerminalOpen, setAuxTerminalOpen] = useState(false);
  const [auxTerminalMounted, setAuxTerminalMounted] = useState(false);
  const [artifactTerminalSuppressedByAux, setArtifactTerminalSuppressedByAux] = useState(false);
  const [artifactResultViewerArtifact, setArtifactResultViewerArtifact] = useState<TerminalArtifact | null>(null);
  const [terminalWindowTarget, setTerminalWindowTarget] = useState<FloatingTerminalWindow | null>(null);
  const [terminalWindowOpen, setTerminalWindowOpen] = useState(false);
  const [activeAuxTerminalTab, setActiveAuxTerminalTab] = useState<AuxTerminalDrawerTab>("terminal");
  const terminalWindowPaneRef = useRef<TerminalPaneHandle | null>(null);
  const auxTerminalSelectionRef = useRef<{ clientId: string | null; windowId: string | null }>({
    clientId: null,
    windowId: null,
  });

  const artifactTerminalVisible = artifactTerminalCarrier !== null && !artifactTerminalSuppressedByAux;
  const auxTerminalTabsVisible = !artifactTerminalVisible && auxTerminalOpen && terminalWindowTarget !== null;
  const terminalDrawerMode = artifactTerminalVisible
    ? "artifact"
    : auxTerminalTabsVisible
      ? activeAuxTerminalTab === "todo" ? "terminal" : "aux"
      : terminalWindowOpen || (terminalWindowTarget !== null && !auxTerminalOpen) ? "terminal" : "aux";
  const terminalDrawerOpen = terminalWindowOpen || auxTerminalOpen || artifactTerminalVisible;
  const terminalDrawerMounted = terminalWindowTarget !== null || auxTerminalMounted || artifactTerminalCarrier !== null;
  const artifactTerminalWindowId = artifactTerminalCarrier?.ephemeral_window_id ?? null;
  const artifactTerminalTitle = artifactTerminalCarrier?.title ?? "Artifact terminal";
  const artifactTerminalStatus = artifactTerminalCarrier === null
    ? ""
    : artifactTerminalCarrierStatusLabel(artifactTerminalCarrier);
  const terminalPaneLayoutVersion = useMemo(() => [
    terminalDrawerOpen ? "open" : "closed",
    auxTerminalWindowMetrics.width,
    auxTerminalWindowMetrics.height,
    auxTerminalWindowMetrics.minHeight,
    activeAuxTerminalTab,
  ].join(":"), [
    activeAuxTerminalTab,
    auxTerminalWindowMetrics.height,
    auxTerminalWindowMetrics.minHeight,
    auxTerminalWindowMetrics.width,
    terminalDrawerOpen,
  ]);

  const focusAuxTerminal = useCallback(() => {
    requestAnimationFrame(() => {
      auxTerminalPaneRef.current?.refit();
      auxTerminalPaneRef.current?.focus();
    });
  }, [auxTerminalPaneRef]);

  const focusTerminalWindow = useCallback(() => {
    requestAnimationFrame(() => {
      terminalWindowPaneRef.current?.refit();
      terminalWindowPaneRef.current?.focus();
    });
  }, []);

  const selectAuxTerminalTab = useCallback((tab: AuxTerminalDrawerTab) => {
    if (tab === "terminal" && !auxTerminalOpen) {
      return;
    }
    if (tab === "todo" && terminalWindowTarget === null) {
      return;
    }
    setActiveAuxTerminalTab(tab);
    if (tab === "terminal") {
      focusAuxTerminal();
      return;
    }
    focusTerminalWindow();
  }, [auxTerminalOpen, focusAuxTerminal, focusTerminalWindow, terminalWindowTarget]);

  const switchAuxTerminalTab = useCallback((direction: "previous" | "next") => {
    if (!auxTerminalTabsVisible) {
      return;
    }
    selectAuxTerminalTab(direction === "previous" ? "terminal" : "todo");
  }, [auxTerminalTabsVisible, selectAuxTerminalTab]);

  const closeOverlaysForDrawer = useCallback(() => {
    setTerminalControlsOpen(false);
    setTerminalSwitcherOpen(false);
    setClientSwitcherOpen(false);
    setProjectTerminalPickerOpen(false);
    setNotificationCenterOpen(false);
    setSettingsOpen(false);
    setAgentRecordModalOpen(false);
    setGitDiffBrowserOpen(false);
  }, [
    setAgentRecordModalOpen,
    setClientSwitcherOpen,
    setGitDiffBrowserOpen,
    setNotificationCenterOpen,
    setProjectTerminalPickerOpen,
    setSettingsOpen,
    setTerminalControlsOpen,
    setTerminalSwitcherOpen,
  ]);

  const openArtifactTerminal = useCallback((artifact: TerminalArtifact) => {
    if (!isActiveTerminalArtifact(artifact)) {
      return;
    }

    queryClient.setQueryData<TerminalArtifactList>(
      ["terminal-artifacts", artifact.client_id, artifact.virtual_window_id, "carrier"],
      (current) => {
        const currentArtifacts = current?.artifacts ?? [];
        const nextArtifacts = currentArtifacts.some((candidate) => candidate.id === artifact.id)
          ? currentArtifacts.map((candidate) => (candidate.id === artifact.id ? artifact : candidate))
          : [artifact, ...currentArtifacts];
        return {
          window_id: artifact.virtual_window_id,
          artifact_scope: artifact.artifact_scope,
          project_path: artifact.project_path,
          artifacts: nextArtifacts,
          total: Math.max(current?.total ?? 0, nextArtifacts.length),
          limit: current?.limit ?? ARTIFACT_MONITOR_PAGE_SIZE,
          offset: current?.offset ?? 0,
          has_more: current?.has_more ?? false,
        };
      }
    );
    void queryClient.invalidateQueries({
      queryKey: ["terminal-artifacts", artifact.client_id, artifact.virtual_window_id],
      exact: false,
    });
    setSelectedArtifactTerminalId(artifact.id);
    setArtifactTerminalSuppressedByAux(false);
    setActiveAuxTerminalTab("terminal");
    setArtifactQuickOpenOpen(false);
    closeOverlaysForDrawer();
    setTerminalWindowOpen(false);
    setAuxTerminalOpen(false);
    requestAnimationFrame(() => {
      auxTerminalPaneRef.current?.refit();
    });
  }, [auxTerminalPaneRef, closeOverlaysForDrawer, queryClient]);

  const openArtifactResult = useCallback((artifact: TerminalArtifact) => {
    if (artifact.status.toUpperCase() !== "SUCCEEDED") {
      return;
    }
    setArtifactResultViewerArtifact(artifact);
    setArtifactQuickOpenOpen(false);
    closeOverlaysForDrawer();
  }, [closeOverlaysForDrawer]);

  const openTerminalWindow = useCallback((target: FloatingTerminalWindow) => {
    closeOverlaysForDrawer();
    setSelectedArtifactTerminalId(null);
    setArtifactTerminalSuppressedByAux(false);
    setTerminalWindowTarget(target);
    setTerminalWindowOpen(true);
    setActiveAuxTerminalTab("todo");
    focusTerminalWindow();
  }, [closeOverlaysForDrawer, focusTerminalWindow, setSelectedArtifactTerminalId]);

  const triggerArtifactQuickOpen = useCallback(() => {
    if (selectedClientId === null || selectedWindowId === null) {
      return;
    }

    closeOverlaysForDrawer();
    void queryClient.invalidateQueries({
      queryKey: ["terminal-artifacts", selectedClientId, selectedWindowId],
      exact: false,
    });
    setArtifactQuickOpenOpen(true);
  }, [closeOverlaysForDrawer, queryClient, selectedClientId, selectedWindowId]);

  const toggleAuxTerminal = useCallback(() => {
    if (selectedClientId === null || selectedWindowId === null) {
      return;
    }

    closeOverlaysForDrawer();
    const nextOpen = !auxTerminalOpen;
    if (nextOpen) {
      if (artifactTerminalCarrier !== null) {
        setArtifactTerminalSuppressedByAux(true);
      }
      setAuxTerminalMounted(true);
      setActiveAuxTerminalTab("terminal");
      ensureAuxTerminalReady({ clientId: selectedClientId, windowId: selectedWindowId });
      focusAuxTerminal();
    } else if (terminalWindowOpen) {
      setActiveAuxTerminalTab("todo");
      focusTerminalWindow();
    } else if (artifactTerminalCarrier !== null) {
      setArtifactTerminalSuppressedByAux(false);
      focusAuxTerminal();
    } else {
      focusSelectedTerminal();
    }
    setAuxTerminalOpen(nextOpen);
  }, [
    artifactTerminalCarrier,
    auxTerminalOpen,
    closeOverlaysForDrawer,
    ensureAuxTerminalReady,
    focusAuxTerminal,
    focusSelectedTerminal,
    focusTerminalWindow,
    selectedClientId,
    selectedWindowId,
    terminalWindowOpen,
  ]);

  const closeTerminalDrawer = useCallback(() => {
    if (terminalDrawerMode === "terminal") {
      setTerminalWindowOpen(false);
      if (auxTerminalOpen) {
        setActiveAuxTerminalTab("terminal");
        focusAuxTerminal();
      } else {
        focusSelectedTerminal();
      }
      return;
    }
    if (terminalDrawerMode === "artifact") {
      setSelectedArtifactTerminalId(null);
      setArtifactTerminalSuppressedByAux(false);
      if (auxTerminalOpen) {
        focusAuxTerminal();
      } else {
        focusSelectedTerminal();
      }
      return;
    }
    if (artifactTerminalCarrier !== null) {
      setAuxTerminalOpen(false);
      setArtifactTerminalSuppressedByAux(false);
      focusAuxTerminal();
      return;
    }
    if (terminalWindowOpen) {
      setAuxTerminalOpen(false);
      setActiveAuxTerminalTab("todo");
      focusTerminalWindow();
      return;
    }
    setAuxTerminalOpen(false);
    focusSelectedTerminal();
  }, [
    artifactTerminalCarrier,
    auxTerminalOpen,
    focusAuxTerminal,
    focusSelectedTerminal,
    focusTerminalWindow,
    terminalDrawerMode,
    terminalWindowOpen,
  ]);

  const generateTraceMutation = useMutation({
    mutationFn: ({ clientId, windowId }: { clientId: string; windowId: string }) => (
      createTerminalArtifact(clientId, windowId, { artifact_kind: "agent_trace_graph" })
    ),
    onSuccess: (artifact, variables) => {
      void queryClient.invalidateQueries({
        queryKey: ["terminal-artifacts", variables.clientId, variables.windowId],
        exact: false,
      });
      openArtifactTerminal(artifact);
    },
  });

  const triggerGenerateTrace = useCallback(() => {
    if (selectedClientId === null || selectedWindowId === null || generateTraceMutation.isPending) {
      return;
    }
    generateTraceMutation.mutate({ clientId: selectedClientId, windowId: selectedWindowId });
  }, [generateTraceMutation, selectedClientId, selectedWindowId]);

  useEffect(() => {
    setAuxTerminalOpen(false);
    setAuxTerminalMounted(false);
    setTerminalWindowOpen(false);
    setTerminalWindowTarget(null);
    setActiveAuxTerminalTab("terminal");
  }, [selectedClientId]);

  useEffect(() => {
    setSelectedArtifactTerminalId(null);
    setArtifactTerminalSuppressedByAux(false);
    setArtifactQuickOpenOpen(false);
    setArtifactResultViewerArtifact(null);
  }, [selectedClientId, selectedWindowId, setArtifactQuickOpenOpen, setSelectedArtifactTerminalId]);

  useEffect(() => {
    if (selectedArtifactTerminalId === null) {
      return;
    }
    if (artifactTerminalMonitorQuery.isFetching && artifactTerminalMonitorQuery.data === undefined) {
      return;
    }
    const selectedArtifactStillActive = artifactTerminalMonitorQuery.data?.artifacts.some((artifact) => (
      artifact.id === selectedArtifactTerminalId
      && isActiveTerminalArtifact(artifact)
    )) ?? false;
    if (!selectedArtifactStillActive) {
      setSelectedArtifactTerminalId(null);
      setArtifactTerminalSuppressedByAux(false);
      if (!auxTerminalOpen) {
        setAuxTerminalMounted(false);
      }
    }
  }, [
    artifactTerminalMonitorQuery.data,
    artifactTerminalMonitorQuery.isFetching,
    auxTerminalOpen,
    selectedArtifactTerminalId,
  ]);

  useEffect(() => {
    const previousSelection = auxTerminalSelectionRef.current;
    const selectionChanged = (
      previousSelection.clientId !== selectedClientId
      || previousSelection.windowId !== selectedWindowId
    );
    auxTerminalSelectionRef.current = { clientId: selectedClientId, windowId: selectedWindowId };
    if (selectedClientId === null || selectedWindowId === null) {
      setAuxTerminalOpen(false);
      setAuxTerminalMounted(false);
      return;
    }
    if (selectionChanged && !auxTerminalOpen) {
      setAuxTerminalMounted(false);
    }
  }, [auxTerminalOpen, selectedClientId, selectedWindowId]);

  return {
    artifactQuickOpenOpen,
    artifactResultViewerArtifact,
    artifactTerminalStatus,
    artifactTerminalTitle,
    artifactTerminalWindowId,
    activeAuxTerminalTab,
    auxTerminalMounted,
    auxTerminalOpen,
    auxTerminalTabsVisible,
    closeTerminalDrawer,
    generateTraceMutation,
    openArtifactResult,
    openArtifactTerminal,
    openTerminalWindow,
    selectedArtifactTerminalId,
    setArtifactResultViewerArtifact,
    setAuxTerminalMounted,
    setAuxTerminalOpen,
    selectAuxTerminalTab,
    switchAuxTerminalTab,
    terminalDrawerMode,
    terminalDrawerMounted,
    terminalDrawerOpen,
    terminalWindowPaneRef,
    terminalWindowClientId: terminalWindowTarget?.clientId ?? null,
    terminalWindowId: terminalWindowTarget?.windowId ?? null,
    terminalWindowProjectPath: terminalWindowTarget?.projectPath ?? null,
    terminalWindowTitle: terminalWindowTarget?.title ?? null,
    terminalPaneLayoutVersion,
    toggleAuxTerminal,
    triggerArtifactQuickOpen,
    triggerGenerateTrace,
  };
}
