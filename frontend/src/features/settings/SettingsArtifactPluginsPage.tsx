import { useEffect, useMemo, useRef, useState, type ChangeEvent, type MutableRefObject } from "react";
import { useMutation, useQuery, useQueryClient, type QueryClient } from "@tanstack/react-query";

import {
  createArtifactPlugin,
  createArtifactPluginPreview,
  deleteArtifactPlugin,
  fetchArtifactPluginPreviewHtml,
  fetchArtifactPluginSource,
  fetchArtifactPlugins,
  previewArtifactPlugin,
  updateArtifactPluginPreview,
  updateArtifactPlugin
} from "../../api";
import type {
  ArtifactPluginDescriptor,
  ArtifactPluginDomain,
  ArtifactPluginPayload,
  ArtifactPluginPreviewPayload
} from "../../types";
import { useAppPrompt } from "../../components/AppPromptProvider";
import type { SummaryOutputLanguage } from "../../userPreferences";
import { useI18n, type TranslateFn } from "../../i18n";
import { ArtifactPluginDetail, type ArtifactPluginStatus } from "./ArtifactPluginDetail";
import {
  artifactPluginOriginLabel,
  draftFromSource,
  draftFromUploadedText,
  draftSignature,
  NEW_PLUGIN_DRAFT,
  payloadFromDraft,
  pluginKey,
  previewContentError,
  schemaError,
  templatePayloadFromDraft,
  type ArtifactPluginDraft
} from "./artifactPluginSettingsModel";

type ArtifactPluginMode = "selected" | "create";

function errorText(error: unknown, fallback: string): string {
  return error instanceof Error ? error.message : fallback;
}

