import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";

import {
  fetchAgentClients,
  fetchClients,
  fetchProjectBrowseRoots,
  fetchProjectSummaries,
  fetchProjects,
  fetchTerminalArtifacts,
  fetchTerminalNotifications,
  fetchTerminalProjects,
  fetchTree,
  fetchWindow,
  fetchWindowActivity,
} from "../api";
import {
  hasActiveTerminalArtifact,
  selectArtifactTerminalCarrier,
} from "../artifactTerminalCarrier";
import { isRemoteClientOffline } from "../appState";
import { DEFAULT_AGENT_CLIENTS } from "../agentLaunch";
import { isCreatableProjectPath } from "../terminalGrouping";
import {
  activityHasWorkingTerminal,
  mergeTreeWithActivity,
  relatedTerminalRecentWindows,
  windowActivityMap,
} from "../terminalTree";
import { findTreeWindow } from "../terminalTreeSelection";
import { terminalThemeForSkin } from "../themeSkins";
import { buildProjectBrowseRootOptions } from "../projectBrowseRoots";
import type { TerminalTimeRange, ThemeSkinId } from "../userPreferences";
import type { TerminalArtifact } from "../types";

const ARTIFACT_MONITOR_PAGE_SIZE = 100;
const EMPTY_TERMINAL_ARTIFACTS: TerminalArtifact[] = [];

type UseAuthenticatedAppQueriesArgs = {
  artifactQuickOpenOpen: boolean;
  projectTerminalPickerOpen: boolean;
  selectedArtifactTerminalId: string | null;
  selectedClientId: string | null;
  selectedProjectPath: string | null;
  selectedWindowId: string | null;
  terminalSwitcherOpen: boolean;
  terminalTimeRange: TerminalTimeRange;
  themeSkin: ThemeSkinId;
};

