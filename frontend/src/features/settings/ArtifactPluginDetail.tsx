import { useEffect, useMemo, useRef, useState, type ReactNode } from "react";

import { ARTIFACT_IFRAME_SANDBOX } from "../../artifactHtmlSecurity";
import { UiIcon } from "../../components/UiIcon";
import { useOverlayFocus } from "../../components/useOverlayFocus";
import { useI18n } from "../../i18n";
import type { ArtifactPluginDescriptor, ArtifactPluginDomain, ArtifactPluginFormat } from "../../types";
import {
  artifactPluginFiles,
  artifactPluginOriginLabel,
  byteLabel,
  draftWithFileContent,
  previewContentError,
  schemaError,
  type ArtifactPluginDraft,
  type ArtifactPluginFile
} from "./artifactPluginSettingsModel";

type ArtifactPluginMode = "selected" | "create";
export type ArtifactPluginStatus = { kind: "info" | "error"; message: string };

export function ArtifactPluginDetail({
  busy,
  draft,
  mode,
  plugin,
  pluginDomain,
  pluginFormat,
  sourceError,
  sourceLoading,
  previewError,
  previewLoading,
  previewModalOpen,
  previewSrcDoc,
  status,
  canDelete,
  canSave,
  onDelete,
  onDraftChange,
  onDownload,
  onPreviewModalOpenChange,
  onSave,
  onStatusClear
}: {
  busy: boolean;
  draft: ArtifactPluginDraft;
  mode: ArtifactPluginMode;
  plugin: ArtifactPluginDescriptor | null;
  pluginDomain: ArtifactPluginDomain;
  pluginFormat: ArtifactPluginFormat;
  sourceError: boolean;
  sourceLoading: boolean;
  previewError: string | null;
  previewLoading: boolean;
  previewModalOpen: boolean;
  previewSrcDoc: string | null;
  status: ArtifactPluginStatus | null;
  canDelete: boolean;
  canSave: boolean;
  onDelete: () => void;
  onDraftChange: (draft: ArtifactPluginDraft) => void;
  onDownload: () => void;
  onPreviewModalOpenChange: (open: boolean) => void;
  onSave: () => void;
  onStatusClear: () => void;
}) {
  const { t } = useI18n();
  const files = useMemo(() => artifactPluginFiles(draft, plugin, pluginFormat, t), [draft, plugin, pluginFormat, t]);
  const [selectedPath, setSelectedPath] = useState<string | null>(null);
  const selectedFile = selectedPath === null
    ? files[0] ?? null
    : files.find((file) => file.path === selectedPath) ?? files[0] ?? null;
  const selectedFileError = selectedFile?.kind === "schema"
    ? schemaError(selectedFile.content, t)
    : selectedFile?.kind === "preview"
      ? previewContentError(selectedFile.content, t)
      : null;
  const editable = plugin?.editable ?? mode === "create";
  const canDownload = mode === "selected" && plugin?.downloadable !== false && !sourceLoading;

  useEffect(() => {
    setSelectedPath(null);
  }, [mode, plugin?.artifact_kind, pluginFormat]);

  const updateFileContent = (file: ArtifactPluginFile, content: string) => {
    onDraftChange(draftWithFileContent(draft, file, content));
    onStatusClear();
  };

  if (sourceLoading) {
    return <section className="system-config-detail"><p className="muted">{t("settings.artifacts.loadingFiles")}</p></section>;
  }

  if (mode === "selected" && (plugin === null || sourceError)) {
    return <section className="system-config-detail"><p className="error">{t("settings.artifacts.loadFilesFailed")}</p></section>;
  }

  return (
    <section
      className="system-config-detail artifact-plugin-detail"
      aria-label={mode === "create" ? t("settings.artifacts.newDetail", { domain: pluginDomain }) : t("settings.artifacts.detail", { label: plugin?.label ?? t("settings.artifacts.plugin") })}
    >
      <header className="system-config-detail-header">
        <div>
          <strong>{mode === "create" ? t("settings.artifacts.newDetail", { domain: pluginDomain }) : plugin?.label}</strong>
          <small>{mode === "create" ? `${pluginDomain}/custom_report` : `${plugin?.domain}/${plugin?.artifact_kind}`}</small>
        </div>
        <div className="system-config-detail-meta">
          <span>{pluginFormat === "template" ? t("settings.artifacts.template") : t("settings.artifacts.legacyPython")}</span>
          <span>{mode === "create" ? t("settings.artifacts.draft") : plugin !== null ? artifactPluginOriginLabel(plugin, t) : t("settings.artifacts.plugin")}</span>
          <span>{editable ? t("settings.artifacts.editable") : t("settings.artifacts.readOnly")}</span>
        </div>
      </header>
      <div className="system-config-detail-grid system-config-skill-detail-grid artifact-plugin-detail-grid">
        <div className="system-config-detail-tree artifact-plugin-file-list">
          <div className="system-config-detail-section-title">
            <h4>{t("settings.artifacts.files")}</h4>
            <span>{files.length}</span>
          </div>
          <ul aria-label={t("settings.artifacts.files")}>
            {files.map((file) => (
              <li key={file.path}>
                <button
                  type="button"
                  className={selectedFile?.path === file.path ? "selected" : ""}
                  aria-pressed={selectedFile?.path === file.path}
                  onClick={() => setSelectedPath(file.path)}
                >
                  <span>{file.path}</span>
                  <small>{file.label}</small>
                </button>
              </li>
            ))}
          </ul>
        </div>
        <div className="artifact-plugin-workbench">
          <div className="system-config-file-editor">
            {selectedFile === null ? (
              <p className="muted system-config-detail-empty">{t("settings.artifacts.noPreviewFiles")}</p>
            ) : (
              <ArtifactPluginFileEditor
                busy={busy}
                canDelete={canDelete}
                canDownload={canDownload}
                canSave={canSave}
                file={selectedFile}
                readOnly={!editable || !selectedFile.editable}
                schemaError={selectedFileError}
                status={status}
                previewControl={(
                  <ArtifactPluginPreview
                    error={previewError}
                    loading={previewLoading}
                    modalOpen={previewModalOpen}
                    pluginFormat={pluginFormat}
                    srcDoc={previewSrcDoc}
                    title={mode === "create" ? t("settings.artifacts.newPreviewTitle", { domain: pluginDomain }) : t("settings.artifacts.previewTitle")}
                    onModalOpenChange={onPreviewModalOpenChange}
                  />
                )}
                onDelete={onDelete}
                onDownload={onDownload}
                onSave={onSave}
                onUpdateContent={(content) => updateFileContent(selectedFile, content)}
              />
            )}
          </div>
        </div>
      </div>
    </section>
  );
}