export function SettingsArtifactPluginsPage({
  previewModalOpen,
  selectedClientId,
  selectedWindowId,
  userPreferredLanguage,
  onPreviewModalOpenChange
}: {
  previewModalOpen: boolean;
  selectedClientId: string | null;
  selectedWindowId: string | null;
  userPreferredLanguage: SummaryOutputLanguage;
  onPreviewModalOpenChange: (open: boolean) => void;
}) {
  const { t } = useI18n();
  const { confirm } = useAppPrompt();
  const queryClient = useQueryClient();
  const previewSessionIdRef = useRef<string | null>(null);
  const [selectedDomain, setSelectedDomain] = useState<ArtifactPluginDomain>("terminal");
  const [selectedKey, setSelectedKey] = useState<string | null>(null);
  const [mode, setMode] = useState<ArtifactPluginMode>("selected");
  const [draft, setDraft] = useState<ArtifactPluginDraft>(NEW_PLUGIN_DRAFT);
  const [status, setStatus] = useState<ArtifactPluginStatus | null>(null);

  const pluginsQuery = useQuery({
    queryKey: ["artifact-plugins"],
    queryFn: fetchArtifactPlugins
  });
  const allPlugins = pluginsQuery.data?.plugins ?? [];
  const plugins = allPlugins.filter((plugin) => plugin.domain === selectedDomain);
  const selectedPlugin = useMemo(
    () => plugins.find((plugin) => pluginKey(plugin) === selectedKey) ?? null,
    [plugins, selectedKey]
  );
  const sourceQuery = useQuery({
    queryKey: ["artifact-plugin-source", selectedPlugin?.domain ?? null, selectedPlugin?.artifact_kind ?? null],
    queryFn: () => fetchArtifactPluginSource(selectedPlugin?.domain ?? "terminal", selectedPlugin?.artifact_kind ?? ""),
    enabled: mode === "selected" && selectedPlugin !== null
  });
  const pluginFormat = mode === "create" ? "template" : selectedPlugin?.plugin_format ?? "template";
  const selectedDraft = draftFromSource(sourceQuery.data, userPreferredLanguage);
  const jsonSchemaError = pluginFormat === "template" ? schemaError(draft.json_schema_text, t) : null;
  const previewDataError = pluginFormat === "template" ? previewContentError(draft.preview_content_text, t) : null;
  const sourceDirty = mode === "create"
    ? draft.python_source.trim().length > 0
    : draftSignature(draft) !== draftSignature(selectedDraft);
  const previewQuery = useQuery({
    queryKey: [
      "artifact-plugin-preview",
      selectedClientId,
      selectedWindowId,
      selectedDomain,
      pluginFormat,
      userPreferredLanguage,
      draftSignature(draft)
    ],
    queryFn: () => renderDraftPreview({
      clientId: selectedClientId,
      domain: selectedDomain,
      draft,
      payload: templatePayloadFromDraft(draft),
      previewSessionIdRef,
      queryClient,
      selectedPlugin,
      windowId: selectedWindowId,
      t
    }),
    enabled: pluginFormat === "template"
      && jsonSchemaError === null
      && previewDataError === null
      && (mode === "create" || sourceQuery.data !== undefined),
    retry: false
  });

  useEffect(() => {
    previewSessionIdRef.current = null;
  }, [selectedClientId, selectedDomain, selectedWindowId]);

  const createMutation = useMutation({
    mutationFn: () => createArtifactPlugin(selectedDomain, payloadFromDraft(draft, "template")),
    onSuccess: (plugin) => {
      setMode("selected");
      setSelectedKey(pluginKey(plugin));
      setDraft(draftFromSource(plugin, userPreferredLanguage));
      setStatus({ kind: "info", message: t("settings.artifacts.created") });
      void queryClient.invalidateQueries({ queryKey: ["artifact-plugins"] });
    },
    onError: (error) => setStatus({ kind: "error", message: errorText(error, t("settings.artifacts.createFailed")) })
  });
  const updateMutation = useMutation({
    mutationFn: () => updateArtifactPlugin(
      selectedPlugin?.domain ?? selectedDomain,
      selectedPlugin?.artifact_kind ?? "",
      payloadFromDraft(draft, pluginFormat)
    ),
    onSuccess: (plugin) => {
      setDraft(draftFromSource(plugin, userPreferredLanguage));
      setStatus({ kind: "info", message: t("settings.artifacts.saved") });
      void queryClient.invalidateQueries({ queryKey: ["artifact-plugins"] });
      void queryClient.invalidateQueries({ queryKey: ["artifact-plugin-source"] });
    },
    onError: (error) => setStatus({ kind: "error", message: errorText(error, t("settings.system.saveFailed")) })
  });
  const deleteMutation = useMutation({
    mutationFn: (plugin: ArtifactPluginDescriptor) => deleteArtifactPlugin(plugin.domain, plugin.artifact_kind),
    onSuccess: () => {
      setSelectedKey(null);
      setDraft(NEW_PLUGIN_DRAFT);
      setStatus({ kind: "info", message: t("settings.artifacts.deleted") });
      void queryClient.invalidateQueries({ queryKey: ["artifact-plugins"] });
    },
    onError: (error) => setStatus({ kind: "error", message: errorText(error, t("settings.system.deleteFailed")) })
  });

  useEffect(() => {
    if (selectedKey !== null || plugins.length === 0 || mode !== "selected") {
      return;
    }
    setSelectedKey(pluginKey(plugins[0]));
  }, [mode, plugins, selectedKey]);

  useEffect(() => {
    if (mode !== "selected" || sourceQuery.data === undefined) {
      return;
    }
    setDraft(draftFromSource(sourceQuery.data, userPreferredLanguage));
  }, [mode, sourceQuery.data, userPreferredLanguage]);

  const startCreate = () => {
    onPreviewModalOpenChange(false);
    setMode("create");
    setSelectedKey(null);
    setDraft(NEW_PLUGIN_DRAFT);
    setStatus(null);
  };
  const selectDomain = (domain: ArtifactPluginDomain) => {
    if (domain === selectedDomain) {
      return;
    }
    onPreviewModalOpenChange(false);
    setSelectedDomain(domain);
    setSelectedKey(null);
    setMode("selected");
    setDraft(NEW_PLUGIN_DRAFT);
    setStatus(null);
  };
  const selectPlugin = (plugin: ArtifactPluginDescriptor) => {
    onPreviewModalOpenChange(false);
    setMode("selected");
    setSelectedKey(pluginKey(plugin));
    setStatus(null);
  };
  const uploadSource = async (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.currentTarget.files?.[0];
    event.currentTarget.value = "";
    if (file === undefined) {
      return;
    }
    onPreviewModalOpenChange(false);
    setMode("create");
    setSelectedKey(null);
    setDraft(draftFromUploadedText(await file.text()));
    setStatus(null);
  };
  const save = () => {
    if (jsonSchemaError !== null) {
      setStatus({ kind: "error", message: jsonSchemaError });
      return;
    }
    if (previewDataError !== null) {
      setStatus({ kind: "error", message: previewDataError });
      return;
    }
    if (mode === "create") {
      createMutation.mutate();
    } else if (selectedPlugin?.editable) {
      updateMutation.mutate();
    }
  };
  const remove = async () => {
    if (selectedPlugin === null || !selectedPlugin.editable) {
      return;
    }
    if (await confirm({
      title: t("settings.artifacts.deleteConfirmTitle"),
      message: t("settings.artifacts.deleteConfirm", { kind: selectedPlugin.artifact_kind }),
      confirmLabel: t("settings.artifacts.deleteConfirmSubmit"),
      tone: "danger"
    })) {
      deleteMutation.mutate(selectedPlugin);
    }
  };
  const downloadSource = () => {
    if (selectedPlugin === null) {
      return;
    }
    if (jsonSchemaError !== null || previewDataError !== null) {
      setStatus({ kind: "error", message: jsonSchemaError ?? previewDataError ?? "" });
      return;
    }
    const payload = payloadFromDraft(draft, pluginFormat);
    const blob = typeof payload === "string"
      ? new Blob([payload], { type: "text/x-python;charset=utf-8" })
      : new Blob([JSON.stringify(payload, null, 2)], { type: "application/json;charset=utf-8" });
    const link = document.createElement("a");
    const url = URL.createObjectURL(blob);
    link.href = url;
    link.download = typeof payload === "string" ? `${selectedPlugin.artifact_kind}.py` : `${selectedPlugin.artifact_kind}.json`;
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(url);
  };

  if (pluginsQuery.isLoading) {
    return <p className="muted">{t("settings.artifacts.loading")}</p>;
  }
  if (pluginsQuery.isError) {
    return <p className="error" role="alert">{t("settings.artifacts.loadFailed")}</p>;
  }

  const canSave = sourceDirty
    && jsonSchemaError === null
    && previewDataError === null
    && (mode === "create" || selectedPlugin?.editable === true);
  const canDelete = mode === "selected" && selectedPlugin?.editable === true;
  const busy = sourceQuery.isFetching
    || createMutation.isPending
    || updateMutation.isPending
    || deleteMutation.isPending;

  return (
    <section className="system-config-page settings-artifact-page">
      <aside className="system-config-sidebar artifact-plugin-sidebar">
        <div className="system-config-sidebar-heading">
          <strong>{t("settings.artifacts.title")}</strong>
          <span>{plugins.length}</span>
        </div>
        <div className="artifact-domain-tabs" role="tablist" aria-label={t("settings.artifacts.domain")}>
          <button
            type="button"
            role="tab"
            aria-selected={selectedDomain === "terminal"}
            className={selectedDomain === "terminal" ? "selected" : undefined}
            onClick={() => selectDomain("terminal")}
          >
            Terminal
            <span>{allPlugins.filter((plugin) => plugin.domain === "terminal").length}</span>
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={selectedDomain === "project"}
            className={selectedDomain === "project" ? "selected" : undefined}
            onClick={() => selectDomain("project")}
          >
            Project
            <span>{allPlugins.filter((plugin) => plugin.domain === "project").length}</span>
          </button>
        </div>
        <div className="system-config-editor system-config-sidebar-form artifact-plugin-sidebar-form">
          <div className="system-config-editor-header">
            <span>{t("settings.artifacts.newUpload")}</span>
            <small>{t("settings.artifacts.saveToDomain", { domain: selectedDomain })}</small>
          </div>
          <button type="button" className="system-config-primary-button" onClick={startCreate}>
            {t("settings.artifacts.newPlugin")}
          </button>
          <label className="system-config-upload artifact-plugin-upload">
            <input
              type="file"
              accept=".json,.py,application/json,text/x-python,text/plain"
              onChange={(event) => void uploadSource(event)}
            />
            <span className="system-config-upload-copy">
              <strong>{t("settings.artifacts.selectFile")}</strong>
              <small>{t("settings.artifacts.fileHelp")}</small>
            </span>
          </label>
        </div>
        <div className="system-config-list artifact-plugin-list">
          {plugins.length === 0 ? (
            <p className="muted quick-key-empty-state">{t("settings.artifacts.empty")}</p>
          ) : (
            <ul>
              {plugins.map((plugin) => (
                <li key={pluginKey(plugin)} className={`system-config-item artifact-plugin-item${selectedKey === pluginKey(plugin) ? " selected" : ""}`}>
                  <button
                    type="button"
                    className="system-config-item-content artifact-plugin-row"
                    aria-pressed={selectedKey === pluginKey(plugin)}
                    onClick={() => selectPlugin(plugin)}
                  >
                    <span className="system-config-item-icon artifact-plugin-item-icon" aria-hidden="true">
                      <svg viewBox="0 0 24 24">
                        <path d="M8 4h8l4 4v12H8a4 4 0 0 1-4-4V8a4 4 0 0 1 4-4Z" />
                        <path d="M15 4v5h5" />
                        <path d="M8 13h8" />
                        <path d="M8 17h5" />
                      </svg>
                    </span>
                    <div className="system-config-item-main">
                      <strong>{plugin.label}</strong>
                      <small>{plugin.artifact_kind}</small>
                      <em>{plugin.validation_error ?? artifactPluginOriginLabel(plugin, t)}</em>
                    </div>
                  </button>
                </li>
              ))}
            </ul>
          )}
          {status !== null && <p className={status.kind === "error" ? "error" : "muted"}>{status.message}</p>}
        </div>
      </aside>
      <main className="system-config-main">
        {mode === "selected" && selectedPlugin === null ? (
          <section className="system-config-detail system-config-empty-detail">
            <p className="muted">{t("settings.artifacts.selectDetail")}</p>
          </section>
        ) : (
          <ArtifactPluginDetail
            busy={busy}
            canDelete={canDelete}
            canSave={canSave}
            draft={draft}
            mode={mode}
            plugin={selectedPlugin}
            pluginDomain={selectedDomain}
            pluginFormat={pluginFormat}
            sourceError={sourceQuery.isError}
            sourceLoading={sourceQuery.isLoading}
            previewError={previewQuery.isError ? errorText(previewQuery.error, t("settings.artifacts.previewFailed")) : null}
            previewLoading={previewQuery.isFetching}
            previewModalOpen={previewModalOpen}
            previewSrcDoc={previewQuery.data ?? null}
            status={status}
            onDelete={remove}
            onDownload={downloadSource}
            onDraftChange={setDraft}
            onPreviewModalOpenChange={onPreviewModalOpenChange}
            onSave={save}
            onStatusClear={() => setStatus(null)}
          />
        )}
      </main>
    </section>
  );
}

