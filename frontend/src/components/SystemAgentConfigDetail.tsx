import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Tree, type NodeRendererProps } from "react-arborist";

import {
  fetchSystemAgentConfig,
  fetchSystemSkillDetail,
  updateSystemSkillFile
} from "../api";
import { useI18n } from "../i18n";
import { MarkdownText } from "./AgentRecordMarkdown";
import { UiIcon } from "./UiIcon";
import { isMarkdown } from "./projectFilesUtils";
import {
  buildSkillTree,
  type SkillTreeNode
} from "./systemAgentConfigDetailModel";
import { SystemDetailHeader } from "./SystemAgentConfigDetailHeader";
import { SystemMcpDetailPanel } from "./SystemAgentMcpDetailPanel";
import type {
  AgentConfig,
  SystemSkillFile
} from "../types";

type SystemConfigSectionId = "skills" | "mcp";
type SystemStatus = { message: string; kind: "info" | "error" };
type SkillFileViewMode = "preview" | "source";

function byteLabel(size: number | null): string {
  if (size === null) {
    return "-";
  }
  if (size < 1024) {
    return `${size} B`;
  }
  if (size < 1024 * 1024) {
    return `${(size / 1024).toFixed(1)} KB`;
  }
  return `${(size / 1024 / 1024).toFixed(1)} MB`;
}

function errorMessage(error: unknown, fallback: string): string {
  return error instanceof Error ? error.message : fallback;
}

function normalizedSearch(value: string): string {
  return value.trim().toLocaleLowerCase();
}

function entryMatchesQuery(entry: SkillTreeNode, query: string): boolean {
  return entry.name.toLocaleLowerCase().includes(query)
    || entry.path.toLocaleLowerCase().includes(query);
}

function filterSkillTree(nodes: SkillTreeNode[], query: string): SkillTreeNode[] {
  if (query === "") {
    return nodes;
  }
  return nodes.flatMap((node) => {
    const children = node.children === undefined ? undefined : filterSkillTree(node.children, query);
    if (entryMatchesQuery(node, query) || (children !== undefined && children.length > 0)) {
      return [{
        ...node,
        children
      }];
    }
    return [];
  });
}

function countSkillTreeNodes(nodes: SkillTreeNode[]): number {
  return nodes.reduce((total, node) => total + 1 + countSkillTreeNodes(node.children ?? []), 0);
}