function ArtifactPluginFileEditor({
  busy,
  canDelete,
  canDownload,
  canSave,
  file,
  readOnly,
  schemaError,
  status,
  onDelete,
  onDownload,
  onSave,
  previewControl,
  onUpdateContent
}: {
  busy: boolean;
  canDelete: boolean;
  canDownload: boolean;
  canSave: boolean;
  file: ArtifactPluginFile;
  readOnly: boolean;
  schemaError: string | null;
  status: ArtifactPluginStatus | null;
  onDelete: () => void;
  onDownload: () => void;
  onSave: () => void;
  previewControl: ReactNode;
  onUpdateContent: (content: string) => void;
}) {
  const { t } = useI18n();
  return (
    <>
      <div className="system-config-file-editor-header">
        <div>
          <strong>{file.path}</strong>
          <small>{file.description} · {byteLabel(file.size)} · {readOnly ? t("settings.artifacts.readOnly") : t("settings.artifacts.editable")}</small>
        </div>
        <div className="system-config-file-editor-actions">
          {previewControl}
          <button
            type="button"
            className="system-config-icon-button"
            disabled={!canDownload}
            aria-label={`${t("common.download")} ${file.path}`}
            title={t("common.download")}
            onClick={onDownload}
          >
            <UiIcon name="download" />
          </button>
          <button
            type="button"
            className="system-config-icon-button"
            disabled={!canSave || busy || readOnly || schemaError !== null}
            aria-label={`${t("common.save")} ${file.path}`}
            title={t("common.save")}
            onClick={onSave}
          >
            <UiIcon name="save" />
          </button>
          <button
            type="button"
            className="system-config-icon-button danger"
            disabled={!canDelete || busy || readOnly}
            aria-label={`${t("common.delete")} ${file.path}`}
            title={t("common.delete")}
            onClick={onDelete}
          >
            <UiIcon name="trash" />
          </button>
        </div>
      </div>
      <div className="system-config-file-body">
        <textarea
          value={file.content}
          readOnly={readOnly}
          spellCheck={false}
          aria-label={t("settings.artifacts.source", { path: file.path })}
          onChange={(event) => onUpdateContent(event.target.value)}
        />
      </div>
      {(schemaError !== null || status !== null) && (
        <div className="artifact-plugin-file-status">
          {schemaError !== null && <span className="error" role="alert">{schemaError}</span>}
          {status !== null && <span className={status.kind === "error" ? "error" : "muted"}>{status.message}</span>}
        </div>
      )}
    </>
  );
}

