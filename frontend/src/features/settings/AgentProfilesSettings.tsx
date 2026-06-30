import { useEffect, useRef, useState, type ChangeEvent } from "react";

import { exportAgentProfile } from "../../api";
import { agentClientCapability, agentClientOptions, agentLabel } from "../../agentLaunch";
import { AgentConfigViewer } from "../../components/AgentConfigViewer";
import { UiIcon } from "../../components/UiIcon";
import { useI18n } from "../../i18n";
import type { AgentClient, AgentConfig, AgentConfigSection, AgentLaunchKind, AgentProfile } from "../../types";
import { downloadJsonFile, jsonFilename, readJsonFile } from "./settingsImportExport";

type AgentProfileTab = "prompt" | "mcp" | "plugins" | "skills" | "create";

type AgentProfilesSettingsProps = {
  selectedClientId: string | null;
  agentClients: AgentClient[];
  profiles: AgentProfile[];
  selectedProfile: AgentProfile | null;
  profileConfig: AgentConfig | null;
  profileConfigAgentClient: AgentLaunchKind;
  profileDraftName: string;
  profileDraftDescription: string;
  profileDraftAgentClient: AgentLaunchKind;
  profileAgentMdDraft: string;
  pendingProfileConfigItem: string | null;
  profilesLoading: boolean;
  profilesError: boolean;
  configLoading: boolean;
  configError: boolean;
  configFetching: boolean;
  creatingProfile: boolean;
  updatingProfile: boolean;
  deletingProfile: boolean;
  importingProfile: boolean;
  updatingConfig: boolean;
  onSelectProfile: (profileId: string) => void;
  onProfileDraftNameChange: (value: string) => void;
  onProfileDraftDescriptionChange: (value: string) => void;
  onProfileDraftAgentClientChange: (value: AgentLaunchKind) => void;
  onCreateProfile: () => void;
  onDeleteProfile: (profile: AgentProfile) => void;
  onImportProfile: (payload: unknown) => Promise<void>;
  onProfileConfigAgentClientChange: (value: AgentLaunchKind) => void;
  onSaveProfileBasics: (profile: AgentProfile) => void;
  onAgentMdDraftChange: (value: string) => void;
  onSaveAgentMd: (profile: AgentProfile) => void;
  onToggleConfigItem: (sectionId: string, itemId: string, enabled: boolean) => void;
};

