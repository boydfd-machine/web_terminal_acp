import { UiIcon } from "../../components/UiIcon";
import { useI18n } from "../../i18n";
import type {
  ClaudeReasoningEffort,
  CodexReasoningEffort,
  SystemModelConfig,
  SystemModelProvider
} from "../../types";

type ModelConfigDraft = SystemModelConfig;

const CODEX_EFFORTS: CodexReasoningEffort[] = ["minimal", "low", "medium", "high", "xhigh"];
const CLAUDE_EFFORTS: ClaudeReasoningEffort[] = ["low", "medium", "high", "xhigh", "max", "auto"];

function numericInputValue(value: number | null | undefined): string {
  return typeof value === "number" && Number.isFinite(value) ? String(value) : "";
}

function numberOrNull(value: string): number | null {
  const clean = value.trim();
  if (clean === "") {
    return null;
  }
  const parsed = Number(clean);
  return Number.isInteger(parsed) && parsed > 0 ? parsed : null;
}

function effortOrNull<T extends string>(value: string, choices: readonly T[]): T | null {
  return (choices as readonly string[]).includes(value) ? (value as T) : null;
}

function updateModelConfig(
  models: ModelConfigDraft[],
  index: number,
  patch: Partial<ModelConfigDraft>
): ModelConfigDraft[] {
  return models.map((model, modelIndex) => modelIndex === index ? { ...model, ...patch } : model);
}

export function SystemModelConfigEditor({
  models,
  providers,
  onChange
}: {
  models: ModelConfigDraft[];
  providers: SystemModelProvider[];
  onChange: (models: ModelConfigDraft[]) => void;
}) {
  const { t } = useI18n();
  const showCodex = providers.includes("openai_compatible");
  const showClaude = providers.includes("anthropic_compatible");

  return (
    <div className="system-model-config-editor system-model-form-wide">
      <div className="system-model-config-header">
        <span>{t("settings.models.models")}</span>
        <button
          type="button"
          className="system-config-icon-button"
          aria-label={t("settings.models.addModel")}
          title={t("settings.models.addModel")}
          onClick={() => onChange([...models, { name: "" }])}
        >
          <UiIcon name="plus" />
        </button>
      </div>
      <div className="system-model-config-grid">
        <span>{t("settings.models.modelName")}</span>
        <span>{t("settings.models.maxContext")}</span>
        <span>{t("settings.models.compactLimit")}</span>
        <span>{t("settings.models.maxOutput")}</span>
        <span />
        {models.map((model, index) => {
          const effortVisible = showCodex || showClaude;
          return (
            <div className="system-model-config-row" key={index}>
              <div className="system-model-config-fields">
                <input
                  value={model.name}
                  onChange={(event) => onChange(updateModelConfig(models, index, { name: event.target.value }))}
                  placeholder="gpt-4.1"
                />
                <input
                  type="number"
                  min={1}
                  inputMode="numeric"
                  value={numericInputValue(model.context_window)}
                  onChange={(event) => onChange(updateModelConfig(models, index, {
                    context_window: numberOrNull(event.target.value)
                  }))}
                />
                <input
                  type="number"
                  min={1}
                  inputMode="numeric"
                  value={numericInputValue(model.auto_compact_token_limit)}
                  onChange={(event) => onChange(updateModelConfig(models, index, {
                    auto_compact_token_limit: numberOrNull(event.target.value)
                  }))}
                />
                <input
                  type="number"
                  min={1}
                  inputMode="numeric"
                  value={numericInputValue(model.max_output_tokens)}
                  onChange={(event) => onChange(updateModelConfig(models, index, {
                    max_output_tokens: numberOrNull(event.target.value)
                  }))}
                />
                <button
                  type="button"
                  className="system-config-icon-button danger"
                  aria-label={t("settings.models.removeModel")}
                  title={t("settings.models.removeModel")}
                  onClick={() => onChange(models.filter((_model, modelIndex) => modelIndex !== index))}
                >
                  <UiIcon name="trash" />
                </button>
              </div>
              {effortVisible && (
                <div className="system-model-config-effort">
                  {showCodex && (
                    <>
                      <label className="system-model-effort-field">
                        <span>{t("settings.models.codexEffort")}</span>
                        <select
                          value={model.codex_model_reasoning_effort ?? ""}
                          onChange={(event) => onChange(updateModelConfig(models, index, {
                            codex_model_reasoning_effort: effortOrNull(event.target.value, CODEX_EFFORTS)
                          }))}
                        >
                          <option value="">{t("settings.models.effortDefault")}</option>
                          {CODEX_EFFORTS.map((effort) => (
                            <option key={effort} value={effort}>{effort}</option>
                          ))}
                        </select>
                      </label>
                      <label className="system-model-effort-field">
                        <span>{t("settings.models.codexPlanEffort")}</span>
                        <select
                          value={model.codex_plan_mode_reasoning_effort ?? ""}
                          onChange={(event) => onChange(updateModelConfig(models, index, {
                            codex_plan_mode_reasoning_effort: effortOrNull(event.target.value, CODEX_EFFORTS)
                          }))}
                        >
                          <option value="">{t("settings.models.effortDefault")}</option>
                          {CODEX_EFFORTS.map((effort) => (
                            <option key={effort} value={effort}>{effort}</option>
                          ))}
                        </select>
                      </label>
                    </>
                  )}
                  {showClaude && (
                    <label className="system-model-effort-field">
                      <span>{t("settings.models.claudeEffort")}</span>
                      <select
                        value={model.claude_reasoning_effort ?? ""}
                        onChange={(event) => onChange(updateModelConfig(models, index, {
                          claude_reasoning_effort: effortOrNull(event.target.value, CLAUDE_EFFORTS)
                        }))}
                      >
                        <option value="">{t("settings.models.effortDefault")}</option>
                        {CLAUDE_EFFORTS.map((effort) => (
                          <option key={effort} value={effort}>{effort}</option>
                        ))}
                      </select>
                    </label>
                  )}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