async function renderDraftPreview({
  clientId,
  domain,
  draft,
  payload,
  previewSessionIdRef,
  queryClient,
  selectedPlugin,
  t,
  windowId
}: {
  clientId: string | null;
  domain: ArtifactPluginDomain;
  draft: ArtifactPluginDraft;
  payload: ArtifactPluginPayload;
  previewSessionIdRef: MutableRefObject<string | null>;
  queryClient: QueryClient;
  selectedPlugin: ArtifactPluginDescriptor | null;
  t: TranslateFn;
  windowId: string | null;
}): Promise<string> {
  if (clientId === null || windowId === null) {
    return previewArtifactPlugin(domain, payload);
  }

  const previewPayload = previewPayloadFromDraft({
    clientId,
    payload,
    selectedPlugin,
    t,
    windowId
  });
  const preview = previewSessionIdRef.current === null
    ? await createArtifactPluginPreview(previewPayload)
    : await updateArtifactPluginPreview(previewSessionIdRef.current, previewPayload).catch(async () => {
        previewSessionIdRef.current = null;
        return createArtifactPluginPreview(previewPayload);
      });
  previewSessionIdRef.current = preview.id;
  void queryClient.invalidateQueries({
    queryKey: ["artifact-plugin-previews", clientId, windowId],
    exact: false
  });
  if (preview.status !== "valid") {
    throw new Error(preview.last_error ?? t("settings.artifacts.invalidPreview"));
  }
  return fetchArtifactPluginPreviewHtml(preview.id);
}

function previewPayloadFromDraft({
  clientId,
  payload,
  selectedPlugin,
  t,
  windowId
}: {
  clientId: string;
  payload: ArtifactPluginPayload;
  selectedPlugin: ArtifactPluginDescriptor | null;
  t: TranslateFn;
  windowId: string;
}): ArtifactPluginPreviewPayload {
  if (
    payload.python_source === undefined
    || payload.python_source === null
    || payload.prompt_template === undefined
    || payload.prompt_template === null
    || payload.html_template === undefined
    || payload.html_template === null
    || payload.json_schema === undefined
    || payload.json_schema === null
  ) {
    throw new Error(t("settings.artifacts.incomplete"));
  }
  return {
    client_id: clientId,
    window_id: windowId,
    title: `${selectedPlugin?.label ?? t("settings.artifacts.customReport")} preview`,
    python_source: payload.python_source,
    prompt_template: payload.prompt_template,
    html_template: payload.html_template,
    json_schema: payload.json_schema,
    demo_content_json: payload.preview_content_json ?? null
  };
}