function ArtifactPluginPreview({
  error,
  loading,
  modalOpen,
  pluginFormat,
  srcDoc,
  title,
  onModalOpenChange
}: {
  error: string | null;
  loading: boolean;
  modalOpen: boolean;
  pluginFormat: ArtifactPluginFormat;
  srcDoc: string | null;
  title: string;
  onModalOpenChange: (open: boolean) => void;
}) {
  const { t } = useI18n();
  const canOpen = pluginFormat === "template" && error === null && srcDoc !== null;
  const titleText = pluginFormat !== "template"
    ? t("settings.artifacts.previewUnavailableLegacy")
    : error !== null
      ? error
      : srcDoc !== null
        ? t("settings.artifacts.previewOpen")
        : loading
          ? t("settings.artifacts.previewRendering")
          : t("settings.artifacts.previewUnavailable");
  useEffect(() => {
    if (modalOpen && !canOpen) {
      onModalOpenChange(false);
    }
  }, [canOpen, modalOpen, onModalOpenChange]);

  return (
    <>
      <button
        type="button"
        className="artifact-plugin-preview-icon-button"
        disabled={!canOpen}
        aria-label={t("settings.artifacts.previewOpen")}
        title={titleText}
        onClick={() => onModalOpenChange(true)}
      >
        <UiIcon name="eye" />
      </button>
      {modalOpen && canOpen && (
        <ArtifactPluginPreviewModal
          srcDoc={srcDoc}
          title={title}
          onClose={() => onModalOpenChange(false)}
        />
      )}
    </>
  );
}

function ArtifactPluginPreviewModal({
  srcDoc,
  title,
  onClose
}: {
  srcDoc: string;
  title: string;
  onClose: () => void;
}) {
  const { t } = useI18n();
  const panelRef = useRef<HTMLElement | null>(null);
  useOverlayFocus({
    isOpen: true,
    ref: panelRef,
    onEscape: onClose,
    preserveExistingFocus: false
  });

  return (
    <div className="artifact-plugin-preview-modal" role="dialog" aria-modal="true" aria-label={title}>
      <button type="button" className="artifact-plugin-preview-modal-backdrop" aria-label={t("settings.artifacts.closePreview")} onClick={onClose} />
      <section ref={panelRef} className="artifact-plugin-preview-modal-panel">
        <header className="artifact-plugin-preview-modal-header">
          <div>
            <strong>{title}</strong>
            <span>{t("settings.artifacts.renderedPreview")}</span>
          </div>
          <button
            type="button"
            className="system-config-icon-button"
            aria-label={t("settings.artifacts.closePreview")}
            title={t("common.close")}
            onClick={onClose}
          >
            <UiIcon name="x" />
          </button>
        </header>
        <div className="artifact-plugin-preview-modal-frame">
          <iframe
            title={t("settings.artifacts.previewTitle")}
            sandbox={ARTIFACT_IFRAME_SANDBOX}
            referrerPolicy="no-referrer"
            srcDoc={srcDoc}
          />
        </div>
      </section>
    </div>
  );
}
