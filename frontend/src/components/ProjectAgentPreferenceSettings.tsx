import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { DEFAULT_AGENT_CLIENTS, agentClientOptions } from "../agentLaunch";
import { fetchAgentClients, fetchAgentProfiles, updateProjectAgentPreference } from "../api";
import { useI18n } from "../i18n";
import type { AgentLaunchKind, AgentModelSelection, ProjectAgentPreference } from "../types";
import { AgentModelSelectionPicker } from "./AgentModelSelectionPicker";
import { CursorOfficialModelPicker } from "./CursorOfficialModelPicker";

type ProjectAgentPreferenceSettingsProps = {
  clientId: string;
  projectPath: string;
  value?: ProjectAgentPreference | null;
};

function emptyToNull(value: string): string | null {
  const trimmed = value.trim();
  return trimmed.length === 0 ? null : trimmed;
}

function preferenceDraft(
  agentProfileId: string,
  agentClient: string,
  agentCommand: string,
  agentModelSelection: AgentModelSelection | null
): ProjectAgentPreference {
  return {
    agent_profile_id: emptyToNull(agentProfileId),
    agent_client: emptyToNull(agentClient),
    agent_command: emptyToNull(agentCommand),
    agent_model_selection: agentModelSelection
  };
}

export function ProjectAgentPreferenceSettings({
  clientId,
  projectPath,
  value = null
}: ProjectAgentPreferenceSettingsProps) {
  const { t } = useI18n();
  const queryClient = useQueryClient();
  const [agentProfileId, setAgentProfileId] = useState(value?.agent_profile_id ?? "");
  const [agentClient, setAgentClient] = useState(value?.agent_client ?? "");
  const [agentCommand, setAgentCommand] = useState(value?.agent_command ?? "");
  const [agentModelSelection, setAgentModelSelection] = useState<AgentModelSelection | null>(value?.agent_model_selection ?? null);

  useEffect(() => {
    setAgentProfileId(value?.agent_profile_id ?? "");
    setAgentClient(value?.agent_client ?? "");
    setAgentCommand(value?.agent_command ?? "");
    setAgentModelSelection(value?.agent_model_selection ?? null);
  }, [value]);

  const agentClientsQuery = useQuery({
    queryKey: ["agent-clients", clientId],
    queryFn: () => fetchAgentClients(clientId),
    staleTime: 60000
  });
  const profilesQuery = useQuery({
    queryKey: ["agent-profiles", clientId],
    queryFn: () => fetchAgentProfiles(clientId),
    staleTime: 10000
  });
  const agentClients = agentClientsQuery.data?.agent_clients ?? DEFAULT_AGENT_CLIENTS;
  const agentOptions = useMemo(() => agentClientOptions(agentClients, "launch"), [agentClients]);
  const profiles = profilesQuery.data?.profiles ?? [];
  const selectedAgent = agentOptions.some((option) => option.id === agentClient)
    ? agentClient as AgentLaunchKind
    : null;
  const selectedProfileMissing = agentProfileId !== "" && !profiles.some((profile) => profile.id === agentProfileId);
  const selectedAgentMissing = agentClient !== "" && !agentOptions.some((option) => option.id === agentClient);
  const saveMutation = useMutation({
    mutationFn: () => updateProjectAgentPreference(
      clientId,
      projectPath,
      preferenceDraft(agentProfileId, agentClient, agentCommand, agentModelSelection)
    ),
    onSuccess: (saved) => {
      setAgentProfileId(saved.agent_profile_id ?? "");
      setAgentClient(saved.agent_client ?? "");
      setAgentCommand(saved.agent_command ?? "");
      setAgentModelSelection(saved.agent_model_selection ?? null);
      void queryClient.invalidateQueries({ queryKey: ["project", clientId, projectPath], exact: false });
      void queryClient.invalidateQueries({ queryKey: ["projects", clientId], exact: false });
    }
  });

  return (
    <section className="project-agent-preference-settings" aria-label={t("project.agentPreference.title")}>
      <h4>{t("project.agentPreference.title")}</h4>
      <div className="project-agent-preference-grid">
        <label className="settings-field">
          <span>{t("project.agentPreference.profile")}</span>
          <select
            aria-label={t("project.agentPreference.profile")}
            value={agentProfileId}
            onChange={(event) => setAgentProfileId(event.target.value)}
            disabled={profilesQuery.isLoading}
          >
            <option value="">{t("project.agentPreference.unset")}</option>
            {selectedProfileMissing && <option value={agentProfileId}>{agentProfileId}</option>}
            {profiles.map((profile) => (
              <option key={profile.id} value={profile.id}>{profile.name}</option>
            ))}
          </select>
        </label>
        <label className="settings-field">
          <span>{t("project.agentPreference.agentClient")}</span>
          <select
            aria-label={t("project.agentPreference.agentClient")}
            value={agentClient}
            onChange={(event) => setAgentClient(event.target.value)}
          >
            <option value="">{t("project.agentPreference.unset")}</option>
            {selectedAgentMissing && <option value={agentClient}>{agentClient}</option>}
            {agentOptions.map((option) => (
              <option key={option.id} value={option.id}>{option.label}</option>
            ))}
          </select>
        </label>
        <label className="settings-field">
          <span>{t("project.agentPreference.command")}</span>
          <input
            aria-label={t("project.agentPreference.command")}
            value={agentCommand}
            onChange={(event) => setAgentCommand(event.target.value)}
            placeholder={t("project.agentPreference.commandPlaceholder")}
          />
        </label>
      </div>
      {selectedAgent !== null && (
        <>
          <AgentModelSelectionPicker
            agent={selectedAgent}
            value={agentModelSelection}
            onChange={setAgentModelSelection}
          />
          {selectedAgent === "cursor" && (
            <CursorOfficialModelPicker
              clientId={clientId}
              value={agentModelSelection}
              onChange={setAgentModelSelection}
            />
          )}
        </>
      )}
      <div className="project-agent-preference-actions">
        <button
          type="button"
          disabled={saveMutation.isPending}
          onClick={() => saveMutation.mutate()}
        >
          {saveMutation.isPending ? t("project.agentPreference.saving") : t("project.agentPreference.save")}
        </button>
        {saveMutation.isSuccess && <span className="muted">{t("project.agentPreference.saved")}</span>}
        {saveMutation.isError && <span className="error">{t("project.agentPreference.saveFailed")}</span>}
      </div>
    </section>
  );
}
