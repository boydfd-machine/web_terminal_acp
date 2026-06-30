import { useEffect, useMemo } from "react";
import { useQuery } from "@tanstack/react-query";

import { fetchSystemModelPresets } from "../api";
import { useI18n } from "../i18n";
import type {
  AgentLaunchKind,
  AgentModelSelection,
  ClaudeReasoningEffort,
  CodexReasoningEffort,
  SystemModelPreset,
  SystemModelProvider
} from "../types";

const CODEX_EFFORTS: CodexReasoningEffort[] = ["minimal", "low", "medium", "high", "xhigh"];
const CLAUDE_EFFORTS: ClaudeReasoningEffort[] = ["low", "medium", "high", "xhigh", "max", "auto"];

function supportedProvider(agent: AgentLaunchKind): SystemModelProvider | null {
  if (agent === "codex") {
    return "openai_compatible";
  }
  if (agent === "claude") {
    return "anthropic_compatible";
  }
  return null;
}

function presetSupportsProvider(preset: SystemModelPreset, provider: SystemModelProvider): boolean {
  return (preset.providers?.length > 0 ? preset.providers : [preset.provider]).includes(provider);
}

function firstModel(preset: SystemModelPreset | null): string {
  return modelNames(preset)[0] ?? "";
}

function modelNames(preset: SystemModelPreset | null): string[] {
  if (preset === null) {
    return [];
  }
  const modelConfigs = preset.model_configs ?? [];
  return modelConfigs.length > 0
    ? modelConfigs.map((model) => model.name)
    : preset.models;
}

function modelValue(selection: AgentModelSelection | null, preset: SystemModelPreset | null): string {
  return selection?.model ?? selection?.claude?.model ?? firstModel(preset);
}

function tierModelValue(
  selection: AgentModelSelection | null,
  preset: SystemModelPreset | null,
  tier: "opus_model" | "sonnet_model" | "haiku_model"
): string {
  return selection?.claude?.[tier] ?? firstModel(preset);
}

function carryEffortOverrides(
  base: AgentModelSelection,
  previous: AgentModelSelection | null
): AgentModelSelection {
  if (previous === null) {
    return base;
  }
  return {
    ...base,
    ...(previous.codex_model_reasoning_effort !== undefined && previous.codex_model_reasoning_effort !== null
      ? { codex_model_reasoning_effort: previous.codex_model_reasoning_effort }
      : {}),
    ...(previous.codex_plan_mode_reasoning_effort !== undefined && previous.codex_plan_mode_reasoning_effort !== null
      ? { codex_plan_mode_reasoning_effort: previous.codex_plan_mode_reasoning_effort }
      : {}),
    ...(previous.claude_reasoning_effort !== undefined && previous.claude_reasoning_effort !== null
      ? { claude_reasoning_effort: previous.claude_reasoning_effort }
      : {})
  };
}

function codexSelection(
  preset: SystemModelPreset,
  model: string,
  previous: AgentModelSelection | null
): AgentModelSelection {
  return carryEffortOverrides({ preset_id: preset.id, model: model || firstModel(preset) }, previous);
}

function claudeAllSelection(
  preset: SystemModelPreset,
  model: string,
  previous: AgentModelSelection | null
): AgentModelSelection {
  return carryEffortOverrides(
    { preset_id: preset.id, claude: { mode: "all", model: model || firstModel(preset) } },
    previous
  );
}

function claudeSplitSelection(
  preset: SystemModelPreset,
  opus: string,
  sonnet: string,
  haiku: string,
  previous: AgentModelSelection | null
): AgentModelSelection {
  const fallback = firstModel(preset);
  return carryEffortOverrides(
    {
      preset_id: preset.id,
      claude: {
        mode: "split",
        opus_model: opus || fallback,
        sonnet_model: sonnet || fallback,
        haiku_model: haiku || fallback
      }
    },
    previous
  );
}