export function AgentProfilesSettings(props: AgentProfilesSettingsProps) {
  const { t } = useI18n();
  const [activeTab, setActiveTab] = useState<AgentProfileTab>("prompt");
  const {
    selectedClientId,
    agentClients,
    profiles,
    selectedProfile,
    profileConfig,
    profileConfigAgentClient,
    profileDraftName,
    profileDraftDescription,
    profileDraftAgentClient,
    profileAgentMdDraft,
    pendingProfileConfigItem,
    profilesLoading,
    profilesError,
    configLoading,
    configError,
    configFetching,
    creatingProfile,
    updatingProfile,
    deletingProfile,
    importingProfile,
    updatingConfig,
    onSelectProfile,
    onProfileDraftNameChange,
    onProfileDraftDescriptionChange,
    onProfileDraftAgentClientChange,
    onCreateProfile,
    onDeleteProfile,
    onImportProfile,
    onProfileConfigAgentClientChange,
    onSaveProfileBasics,
    onAgentMdDraftChange,
    onSaveAgentMd,
    onToggleConfigItem
  } = props;
  const importInputRef = useRef<HTMLInputElement | null>(null);
  const [status, setStatus] = useState<{ kind: "info" | "error"; message: string } | null>(null);
  const canCreate = selectedClientId !== null && profileDraftName.trim().length > 0 && !creatingProfile;
  const agentOptions = agentClientOptions(agentClients, "launch");
  const configAgentOptions = agentClientOptions(agentClients, "profile_config");
  const configAgentSupported = agentClientCapability(profileConfigAgentClient, agentClients, "profile_config");
  const configTab = activeTab === "mcp" || activeTab === "plugins" || activeTab === "skills" ? activeTab : null;
  const configTabTitle = configTab === "mcp"
    ? t("settings.agent.mcpTab")
    : configTab === "plugins"
      ? t("settings.agent.pluginTab")
      : t("settings.agent.skillsTab");
  const filteredProfileConfig = (sectionId: AgentConfigSection["id"]): AgentConfig | null => profileConfig === null
    ? null
    : { ...profileConfig, sections: profileConfig.sections.filter((section) => section.id === sectionId) };
  const onImportFileChange = async (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.currentTarget.files?.[0] ?? null;
    event.currentTarget.value = "";
    if (file === null) {
      return;
    }
    try {
      await onImportProfile(await readJsonFile(file));
      setStatus({ kind: "info", message: t("settings.agent.imported") });
    } catch {
      setStatus({ kind: "error", message: t("settings.agent.importFailed") });
    }
  };
  const onExportProfile = async (profile: AgentProfile) => {
    if (selectedClientId === null) {
      return;
    }
    try {
      const bundle = await exportAgentProfile(selectedClientId, profile.id);
      downloadJsonFile(bundle, jsonFilename(profile.id));
      setStatus(null);
    } catch {
      setStatus({ kind: "error", message: t("settings.agent.exportFailed") });
    }
  };

  if (selectedClientId === null) {
    return <section className="agent-profile-settings"><p className="muted">{t("settings.agent.noClient")}</p></section>;
  }
  if (profilesError) {
    return <section className="agent-profile-settings"><p className="error" role="alert">{t("settings.agent.loadFailed")}</p></section>;
  }

  return (
    <section className="agent-profile-settings">
      <div className="agent-profile-grid">
        <aside className="agent-profile-list">
          <div className="agent-profile-list-header">
            <div className="quick-key-list-header">
              <h3>{t("settings.agent.agents")}</h3>
              <span>{profilesLoading ? "..." : profiles.length}</span>
            </div>
            <div className="agent-profile-list-actions">
              <input
                ref={importInputRef}
                className="settings-import-file-input"
                type="file"
                accept=".json,application/json"
                aria-label={t("settings.agent.import")}
                onChange={onImportFileChange}
              />
              <button
                type="button"
                className="system-config-icon-button"
                disabled={importingProfile}
                aria-label={t("settings.agent.import")}
                title={t("settings.agent.import")}
                onClick={() => importInputRef.current?.click()}
              >
                <UiIcon name="upload" />
              </button>
              <button
                type="button"
                className="system-config-icon-button agent-profile-create-button"
                aria-label={t("settings.agent.create")}
                title={t("settings.agent.create")}
                onClick={() => setActiveTab("create")}
              >
                <UiIcon name="plus" />
              </button>
            </div>
          </div>
          <div className="agent-profile-list-scroll">
            {profiles.length === 0 ? (
              <p className="muted quick-key-empty-state">{t("settings.agent.empty")}</p>
            ) : (
              profiles.map((profile) => (
                <button
                  key={profile.id}
                  type="button"
                  className={selectedProfile?.id === profile.id ? "agent-profile-row selected" : "agent-profile-row"}
                  onClick={() => {
                    onSelectProfile(profile.id);
                    if (activeTab === "create") {
                      setActiveTab("prompt");
                    }
                  }}
                >
                  <strong>{profile.name}</strong>
                  <span>{agentLabel(profile.default_agent_client, agentClients)}</span>
                </button>
              ))
            )}
          </div>
        </aside>
        <div className="agent-profile-editor">
          <div className="agent-profile-tabs" role="tablist" aria-label={t("settings.agent.profileTabs")}>
            {[
              ["prompt", t("settings.agent.promptTab")],
              ["mcp", t("settings.agent.mcpTab")],
              ["plugins", t("settings.agent.pluginTab")],
              ["skills", t("settings.agent.skillsTab")],
              ["create", t("settings.agent.createTab")]
            ].map(([tab, label]) => (
              <button key={tab} type="button" role="tab" aria-selected={activeTab === tab} className={activeTab === tab ? "active" : ""} onClick={() => setActiveTab(tab as AgentProfileTab)}>
                {label}
              </button>
            ))}
          </div>
          <div className="agent-profile-editor-scroll">
            {activeTab === "create" ? (
              <AgentProfileCreateForm
                canCreate={canCreate}
                creatingProfile={creatingProfile}
                agentOptions={agentOptions}
                profileDraftName={profileDraftName}
                profileDraftDescription={profileDraftDescription}
                profileDraftAgentClient={profileDraftAgentClient}
                onProfileDraftNameChange={onProfileDraftNameChange}
                onProfileDraftDescriptionChange={onProfileDraftDescriptionChange}
                onProfileDraftAgentClientChange={onProfileDraftAgentClientChange}
                onCreateProfile={onCreateProfile}
              />
            ) : selectedProfile === null ? (
              <p className="muted quick-key-empty-state">{t("settings.agent.empty")}</p>
            ) : (
              <div className="agent-profile-detail">
                <ProfileActions
                  profile={selectedProfile}
                  deletingProfile={deletingProfile}
                  onDeleteProfile={onDeleteProfile}
                  onExportProfile={onExportProfile}
                />
                {status !== null && <p className={status.kind === "error" ? "error" : "muted"}>{status.message}</p>}
                {activeTab === "prompt" ? (
                  <AgentProfilePromptForm
                    profile={selectedProfile}
                    agentOptions={agentOptions}
                    profileAgentMdDraft={profileAgentMdDraft}
                    updatingProfile={updatingProfile}
                    onSaveProfileBasics={onSaveProfileBasics}
                    onAgentMdDraftChange={onAgentMdDraftChange}
                    onSaveAgentMd={onSaveAgentMd}
                  />
                ) : (
                  <>
                    {configAgentOptions.length > 0 && (
                      <label className="settings-field">
                        <span>{t("settings.agent.configTarget")}</span>
                        <select
                          value={profileConfigAgentClient}
                          onChange={(event) => onProfileConfigAgentClientChange(event.target.value as AgentLaunchKind)}
                        >
                          {configAgentOptions.map((option) => (
                            <option key={option.id} value={option.id}>{option.label}</option>
                          ))}
                        </select>
                      </label>
                    )}
                    {configAgentSupported && configTab !== null && (
                      <AgentConfigViewer
                        config={filteredProfileConfig(configTab)}
                        isLoading={configLoading}
                        isError={configError}
                        isFetching={configFetching}
                        pendingItemId={pendingProfileConfigItem}
                        isToggling={updatingConfig}
                        title={configTabTitle}
                        metaPrefix="profile config"
                        emptyMessage={t("settings.agent.profileConfigLoadFailed")}
                        onToggleItem={onToggleConfigItem}
                      />
                    )}
                  </>
                )}
              </div>
            )}
          </div>
        </div>
      </div>
    </section>
  );
}

