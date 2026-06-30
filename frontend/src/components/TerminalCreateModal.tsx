import { type ReactNode, useCallback, useEffect, useId, useMemo, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";

import {
  fetchAgentClients,
  fetchAgentProfileConfig,
  fetchAgentProfiles,
  fetchClientAgentConfig,
  fetchClientSystemAgentConfig
} from "../api";
import { useI18n } from "../i18n";
import {
  readAgentModelSelectionSettings,
  type AgentModelSelectionSettings
} from "../userPreferences";
import {
  DEFAULT_AGENT_CLIENTS,
  agentClientOptions,
  agentClientCapability,
  agentDefaultCommand,
  agentLaunchOptions,
  configToSelection,
  isAgentLaunchKind,
  mergeSelectionWithConfigDefaults,
  readDefaultAgentCommands,
  selectedEnabledCount,
  selectionItemCount
} from "../agentLaunch";
import type { AgentLaunchMode } from "../agentLaunch";
import type { AgentConfigSelection, AgentLaunchConfig, AgentLaunchKind, AgentModelSelection } from "../types";
import { AgentModelSelectionPicker } from "./AgentModelSelectionPicker";
import { CursorOfficialModelPicker } from "./CursorOfficialModelPicker";
import { TerminalCreateConfigAccordion } from "./TerminalCreateConfigAccordion";
import {
  agentConfigSelectionsEqual,
  defaultModelSelection,
  mergeConfigWithSystemDefaults,
  selectionForConfig
} from "./terminalCreateModalLogic";
import { UiIcon } from "./UiIcon";
import { useOverlayFocus } from "./useOverlayFocus";

export type TerminalCreateContext = {
  title: string;
  description?: string;
  cwd?: string | null;
  folder_path?: string | null;
  initialAgent?: AgentLaunchKind;
  initialAgentCommand?: string | null;
  initialAgentModelSelection?: AgentModelSelection | null;
  initialAgentProfileId?: string | null;
  requireAgent?: boolean;
  showConfigInitially?: boolean;
  submitLabel?: string;
  afterCreate?: () => void;
};

export type TerminalCreateSubmit = {
  cwd?: string | null;
  folder_path?: string | null;
  agent_launch?: AgentLaunchConfig | null;
};

type TerminalCreateModalProps = {
  isOpen: boolean;
  clientId: string | null;
  context: TerminalCreateContext | null;
  children?: ReactNode;
  creatingTerminal?: boolean;
  createTerminalDisabled?: boolean;
  onClose: () => void;
  onSubmit: (payload: TerminalCreateSubmit) => void;
};

function terminalCreateContextKey(context: TerminalCreateContext | null): string | null {
  if (context === null) {
    return null;
  }
  return JSON.stringify([
    context.title,
    context.description ?? null,
    context.cwd ?? null,
    context.folder_path ?? null,
    context.initialAgent ?? null,
    context.initialAgentCommand ?? null,
    context.initialAgentModelSelection ?? null,
    context.initialAgentProfileId ?? null,
    context.requireAgent === true,
    context.showConfigInitially === true,
    context.submitLabel ?? null
  ]);
}

export function TerminalCreateModal({
  isOpen,
  clientId,
  context,
  children,
  creatingTerminal = false,
  createTerminalDisabled = false,
  onClose,
  onSubmit
}: TerminalCreateModalProps) {
  const { t } = useI18n();
  const [mode, setMode] = useState<AgentLaunchMode>("shell");
  const [commands, setCommands] = useState<Record<AgentLaunchKind, string>>(() => readDefaultAgentCommands());
  const [defaultModelSelections, setDefaultModelSelections] = useState<AgentModelSelectionSettings>(() => readAgentModelSelectionSettings());
  const [configPanelOpen, setConfigPanelOpen] = useState(false);
  const [selection, setSelection] = useState<AgentConfigSelection | null>(null);
  const [selectionOverride, setSelectionOverride] = useState(false);
  const [modelSelection, setModelSelection] = useState<AgentModelSelection | null>(null);
  const [selectedProfileId, setSelectedProfileId] = useState<string>("");
  const configPanelId = useId();
  const panelRef = useRef<HTMLElement | null>(null);
  const selectionDefaultsRef = useRef<AgentConfigSelection | null>(null);
  const initializedContextKeyRef = useRef<string | null>(null);
  const agentClientsQuery = useQuery({
    queryKey: ["agent-clients", clientId],
    queryFn: () => fetchAgentClients(clientId as string),
    enabled: isOpen && clientId !== null,
    staleTime: 60000
  });
  const agentClients = agentClientsQuery.data?.agent_clients ?? DEFAULT_AGENT_CLIENTS;
  const launchOptions = useMemo(
    () => context?.requireAgent === true ? agentClientOptions(agentClients, "launch") : agentLaunchOptions(agentClients),
    [agentClients, context?.requireAgent]
  );
  const profilesQuery = useQuery({
    queryKey: ["agent-profiles", clientId],
    queryFn: () => fetchAgentProfiles(clientId as string),
    enabled: isOpen && clientId !== null,
    staleTime: 10000
  });
  const profiles = profilesQuery.data?.profiles ?? [];
  const selectedProfile = profiles.find((profile) => profile.id === selectedProfileId) ?? null;
  const configSupported = isAgentLaunchKind(mode)
    ? agentClientCapability(mode, agentClients, "client_config")
    : false;
  const configQuery = useQuery({
    queryKey: ["client-agent-config", clientId, mode, selectedProfileId],
    queryFn: () => selectedProfile !== null
      ? fetchAgentProfileConfig(clientId as string, selectedProfile.id, mode as AgentLaunchKind)
      : fetchClientAgentConfig(clientId as string, mode as AgentLaunchKind),
    enabled: isOpen
      && clientId !== null
      && isAgentLaunchKind(mode)
      && configPanelOpen
      && configSupported
      && (selectedProfileId === "" || selectedProfile !== null),
    staleTime: 10000
  });
  const systemConfigQuery = useQuery({
    queryKey: ["client-system-agent-config", clientId],
    queryFn: () => fetchClientSystemAgentConfig(clientId as string),
    enabled: isOpen
      && clientId !== null
      && isAgentLaunchKind(mode)
      && configPanelOpen
      && configSupported
      && selectedProfileId === "",
    staleTime: 0,
    refetchOnMount: "always"
  });
  const launchConfig = useMemo(() => {
    if (selectedProfile !== null) {
      return configQuery.data ?? null;
    }
    if (systemConfigQuery.data === undefined) {
      return null;
    }
    return mergeConfigWithSystemDefaults(configQuery.data ?? null, systemConfigQuery.data);
  }, [configQuery.data, selectedProfile, systemConfigQuery.data]);
  const activeSelection = isAgentLaunchKind(mode) ? selectionForConfig(mode, selection) : null;
  const contextKey = terminalCreateContextKey(context);
  const contextInitialAgent = context?.initialAgent;
  const contextInitialAgentCommand = context?.initialAgentCommand?.trim() ?? "";
  const contextInitialAgentModelSelection = context?.initialAgentModelSelection ?? null;
  const contextInitialAgentProfileId = context?.initialAgentProfileId ?? "";
  const contextRequireAgent = context?.requireAgent === true;
  const contextShowConfigInitially = context?.showConfigInitially === true;

  useEffect(() => {
    if (!isOpen || contextKey === null) {
      initializedContextKeyRef.current = null;
      setMode("shell");
      setCommands(readDefaultAgentCommands());
      setConfigPanelOpen(false);
      setSelection(null);
      setSelectionOverride(false);
      selectionDefaultsRef.current = null;
      setModelSelection(null);
      setSelectedProfileId("");
      return;
    }

    if (initializedContextKeyRef.current === contextKey) {
      return;
    }

    initializedContextKeyRef.current = contextKey;
    const contextAgentIsLaunchable = contextInitialAgent !== undefined
      && launchOptions.some((option) => option.id === contextInitialAgent);
    const nextMode = contextAgentIsLaunchable
      ? contextInitialAgent
      : (contextRequireAgent ? launchOptions[0]?.id ?? "shell" : "shell");
    const nextDefaultModelSelections = readAgentModelSelectionSettings();
    const nextCommands = readDefaultAgentCommands();
    if (isAgentLaunchKind(nextMode) && contextInitialAgentCommand.length > 0) {
      nextCommands[nextMode] = contextInitialAgentCommand;
    }
    setMode(nextMode);
    setCommands(nextCommands);
    setDefaultModelSelections(nextDefaultModelSelections);
    setConfigPanelOpen(contextShowConfigInitially);
    setSelection(null);
    setSelectionOverride(false);
    selectionDefaultsRef.current = null;
    setModelSelection(contextInitialAgentModelSelection ?? defaultModelSelection(nextMode, nextDefaultModelSelections));
    setSelectedProfileId(contextInitialAgentProfileId);
  }, [
    contextInitialAgent,
    contextInitialAgentCommand,
    contextInitialAgentModelSelection,
    contextInitialAgentProfileId,
    contextKey,
    contextRequireAgent,
    contextShowConfigInitially,
    isOpen,
    launchOptions
  ]);

  useEffect(() => {
    if (!isOpen || context?.requireAgent !== true || launchOptions.length === 0) {
      return;
    }
    if (mode === "shell" || !launchOptions.some((option) => option.id === mode)) {
      setMode(launchOptions[0].id);
      setModelSelection(contextInitialAgentModelSelection ?? defaultModelSelection(launchOptions[0].id, defaultModelSelections));
      if (contextInitialAgentCommand.length > 0) {
        setCommands((current) => ({ ...current, [launchOptions[0].id]: contextInitialAgentCommand }));
      }
    }
  }, [context?.requireAgent, contextInitialAgentCommand, contextInitialAgentModelSelection, defaultModelSelections, isOpen, launchOptions, mode]);

  useEffect(() => {
    if (!isAgentLaunchKind(mode) || launchConfig === null) {
      return;
    }
    const nextDefaults = configToSelection(launchConfig);
    const previousDefaults = selectionDefaultsRef.current;
    setSelection((current) => {
      const nextSelection = mergeSelectionWithConfigDefaults(
        current,
        nextDefaults,
        previousDefaults
      );
      selectionDefaultsRef.current = nextDefaults;
      return nextSelection;
    });
    if (previousDefaults !== null && !agentConfigSelectionsEqual(previousDefaults, nextDefaults)) {
      setSelectionOverride(true);
    }
  }, [launchConfig, mode, selectedProfile]);

  useEffect(() => {
    if (!isAgentLaunchKind(mode) || selectedProfile !== null || selectedProfileId !== "") {
      return;
    }
    setSelection(null);
    setSelectionOverride(false);
  }, [mode, selectedProfile, selectedProfileId]);

  useEffect(() => {
    if (selectedProfileId === "" || selectedProfile !== null || profilesQuery.isLoading) {
      return;
    }
    setSelectedProfileId("");
  }, [profilesQuery.isLoading, selectedProfile, selectedProfileId]);

  const previousSelectedProfileIdRef = useRef<string>("");

  useEffect(() => {
    if (!isOpen || selectedProfile === null) {
      previousSelectedProfileIdRef.current = "";
      return;
    }
    // Only apply profile's default agent client when profile is first selected,
    // not when user manually changes agent client after selecting profile
    if (previousSelectedProfileIdRef.current !== selectedProfileId) {
      previousSelectedProfileIdRef.current = selectedProfileId;
      const selectedFromInitialContext = selectedProfileId === contextInitialAgentProfileId
        && (contextInitialAgent !== undefined || contextInitialAgentCommand.length > 0 || contextInitialAgentModelSelection !== null);
      if (!selectedFromInitialContext) {
        setMode(selectedProfile.default_agent_client);
        setModelSelection(defaultModelSelection(selectedProfile.default_agent_client, defaultModelSelections));
      }
      setSelection(null);
      setSelectionOverride(false);
      selectionDefaultsRef.current = null;
    }
  }, [
    contextInitialAgent,
    contextInitialAgentCommand,
    contextInitialAgentModelSelection,
    contextInitialAgentProfileId,
    defaultModelSelections,
    isOpen,
    selectedProfile,
    selectedProfileId
  ]);

  const command = isAgentLaunchKind(mode) ? commands[mode] ?? agentDefaultCommand(mode, agentClients) : "";
  const handleEscape = useCallback(() => {
    onClose();
  }, [onClose]);
  useOverlayFocus({
    isOpen: isOpen && context !== null,
    ref: panelRef,
    onEscape: handleEscape
  });
  const configSummary = useMemo(() => {
    if (!isAgentLaunchKind(mode)) {
      return t("terminal.create.config.unconfigured");
    }
    if (selectedProfile !== null) {
      return selectedProfile.name;
    }
    if (activeSelection === null) {
      return t("terminal.create.config.current");
    }
    const total = selectionItemCount(activeSelection);
    const enabled = selectedEnabledCount(activeSelection);
    return total > 0 ? t("terminal.create.config.enabledCount", { enabled, total }) : t("terminal.create.config.empty");
  }, [activeSelection, mode, selectedProfile, t]);

  if (!isOpen || context === null) {
    return null;
  }

  const canSubmit = clientId !== null
    && !creatingTerminal
    && !createTerminalDisabled
    && (context.requireAgent !== true || isAgentLaunchKind(mode));
  const submit = () => {
    if (!canSubmit) {
      return;
    }
    onSubmit({
      cwd: context.cwd ?? null,
      folder_path: context.folder_path ?? null,
      agent_launch: isAgentLaunchKind(mode)
        ? {
            agent: mode,
            command: command.trim() || agentDefaultCommand(mode, agentClients),
            config: selectionOverride ? activeSelection : null,
            ...(modelSelection !== null ? { model_selection: modelSelection } : {}),
            profile_id: selectedProfile?.id ?? (selectedProfileId.trim() || null)
          }
        : null
    });
  };
  return (
    <div
      className="terminal-create-modal-backdrop"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) {
          onClose();
        }
      }}
    >
      <section
        ref={panelRef}
        className="terminal-create-modal"
        data-onboarding-id="terminal-create-modal"
        role="dialog"
        aria-modal="true"
        aria-label={t("terminal.create.dialog")}
      >
        <div className="terminal-create-header">
          <div>
            <h2>{context.title}</h2>
            {context.description && <p className="muted">{context.description}</p>}
          </div>
          <button
            type="button"
            className="ui-icon-button"
            aria-label={t("terminal.create.close")}
            title={t("terminal.create.close")}
            onClick={onClose}
          >
            <UiIcon name="x" />
          </button>
        </div>

        <div className="terminal-create-body">
          <div className="terminal-create-agent-tabs" role="tablist" aria-label={t("terminal.create.agent")}>
            {launchOptions.map((option) => (
              <button
                key={option.id}
                type="button"
                className={mode === option.id ? "active" : undefined}
                aria-selected={mode === option.id}
                onClick={() => {
                  setMode(option.id);
                  setConfigPanelOpen(false);
                  setSelection(null);
                  setSelectionOverride(false);
                  selectionDefaultsRef.current = null;
                  setModelSelection(defaultModelSelection(option.id, defaultModelSelections));
                }}
              >
                {option.label}
              </button>
            ))}
          </div>

          {isAgentLaunchKind(mode) && (
            <>
              <label className="settings-field">
                <span>{t("terminal.create.agent")}</span>
                <select
                  value={selectedProfileId}
                  onChange={(event) => {
                    const nextProfileId = event.target.value;
                    const nextProfile = profiles.find((profile) => profile.id === nextProfileId) ?? null;
                    setSelectedProfileId(nextProfileId);
                    if (nextProfile !== null) {
                      setMode(nextProfile.default_agent_client);
                      setConfigPanelOpen(false);
                    }
                    setSelection(null);
                    setSelectionOverride(false);
                    selectionDefaultsRef.current = null;
                    setModelSelection(nextProfile !== null ? defaultModelSelection(nextProfile.default_agent_client, defaultModelSelections) : defaultModelSelection(mode, defaultModelSelections));
                  }}
                  disabled={profilesQuery.isLoading}
                >
                  <option value="">{t("terminal.create.directAgentClient")}</option>
                  {profiles.map((profile) => (
                    <option key={profile.id} value={profile.id}>
                      {profile.name}
                    </option>
                  ))}
                </select>
              </label>
              <label className="settings-field">
                <span>{t("terminal.create.command")}</span>
                <input
                  value={command}
                  onChange={(event) => setCommands((current) => ({ ...current, [mode]: event.target.value }))}
                  placeholder={agentDefaultCommand(mode, agentClients)}
                />
              </label>
              <AgentModelSelectionPicker
                agent={mode}
                value={modelSelection}
                onChange={setModelSelection}
              />
              {mode === "cursor" && (
                <CursorOfficialModelPicker
                  clientId={clientId}
                  value={modelSelection}
                  onChange={setModelSelection}
                />
              )}
              {configSupported && (
                <TerminalCreateConfigAccordion
                  config={launchConfig}
                  configSummary={configSummary}
                  expanded={configPanelOpen}
                  isLoading={configQuery.isLoading || (selectedProfile === null && systemConfigQuery.isLoading)}
                  isError={configQuery.isError || (selectedProfile === null && systemConfigQuery.isError)}
                  isFetching={configQuery.isFetching || (selectedProfile === null && systemConfigQuery.isFetching)}
                  panelId={configPanelId}
                  selection={activeSelection}
                  onToggle={() => setConfigPanelOpen((open) => !open)}
                  onSelectionChange={(nextSelection) => {
                    setSelection(nextSelection);
                    setSelectionOverride(true);
                  }}
                />
              )}
            </>
          )}

          {children}
        </div>

        <div className="terminal-create-actions">
          <button
            type="button"
            className="ui-icon-button"
            aria-label={t("terminal.create.cancel")}
            title={t("terminal.create.cancel")}
            onClick={onClose}
          >
            <UiIcon name="x" />
          </button>
          <button type="button" disabled={!canSubmit} onClick={submit}>
            {creatingTerminal && <span className="terminal-create-progress-spinner" aria-hidden="true" />}
            <span>{creatingTerminal ? t("terminal.create.creating") : context.submitLabel ?? t("terminal.create.submit")}</span>
          </button>
        </div>
      </section>
    </div>
  );
}