export function AgentModelSelectionPicker({
  agent,
  value,
  onChange
}: {
  agent: AgentLaunchKind;
  value: AgentModelSelection | null;
  onChange: (value: AgentModelSelection | null) => void;
}) {
  const { t } = useI18n();
  const provider = supportedProvider(agent);
  const presetsQuery = useQuery({
    queryKey: ["system-model-presets"],
    queryFn: fetchSystemModelPresets,
    enabled: provider !== null,
    staleTime: 10000
  });
  const presets = useMemo(
    () => (presetsQuery.data?.presets ?? []).filter((preset) => provider !== null && presetSupportsProvider(preset, provider)),
    [presetsQuery.data?.presets, provider]
  );
  const selectedPreset = presets.find((preset) => preset.id === value?.preset_id) ?? null;
  const claudeMode = value?.claude?.mode ?? "all";

  useEffect(() => {
    if (provider === null || value === null || presetsQuery.isLoading) {
      return;
    }
    if (!presets.some((preset) => preset.id === value.preset_id)) {
      onChange(null);
    }
  }, [onChange, presets, presetsQuery.isLoading, provider, value]);

  if (provider === null) {
    return null;
  }

  const changePreset = (presetId: string) => {
    const nextPreset = presets.find((preset) => preset.id === presetId) ?? null;
    if (nextPreset === null) {
      onChange(null);
      return;
    }
    if (agent === "claude") {
      onChange(claudeAllSelection(nextPreset, firstModel(nextPreset), value));
      return;
    }
    onChange(codexSelection(nextPreset, firstModel(nextPreset), value));
  };
  const setAllModel = (model: string) => {
    if (selectedPreset === null) {
      return;
    }
    onChange(
      agent === "claude"
        ? claudeAllSelection(selectedPreset, model, value)
        : codexSelection(selectedPreset, model, value)
    );
  };
  const setClaudeMode = (mode: "all" | "split") => {
    if (selectedPreset === null) {
      return;
    }
    if (mode === "all") {
      onChange(claudeAllSelection(selectedPreset, modelValue(value, selectedPreset), value));
      return;
    }
    onChange(claudeSplitSelection(
      selectedPreset,
      tierModelValue(value, selectedPreset, "opus_model"),
      tierModelValue(value, selectedPreset, "sonnet_model"),
      tierModelValue(value, selectedPreset, "haiku_model"),
      value
    ));
  };
  const setClaudeTier = (tier: "opus_model" | "sonnet_model" | "haiku_model", model: string) => {
    if (selectedPreset === null) {
      return;
    }
    onChange(claudeSplitSelection(
      selectedPreset,
      tier === "opus_model" ? model : tierModelValue(value, selectedPreset, "opus_model"),
      tier === "sonnet_model" ? model : tierModelValue(value, selectedPreset, "sonnet_model"),
      tier === "haiku_model" ? model : tierModelValue(value, selectedPreset, "haiku_model"),
      value
    ));
  };
  const setEffortOverride = (patch: Partial<AgentModelSelection>) => {
    if (value === null) {
      return;
    }
    onChange({ ...value, ...patch });
  };

  return (
    <section className="agent-model-picker">
      <label className="settings-field">
        <span>{t("terminal.model.label")}</span>
        <select
          value={selectedPreset?.id ?? ""}
          onChange={(event) => changePreset(event.target.value)}
          disabled={presetsQuery.isLoading}
        >
          <option value="">{t("terminal.model.clientDefault")}</option>
          {presets.map((preset) => (
            <option key={preset.id} value={preset.id}>
              {preset.name}
            </option>
          ))}
        </select>
      </label>
      {presetsQuery.isError && <p className="error settings-hint">{t("terminal.model.loadFailed")}</p>}
      {selectedPreset !== null && agent !== "claude" && (
        <label className="settings-field">
          <span>{t("terminal.model.name")}</span>
          <select value={modelValue(value, selectedPreset)} onChange={(event) => setAllModel(event.target.value)}>
            {modelNames(selectedPreset).map((model) => (
              <option key={model} value={model}>{model}</option>
            ))}
          </select>
        </label>
      )}
      {selectedPreset !== null && agent === "claude" && (
        <>
          <label className="settings-field">
            <span>{t("terminal.model.route")}</span>
            <select value={claudeMode} onChange={(event) => setClaudeMode(event.target.value as "all" | "split")}>
              <option value="all">{t("terminal.model.routeAll")}</option>
              <option value="split">{t("terminal.model.routeSplit")}</option>
            </select>
          </label>
          {claudeMode === "all" ? (
            <label className="settings-field">
              <span>{t("terminal.model.name")}</span>
              <select value={modelValue(value, selectedPreset)} onChange={(event) => setAllModel(event.target.value)}>
                {modelNames(selectedPreset).map((model) => (
                  <option key={model} value={model}>{model}</option>
                ))}
              </select>
            </label>
          ) : (
            <div className="agent-model-split-grid">
              {[
                ["opus_model", "Opus"],
                ["sonnet_model", "Sonnet"],
                ["haiku_model", "Haiku"]
              ].map(([tier, label]) => (
                <label key={tier} className="settings-field">
                  <span>{label}</span>
                  <select
                    value={tierModelValue(value, selectedPreset, tier as "opus_model" | "sonnet_model" | "haiku_model")}
                    onChange={(event) => setClaudeTier(
                      tier as "opus_model" | "sonnet_model" | "haiku_model",
                      event.target.value
                    )}
                  >
                    {modelNames(selectedPreset).map((model) => (
                      <option key={model} value={model}>{model}</option>
                    ))}
                  </select>
                </label>
              ))}
            </div>
          )}
        </>
      )}
      {selectedPreset !== null && agent === "codex" && (
        <div className="agent-model-effort-grid">
          <label className="settings-field">
            <span>{t("terminal.model.codexEffort")}</span>
            <select
              value={value?.codex_model_reasoning_effort ?? ""}
              onChange={(event) => setEffortOverride({
                codex_model_reasoning_effort: CODEX_EFFORTS.includes(event.target.value as CodexReasoningEffort)
                  ? (event.target.value as CodexReasoningEffort)
                  : null
              })}
            >
              <option value="">{t("terminal.model.effortInherit")}</option>
              {CODEX_EFFORTS.map((effort) => (
                <option key={effort} value={effort}>{effort}</option>
              ))}
            </select>
          </label>
          <label className="settings-field">
            <span>{t("terminal.model.codexPlanEffort")}</span>
            <select
              value={value?.codex_plan_mode_reasoning_effort ?? ""}
              onChange={(event) => setEffortOverride({
                codex_plan_mode_reasoning_effort: CODEX_EFFORTS.includes(event.target.value as CodexReasoningEffort)
                  ? (event.target.value as CodexReasoningEffort)
                  : null
              })}
            >
              <option value="">{t("terminal.model.effortInherit")}</option>
              {CODEX_EFFORTS.map((effort) => (
                <option key={effort} value={effort}>{effort}</option>
              ))}
            </select>
          </label>
        </div>
      )}
      {selectedPreset !== null && agent === "claude" && (
        <label className="settings-field">
          <span>{t("terminal.model.claudeEffort")}</span>
          <select
            value={value?.claude_reasoning_effort ?? ""}
            onChange={(event) => setEffortOverride({
              claude_reasoning_effort: CLAUDE_EFFORTS.includes(event.target.value as ClaudeReasoningEffort)
                ? (event.target.value as ClaudeReasoningEffort)
                : null
            })}
          >
            <option value="">{t("terminal.model.effortInherit")}</option>
            {CLAUDE_EFFORTS.map((effort) => (
              <option key={effort} value={effort}>{effort}</option>
            ))}
          </select>
        </label>
      )}
    </section>
  );
}
