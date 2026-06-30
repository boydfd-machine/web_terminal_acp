import { useCallback } from "react";

import type {
  TerminalCreateContext,
  TerminalCreateSubmit,
} from "../components/TerminalCreateModal";
import type { AgentLaunchConfig } from "../types";
import {
  createWindowInputForGroupNode,
  type SwitcherGroupNode,
} from "../terminalGrouping";
import type { CreateWindowVariables } from "./useTerminalCreationMutations";

type CreateMutation = {
  mutate: (variables: CreateWindowVariables) => void;
};

type UseTerminalCreateActionsArgs = {
  createMutation: CreateMutation;
  selectedClientId: string | null;
  selectedClientOffline: boolean;
  terminalCreateBusy: boolean;
  terminalCreateContext: TerminalCreateContext | null;
  setProjectTerminalPickerOpen: (open: boolean) => void;
  setTerminalCreateContext: (context: TerminalCreateContext | null) => void;
  setTerminalSwitcherOpen: (open: boolean) => void;
};

function canCreateTerminal(
  selectedClientId: string | null,
  selectedClientOffline: boolean,
  terminalCreateBusy: boolean,
): selectedClientId is string {
  return selectedClientId !== null && !selectedClientOffline && !terminalCreateBusy;
}

export function useTerminalCreateActions({
  createMutation,
  selectedClientId,
  selectedClientOffline,
  terminalCreateBusy,
  terminalCreateContext,
  setProjectTerminalPickerOpen,
  setTerminalCreateContext,
  setTerminalSwitcherOpen,
}: UseTerminalCreateActionsArgs) {
  const triggerNewTerminalShortcut = useCallback(() => {
    if (!canCreateTerminal(selectedClientId, selectedClientOffline, terminalCreateBusy)) {
      return;
    }

    createMutation.mutate({
      clientId: selectedClientId,
      agent_launch: null,
    });
  }, [createMutation, selectedClientId, selectedClientOffline, terminalCreateBusy]);

  const triggerNewTerminalByProjectShortcut = useCallback(() => {
    if (!canCreateTerminal(selectedClientId, selectedClientOffline, terminalCreateBusy)) {
      return;
    }

    setProjectTerminalPickerOpen(true);
    setTerminalSwitcherOpen(false);
  }, [
    selectedClientId,
    selectedClientOffline,
    setProjectTerminalPickerOpen,
    setTerminalSwitcherOpen,
    terminalCreateBusy,
  ]);

  const handleCreateTerminalAtProjectPath = useCallback((
    projectPath: string,
    agentLaunch: AgentLaunchConfig | null,
  ) => {
    if (!canCreateTerminal(selectedClientId, selectedClientOffline, terminalCreateBusy)) {
      return;
    }

    createMutation.mutate({
      clientId: selectedClientId,
      cwd: projectPath,
      agent_launch: agentLaunch,
      afterCreate: () => setProjectTerminalPickerOpen(false),
    });
  }, [
    createMutation,
    selectedClientId,
    selectedClientOffline,
    setProjectTerminalPickerOpen,
    terminalCreateBusy,
  ]);

  const handleConfigureTerminalAtProjectPath = useCallback((projectPath: string, agentLaunch: AgentLaunchConfig) => {
    if (!canCreateTerminal(selectedClientId, selectedClientOffline, terminalCreateBusy)) {
      return;
    }

    setProjectTerminalPickerOpen(false);
    setTerminalCreateContext({
      title: "New terminal by project path",
      description: projectPath,
      cwd: projectPath,
      initialAgent: agentLaunch.agent,
      initialAgentCommand: agentLaunch.command ?? null,
      initialAgentModelSelection: agentLaunch.model_selection ?? null,
      initialAgentProfileId: agentLaunch.profile_id ?? null,
      showConfigInitially: true,
    });
  }, [
    selectedClientId,
    selectedClientOffline,
    setProjectTerminalPickerOpen,
    setTerminalCreateContext,
    terminalCreateBusy,
  ]);

  const handleCreateTerminalAtGroup = useCallback((node: SwitcherGroupNode) => {
    if (!canCreateTerminal(selectedClientId, selectedClientOffline, terminalCreateBusy)) {
      return;
    }

    const input = createWindowInputForGroupNode(node);
    createMutation.mutate({
      clientId: selectedClientId,
      cwd: input.cwd,
      folder_path: input.folder_path,
      agent_launch: null,
      afterCreate: () => {
        setTerminalSwitcherOpen(false);
      },
    });
  }, [createMutation, selectedClientId, selectedClientOffline, setTerminalSwitcherOpen, terminalCreateBusy]);

  const handleConfigureTerminalAtGroup = useCallback((node: SwitcherGroupNode) => {
    if (!canCreateTerminal(selectedClientId, selectedClientOffline, terminalCreateBusy)) {
      return;
    }

    const input = createWindowInputForGroupNode(node);
    setTerminalCreateContext({
      title: "New terminal",
      description: node.projectPath ?? node.topicPath ?? node.label,
      cwd: input.cwd,
      folder_path: input.folder_path,
      requireAgent: true,
      showConfigInitially: true,
      afterCreate: () => {
        setTerminalSwitcherOpen(false);
      },
    });
  }, [
    selectedClientId,
    selectedClientOffline,
    setTerminalCreateContext,
    setTerminalSwitcherOpen,
    terminalCreateBusy,
  ]);

  const handleCreateTerminalSubmit = useCallback((payload: TerminalCreateSubmit) => {
    if (!canCreateTerminal(selectedClientId, selectedClientOffline, terminalCreateBusy)) {
      return;
    }
    createMutation.mutate({
      clientId: selectedClientId,
      cwd: payload.cwd,
      folder_path: payload.folder_path,
      agent_launch: payload.agent_launch,
      afterCreate: terminalCreateContext?.afterCreate,
    });
  }, [createMutation, selectedClientId, selectedClientOffline, terminalCreateBusy, terminalCreateContext]);

  return {
    handleConfigureTerminalAtGroup,
    handleConfigureTerminalAtProjectPath,
    handleCreateTerminalAtGroup,
    handleCreateTerminalAtProjectPath,
    handleCreateTerminalSubmit,
    triggerNewTerminalByProjectShortcut,
    triggerNewTerminalShortcut,
  };
}
