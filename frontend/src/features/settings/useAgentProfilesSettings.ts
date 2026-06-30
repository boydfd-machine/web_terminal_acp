import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  createAgentProfile,
  deleteAgentProfile,
  fetchAgentClients,
  fetchAgentProfileConfig,
  fetchAgentProfiles,
  importAgentProfile,
  updateAgentProfile,
  updateAgentProfileConfigItem
} from "../../api";
import { DEFAULT_AGENT_CLIENTS, agentClientCapability } from "../../agentLaunch";
import type { AgentLaunchKind, AgentProfile } from "../../types";

export function useAgentProfilesSettings({
  isOpen,
  selectedClientId,
  view
}: {
  isOpen: boolean;
  selectedClientId: string | null;
  view: string;
}) {
  const queryClient = useQueryClient();
  const [selectedAgentProfileId, setSelectedAgentProfileId] = useState<string | null>(null);
  const [profileDraftName, setProfileDraftName] = useState("");
  const [profileDraftDescription, setProfileDraftDescription] = useState("");
  const [profileDraftAgentClient, setProfileDraftAgentClient] = useState<AgentLaunchKind>("codex");
  const [profileConfigAgentClient, setProfileConfigAgentClient] = useState<AgentLaunchKind>("codex");
  const [profileAgentMdDraft, setProfileAgentMdDraft] = useState("");
  const [pendingProfileConfigItem, setPendingProfileConfigItem] = useState<string | null>(null);

  const agentProfilesQuery = useQuery({
    queryKey: ["agent-profiles", selectedClientId],
    queryFn: () => fetchAgentProfiles(selectedClientId as string),
    enabled: isOpen && view === "agents" && selectedClientId !== null
  });
  const agentClientsQuery = useQuery({
    queryKey: ["agent-clients", selectedClientId],
    queryFn: () => fetchAgentClients(selectedClientId as string),
    enabled: isOpen && (view === "agents" || view === "system-models") && selectedClientId !== null,
    staleTime: 60000
  });
  const agentClients = agentClientsQuery.data?.agent_clients ?? DEFAULT_AGENT_CLIENTS;
  const agentProfiles = agentProfilesQuery.data?.profiles ?? [];
  const selectedAgentProfile = agentProfiles.find((profile) => profile.id === selectedAgentProfileId) ?? agentProfiles[0] ?? null;
  const profileConfigSupported = agentClientCapability(profileConfigAgentClient, agentClients, "profile_config");
  const profileConfigQuery = useQuery({
    queryKey: ["agent-profile-config", selectedClientId, selectedAgentProfile?.id ?? null, profileConfigAgentClient],
    queryFn: () => fetchAgentProfileConfig(selectedClientId as string, selectedAgentProfile?.id as string, profileConfigAgentClient),
    enabled: isOpen && view === "agents" && selectedClientId !== null && selectedAgentProfile !== null && profileConfigSupported
  });

  const createProfileMutation = useMutation({
    mutationFn: () => createAgentProfile(selectedClientId as string, {
      name: profileDraftName,
      description: profileDraftDescription || null,
      default_agent_client: profileDraftAgentClient,
      source_agent_client: profileDraftAgentClient
    }),
    onSuccess: (profile) => {
      queryClient.invalidateQueries({ queryKey: ["agent-profiles", selectedClientId] });
      setSelectedAgentProfileId(profile.id);
      setProfileConfigAgentClient(profile.default_agent_client);
      setProfileDraftName("");
      setProfileDraftDescription("");
    }
  });
  const updateProfileMutation = useMutation({
    mutationFn: (input: { profile: AgentProfile; patch: Partial<Pick<AgentProfile, "name" | "description" | "default_agent_client" | "agent_md">> }) =>
      updateAgentProfile(selectedClientId as string, input.profile.id, input.patch),
    onSuccess: (profile) => {
      queryClient.invalidateQueries({ queryKey: ["agent-profiles", selectedClientId] });
      queryClient.setQueryData(["agent-profiles", selectedClientId], (current: { profiles?: AgentProfile[] } | undefined) => ({
        profiles: (current?.profiles ?? []).map((candidate) => candidate.id === profile.id ? profile : candidate)
      }));
    }
  });
  const deleteProfileMutation = useMutation({
    mutationFn: (profile: AgentProfile) => deleteAgentProfile(selectedClientId as string, profile.id),
    onSuccess: (_result, profile) => {
      queryClient.invalidateQueries({ queryKey: ["agent-profiles", selectedClientId] });
      if (selectedAgentProfileId === profile.id) {
        setSelectedAgentProfileId(null);
      }
    }
  });
  const importProfileMutation = useMutation({
    mutationFn: (payload: unknown) => importAgentProfile(selectedClientId as string, payload),
    onSuccess: (profile) => {
      queryClient.invalidateQueries({ queryKey: ["agent-profiles", selectedClientId] });
      setSelectedAgentProfileId(profile.id);
      setProfileConfigAgentClient(profile.default_agent_client);
    }
  });
  const updateProfileConfigMutation = useMutation({
    mutationFn: (input: { sectionId: string; itemId: string; enabled: boolean }) =>
      updateAgentProfileConfigItem(selectedClientId as string, selectedAgentProfile?.id as string, profileConfigAgentClient, input.sectionId, input.itemId, input.enabled),
    onMutate: (input) => setPendingProfileConfigItem(`${input.sectionId}:${input.itemId}`),
    onSuccess: (config) => {
      queryClient.setQueryData(["agent-profile-config", selectedClientId, selectedAgentProfile?.id ?? null, profileConfigAgentClient], config);
      queryClient.invalidateQueries({ queryKey: ["agent-profiles", selectedClientId] });
    },
    onSettled: () => setPendingProfileConfigItem(null)
  });

  useEffect(() => {
    if (selectedAgentProfile === null) {
      setProfileAgentMdDraft("");
      return;
    }
    setProfileAgentMdDraft(selectedAgentProfile.agent_md);
    setProfileConfigAgentClient(selectedAgentProfile.default_agent_client);
  }, [selectedAgentProfile?.id, selectedAgentProfile?.agent_md, selectedAgentProfile?.default_agent_client]);

  useEffect(() => {
    if (agentClientCapability(profileConfigAgentClient, agentClients, "profile_config")) {
      return;
    }
    const fallback = agentClients.find((agentClient) => agentClientCapability(agentClient.id, agentClients, "profile_config"));
    if (fallback !== undefined) {
      setProfileConfigAgentClient(fallback.id);
    }
  }, [agentClients, profileConfigAgentClient]);

  useEffect(() => {
    if (selectedAgentProfileId !== null || agentProfiles.length === 0) {
      return;
    }
    setSelectedAgentProfileId(agentProfiles[0].id);
  }, [agentProfiles, selectedAgentProfileId]);

  const createProfile = () => {
    if (selectedClientId === null || profileDraftName.trim().length === 0) {
      return;
    }
    createProfileMutation.mutate();
  };
  const saveProfileBasics = (profile: AgentProfile) => {
    updateProfileMutation.mutate({
      profile,
      patch: {
        name: profile.name,
        description: profile.description,
        default_agent_client: profile.default_agent_client
      }
    });
  };
  const saveProfileAgentMd = (profile: AgentProfile) => {
    updateProfileMutation.mutate({ profile, patch: { agent_md: profileAgentMdDraft } });
  };
  const importProfile = async (payload: unknown) => {
    if (selectedClientId === null) {
      return;
    }
    await importProfileMutation.mutateAsync(payload);
  };

  return {
    agentClients,
    agentProfiles,
    selectedAgentProfile,
    profileConfigQuery,
    createProfileMutation,
    updateProfileMutation,
    deleteProfileMutation,
    importProfileMutation,
    updateProfileConfigMutation,
    selectedAgentProfileId,
    setSelectedAgentProfileId,
    profileDraftName,
    setProfileDraftName,
    profileDraftDescription,
    setProfileDraftDescription,
    profileDraftAgentClient,
    setProfileDraftAgentClient,
    profileConfigAgentClient,
    setProfileConfigAgentClient,
    profileAgentMdDraft,
    setProfileAgentMdDraft,
    pendingProfileConfigItem,
    agentProfilesQuery,
    createProfile,
    importProfile,
    saveProfileBasics,
    saveProfileAgentMd
  };
}
