import { useRef, useState, type ChangeEvent } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  deleteSystemModelPreset,
  exportSystemModelPreset,
  fetchSystemModelPresets,
  importSystemModelPreset,
  upsertSystemModelPreset
} from "../../api";
import { UiIcon } from "../../components/UiIcon";
import { useI18n, type TranslateFn } from "../../i18n";
import type { AgentClient, AgentModelSelection, SystemModelConfig, SystemModelPreset, SystemModelProvider } from "../../types";
import type { AgentCommandSettings, AgentModelSelectionSettings } from "../../userPreferences";
import { AgentCliModelSettings } from "./AgentCliModelSettings";
import { SystemModelConfigEditor } from "./SystemModelConfigEditor";
import { downloadJsonFile, jsonFilename, readJsonFile } from "./settingsImportExport";

type Draft = {
  id: string;
  name: string;
  providers: SystemModelProvider[];
  base_url: string;
  api_key: string;
  model_configs: SystemModelConfig[];
};

type SystemModelInnerTab = "models" | "cli";

const MODEL_PROVIDERS: SystemModelProvider[] = ["openai_compatible", "anthropic_compatible"];

const EMPTY_DRAFT: Draft = {
  id: "",
  name: "",
  providers: ["openai_compatible"],
  base_url: "",
  api_key: "",
  model_configs: [{ name: "" }]
};

function emptyDraft(): Draft {
  return {
    ...EMPTY_DRAFT,
    providers: [...EMPTY_DRAFT.providers],
    model_configs: EMPTY_DRAFT.model_configs.map((model) => ({ ...model }))
  };
}

function providerLabel(provider: SystemModelProvider, t: TranslateFn): string {
  return provider === "openai_compatible"
    ? t("settings.models.provider.openai")
    : t("settings.models.provider.anthropic");
}

function presetProviders(preset: SystemModelPreset): SystemModelProvider[] {
  return preset.providers?.length > 0 ? preset.providers : [preset.provider];
}

function providerLabels(providers: SystemModelProvider[], t: TranslateFn): string {
  return providers.map((provider) => providerLabel(provider, t)).join(", ");
}

function ProviderIcon({ provider }: { provider: SystemModelProvider }) {
  return (
    <span className={`system-model-provider-glyph ${provider}`} aria-hidden="true">
      {provider === "openai_compatible" ? "O" : "A"}
    </span>
  );
}

function draftFromPreset(preset: SystemModelPreset): Draft {
  return {
    id: preset.id,
    name: preset.name,
    providers: presetProviders(preset),
    base_url: preset.base_url,
    api_key: preset.api_key,
    model_configs: modelConfigsFromPreset(preset)
  };
}

function modelConfigsFromPreset(preset: SystemModelPreset): SystemModelConfig[] {
  const modelConfigs = preset.model_configs ?? [];
  return modelConfigs.length > 0
    ? modelConfigs.map((model) => ({ ...model }))
    : preset.models.map((name) => ({ name }));
}

function cleanModelConfigs(value: SystemModelConfig[]): SystemModelConfig[] {
  const seen = new Set<string>();
  const models: SystemModelConfig[] = [];
  for (const model of value) {
    const name = model.name.trim();
    if (name !== "" && !seen.has(name)) {
      seen.add(name);
      models.push({
        name,
        ...(model.max_output_tokens ? { max_output_tokens: model.max_output_tokens } : {}),
        ...(model.context_window ? { context_window: model.context_window } : {}),
        ...(model.auto_compact_token_limit ? { auto_compact_token_limit: model.auto_compact_token_limit } : {}),
        ...(model.codex_model_reasoning_effort
          ? { codex_model_reasoning_effort: model.codex_model_reasoning_effort }
          : {}),
        ...(model.codex_plan_mode_reasoning_effort
          ? { codex_plan_mode_reasoning_effort: model.codex_plan_mode_reasoning_effort }
          : {}),
        ...(model.claude_reasoning_effort
          ? { claude_reasoning_effort: model.claude_reasoning_effort }
          : {})
      });
    }
  }
  return models;
}

function modelNames(value: SystemModelConfig[]): string[] {
  return cleanModelConfigs(value).map((model) => model.name);
}

function errorMessage(error: unknown, fallback: string): string {
  return error instanceof Error ? error.message : fallback;
}