export function useAuthenticatedAppQueries({
  artifactQuickOpenOpen,
  projectTerminalPickerOpen,
  selectedArtifactTerminalId,
  selectedClientId,
  selectedProjectPath,
  selectedWindowId,
  terminalSwitcherOpen,
  terminalTimeRange,
  themeSkin,
}: UseAuthenticatedAppQueriesArgs) {
  const clientsQuery = useQuery({ queryKey: ["clients"], queryFn: fetchClients, refetchInterval: 10000 });
  const agentClientsQuery = useQuery({
    queryKey: ["agent-clients", selectedClientId],
    queryFn: () => fetchAgentClients(selectedClientId as string),
    enabled: selectedClientId !== null,
    staleTime: 60000,
  });
  const terminalProjectsQuery = useQuery({
    queryKey: ["terminal-projects", selectedClientId, terminalTimeRange],
    queryFn: () => fetchTerminalProjects(selectedClientId as string, terminalTimeRange),
    enabled: selectedClientId !== null,
    refetchInterval: 10000,
  });
  const projectsQuery = useQuery({
    queryKey: ["projects", selectedClientId, terminalTimeRange],
    queryFn: () => fetchProjects(selectedClientId as string, terminalTimeRange),
    enabled: selectedClientId !== null,
    refetchInterval: 10000,
  });
  const projectBrowseRootsQuery = useQuery({
    queryKey: ["project-browse-roots", selectedClientId, selectedProjectPath],
    queryFn: () => fetchProjectBrowseRoots(selectedClientId as string, selectedProjectPath as string),
    enabled: selectedClientId !== null && selectedProjectPath !== null,
    staleTime: 10000,
  });
  const treeQuery = useQuery({
    queryKey: ["tree", selectedClientId, terminalTimeRange, selectedProjectPath],
    queryFn: () => fetchTree(selectedClientId as string, terminalTimeRange, selectedProjectPath),
    enabled: selectedClientId !== null && selectedProjectPath !== null,
    refetchInterval: 10000,
  });
  const windowActivityQuery = useQuery({
    queryKey: ["window-activity", selectedClientId, terminalTimeRange, selectedProjectPath],
    queryFn: () => fetchWindowActivity(selectedClientId as string, {
      includeRuntimeTags: true,
      range: terminalTimeRange,
      projectPath: selectedProjectPath,
    }),
    enabled: selectedClientId !== null && selectedProjectPath !== null && treeQuery.isSuccess,
    refetchInterval: (query) => (activityHasWorkingTerminal(query.state.data) ? 3000 : 10000),
  });
  const terminalSwitcherTreeQuery = useQuery({
    queryKey: ["tree", selectedClientId, terminalTimeRange, null],
    queryFn: () => fetchTree(selectedClientId as string, terminalTimeRange, null),
    enabled: selectedClientId !== null && terminalSwitcherOpen,
    refetchInterval: 10000,
  });
  const terminalSwitcherActivityQuery = useQuery({
    queryKey: ["window-activity", selectedClientId, terminalTimeRange, null],
    queryFn: () => fetchWindowActivity(selectedClientId as string, {
      includeRuntimeTags: true,
      range: terminalTimeRange,
      projectPath: null,
    }),
    enabled: selectedClientId !== null && terminalSwitcherOpen && terminalSwitcherTreeQuery.isSuccess,
    refetchInterval: (query) => (activityHasWorkingTerminal(query.state.data) ? 3000 : 10000),
  });
  const selectedWindowQuery = useQuery({
    queryKey: ["window", selectedClientId, selectedWindowId],
    queryFn: () => fetchWindow(selectedClientId as string, selectedWindowId as string),
    enabled: selectedClientId !== null && selectedWindowId !== null,
    staleTime: 5000,
  });
  const artifactTerminalMonitorQuery = useQuery({
    queryKey: ["terminal-artifacts", selectedClientId, selectedWindowId, "carrier"],
    queryFn: () => fetchTerminalArtifacts(
      selectedClientId as string,
      selectedWindowId as string,
      ARTIFACT_MONITOR_PAGE_SIZE,
      0,
    ),
    enabled: selectedClientId !== null && selectedWindowId !== null,
    refetchInterval: (query) => (
      artifactQuickOpenOpen
      || selectedArtifactTerminalId !== null
      || hasActiveTerminalArtifact(query.state.data?.artifacts ?? [])
        ? 1500
        : false
    ),
  });
  const lastNotificationActivitySignature = useMemo(() => {
    if (!windowActivityQuery.data) {
      return "";
    }

    return windowActivityQuery.data.windows
      .map((window) => [
        window.window_id,
        window.last_agent_task_status ?? "",
        window.last_agent_task_status_at ?? window.last_agent_task_completed_at ?? "",
      ].join(":"))
      .sort()
      .join("|");
  }, [windowActivityQuery.data]);
  const terminalNotificationsQuery = useQuery({
    queryKey: ["terminal-notifications", selectedClientId, lastNotificationActivitySignature],
    queryFn: () => fetchTerminalNotifications(selectedClientId as string),
    enabled: selectedClientId !== null && windowActivityQuery.isSuccess,
    refetchInterval: 10000,
  });
  const projectSummariesQuery = useQuery({
    queryKey: ["project-summaries", selectedClientId],
    queryFn: () => fetchProjectSummaries(selectedClientId as string),
    enabled: selectedClientId !== null && projectTerminalPickerOpen,
  });

  const treeFolders = useMemo(
    () => mergeTreeWithActivity(treeQuery.data, windowActivityMap(windowActivityQuery.data)),
    [treeQuery.data, windowActivityQuery.data],
  );
  const terminalSwitcherFolders = useMemo(
    () => mergeTreeWithActivity(
      terminalSwitcherTreeQuery.data,
      windowActivityMap(terminalSwitcherActivityQuery.data),
    ) ?? treeFolders,
    [terminalSwitcherActivityQuery.data, terminalSwitcherTreeQuery.data, treeFolders],
  );
  const relatedSwitcherWindows = useMemo(
    () => relatedTerminalRecentWindows(terminalSwitcherFolders ?? treeFolders, selectedWindowId),
    [selectedWindowId, terminalSwitcherFolders, treeFolders],
  );
  const selectedClient = clientsQuery.data?.find((client) => client.id === selectedClientId) ?? null;
  const selectedClientOffline = isRemoteClientOffline(selectedClient);
  const terminalProjects = Array.isArray(terminalProjectsQuery.data) ? terminalProjectsQuery.data : [];
  const projects = Array.isArray(projectsQuery.data) ? projectsQuery.data : [];
  const selectedProject = projects.find((project) => project.path === selectedProjectPath) ?? null;
  const projectPaths = useMemo(
    () => terminalProjects.map((project) => project.project_path).filter(isCreatableProjectPath),
    [terminalProjects],
  );
  const terminalTheme = useMemo(() => terminalThemeForSkin(themeSkin), [themeSkin]);
  const selectedTreeWindow = findTreeWindow(treeFolders, selectedWindowId);
  const selectedWindow = selectedTreeWindow ?? selectedWindowQuery.data ?? null;
  const selectedWindowTitle = selectedWindow?.title ?? null;
  const selectedWindowRuntimeTags = useMemo(() => {
    const activityTags = windowActivityQuery.data?.windows.find(
      (window) => window.window_id === selectedWindowId,
    )?.runtime_tags;
    for (const tags of [selectedWindow?.runtime_tags, selectedWindowQuery.data?.runtime_tags, activityTags]) {
      if (tags !== undefined && tags !== null && tags.length > 0) {
        return tags;
      }
    }
    return selectedWindow?.runtime_tags ?? selectedWindowQuery.data?.runtime_tags ?? activityTags ?? [];
  }, [selectedWindow?.runtime_tags, selectedWindowId, selectedWindowQuery.data?.runtime_tags, windowActivityQuery.data]);
  const artifactMonitorArtifacts = artifactTerminalMonitorQuery.data?.artifacts ?? EMPTY_TERMINAL_ARTIFACTS;
  const artifactTerminalCarrier = useMemo(
    () => selectArtifactTerminalCarrier(artifactMonitorArtifacts, selectedArtifactTerminalId),
    [artifactMonitorArtifacts, selectedArtifactTerminalId],
  );
  const projectBrowseRootOptions = useMemo(
    () => buildProjectBrowseRootOptions({
      activityWindows: windowActivityQuery.data?.windows ?? null,
      browseRoots: projectBrowseRootsQuery.data?.roots ?? null,
      projectPath: selectedProjectPath,
      selectedWindow,
      treeFolders,
    }),
    [
      projectBrowseRootsQuery.data,
      selectedProjectPath,
      selectedWindow,
      treeFolders,
      windowActivityQuery.data,
    ],
  );

  return {
    agentClients: agentClientsQuery.data?.agent_clients ?? DEFAULT_AGENT_CLIENTS,
    agentClientsQuery,
    artifactMonitorArtifacts,
    artifactTerminalCarrier,
    artifactTerminalMonitorQuery,
    clientsQuery,
    projectPaths,
    projectBrowseRootOptions,
    projectBrowseRootsQuery,
    projectSummariesQuery,
    projects,
    projectsQuery,
    relatedSwitcherWindows,
    selectedClient,
    selectedClientOffline,
    selectedProject,
    selectedTreeWindow,
    selectedWindow,
    selectedWindowQuery,
    selectedWindowRuntimeTags,
    selectedWindowTitle,
    terminalNotificationsQuery,
    terminalProjects,
    terminalProjectsQuery,
    terminalSwitcherActivityQuery,
    terminalSwitcherFolders,
    terminalSwitcherTreeQuery,
    terminalTheme,
    treeFolders,
    treeQuery,
    windowActivityQuery,
  };
}