function AgentProfileCreateForm({
  canCreate,
  creatingProfile,
  agentOptions,
  profileDraftName,
  profileDraftDescription,
  profileDraftAgentClient,
  onProfileDraftNameChange,
  onProfileDraftDescriptionChange,
  onProfileDraftAgentClientChange,
  onCreateProfile
}: {
  canCreate: boolean;
  creatingProfile: boolean;
  agentOptions: Array<{ id: AgentLaunchKind; label: string }>;
  profileDraftName: string;
  profileDraftDescription: string;
  profileDraftAgentClient: AgentLaunchKind;
  onProfileDraftNameChange: (value: string) => void;
  onProfileDraftDescriptionChange: (value: string) => void;
  onProfileDraftAgentClientChange: (value: AgentLaunchKind) => void;
  onCreateProfile: () => void;
}) {
  const { t } = useI18n();
  return (
    <div className="agent-profile-create-row">
      <div className="system-config-detail-header">
        <div>
          <strong>{t("settings.agent.createTab")}</strong>
          <small>{t("settings.agent.createHint")}</small>
        </div>
      </div>
      <label className="settings-field">
        <span>{t("settings.agent.name")}</span>
        <input value={profileDraftName} onChange={(event) => onProfileDraftNameChange(event.target.value)} placeholder={t("settings.agent.namePlaceholder")} />
      </label>
      <label className="settings-field">
        <span>{t("settings.agent.defaultClient")}</span>
        <select value={profileDraftAgentClient} onChange={(event) => onProfileDraftAgentClientChange(event.target.value as AgentLaunchKind)}>
          {agentOptions.map((option) => (
            <option key={option.id} value={option.id}>{option.label}</option>
          ))}
        </select>
      </label>
      <label className="settings-field">
        <span>{t("settings.agent.description")}</span>
        <input value={profileDraftDescription} onChange={(event) => onProfileDraftDescriptionChange(event.target.value)} placeholder={t("settings.agent.optionalPlaceholder")} />
      </label>
      <div className="settings-actions">
        <button type="button" disabled={!canCreate} onClick={onCreateProfile}>
          {creatingProfile ? t("settings.agent.creating") : t("settings.agent.create")}
        </button>
      </div>
    </div>
  );
}

