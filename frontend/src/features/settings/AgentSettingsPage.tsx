import type { AgentClient, AgentConfig, AgentLaunchKind, AgentProfile } from "../../types";
import { AgentProfilesSettings } from "./AgentProfilesSettings";

export function AgentSettingsPage({
  agentClients,
  selectedClientId,
  selectedProfile,
  profiles,
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
}: {
  agentClients: AgentClient[];
  selectedClientId: string | null;
  selectedProfile: AgentProfile | null;
  profiles: AgentProfile[];
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
}) {
  return (
    <section className="settings-agent-page">
      <AgentProfilesSettings
        selectedClientId={selectedClientId}
        agentClients={agentClients}
        profiles={profiles}
        selectedProfile={selectedProfile}
        profileConfig={profileConfig}
        profileConfigAgentClient={profileConfigAgentClient}
        profileDraftName={profileDraftName}
        profileDraftDescription={profileDraftDescription}
        profileDraftAgentClient={profileDraftAgentClient}
        profileAgentMdDraft={profileAgentMdDraft}
        pendingProfileConfigItem={pendingProfileConfigItem}
        profilesLoading={profilesLoading}
        profilesError={profilesError}
        configLoading={configLoading}
        configError={configError}
        configFetching={configFetching}
        creatingProfile={creatingProfile}
        updatingProfile={updatingProfile}
        deletingProfile={deletingProfile}
        importingProfile={importingProfile}
        updatingConfig={updatingConfig}
        onSelectProfile={onSelectProfile}
        onProfileDraftNameChange={onProfileDraftNameChange}
        onProfileDraftDescriptionChange={onProfileDraftDescriptionChange}
        onProfileDraftAgentClientChange={onProfileDraftAgentClientChange}
        onCreateProfile={onCreateProfile}
        onDeleteProfile={onDeleteProfile}
        onImportProfile={onImportProfile}
        onProfileConfigAgentClientChange={onProfileConfigAgentClientChange}
        onSaveProfileBasics={onSaveProfileBasics}
        onAgentMdDraftChange={onAgentMdDraftChange}
        onSaveAgentMd={onSaveAgentMd}
        onToggleConfigItem={onToggleConfigItem}
      />
    </section>
  );
}
