import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Tree } from "react-arborist";

import { downloadProjectFile, fetchProjectFiles, uploadProjectFile } from "../api";
import { useI18n } from "../i18n";
import type { ProjectFileEntry } from "../types";
import { ProjectFilePreviewPanel } from "./ProjectFilePreviewPanel";
import { FileNode, ProjectFileTreePanel } from "./ProjectFileTreePanel";
import {
  ROOT_PATH,
  childPath,
  entryFromNode,
  findNode,
  mergeDirectoryEntries,
  toBase64,
  type FileTreeNode
} from "./projectFilesUtils";

type ProjectFilesViewProps = {
  browseRoot?: string | null;
  clientId: string | null;
  projectPath: string | null;
};

export function ProjectFilesView({
  browseRoot,
  clientId,
  projectPath
}: ProjectFilesViewProps) {
  const { t } = useI18n();
  const queryClient = useQueryClient();
  const [nodes, setNodes] = useState<FileTreeNode[]>([]);
  const [selectedPath, setSelectedPath] = useState<string | null>(null);
  const [activeDirectoryPath, setActiveDirectoryPath] = useState(ROOT_PATH);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [previewMode, setPreviewMode] = useState<"edit" | "preview">("preview");
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  const rootQuery = useQuery({
    queryKey: ["project-files", clientId, projectPath, browseRoot ?? null, ROOT_PATH],
    queryFn: () => fetchProjectFiles(clientId as string, projectPath as string, ROOT_PATH, browseRoot),
    enabled: clientId !== null && projectPath !== null,
    refetchInterval: 15000
  });

  useEffect(() => {
    setNodes([]);
    setSelectedPath(null);
    setActiveDirectoryPath(ROOT_PATH);
    setUploadError(null);
  }, [browseRoot, clientId, projectPath]);

  useEffect(() => {
    if (!rootQuery.data) {
      return;
    }
    setNodes((currentNodes) => mergeDirectoryEntries(currentNodes, ROOT_PATH, rootQuery.data.entries));
  }, [rootQuery.data]);

  const directoryQuery = useQuery({
    queryKey: ["project-files", clientId, projectPath, browseRoot ?? null, activeDirectoryPath],
    queryFn: () => fetchProjectFiles(clientId as string, projectPath as string, activeDirectoryPath, browseRoot),
    enabled: clientId !== null
      && projectPath !== null
      && activeDirectoryPath !== ROOT_PATH,
    staleTime: 10000
  });

  useEffect(() => {
    if (!directoryQuery.data) {
      return;
    }
    setNodes((currentNodes) => mergeDirectoryEntries(
      currentNodes,
      directoryQuery.data.path,
      directoryQuery.data.entries
    ));
  }, [directoryQuery.data]);

  const selectedNode = useMemo(
    () => selectedPath === null ? null : findNode(nodes, selectedPath),
    [nodes, selectedPath]
  );
  const selectedFilePath = selectedNode?.kind === "file" ? selectedNode.path : null;

  const uploadMutation = useMutation({
    mutationFn: async ({ file, targetPath }: { file: File; targetPath: string }) => {
      const contentBase64 = toBase64(await file.arrayBuffer());
      return uploadProjectFile(clientId as string, projectPath as string, targetPath, contentBase64, true, browseRoot);
    },
    onSuccess: (_result, variables) => {
      const directory = variables.targetPath.includes("/")
        ? variables.targetPath.slice(0, variables.targetPath.lastIndexOf("/"))
        : ROOT_PATH;
      queryClient.invalidateQueries({ queryKey: ["project-files", clientId, projectPath, browseRoot ?? null, directory] });
      queryClient.invalidateQueries({ queryKey: ["project-file-content", clientId, projectPath, browseRoot ?? null] });
      setActiveDirectoryPath(directory);
      setUploadError(null);
    },
    onError: (error) => {
      setUploadError(error instanceof Error ? error.message : t("projectFiles.uploadFailed"));
    }
  });

  const handleSelectPath = useCallback((path: string) => {
    const node = findNode(nodes, path);
    if (node === null) {
      return;
    }
    setSelectedPath(path);
    if (node.kind === "directory") {
      setActiveDirectoryPath(node.path);
    }
  }, [nodes]);

  const selectedDirectoryPath = selectedNode?.kind === "directory"
    ? selectedNode.path
    : selectedNode?.path.includes("/")
      ? selectedNode.path.slice(0, selectedNode.path.lastIndexOf("/"))
      : ROOT_PATH;

  if (clientId === null || projectPath === null) {
    return (
      <div className="project-files-empty">
        <p>{t("projectFiles.selectProject")}</p>
      </div>
    );
  }

  return (
    <div className="project-files-view">
      <aside className="project-files-sidebar" aria-label={t("projectFiles.sidebarLabel")}>
        <div className="project-files-toolbar">
          <strong>{t("projectFiles.title")}</strong>
          <div className="project-files-actions">
            <button
              type="button"
              disabled={uploadMutation.isPending}
              onClick={() => fileInputRef.current?.click()}
            >
              {t("projectFiles.upload")}
            </button>
            <button
              type="button"
              disabled={selectedFilePath === null}
              onClick={() => {
                if (selectedFilePath !== null) {
                  void downloadProjectFile(clientId, projectPath, selectedFilePath, browseRoot)
                    .catch((error) => setUploadError(error instanceof Error ? error.message : t("projectFiles.downloadFailed")));
                }
              }}
            >
              {t("common.download")}
            </button>
          </div>
          <input
            ref={fileInputRef}
            type="file"
            className="visually-hidden"
            onChange={(event) => {
              const file = event.currentTarget.files?.[0] ?? null;
              event.currentTarget.value = "";
              if (file === null) {
                return;
              }
              uploadMutation.mutate({
                file,
                targetPath: childPath(selectedDirectoryPath, file.name)
              });
            }}
          />
        </div>
        {rootQuery.isLoading && <p className="muted project-files-status">{t("projectFiles.loading")}</p>}
        {rootQuery.isError && <p className="error project-files-status" role="alert">{t("projectFiles.loadFailed")}</p>}
        {uploadError !== null && <p className="error project-files-status" role="alert">{uploadError}</p>}
        {!rootQuery.isLoading && nodes.length === 0 && !rootQuery.isError && (
          <p className="muted project-files-status">{t("projectFiles.empty")}</p>
        )}
        {nodes.length > 0 && (
          <Tree<FileTreeNode>
            data={nodes}
            idAccessor="id"
            childrenAccessor="children"
            width="100%"
            height={560}
            indent={16}
            rowHeight={28}
            openByDefault={false}
            selection={selectedPath ?? undefined}
            disableDrag
            disableDrop
            onActivate={(node) => {
              const item = node.data;
              if (item.kind !== "directory") {
                return;
              }
              setActiveDirectoryPath(item.path);
              if (node.isClosed) {
                node.open();
              }
            }}
            onSelect={(selectedNodes) => {
              const item = selectedNodes[0]?.data;
              if (item !== undefined) {
                handleSelectPath(item.path);
              }
            }}
            onToggle={(nodeId) => {
              const node = findNode(nodes, String(nodeId));
              if (node?.kind === "directory") {
                setActiveDirectoryPath(node.path);
              }
            }}
          >
            {FileNode}
          </Tree>
        )}
      </aside>
      <ProjectFilePreviewPanel
        browseRoot={browseRoot}
        clientId={clientId}
        projectPath={projectPath}
        entry={entryFromNode(selectedNode)}
        mode={previewMode}
        onModeChange={setPreviewMode}
      />
    </div>
  );
}

export { ProjectFilePreviewPanel } from "./ProjectFilePreviewPanel";
export { ProjectFileTreePanel } from "./ProjectFileTreePanel";