function ProfileActions({
  profile,
  deletingProfile,
  onDeleteProfile,
  onExportProfile
}: {
  profile: AgentProfile;
  deletingProfile: boolean;
  onDeleteProfile: (profile: AgentProfile) => void;
  onExportProfile: (profile: AgentProfile) => void;
}) {
  const { t } = useI18n();
  return (
    <div className="agent-profile-detail-toolbar">
      <button type="button" className="system-config-icon-button" aria-label={`${t("common.download")} ${profile.name}`} title={t("common.download")} onClick={() => onExportProfile(profile)}>
        <UiIcon name="download" />
      </button>
      <button type="button" className="system-config-icon-button danger" disabled={deletingProfile} aria-label={`${t("common.delete")} ${profile.name}`} title={t("common.delete")} onClick={() => onDeleteProfile(profile)}>
        <UiIcon name="trash" />
      </button>
    </div>
  );
}

function AgentProfilePromptForm({
  profile,
  agentOptions,
  profileAgentMdDraft,
  updatingProfile,
  onSaveProfileBasics,
  onAgentMdDraftChange,
  onSaveAgentMd
}: {
  profile: AgentProfile;
  agentOptions: Array<{ id: AgentLaunchKind; label: string }>;
  profileAgentMdDraft: string;
  updatingProfile: boolean;
  onSaveProfileBasics: (profile: AgentProfile) => void;
  onAgentMdDraftChange: (value: string) => void;
  onSaveAgentMd: (profile: AgentProfile) => void;
}) {
  const { t } = useI18n();
  const [nameDraft, setNameDraft] = useState(profile.name);
  const [descriptionDraft, setDescriptionDraft] = useState(profile.description ?? "");

  useEffect(() => {
    setNameDraft(profile.name);
    setDescriptionDraft(profile.description ?? "");
  }, [profile.description, profile.id, profile.name]);

  const saveName = () => {
    const nextName = nameDraft.trim();
    if (nextName.length === 0) {
      setNameDraft(profile.name);
      return;
    }
    if (nextName !== profile.name) {
      onSaveProfileBasics({ ...profile, name: nextName });
    } else {
      setNameDraft(nextName);
    }
  };
  const saveDescription = () => {
    const nextDescription = descriptionDraft.trim();
    if (nextDescription !== (profile.description ?? "")) {
      onSaveProfileBasics({ ...profile, description: nextDescription || null });
    } else {
      setDescriptionDraft(nextDescription);
    }
  };

  return (
    <>
      <div className="settings-agent-command-grid">
        <label className="settings-field">
          <span>{t("settings.agent.name")}</span>
          <input
            value={nameDraft}
            onChange={(event) => setNameDraft(event.target.value)}
            onBlur={saveName}
          />
        </label>
        <label className="settings-field">
          <span>{t("settings.agent.defaultClient")}</span>
          <select
            value={profile.default_agent_client}
            onChange={(event) => onSaveProfileBasics({
              ...profile,
              default_agent_client: event.target.value as AgentLaunchKind
            })}
          >
            {agentOptions.map((option) => (
              <option key={option.id} value={option.id}>{option.label}</option>
            ))}
          </select>
        </label>
      </div>
      <label className="settings-field">
        <span>{t("settings.agent.description")}</span>
        <input
          value={descriptionDraft}
          onChange={(event) => setDescriptionDraft(event.target.value)}
          onBlur={saveDescription}
        />
      </label>
      <label className="settings-field agent-profile-agent-md">
        <span>AGENT.md</span>
        <textarea rows={8} value={profileAgentMdDraft} onChange={(event) => onAgentMdDraftChange(event.target.value)} />
      </label>
      <div className="settings-actions">
        <button type="button" disabled={updatingProfile || profileAgentMdDraft === profile.agent_md} onClick={() => onSaveAgentMd(profile)}>
          {t("settings.agent.saveAgentMd")}
        </button>
      </div>
    </>
  );
}
