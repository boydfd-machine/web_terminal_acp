import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";

import {
  createProjectTodoFromPageReviewCard,
  createTerminalArtifact,
  fetchCommandHistory,
  fetchWindow,
  fetchWindowTitleHistory,
  retrySummary,
  updateManualWorkStatus,
  updateWindowTitle
} from "../api";
import { artifactModelAgentFromWindow, artifactModelDefaultSelection } from "../artifactModelSelection";
import { useAgentConfigData } from "../hooks/useAgentConfigData";
import { useAgentRecordData } from "../hooks/useAgentRecordData";
import type { ProjectFileLinkContext } from "../projectFileLinks";
import { projectPathForWindow } from "../terminalTree";
import type {
  ArtifactScope,
  GitWorktreeActivity,
  TerminalArtifact,
  TreeFolderCore,
  VirtualWindow,
  WorkStatusState
} from "../types";
import type { AgentModelSelection } from "../types";
import { DetailPanelTabs, type DetailPanelTab } from "./DetailPanelTabs";
import { GitRunViewer } from "./GitRunViewer";
import { WindowArtifactsPanel } from "./WindowArtifactsPanel";
import { WindowAgentSection, WindowHistorySection } from "./WindowDetailSections";
import { WindowOverviewPanel } from "./WindowOverviewPanel";
import { WindowTitleHeader } from "./WindowTitleHeader";
import { terminalArtifactItemId, useWindowArtifactItems } from "./useWindowArtifactItems";
import { useArtifactProjectTodoCreator } from "./useArtifactProjectTodoCreator";
import {
  COMMAND_HISTORY_PAGE_SIZE, MAX_TITLE_LENGTH, TITLE_HISTORY_PAGE_SIZE,
  displayTags, formatDateTime, renameTreeWindow, summaryStatus,
  type AgentDetailTab,
  type HistoryDetailTab
} from "./windowDetailData";
import { useI18n } from "../i18n";

type WindowDetailProps = {
  clientId: string | null;
  windowId: string | null;
  gitWorktree?: GitWorktreeActivity | null;
  projectFileContext?: ProjectFileLinkContext | null;
  terminalStatusLabel?: string;
  terminalStatusTone?: "connected" | "connecting" | "reconnecting" | "unavailable" | "error";
  quickInputDraft?: string;
  canSendQuickInput?: boolean;
  agentRecordShortcutLabel?: string;
  onQuickInputDraftChange?: (draft: string) => void;
  onQuickInputSubmit?: (draft: string) => boolean;
  onOpenArtifactTerminal?: (artifact: TerminalArtifact) => void;
  onFocusProjectTodo?: (projectPath: string, todoId: string) => void;
};

