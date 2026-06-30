import { agentClientCapability } from "../../agentLaunch";
import { artifactModelAgentSupportsSelection } from "../../artifactModelSelection";
import { AgentModelSelectionPicker } from "../../components/AgentModelSelectionPicker";
import { CursorOfficialModelPicker } from "../../components/CursorOfficialModelPicker";
import { useI18n } from "../../i18n";
import type { AgentCommandSettings, AgentModelSelectionSettings } from "../../userPreferences";
import type { AgentClient, AgentLaunchKind, AgentModelSelection } from "../../types";

export function AgentCliModelSettings({
  clientId,
  agentClients,
  agentCommandSettings,
  agentModelSelectionSettings,
  artifactModelSelectionSettings,
  onAgentCommandChange,
  onAgentModelSelectionChange,
  onArtifactModelSelectionChange
}: {
  clientId: string | null;
  agentClients: AgentClient[];
  agentCommandSettings: AgentCommandSettings;
  agentModelSelectionSettings: AgentModelSelectionSettings;
  artifactModelSelectionSettings: AgentModelSelectionSettings;
  onAgentCommandChange: (agent: string, value: string) => void;
  onAgentModelSelectionChange: (agent: string, value: AgentModelSelection | null) => void;
  onArtifactModelSelectionChange: (agent: string, value: AgentModelSelection | null) => void;
}) {
  const { t } = useI18n();
  const launchClients = agentClients.filter((agentClient) => agentClientCapability(agentClient.id, agentClients, "launch"));

  if (launchClients.length === 0) {
    return null;
  }

  return (
    <section className="agent-cli-settings">
      <div className="system-config-detail-header">
        <div>
          <strong>{t("settings.models.agentCliTitle")}</strong>
          <small>{t("settings.models.agentCliHint")}</small>
        </div>
      </div>
      <div className="agent-cli-settings-grid">
        {launchClients.map((agentClient) => {
          const supportsPresetModelSelection = artifactModelAgentSupportsSelection(agentClient.id);
          const supportsCursorOfficialModel = agentClient.id === "cursor";
          return (
            <section key={agentClient.id} className="agent-cli-settings-item">
              <label className="settings-field">
                <span>{t("settings.agent.launchCommand", { label: agentClient.label })}</span>
                <input
                  value={agentCommandSettings[agentClient.id] ?? agentClient.default_command}
                  onChange={(event) => onAgentCommandChange(agentClient.id, event.target.value)}
                  placeholder={agentClient.default_command}
                />
              </label>
              {supportsPresetModelSelection && (
                <>
                  <section className="agent-cli-model-block">
                    <strong>{t("settings.models.terminalDefaultModel")}</strong>
                    <AgentModelSelectionPicker
                      agent={agentClient.id as AgentLaunchKind}
                      value={agentModelSelectionSettings[agentClient.id] ?? null}
                      onChange={(value) => onAgentModelSelectionChange(agentClient.id, value)}
                    />
                  </section>
                  <section className="agent-cli-model-block">
                    <strong>{t("settings.models.artifactDefaultModel")}</strong>
                    <AgentModelSelectionPicker
                      agent={agentClient.id as AgentLaunchKind}
                      value={artifactModelSelectionSettings[agentClient.id] ?? null}
                      onChange={(value) => onArtifactModelSelectionChange(agentClient.id, value)}
                    />
                  </section>
                </>
              )}
              {supportsCursorOfficialModel && (
                <section className="agent-cli-model-block">
                  <strong>{t("settings.models.terminalDefaultModel")}</strong>
                  <CursorOfficialModelPicker
                    clientId={clientId}
                    value={agentModelSelectionSettings[agentClient.id] ?? null}
                    onChange={(value) => onAgentModelSelectionChange(agentClient.id, value)}
                  />
                </section>
              )}
            </section>
          );
        })}
      </div>
    </section>
  );
}
