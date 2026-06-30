import { useCallback, useEffect, useRef, useState } from "react";
import { useMutation, type QueryClient } from "@tanstack/react-query";

import {
  cloneWindow,
  createWindow,
  fetchWindow,
} from "../api";
import type { DetailContext, TerminalRouteSelection } from "../appState";
import { writeTerminalRoute } from "../appState";
import { projectPathForWindow } from "../terminalTree";
import {
  terminalRuntimeReadiness,
  waitForTerminalRuntime,
} from "../terminalCreateReadiness";
import type { AgentLaunchConfig, VirtualWindow } from "../types";
import { markTerminalListsStale } from "../uiEvents";

export type CloneWindowVariables = {
  clientId: string;
  windowId: string;
};

export type CreateWindowVariables = {
  clientId: string;
  cwd?: string | null;
  folder_path?: string | null;
  agent_launch?: AgentLaunchConfig | null;
  afterCreate?: () => void;
};

type PendingTerminalCreate = {
  clientId: string;
  windowId: string;
  title: string;
};

type UseTerminalCreationMutationsArgs = {
  focusSelectedTerminal: () => void;
  persistTerminalRecent: (clientId: string, windowId: string, title: string) => void;
  queryClient: QueryClient;
  rememberClientUse: (clientId: string) => void;
  rememberClientWindowSelection: (clientId: string, windowId: string | null) => void;
  setAgentRecordModalOpen: (open: boolean) => void;
  setDeferredTreeSelection: (selection: TerminalRouteSelection | null) => void;
  setDetailContext: (context: DetailContext) => void;
  setMobileTerminalActive: (active: boolean) => void;
  setPendingTerminalCreateSurfaceClosed: () => void;
  setRouteSelectionRequest: (selection: TerminalRouteSelection | null) => void;
  setSelectedClientId: (clientId: string) => void;
  setSelectedProjectPath: (projectPath: string | null) => void;
  setSelectedWindowId: (windowId: string) => void;
  setTerminalControlsOpen: (open: boolean) => void;
};

