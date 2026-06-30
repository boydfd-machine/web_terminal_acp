import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useMemo, useRef, useState } from "react";
import { Tree, type NodeRendererProps, type TreeApi } from "react-arborist";

import { downloadProjectFile, fetchProjectFiles, uploadProjectFile } from "../api";
import { useI18n } from "../i18n";
import type { ProjectFileEntry } from "../types";
import {
  ROOT_PATH,
  childPath,
  findNode,
  mergeDirectoryEntries,
  toBase64,
  type FileTreeNode
} from "./projectFilesUtils";

export function FileNode({
  node,
  style,
  dragHandle
}: NodeRendererProps<FileTreeNode>) {
  const item = node.data;
  return (
    <div
      ref={dragHandle}
      style={style}
      className={[
        "project-file-node",
        item.kind,
        node.isSelected ? "selected" : ""
      ].filter(Boolean).join(" ")}
    >
      <span
        className="project-file-disclosure"
        aria-hidden="true"
        onClick={(event) => {
          if (item.kind !== "directory") {
            return;
          }
          event.stopPropagation();
          node.toggle();
        }}
      >
        {item.kind === "directory" ? (node.isOpen ? "▾" : "▸") : ""}
      </span>
      <span className="project-file-icon" aria-hidden="true">
        {item.kind === "directory" ? "▣" : "□"}
      </span>
      <span className="project-file-name">{item.name}</span>
    </div>
  );
}

export function ProjectFileTreePanel({
  active = true,
  browseRoot,
  clientId,
  projectPath,
  selectedPath,
  onSelectEntry
}: {
  active?: boolean;
  browseRoot?: string | null;
  clientId: string | null;
  projectPath: string | null;
  selectedPath: string | null;
  onSelectEntry: (entry: ProjectFileEntry | null) => void;
}) {
  const { t } = useI18n();
  const queryClient = useQueryClient();
  const [nodes, setNodes] = useState<FileTreeNode[]>([]);
  const [activeDirectoryPath, setActiveDirectoryPath] = useState(ROOT_PATH);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const treeHostRef = useRef<HTMLDivElement | null>(null);
  const treeRef = useRef<TreeApi<FileTreeNode> | undefined>(undefined);
  const [treeHeight, setTreeHeight] = useState(560);
  const selectedPathRef = useRef(selectedPath);
  selectedPathRef.current = selectedPath;
  const onSelectEntryRef = useRef(onSelectEntry);
  onSelectEntryRef.current = onSelectEntry;
  const rootQuery = useQuery({
    queryKey: ["project-files", clientId, projectPath, browseRoot ?? null, ROOT_PATH],
    queryFn: () => fetchProjectFiles(clientId as string, projectPath as string, ROOT_PATH, browseRoot),
    enabled: active && clientId !== null && projectPath !== null,
    refetchInterval: 15000
  });
  const directoryQuery = useQuery({
    queryKey: ["project-files", clientId, projectPath, browseRoot ?? null, activeDirectoryPath],
    queryFn: () => fetchProjectFiles(clientId as string, projectPath as string, activeDirectoryPath, browseRoot),
    enabled: active && clientId !== null && projectPath !== null && activeDirectoryPath !== ROOT_PATH,
    staleTime: 10000
  });

  useEffect(() => {
    setNodes([]);
    setActiveDirectoryPath(ROOT_PATH);
    setUploadError(null);
    if (selectedPathRef.current === null) {
      onSelectEntryRef.current(null);
    }
  }, [browseRoot, clientId, projectPath]);

  useEffect(() => {
    if (rootQuery.data) {
      setNodes((currentNodes) => mergeDirectoryEntries(currentNodes, ROOT_PATH, rootQuery.data.entries));
    }
  }, [rootQuery.data]);

  useEffect(() => {
    if (directoryQuery.data) {
      setNodes((currentNodes) => mergeDirectoryEntries(
        currentNodes,
        directoryQuery.data.path,
        directoryQuery.data.entries
      ));
    }
  }, [directoryQuery.data]);

  useEffect(() => {
    const treeHost = treeHostRef.current;
    if (treeHost === null) {
      return;
    }
    const measure = () => {
      setTreeHeight(Math.max(240, Math.floor(treeHost.clientHeight)));
    };
    measure();
    if (typeof ResizeObserver === "undefined") {
      window.addEventListener("resize", measure);
      return () => window.removeEventListener("resize", measure);
    }
    const observer = new ResizeObserver(measure);
    observer.observe(treeHost);
    return () => observer.disconnect();
  }, [nodes.length]);

  const selectedNode = useMemo(
    () => selectedPath === null ? null : findNode(nodes, selectedPath),
    [nodes, selectedPath]
  );
  useEffect(() => {
    if (selectedPath === null || selectedNode !== null) {
      return;
    }
    setActiveDirectoryPath(
      selectedPath.includes("/") ? selectedPath.slice(0, selectedPath.lastIndexOf("/")) : ROOT_PATH
    );
  }, [selectedNode, selectedPath]);
  useEffect(() => {
    if (selectedPath === null || selectedNode === null) {
      return;
    }
    const tree = treeRef.current;
    if (tree === undefined) {
      return;
    }
    let cancelled = false;
    Promise.resolve(tree.scrollTo(selectedPath, "center")).then(() => {
      if (!cancelled) {
        tree.select(selectedPath, { align: "center", focus: false });
      }
    });
    return () => {
      cancelled = true;
    };
  }, [selectedNode, selectedPath]);
  const selectedDirectoryPath = selectedNode?.kind === "directory"
    ? selectedNode.path
    : selectedNode?.path.includes("/")
      ? selectedNode.path.slice(0, selectedNode.path.lastIndexOf("/"))
      : ROOT_PATH;
  const selectedFilePath = selectedNode?.kind === "file" ? selectedNode.path : null;
  const canDownload = clientId !== null && projectPath !== null && selectedFilePath !== null;
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
    onError: (error) => setUploadError(error instanceof Error ? error.message : t("projectFiles.uploadFailed"))
  });

  if (clientId === null || projectPath === null) {
    return <p className="muted terminal-project-empty">{t("projectFiles.noProjectTree")}</p>;
  }

  return (
    <div className="project-file-tree-panel">
      <div className="project-files-toolbar">
        <strong>{t("projectFiles.title")}</strong>
        <div className="project-files-actions">
          <button type="button" disabled={uploadMutation.isPending} onClick={() => fileInputRef.current?.click()}>
            {t("projectFiles.upload")}
          </button>
          <button
            type="button"
            disabled={!canDownload}
            onClick={() => {
              if (clientId !== null && projectPath !== null && selectedFilePath !== null) {
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
            uploadMutation.mutate({ file, targetPath: childPath(selectedDirectoryPath, file.name) });
          }}
        />
      </div>
      {rootQuery.isLoading && <p className="muted project-files-status">{t("projectFiles.loading")}</p>}
      {rootQuery.isError && <p className="error project-files-status" role="alert">{t("projectFiles.loadFailed")}</p>}
      {uploadError !== null && <p className="error project-files-status" role="alert">{uploadError}</p>}
      {nodes.length > 0 && (
        <div ref={treeHostRef} className="project-file-tree-host">
        <Tree<FileTreeNode>
          ref={treeRef}
          data={nodes}
          idAccessor="id"
          childrenAccessor="children"
          width="100%"
          height={treeHeight}
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
            if (item === undefined) {
              return;
            }
            onSelectEntry(item);
            if (item.kind === "directory") {
              setActiveDirectoryPath(item.path);
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
        </div>
      )}
    </div>
  );
}