function SkillTreeNodeRow({
  node,
  style,
  dragHandle
}: NodeRendererProps<SkillTreeNode>) {
  const item = node.data;
  return (
    <div
      ref={dragHandle}
      style={style}
      className={[
        "project-file-node",
        "system-skill-file-node",
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

export function SystemAgentConfigDetail({
  sectionId,
  itemId,
  onConfigChange,
  onReset,
  onStatus
}: {
  sectionId: SystemConfigSectionId;
  itemId: string;
  onConfigChange: (config: AgentConfig) => void;
  onReset: (sectionId: SystemConfigSectionId, itemId: string) => void;
  onStatus: (status: SystemStatus | null) => void;
}) {
  if (sectionId === "skills") {
    return (
      <SystemSkillDetailPanel
        itemId={itemId}
        onConfigChange={onConfigChange}
        onReset={onReset}
        onStatus={onStatus}
      />
    );
  }
  return <SystemMcpDetailPanel itemId={itemId} onReset={onReset} />;
}

function SystemSkillDetailPanel({
  itemId,
  onConfigChange,
  onReset,
  onStatus
}: {
  itemId: string;
  onConfigChange: (config: AgentConfig) => void;
  onReset: (sectionId: SystemConfigSectionId, itemId: string) => void;
  onStatus: (status: SystemStatus | null) => void;
}) {
  const { t } = useI18n();
  const queryClient = useQueryClient();
  const query = useQuery({
    queryKey: ["system-skill-detail", itemId],
    queryFn: () => fetchSystemSkillDetail(itemId)
  });
  const detail = query.data ?? null;
  const editableFiles = useMemo(
    () => detail?.files.filter((file) => file.content !== null) ?? [],
    [detail?.files]
  );
  const treeData = useMemo(() => buildSkillTree(detail?.entries ?? []), [detail?.entries]);
  const [selectedPath, setSelectedPath] = useState<string | null>(null);
  const [fileSearch, setFileSearch] = useState("");
  const fileSearchQuery = normalizedSearch(fileSearch);
  const filteredTreeData = useMemo(() => filterSkillTree(treeData, fileSearchQuery), [fileSearchQuery, treeData]);
  const filteredEntryCount = useMemo(() => countSkillTreeNodes(filteredTreeData), [filteredTreeData]);
  const filteredEditableFiles = useMemo(
    () => fileSearchQuery.length === 0
      ? editableFiles
      : editableFiles.filter((file) => file.path.toLocaleLowerCase().includes(fileSearchQuery)),
    [editableFiles, fileSearchQuery]
  );
  const selectedFile = selectedPath === null
    ? filteredEditableFiles[0] ?? null
    : filteredEditableFiles.find((file) => file.path === selectedPath) ?? filteredEditableFiles[0] ?? null;
  const [draft, setDraft] = useState("");

  useEffect(() => {
    setSelectedPath(null);
    setFileSearch("");
  }, [itemId]);

  useEffect(() => {
    setDraft(selectedFile?.content ?? "");
  }, [selectedFile?.content, selectedFile?.path]);

  const saveMutation = useMutation({
    mutationFn: (input: { path: string; content: string }) =>
      updateSystemSkillFile(itemId, input.path, input.content),
    onMutate: () => onStatus(null),
    onSuccess: (nextDetail) => {
      queryClient.setQueryData(["system-skill-detail", itemId], nextDetail);
      void fetchSystemAgentConfig().then((nextConfig) => {
        queryClient.setQueryData(["system-agent-config"], nextConfig);
        onConfigChange(nextConfig);
      });
      onStatus({ kind: "info", message: t("settings.system.savedSkillFile") });
    },
    onError: (error) => onStatus({ kind: "error", message: errorMessage(error, t("settings.system.saveFailed")) })
  });

  if (query.isLoading) {
    return <section className="system-config-detail"><p className="muted">{t("settings.system.loadingDetail")}</p></section>;
  }
  if (query.isError || detail === null) {
    return <section className="system-config-detail"><p className="error">{t("settings.system.loadDetailFailed")}</p></section>;
  }

  const dirty = selectedFile !== null && draft !== (selectedFile.content ?? "");
  const canSave = selectedFile?.editable === true && dirty && !saveMutation.isPending;

  return (
    <section className="system-config-detail" aria-label={t("settings.system.detailLabel", { name: detail.name })}>
      <SystemDetailHeader detail={detail} onReset={() => onReset("skills", itemId)} />
      <div className="system-config-detail-grid system-config-skill-detail-grid">
        <div className="system-config-detail-tree system-config-skill-tree">
          <div className="system-config-detail-section-title">
            <h4>{t("settings.system.directory")}</h4>
            <span>
              {fileSearchQuery.length > 0
                ? t("settings.system.filteredEntriesCount", { count: filteredEntryCount, total: detail.entries.length })
                : detail.entries.length}
            </span>
          </div>
          <label className="system-config-search system-config-file-search">
            <span>{t("settings.system.searchFiles")}</span>
            <div className="system-config-search-row">
              <input
                type="search"
                value={fileSearch}
                placeholder={t("settings.system.searchFilesPlaceholder")}
                onChange={(event) => setFileSearch(event.target.value)}
              />
              {fileSearchQuery.length > 0 ? (
                <button
                  type="button"
                  className="ui-icon-button"
                  aria-label={t("common.clear")}
                  title={t("common.clear")}
                  onClick={() => setFileSearch("")}
                >
                  <UiIcon name="x" />
                </button>
              ) : null}
            </div>
          </label>
          {treeData.length === 0 ? (
            <p className="muted system-config-detail-empty">{t("settings.system.noFiles")}</p>
          ) : filteredTreeData.length === 0 ? (
            <p className="muted system-config-detail-empty">{t("settings.system.noMatchingItems")}</p>
          ) : (
            <Tree<SkillTreeNode>
              data={filteredTreeData}
              idAccessor="id"
              childrenAccessor="children"
              width="100%"
              height={520}
              indent={16}
              rowHeight={28}
              openByDefault
              selection={selectedFile?.path ?? undefined}
              disableDrag
              disableDrop
              onActivate={(node) => {
                const item = node.data;
                if (item.kind === "directory") {
                  node.toggle();
                  return;
                }
                setSelectedPath(item.path);
              }}
              onSelect={(selectedNodes) => {
                const item = selectedNodes[0]?.data;
                if (item?.kind === "file") {
                  setSelectedPath(item.path);
                }
              }}
            >
              {SkillTreeNodeRow}
            </Tree>
          )}
        </div>
        <div className="system-config-file-editor">
          {selectedFile === null ? (
            <p className="muted system-config-detail-empty">{t("settings.system.noPreviewText")}</p>
          ) : (
            <SkillFileEditor
              canSave={canSave}
              draft={draft}
              file={selectedFile}
              readOnly={!selectedFile.editable}
              onDraftChange={setDraft}
              onSave={() => saveMutation.mutate({ path: selectedFile.path, content: draft })}
            />
          )}
        </div>
      </div>
    </section>
  );
}

function SkillFileEditor({
  canSave,
  draft,
  file,
  readOnly,
  onDraftChange,
  onSave
}: {
  canSave: boolean;
  draft: string;
  file: SystemSkillFile;
  readOnly: boolean;
  onDraftChange: (value: string) => void;
  onSave: () => void;
}) {
  const { t } = useI18n();
  const markdown = isMarkdown(file.path);
  const [viewMode, setViewMode] = useState<SkillFileViewMode>(markdown ? "preview" : "source");

  useEffect(() => {
    setViewMode(markdown ? "preview" : "source");
  }, [file.path, markdown]);

  return (
    <>
      <div className="system-config-file-editor-header">
        <div>
          <strong>{file.path}</strong>
          <small>{byteLabel(file.size)} · {readOnly ? t("settings.artifacts.readOnly") : t("settings.artifacts.editable")}</small>
        </div>
        <div className="system-config-file-editor-actions">
          {markdown && (
            <div className="workspace-mode-toggle" role="group" aria-label={t("settings.system.skillDisplayMode")}>
              <button
                type="button"
                className={viewMode === "preview" ? "active" : ""}
                aria-pressed={viewMode === "preview"}
                onClick={() => setViewMode("preview")}
              >
                Markdown
              </button>
              <button
                type="button"
                className={viewMode === "source" ? "active" : ""}
                aria-pressed={viewMode === "source"}
                onClick={() => setViewMode("source")}
              >
                {t("settings.system.source")}
              </button>
            </div>
          )}
          <button
            type="button"
            className="system-config-icon-button"
            disabled={!canSave}
            aria-label={`${t("common.save")} ${file.path}`}
            title={t("common.save")}
            onClick={onSave}
          >
            <UiIcon name="save" />
          </button>
        </div>
      </div>
      <div className="system-config-file-body">
        {markdown && viewMode === "preview" ? (
          <article className="system-config-markdown-preview markdown-preview" aria-label={t("settings.system.renderedMarkdown", { path: file.path })}>
            <MarkdownText text={draft} />
          </article>
        ) : (
          <textarea
            value={draft}
            readOnly={readOnly}
            spellCheck={false}
            aria-label={`${file.path} ${t("settings.system.source")}`}
            onChange={(event) => onDraftChange(event.target.value)}
          />
        )}
      </div>
    </>
  );
}