export function WindowDetail({
  clientId,
  windowId,
  gitWorktree = null,
  projectFileContext = null,
  terminalStatusLabel,
  terminalStatusTone,
  quickInputDraft,
  canSendQuickInput,
  agentRecordShortcutLabel = "Expand",
  onQuickInputDraftChange,
  onQuickInputSubmit,
  onOpenArtifactTerminal,
  onFocusProjectTodo
}: WindowDetailProps) {
  const { t } = useI18n();
  const [allowTitleFolderOverride, setAllowTitleFolderOverride] = useState(false);
  const [detailTab, setDetailTab] = useState<DetailPanelTab>("overview");
  const [agentDetailTab, setAgentDetailTab] = useState<AgentDetailTab>("record");
  const [historyDetailTab, setHistoryDetailTab] = useState<HistoryDetailTab>("commands");
  const [commandHistoryPage, setCommandHistoryPage] = useState(0);
  const [titleHistoryPage, setTitleHistoryPage] = useState(0);
  const [artifactPage, setArtifactPage] = useState(0);
  const [artifactScope, setArtifactScope] = useState<ArtifactScope>("terminal");
  const [selectedArtifactId, setSelectedArtifactId] = useState<string | null>(null);
  const [artifactModelSelection, setArtifactModelSelection] = useState<AgentModelSelection | null>(null);
  const [artifactFullscreen, setArtifactFullscreen] = useState(false);
  const [isEditingTitle, setIsEditingTitle] = useState(false);
  const [titleDraft, setTitleDraft] = useState("");
  const queryClient = useQueryClient();
  const agentRecord = useAgentRecordData({
    clientId,
    windowId,
    enabled: detailTab === "agent" && agentDetailTab === "record"
  });
  const agentConfig = useAgentConfigData({
    clientId,
    windowId,
    enabled: detailTab === "agent" && agentDetailTab === "config"
  });

  useEffect(() => {
    setDetailTab("overview");
    setAgentDetailTab("record");
    setHistoryDetailTab("commands");
    setCommandHistoryPage(0);
    setTitleHistoryPage(0);
    setArtifactPage(0);
    setArtifactScope("terminal");
    setSelectedArtifactId(null);
    setArtifactModelSelection(null);
    setArtifactFullscreen(false);
    setIsEditingTitle(false);
    setTitleDraft("");
  }, [clientId, windowId]);

  const windowQuery = useQuery({
    queryKey: ["window", clientId, windowId],
    queryFn: () => fetchWindow(clientId as string, windowId as string),
    enabled: clientId !== null && windowId !== null,
    refetchInterval: 10000
  });
  const queryGitWorktree = windowQuery.data?.git_worktree ?? null;
  const showGitTab = queryGitWorktree !== null || gitWorktree !== null;
  const itemProjectPath = windowQuery.data ? projectPathForWindow(windowQuery.data) : null;

  useEffect(() => {
    if (!showGitTab && detailTab === "git") {
      setDetailTab("overview");
    }
  }, [showGitTab, detailTab]);
  const commandHistoryQuery = useQuery({
    queryKey: ["command-history", clientId, windowId, commandHistoryPage, COMMAND_HISTORY_PAGE_SIZE],
    queryFn: () => fetchCommandHistory(
      clientId as string,
      windowId as string,
      COMMAND_HISTORY_PAGE_SIZE,
      commandHistoryPage * COMMAND_HISTORY_PAGE_SIZE
    ),
    enabled: clientId !== null && windowId !== null && detailTab === "history" && historyDetailTab === "commands",
    placeholderData: keepPreviousData,
    refetchInterval: 10000
  });
  const titleHistoryQuery = useQuery({
    queryKey: ["title-history", clientId, windowId, titleHistoryPage, TITLE_HISTORY_PAGE_SIZE],
    queryFn: () => fetchWindowTitleHistory(
      clientId as string,
      windowId as string,
      TITLE_HISTORY_PAGE_SIZE,
      titleHistoryPage * TITLE_HISTORY_PAGE_SIZE
    ),
    enabled: clientId !== null && windowId !== null && detailTab === "history" && historyDetailTab === "title",
    placeholderData: keepPreviousData,
    refetchInterval: 10000
  });
  const {
    artifactItems,
    artifactsData,
    artifactsQuery,
    previewQuery,
    selectedItem,
    selectedItemCanDisplay,
    selectedItemHtmlQuery,
    selectedItemReady,
    selectedItemSrcDoc
  } = useWindowArtifactItems({
    artifactPage,
    artifactScope,
    clientId,
    enabled: detailTab === "artifacts",
    projectPath: itemProjectPath,
    selectedItemId: selectedArtifactId,
    setSelectedItemId: setSelectedArtifactId,
    windowId
  });
  const createArtifactMutation = useMutation({
    mutationFn: ({
      artifactKind,
      artifactScope,
      artifactModelSelection,
      clientId,
      projectPath,
      windowId
    }: {
      artifactKind: string;
      artifactScope: ArtifactScope;
      artifactModelSelection: AgentModelSelection | null;
      clientId: string;
      projectPath: string | null;
      windowId: string;
    }) => (
      createTerminalArtifact(clientId, windowId, {
        artifact_kind: artifactKind,
        artifact_scope: artifactScope,
        project_path: projectPath,
        artifact_model_selection: artifactModelSelection
      })
    ),
    onSuccess: (artifact, variables) => {
      setSelectedArtifactId(terminalArtifactItemId(artifact.id));
      queryClient.invalidateQueries({ queryKey: ["terminal-artifacts", variables.clientId, variables.windowId] });
    }
  });
  const createPageReviewTodoMutation = useMutation({
    mutationFn: ({
      artifact,
      cardId,
      clientId,
      projectPath
    }: {
      artifact: TerminalArtifact;
      cardId: string;
      clientId: string;
      projectPath: string;
    }) => createProjectTodoFromPageReviewCard(clientId, projectPath, {
      artifact_id: artifact.id,
      card_id: cardId
    }),
    onSuccess: (todo, variables) => {
      queryClient.invalidateQueries({ queryKey: ["project-todos", variables.clientId, variables.projectPath] });
      queryClient.invalidateQueries({ queryKey: ["terminal-artifacts", variables.clientId, variables.artifact.virtual_window_id], exact: false });
      setSelectedArtifactId(terminalArtifactItemId(variables.artifact.id));
      if (onFocusProjectTodo) {
        onFocusProjectTodo(todo.project_path, todo.id);
      }
    }
  });
  const createProjectTodoFromArtifactMutation = useArtifactProjectTodoCreator({
    onCreated: onFocusProjectTodo,
    onInvalidateArtifactSource: (nextClientId) => {
      queryClient.invalidateQueries({ queryKey: ["terminal-artifacts", nextClientId], exact: false });
    }
  });

  useEffect(() => {
    function onKeyDown(event: KeyboardEvent): void {
      if (event.key === "Escape" && artifactFullscreen) {
        event.preventDefault();
        setArtifactFullscreen(false);
      }
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [artifactFullscreen]);
  const retryMutation = useMutation({
    mutationFn: ({
      clientId,
      windowId,
      allowTitleFolderOverride
    }: {
      clientId: string;
      windowId: string;
      allowTitleFolderOverride: boolean;
    }) => retrySummary(clientId, windowId, { allow_title_folder_override: allowTitleFolderOverride }),
    onSuccess: (_data, variables) => {
      queryClient.invalidateQueries({ queryKey: ["window", variables.clientId, variables.windowId] });
      queryClient.invalidateQueries({ queryKey: ["tree", variables.clientId], exact: false });
      queryClient.invalidateQueries({ queryKey: ["terminal-projects", variables.clientId], exact: false });
      queryClient.invalidateQueries({ queryKey: ["projects", variables.clientId], exact: false });
      queryClient.invalidateQueries({ queryKey: ["window-activity", variables.clientId], exact: false });
    }
  });
  const renameMutation = useMutation({
    mutationFn: ({
      clientId,
      windowId,
      title
    }: {
      clientId: string;
      windowId: string;
      title: string;
    }) => updateWindowTitle(clientId, windowId, title),
    onSuccess: (updated, variables) => {
      queryClient.setQueryData(["window", variables.clientId, variables.windowId], updated);
      queryClient.setQueriesData<TreeFolderCore[]>(
        { queryKey: ["tree", variables.clientId], exact: false },
        (current) => renameTreeWindow(current, variables.windowId, updated.title)
      );
      queryClient.invalidateQueries({ queryKey: ["window", variables.clientId, variables.windowId] });
      queryClient.invalidateQueries({ queryKey: ["tree", variables.clientId], exact: false });
      queryClient.invalidateQueries({ queryKey: ["terminal-projects", variables.clientId], exact: false });
      queryClient.invalidateQueries({ queryKey: ["projects", variables.clientId], exact: false });
      queryClient.invalidateQueries({ queryKey: ["window-activity", variables.clientId], exact: false });
      queryClient.invalidateQueries({ queryKey: ["title-history", variables.clientId, variables.windowId] });
      queryClient.invalidateQueries({ queryKey: ["terminal-recents", variables.clientId] });
      setTitleDraft(updated.title);
      setIsEditingTitle(false);
    }
  });
  const manualWorkStatusMutation = useMutation({
    mutationFn: ({
      clientId,
      windowId,
      state
    }: {
      clientId: string;
      windowId: string;
      state: WorkStatusState | null;
    }) => updateManualWorkStatus(clientId, windowId, state),
    onSuccess: (workStatus, variables) => {
      queryClient.setQueryData<VirtualWindow>(
        ["window", variables.clientId, variables.windowId],
        (current) => current ? { ...current, work_status: workStatus } : current
      );
      queryClient.invalidateQueries({ queryKey: ["window", variables.clientId, variables.windowId] });
      queryClient.invalidateQueries({ queryKey: ["window-activity", variables.clientId], exact: false });
      queryClient.invalidateQueries({ queryKey: ["terminal-notifications", variables.clientId], exact: false });
      queryClient.invalidateQueries({ queryKey: ["tree", variables.clientId], exact: false });
    }
  });

  if (clientId === null || windowId === null) {
    return <p className="muted">{t("window.detail.selectArtifact")}</p>;
  }
  if (windowQuery.isLoading) {
    return <p className="muted">{t("window.detail.loading")}</p>;
  }
  if (windowQuery.isError || !windowQuery.data) {
    return <p className="error" role="alert">{t("window.detail.loadFailed")}</p>;
  }

  const item = windowQuery.data;
  const artifactModelAgent = artifactModelAgentFromWindow(item);
  const effectiveGitWorktree = queryGitWorktree ?? gitWorktree;
  const status = summaryStatus(item.summary_job, item.command_capture_supported !== false, t);
  const tags = displayTags(item);
  const trimmedTitleDraft = titleDraft.trim();
  const titleSaveDisabled =
    renameMutation.isPending
    || trimmedTitleDraft.length === 0
    || trimmedTitleDraft.length > MAX_TITLE_LENGTH
    || trimmedTitleDraft === item.title;
  const manualLocks = [
    item.title_manually_overridden ? t("window.detail.titleLocked") : null,
    item.folder_manually_overridden ? t("window.detail.folderLocked") : null
  ].filter((lock): lock is string => lock !== null);
  const creatingPageReviewTodo = createPageReviewTodoMutation.isPending && createPageReviewTodoMutation.variables
    ? {
        artifactId: createPageReviewTodoMutation.variables.artifact.id,
        cardId: createPageReviewTodoMutation.variables.cardId
      }
    : null;
  return (
    <div>
      <WindowTitleHeader
        isEditingTitle={isEditingTitle}
        renameError={renameMutation.isError ? renameMutation.error : null}
        renamePending={renameMutation.isPending}
        title={item.title}
        titleDraft={titleDraft}
        titleSaveDisabled={titleSaveDisabled}
        onBeginEdit={() => {
          setTitleDraft(item.title);
          setIsEditingTitle(true);
          renameMutation.reset();
        }}
        onCancelEdit={() => {
          setTitleDraft(item.title);
          setIsEditingTitle(false);
          renameMutation.reset();
        }}
        onSubmit={() => renameMutation.mutate({ clientId, windowId: item.id, title: trimmedTitleDraft })}
        onTitleDraftChange={setTitleDraft}
      />
      <DetailPanelTabs activeTab={detailTab} showGitTab={showGitTab} onTabChange={setDetailTab} />

      {detailTab === "overview" && (
        <WindowOverviewPanel
          allowTitleFolderOverride={allowTitleFolderOverride}
          clientId={clientId}
          gitWorktree={effectiveGitWorktree}
          item={item}
          manualLocks={manualLocks}
          manualWorkStatusError={manualWorkStatusMutation.isError}
          manualWorkStatusPending={manualWorkStatusMutation.isPending}
          retryError={retryMutation.isError}
          retryPending={retryMutation.isPending}
          showGitTab={effectiveGitWorktree !== null}
          status={status}
          tags={tags}
          windowId={windowId}
          onAllowTitleFolderOverrideChange={setAllowTitleFolderOverride}
          onFocusProjectTodo={onFocusProjectTodo}
          onManualWorkStatusChange={(state) => (
            manualWorkStatusMutation.mutate({ clientId, windowId: item.id, state })
          )}
          onRetrySummary={() => retryMutation.mutate({ clientId, windowId: item.id, allowTitleFolderOverride })}
        />
      )}

      {detailTab === "agent" && (
        <WindowAgentSection
          agentConfig={agentConfig}
          agentDetailTab={agentDetailTab}
          agentRecord={agentRecord}
          agentRecordShortcutLabel={agentRecordShortcutLabel}
          canSendQuickInput={canSendQuickInput}
          onQuickInputDraftChange={onQuickInputDraftChange}
          onQuickInputSubmit={onQuickInputSubmit}
          projectFileContext={projectFileContext}
          quickInputDraft={quickInputDraft}
          setAgentDetailTab={setAgentDetailTab}
          terminalStatusLabel={terminalStatusLabel}
          terminalStatusTone={terminalStatusTone}
        />
      )}

      {detailTab === "history" && (
        <WindowHistorySection
          commandHistoryQuery={commandHistoryQuery}
          historyDetailTab={historyDetailTab}
          setCommandHistoryPage={setCommandHistoryPage}
          setHistoryDetailTab={setHistoryDetailTab}
          setTitleHistoryPage={setTitleHistoryPage}
          titleHistoryQuery={titleHistoryQuery}
        />
      )}

      {detailTab === "artifacts" && (
        <WindowArtifactsPanel
          artifactFullscreen={artifactFullscreen}
          artifactPage={artifactPage}
          artifactScope={artifactScope}
          artifactItems={artifactItems}
          artifactsData={artifactsData}
          artifactsError={artifactsQuery.isError || previewQuery.isError}
          artifactsFetching={artifactsQuery.isFetching || previewQuery.isFetching}
          artifactsLoading={artifactsQuery.isLoading || previewQuery.isLoading}
          clientId={clientId}
          createArtifactError={createArtifactMutation.isError ? createArtifactMutation.error : null}
          createArtifactPending={createArtifactMutation.isPending}
          createPageReviewTodoError={
            createPageReviewTodoMutation.isError
              ? createPageReviewTodoMutation.error
              : createProjectTodoFromArtifactMutation.isError
                ? createProjectTodoFromArtifactMutation.error
                : null
          }
          creatingPageReviewTodo={creatingPageReviewTodo}
          itemWindowId={item.id}
          artifactModelAgent={artifactModelAgent}
          artifactModelSelection={artifactModelSelection}
          projectPath={itemProjectPath}
          selectedItem={selectedItem}
          selectedItemCanDisplay={selectedItemCanDisplay}
          selectedItemId={selectedArtifactId}
          selectedItemReady={selectedItemReady}
          selectedItemSrcDoc={selectedItemSrcDoc}
          selectedItemHtmlError={selectedItemHtmlQuery.isError}
          windowId={windowId}
          onCreateArtifact={(nextClientId, nextWindowId, artifactKind, nextArtifactScope, nextArtifactModelSelection) => (
            createArtifactMutation.mutate({
              artifactKind,
              artifactScope: nextArtifactScope,
              artifactModelSelection: nextArtifactModelSelection ?? artifactModelDefaultSelection(artifactModelAgent),
              clientId: nextClientId,
              projectPath: nextArtifactScope === "project" ? itemProjectPath : null,
              windowId: nextWindowId
            })
          )}
          onCreateProjectTodoFromArtifact={(card, artifactId) => {
            if (itemProjectPath === null) {
              return Promise.reject(new Error("project path is required"));
            }
            return createProjectTodoFromArtifactMutation.mutateAsync({
              artifactId,
              card,
              clientId,
              projectPath: itemProjectPath
            });
          }}
          onArtifactModelSelectionChange={setArtifactModelSelection}
          onArtifactScopeChange={(nextScope) => {
            setArtifactScope(nextScope);
            setArtifactPage(0);
            setSelectedArtifactId(null);
          }}
          onCreatePageReviewTodo={(artifact, cardId) => {
            if (itemProjectPath === null) {
              return;
            }
            createPageReviewTodoMutation.mutate({
              artifact,
              cardId,
              clientId,
              projectPath: itemProjectPath
            });
          }}
          onOpenArtifactTerminal={onOpenArtifactTerminal}
          setArtifactFullscreen={setArtifactFullscreen}
          setArtifactPage={setArtifactPage}
          setSelectedItemId={setSelectedArtifactId}
        />
      )}

      {detailTab === "git" && effectiveGitWorktree !== null && <GitRunViewer clientId={clientId} windowId={windowId} />}
    </div>
  );
}