export function useTerminalCreationMutations({
  focusSelectedTerminal,
  persistTerminalRecent,
  queryClient,
  rememberClientUse,
  rememberClientWindowSelection,
  setAgentRecordModalOpen,
  setDeferredTreeSelection,
  setDetailContext,
  setMobileTerminalActive,
  setPendingTerminalCreateSurfaceClosed,
  setRouteSelectionRequest,
  setSelectedClientId,
  setSelectedProjectPath,
  setSelectedWindowId,
  setTerminalControlsOpen,
}: UseTerminalCreationMutationsArgs) {
  const [pendingTerminalCreate, setPendingTerminalCreate] = useState<PendingTerminalCreate | null>(null);
  const [cloneTerminalStatus, setCloneTerminalStatus] = useState<"idle" | "success">("idle");
  const terminalCreateWaitRef = useRef(0);
  const cloneTerminalStatusTimerRef = useRef<ReturnType<typeof globalThis.setTimeout> | null>(null);

  const selectCreatedTerminal = useCallback((window: VirtualWindow, mode: "push" | "replace" = "push") => {
    setSelectedClientId(window.client_id);
    setSelectedWindowId(window.id);
    setSelectedProjectPath(projectPathForWindow(window));
    setDetailContext("terminal");
    rememberClientUse(window.client_id);
    rememberClientWindowSelection(window.client_id, window.id);
    setRouteSelectionRequest(null);
    setDeferredTreeSelection({ clientId: window.client_id, windowId: window.id });
    setMobileTerminalActive(true);
    setAgentRecordModalOpen(false);
    writeTerminalRoute(window.client_id, window.id, mode);
    persistTerminalRecent(window.client_id, window.id, window.title);
    focusSelectedTerminal();
  }, [
    focusSelectedTerminal,
    persistTerminalRecent,
    rememberClientUse,
    rememberClientWindowSelection,
    setAgentRecordModalOpen,
    setDeferredTreeSelection,
    setDetailContext,
    setMobileTerminalActive,
    setRouteSelectionRequest,
    setSelectedClientId,
    setSelectedProjectPath,
    setSelectedWindowId,
  ]);

  const createMutation = useMutation({
    mutationFn: (variables: CreateWindowVariables) =>
      createWindow(variables.clientId, {
        cwd: variables.cwd,
        folder_path: variables.folder_path,
        agent_launch: variables.agent_launch,
      }),
    onSuccess: async (window, variables) => {
      const waitId = terminalCreateWaitRef.current + 1;
      terminalCreateWaitRef.current = waitId;
      queryClient.setQueryData(["window", window.client_id, window.id], window);
      markTerminalListsStale(queryClient, window.client_id);

      let createSurfacesClosed = false;
      const closeCreateSurfaces = () => {
        if (createSurfacesClosed) {
          return;
        }
        createSurfacesClosed = true;
        setPendingTerminalCreateSurfaceClosed();
        variables.afterCreate?.();
      };

      try {
        const shouldWaitForRuntime = terminalRuntimeReadiness(window) === "pending";
        if (shouldWaitForRuntime) {
          setPendingTerminalCreate({
            clientId: window.client_id,
            windowId: window.id,
            title: window.title,
          });
          setMobileTerminalActive(true);
          closeCreateSurfaces();
        }
        const readyWindow = shouldWaitForRuntime
          ? await waitForTerminalRuntime(window, fetchWindow)
          : window;
        if (terminalCreateWaitRef.current !== waitId) {
          return;
        }

        queryClient.setQueryData(["window", readyWindow.client_id, readyWindow.id], readyWindow);
        markTerminalListsStale(queryClient, readyWindow.client_id);
        selectCreatedTerminal(readyWindow);
        closeCreateSurfaces();
      } catch {
        if (terminalCreateWaitRef.current === waitId) {
          selectCreatedTerminal(window);
          closeCreateSurfaces();
        }
      } finally {
        if (terminalCreateWaitRef.current === waitId) {
          setPendingTerminalCreate(null);
        }
      }
    },
    onError: () => {
      terminalCreateWaitRef.current += 1;
      setPendingTerminalCreate(null);
    },
  });

  const cloneMutation = useMutation({
    mutationFn: ({ clientId, windowId }: CloneWindowVariables) =>
      cloneWindow(clientId, windowId, { mode: "linked" }),
    onMutate: () => {
      if (cloneTerminalStatusTimerRef.current !== null) {
        globalThis.clearTimeout(cloneTerminalStatusTimerRef.current);
        cloneTerminalStatusTimerRef.current = null;
      }
      setCloneTerminalStatus("idle");
    },
    onSuccess: async (createdWindow) => {
      const waitId = terminalCreateWaitRef.current + 1;
      terminalCreateWaitRef.current = waitId;
      const markCloneDone = () => {
        setCloneTerminalStatus("success");
        if (cloneTerminalStatusTimerRef.current !== null) {
          globalThis.clearTimeout(cloneTerminalStatusTimerRef.current);
        }
        cloneTerminalStatusTimerRef.current = globalThis.setTimeout(() => {
          setCloneTerminalStatus("idle");
          cloneTerminalStatusTimerRef.current = null;
        }, 2000);
      };
      queryClient.setQueryData(["window", createdWindow.client_id, createdWindow.id], createdWindow);
      markTerminalListsStale(queryClient, createdWindow.client_id);
      setTerminalControlsOpen(false);

      try {
        const readyWindow = terminalRuntimeReadiness(createdWindow) === "pending"
          ? await waitForTerminalRuntime(createdWindow, fetchWindow)
          : createdWindow;
        if (terminalCreateWaitRef.current !== waitId) {
          return;
        }
        queryClient.setQueryData(["window", readyWindow.client_id, readyWindow.id], readyWindow);
        markTerminalListsStale(queryClient, readyWindow.client_id);
        selectCreatedTerminal(readyWindow);
        markCloneDone();
      } catch {
        if (terminalCreateWaitRef.current === waitId) {
          selectCreatedTerminal(createdWindow);
          markCloneDone();
        }
      }
    },
    onError: () => {
      setCloneTerminalStatus("idle");
    },
  });

  useEffect(() => {
    return () => {
      if (cloneTerminalStatusTimerRef.current !== null) {
        globalThis.clearTimeout(cloneTerminalStatusTimerRef.current);
      }
    };
  }, []);

  return {
    cloneMutation,
    cloneTerminalStatus,
    createMutation,
    pendingTerminalCreate,
    selectCreatedTerminal,
    terminalCloneBusy: cloneMutation.isPending,
    terminalCreateBusy: createMutation.isPending || pendingTerminalCreate !== null,
  };
}