function bundlePresetId(payload: unknown): string | null {
  const preset = typeof payload === "object" && payload !== null && "preset" in payload
    ? (payload as { preset?: { id?: unknown } }).preset
    : null;
  return typeof preset?.id === "string" ? preset.id : null;
}

export function SystemModelSettings({
  clientId,
  agentClients,
  agentCommandSettings,
  agentModelSelectionSettings,
  artifactModelSelectionSettings,
  onAgentCommandChange,
  onAgentModelSelectionChange,
  onArtifactModelSelectionChange
}: {
  clientId: string | null;
  agentClients: AgentClient[];
  agentCommandSettings: AgentCommandSettings;
  agentModelSelectionSettings: AgentModelSelectionSettings;
  artifactModelSelectionSettings: AgentModelSelectionSettings;
  onAgentCommandChange: (agent: string, value: string) => void;
  onAgentModelSelectionChange: (agent: string, value: AgentModelSelection | null) => void;
  onArtifactModelSelectionChange: (agent: string, value: AgentModelSelection | null) => void;
}) {
  const { t } = useI18n();
  const queryClient = useQueryClient();
  const importInputRef = useRef<HTMLInputElement | null>(null);
  const [innerTab, setInnerTab] = useState<SystemModelInnerTab>("models");
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [draft, setDraft] = useState<Draft>(() => emptyDraft());
  const [status, setStatus] = useState<{ kind: "info" | "error"; message: string } | null>(null);

  const presetsQuery = useQuery({
    queryKey: ["system-model-presets"],
    queryFn: fetchSystemModelPresets
  });
  const presets = presetsQuery.data?.presets ?? [];
  const selected = presets.find((preset) => preset.id === selectedId) ?? null;

  const saveMutation = useMutation({
    mutationFn: (input: { id: string; draft: Draft }) => upsertSystemModelPreset(input.id, {
      name: input.draft.name.trim(),
      providers: input.draft.providers,
      base_url: input.draft.base_url.trim(),
      api_key: input.draft.api_key,
      models: modelNames(input.draft.model_configs),
      model_configs: cleanModelConfigs(input.draft.model_configs)
    }),
    onSuccess: (nextList, input) => {
      queryClient.setQueryData(["system-model-presets"], nextList);
      setSelectedId(input.id);
      const saved = nextList.presets.find((preset) => preset.id === input.id);
      if (saved !== undefined) {
        setDraft(draftFromPreset(saved));
      }
      setStatus({ kind: "info", message: t("settings.models.saved") });
    },
    onError: (error) => setStatus({ kind: "error", message: errorMessage(error, t("settings.system.saveFailed")) })
  });
  const deleteMutation = useMutation({
    mutationFn: deleteSystemModelPreset,
    onSuccess: (nextList) => {
      queryClient.setQueryData(["system-model-presets"], nextList);
      setSelectedId(null);
      setDraft(emptyDraft());
      setStatus({ kind: "info", message: t("settings.models.deleted") });
    },
    onError: (error) => setStatus({ kind: "error", message: errorMessage(error, t("settings.system.deleteFailed")) })
  });
  const importMutation = useMutation({
    mutationFn: importSystemModelPreset,
    onSuccess: (nextList, payload) => {
      queryClient.setQueryData(["system-model-presets"], nextList);
      const importedId = bundlePresetId(payload) ?? nextList.presets[0]?.id ?? null;
      setSelectedId(importedId);
      const imported = nextList.presets.find((preset) => preset.id === importedId);
      setDraft(imported !== undefined ? draftFromPreset(imported) : emptyDraft());
      setStatus({ kind: "info", message: t("settings.models.imported") });
    },
    onError: (error) => setStatus({ kind: "error", message: errorMessage(error, t("settings.models.importFailed")) })
  });

  const models = cleanModelConfigs(draft.model_configs);
  const canSave = draft.id.trim() !== ""
    && draft.name.trim() !== ""
    && draft.providers.length > 0
    && draft.base_url.trim() !== ""
    && models.length > 0
    && !saveMutation.isPending;
  const selectPreset = (preset: SystemModelPreset) => {
    setSelectedId(preset.id);
    setDraft(draftFromPreset(preset));
    setStatus(null);
  };
  const resetDraft = () => {
    setSelectedId(null);
    setDraft(emptyDraft());
    setStatus(null);
  };
  const save = () => {
    if (!canSave) {
      return;
    }
    saveMutation.mutate({ id: draft.id.trim(), draft });
  };
  const importPreset = async (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.currentTarget.files?.[0] ?? null;
    event.currentTarget.value = "";
    if (file === null) {
      return;
    }
    try {
      importMutation.mutate(await readJsonFile(file));
    } catch {
      setStatus({ kind: "error", message: t("settings.models.importFailed") });
    }
  };
  const exportPreset = async (preset: SystemModelPreset) => {
    try {
      downloadJsonFile(await exportSystemModelPreset(preset.id), jsonFilename(preset.id));
      setStatus(null);
    } catch {
      setStatus({ kind: "error", message: t("settings.models.exportFailed") });
    }
  };
  const toggleProvider = (provider: SystemModelProvider, checked: boolean) => {
    setDraft((current) => {
      if (checked) {
        return current.providers.includes(provider)
          ? current
          : { ...current, providers: MODEL_PROVIDERS.filter((candidate) => candidate === provider || current.providers.includes(candidate)) };
      }
      return { ...current, providers: current.providers.filter((candidate) => candidate !== provider) };
    });
  };

  if (presetsQuery.isLoading) {
    return <p className="muted">{t("settings.models.loading")}</p>;
  }
  if (presetsQuery.isError) {
    return <p className="error" role="alert">{t("settings.models.loadFailed")}</p>;
  }

  return (
    <section className="system-model-page">
      <div className="system-model-inner-tabs" role="tablist" aria-label={t("settings.models.innerTabs")}>
        <button
          type="button"
          role="tab"
          aria-selected={innerTab === "models"}
          className={innerTab === "models" ? "active" : ""}
          onClick={() => setInnerTab("models")}
        >
          {t("settings.models.tab.models")}
        </button>
        <button
          type="button"
          role="tab"
          aria-selected={innerTab === "cli"}
          className={innerTab === "cli" ? "active" : ""}
          onClick={() => setInnerTab("cli")}
        >
          {t("settings.models.tab.cli")}
        </button>
      </div>
      {innerTab === "models" ? (
        <div className="system-model-workbench">
          <aside className="system-model-list">
            <div className="system-model-list-header">
              <div className="system-config-sidebar-heading">
                <strong>{t("settings.models.title")}</strong>
                <span>{presets.length}</span>
              </div>
              <div className="system-model-list-actions">
                <input ref={importInputRef} className="settings-import-file-input" type="file" accept=".json,application/json" aria-label={t("settings.models.import")} onChange={importPreset} />
                <button
                  type="button"
                  className="system-config-icon-button"
                  disabled={importMutation.isPending}
                  aria-label={t("settings.models.import")}
                  title={t("settings.models.import")}
                  onClick={() => importInputRef.current?.click()}
                >
                  <UiIcon name="upload" />
                </button>
                <button
                  type="button"
                  className="system-config-icon-button system-model-create-button"
                  aria-label={t("settings.models.create")}
                  title={t("settings.models.create")}
                  onClick={resetDraft}
                >
                  <UiIcon name="plus" />
                </button>
              </div>
            </div>
            <div className="system-config-list system-model-preset-list">
              {presets.length === 0 ? (
                <p className="muted quick-key-empty-state">{t("settings.models.empty")}</p>
              ) : (
                <ul>
                  {presets.map((preset) => {
                    const providers = presetProviders(preset);
                    return (
                      <li key={preset.id} className={`system-config-item${selectedId === preset.id ? " selected" : ""}`}>
                        <button
                          type="button"
                          className="system-config-item-content"
                          aria-pressed={selectedId === preset.id}
                          onClick={() => selectPreset(preset)}
                        >
                          <span className="system-config-item-icon" aria-hidden="true">
                            <UiIcon name="list-tree" />
                          </span>
                          <div className="system-config-item-main">
                            <strong>{preset.name}</strong>
                            <small>{preset.id}</small>
                            <span className="system-model-list-meta">
                              <span className="system-model-provider-icons" aria-label={providerLabels(providers, t)}>
                                {providers.map((provider) => (
                                  <span key={provider} title={providerLabel(provider, t)}>
                                    <ProviderIcon provider={provider} />
                                  </span>
                                ))}
                              </span>
                              <em>{t("settings.models.count", { count: preset.models.length })}</em>
                            </span>
                          </div>
                        </button>
                      </li>
                    );
                  })}
                </ul>
              )}
              {status !== null && <p className={status.kind === "error" ? "error" : "muted"}>{status.message}</p>}
            </div>
          </aside>
          <main className="system-model-editor">
            <section className="system-model-preset-editor">
              <div className="system-config-detail-header">
                <div>
                  <strong>{selected === null ? t("settings.models.create") : selected.name}</strong>
                  <small>{selected === null ? t("settings.models.createHint") : selected.id}</small>
                </div>
                {selected !== null && (
                  <div className="system-config-detail-actions">
                    <button
                      type="button"
                      className="system-config-icon-button"
                      aria-label={`${t("common.download")} ${selected.name}`}
                      title={t("common.download")}
                      onClick={() => exportPreset(selected)}
                    >
                      <UiIcon name="download" />
                    </button>
                    <button
                      type="button"
                      className="system-config-icon-button danger"
                      disabled={deleteMutation.isPending}
                      aria-label={`${t("common.delete")} ${selected.name}`}
                      title={t("common.delete")}
                      onClick={() => deleteMutation.mutate(selected.id)}
                    >
                      <UiIcon name="trash" />
                    </button>
                  </div>
                )}
              </div>
              <div className="system-model-form">
                <label className="settings-field system-model-form-wide">
                  <span>ID</span>
                  <input
                    value={draft.id}
                    onChange={(event) => setDraft((current) => ({ ...current, id: event.target.value }))}
                    disabled={selected !== null}
                    placeholder="openai-main"
                  />
                </label>
                <label className="settings-field system-model-form-wide">
                  <span>{t("settings.models.name")}</span>
                  <input
                    value={draft.name}
                    onChange={(event) => setDraft((current) => ({ ...current, name: event.target.value }))}
                    placeholder="OpenAI main"
                  />
                </label>
                <fieldset className="settings-field system-model-provider-group system-model-form-wide">
                  <span>{t("settings.models.provider")}</span>
                  <div className="system-model-provider-options" role="group" aria-label={t("settings.models.provider")}>
                    {MODEL_PROVIDERS.map((provider) => {
                      const checked = draft.providers.includes(provider);
                      return (
                        <button
                          key={provider}
                          type="button"
                          className={`system-model-provider-option${checked ? " selected" : ""}`}
                          aria-pressed={checked}
                          aria-label={providerLabel(provider, t)}
                          title={providerLabel(provider, t)}
                          onClick={() => toggleProvider(provider, !checked)}
                        >
                          <ProviderIcon provider={provider} />
                        </button>
                      );
                    })}
                  </div>
                </fieldset>
                <label className="settings-field system-model-form-wide">
                  <span>Base URL</span>
                  <input
                    value={draft.base_url}
                    onChange={(event) => setDraft((current) => ({ ...current, base_url: event.target.value }))}
                    placeholder="https://api.example.com/v1"
                  />
                </label>
                <label className="settings-field system-model-form-wide">
                  <span>API Key</span>
                  <input
                    type="password"
                    value={draft.api_key}
                    onChange={(event) => setDraft((current) => ({ ...current, api_key: event.target.value }))}
                    autoComplete="off"
                  />
                </label>
                <SystemModelConfigEditor
                  models={draft.model_configs}
                  providers={draft.providers}
                  onChange={(modelConfigs) => setDraft((current) => ({ ...current, model_configs: modelConfigs }))}
                />
              </div>
              <div className="settings-actions system-model-actions">
                <button
                  type="button"
                  className="ui-icon-button"
                  aria-label={t("common.reset")}
                  title={t("common.reset")}
                  onClick={resetDraft}
                >
                  <UiIcon name="rotate-ccw" />
                </button>
                <button
                  type="button"
                  className="system-config-icon-button"
                  disabled={!canSave}
                  aria-label={t("settings.models.savePreset")}
                  title={saveMutation.isPending ? t("common.saving") : t("settings.models.savePreset")}
                  onClick={save}
                >
                  <UiIcon name="save" />
                </button>
              </div>
            </section>
          </main>
        </div>
      ) : (
        <AgentCliModelSettings
          clientId={clientId}
          agentClients={agentClients}
          agentCommandSettings={agentCommandSettings}
          agentModelSelectionSettings={agentModelSelectionSettings}
          artifactModelSelectionSettings={artifactModelSelectionSettings}
          onAgentCommandChange={onAgentCommandChange}
          onAgentModelSelectionChange={onAgentModelSelectionChange}
          onArtifactModelSelectionChange={onArtifactModelSelectionChange}
        />
      )}
    </section>
  );
}
