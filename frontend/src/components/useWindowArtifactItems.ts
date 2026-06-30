import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { useEffect, type Dispatch, type SetStateAction } from "react";

import {
  fetchArtifactPluginPreviewHtml,
  fetchArtifactPluginPreviews,
  fetchProjectArtifactHtml,
  fetchTerminalArtifactHtml,
  fetchTerminalArtifacts
} from "../api";
import type { ArtifactListItem, ArtifactScope } from "../types";
import { ARTIFACT_PAGE_SIZE } from "./windowDetailData";

type UseWindowArtifactItemsArgs = {
  artifactPage: number;
  artifactScope: ArtifactScope;
  clientId: string | null;
  enabled: boolean;
  projectPath: string | null;
  selectedItemId: string | null;
  setSelectedItemId: Dispatch<SetStateAction<string | null>>;
  windowId: string | null;
};

export function useWindowArtifactItems({
  artifactPage,
  artifactScope,
  clientId,
  enabled,
  projectPath,
  selectedItemId,
  setSelectedItemId,
  windowId
}: UseWindowArtifactItemsArgs) {
  const artifactsQuery = useQuery({
    queryKey: [
      "terminal-artifacts",
      clientId,
      windowId,
      artifactScope,
      projectPath,
      artifactPage,
      ARTIFACT_PAGE_SIZE
    ],
    queryFn: () => fetchTerminalArtifacts(
      clientId as string,
      windowId as string,
      ARTIFACT_PAGE_SIZE,
      artifactPage * ARTIFACT_PAGE_SIZE,
      artifactScope,
      projectPath
    ),
    enabled: clientId !== null
      && windowId !== null
      && enabled
      && (artifactScope === "terminal" || projectPath !== null),
    placeholderData: keepPreviousData,
    refetchInterval: (query) => {
      const artifacts = query.state.data?.artifacts ?? [];
      return artifacts.some((artifact) => ["PENDING", "RUNNING"].includes(artifact.status.toUpperCase()))
        ? 2500
        : 10000;
    }
  });
  const previewQuery = useQuery({
    queryKey: ["artifact-plugin-previews", clientId, windowId, artifactPage, ARTIFACT_PAGE_SIZE],
    queryFn: () => fetchArtifactPluginPreviews(
      clientId as string,
      windowId as string,
      ARTIFACT_PAGE_SIZE,
      artifactPage * ARTIFACT_PAGE_SIZE
    ),
    enabled: clientId !== null && windowId !== null && enabled && artifactScope === "terminal",
    placeholderData: keepPreviousData,
    refetchInterval: 10000
  });
  const previews = artifactScope === "terminal" ? previewQuery.data?.previews ?? [] : [];
  const artifactItems: ArtifactListItem[] = [
    ...previews.map((preview): ArtifactListItem => ({
      kind: "plugin_preview",
      id: pluginPreviewItemId(preview.id),
      preview
    })),
    ...(artifactsQuery.data?.artifacts ?? []).map((artifact): ArtifactListItem => ({
      kind: "terminal_artifact",
      id: terminalArtifactItemId(artifact.id),
      artifact
    }))
  ];
  const artifactsData = artifactsQuery.data !== undefined
    || (artifactScope === "terminal" && previewQuery.data !== undefined)
    ? {
        offset: artifactPage * ARTIFACT_PAGE_SIZE,
        has_more: (artifactsQuery.data?.has_more ?? false)
          || (artifactScope === "terminal" && (previewQuery.data?.has_more ?? false))
      }
    : null;
  const selectedItem = artifactItems.find((item) => item.id === selectedItemId) ?? null;
  const selectedItemReady = selectedItem?.kind === "terminal_artifact"
    ? selectedItem.artifact.status.toUpperCase() === "SUCCEEDED"
    : selectedItem?.kind === "plugin_preview"
      ? selectedItem.preview.status === "valid"
      : false;
  const selectedItemHtmlQuery = useQuery({
    queryKey: [
      "artifact-list-item-html",
      clientId,
      windowId,
      selectedItem?.kind ?? null,
      selectedItem?.kind === "terminal_artifact" ? selectedItem.artifact.artifact_scope : null,
      selectedItem?.kind === "terminal_artifact" ? selectedItem.artifact.project_path : null,
      selectedItem?.kind === "terminal_artifact" ? selectedItem.artifact.id : selectedItem?.preview.id ?? null,
      selectedItem?.kind === "terminal_artifact" ? selectedItem.artifact.updated_at : selectedItem?.preview.updated_at ?? null
    ],
    queryFn: () => {
      if (selectedItem?.kind === "plugin_preview") {
        return fetchArtifactPluginPreviewHtml(selectedItem.preview.id);
      }
      if (selectedItem?.artifact.artifact_scope === "project" && selectedItem.artifact.project_path !== null) {
        return fetchProjectArtifactHtml(
          clientId as string,
          selectedItem.artifact.project_path,
          selectedItem.artifact.id
        );
      }
      return fetchTerminalArtifactHtml(clientId as string, windowId as string, selectedItem?.artifact.id ?? "");
    },
    enabled: clientId !== null && windowId !== null && enabled && selectedItem !== null && selectedItemReady,
    staleTime: Infinity
  });

  useEffect(() => {
    if (!enabled) {
      return;
    }
    const artifacts = artifactsQuery.data?.artifacts ?? [];
    const nextItems = [
      ...previews.map((preview) => pluginPreviewItemId(preview.id)),
      ...artifacts.map((artifact) => terminalArtifactItemId(artifact.id))
    ];
    if (nextItems.length === 0) {
      setSelectedItemId(null);
      return;
    }
    if (selectedItemId === null || !nextItems.includes(selectedItemId)) {
      setSelectedItemId(nextItems[0]);
    }
  }, [artifactScope, artifactsQuery.data, enabled, previewQuery.data, selectedItemId, setSelectedItemId]);

  const selectedItemSrcDoc = selectedItemHtmlQuery.data ?? null;
  return {
    artifactItems,
    artifactsData,
    artifactsQuery,
    previewQuery,
    selectedItem,
    selectedItemCanDisplay: selectedItemReady && selectedItemSrcDoc !== null,
    selectedItemHtmlQuery,
    selectedItemReady,
    selectedItemSrcDoc
  };
}

export function terminalArtifactItemId(artifactId: string): string {
  return `terminal_artifact:${artifactId}`;
}

function pluginPreviewItemId(previewId: string): string {
  return `plugin_preview:${previewId}`;
}
