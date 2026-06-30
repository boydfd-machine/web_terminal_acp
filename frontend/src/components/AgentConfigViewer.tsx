import { useMemo, useState } from "react";

import type {
  AgentConfig,
  AgentConfigItem,
  AgentConfigModel,
  AgentConfigModelUpdate,
  AgentConfigSection,
  ClaudeReasoningEffort,
  CodexReasoningEffort
} from "../types";
import { agentLabel, DEFAULT_AGENT_CLIENTS } from "../agentLaunch";
import { useI18n } from "../i18n";
import { UiIcon } from "./UiIcon";

type AgentConfigViewerProps = {
  config: AgentConfig | null;
  isLoading?: boolean;
  isError?: boolean;
  isFetching?: boolean;
  pendingItemId?: string | null;
  isToggling?: boolean;
  toggleError?: boolean;
  title?: string;
  metaPrefix?: string;
  emptyMessage?: string;
  readOnly?: boolean;
  onToggleItem: (sectionId: string, itemId: string, nextEnabled: boolean) => void;
  onUpdateModel?: (input: AgentConfigModelUpdate) => void;
  isUpdatingModel?: boolean;
  modelUpdateError?: boolean;
};

function AgentConfigModelSection({
  model,
  agent,
  readOnly,
  isUpdatingModel,
  onUpdateModel
}: {
  model: AgentConfigModel;
  agent: string;
  readOnly: boolean;
  isUpdatingModel: boolean;
  onUpdateModel: (input: AgentConfigModelUpdate) => void;
}) {
  const { t } = useI18n();
  const isCodex = model.provider === "codex";
  const modelValue = model.model ?? "";
  const codexEffort = model.codex_model_reasoning_effort ?? null;
  const codexPlanEffort = model.codex_plan_mode_reasoning_effort ?? null;
  const claudeEffort = model.claude_reasoning_effort ?? null;
  return (
    <section className="agent-config-section agent-config-model">
      <header>
        <h4>{t("settings.agent.model")}</h4>
        <small>{model.preset_name ?? model.preset_id ?? model.provider ?? ""}</small>
      </header>
      <ul>
        <li className="agent-config-item agent-config-item-field">
          <div>
            <strong>{t("settings.agent.modelName")}</strong>
            <small>{model.provider ?? ""}</small>
          </div>
          {model.editable && !readOnly && model.available_models.length > 0 ? (
            <select
              className="agent-config-select"
              value={modelValue}
              disabled={isUpdatingModel}
              aria-label={t("settings.agent.modelName")}
              onChange={(event) => onUpdateModel({ model: event.target.value })}
            >
              {model.available_models.map((name) => (
                <option key={name} value={name}>{name}</option>
              ))}
              {modelValue && !model.available_models.includes(modelValue) ? (
                <option value={modelValue}>{modelValue}</option>
              ) : null}
            </select>
          ) : (
            <span className="agent-config-value">{modelValue || t("settings.agent.modelUnavailable")}</span>
          )}
        </li>
        {isCodex ? (
          <>
            <EffortRow
              label={t("settings.agent.modelReasoningEffort")}
              value={codexEffort}
              options={model.codex_reasoning_efforts as CodexReasoningEffort[]}
              editable={model.editable && !readOnly}
              disabled={isUpdatingModel}
              onSelect={(next) => onUpdateModel(
                next === null
                  ? { clear_codex_model_reasoning_effort: true }
                  : { codex_model_reasoning_effort: next as CodexReasoningEffort }
              )}
            />
            <EffortRow
              label={t("settings.agent.modelPlanModeEffort")}
              value={codexPlanEffort}
              options={model.codex_reasoning_efforts as CodexReasoningEffort[]}
              editable={model.editable && !readOnly}
              disabled={isUpdatingModel}
              onSelect={(next) => onUpdateModel(
                next === null
                  ? { clear_codex_plan_mode_reasoning_effort: true }
                  : { codex_plan_mode_reasoning_effort: next as CodexReasoningEffort }
              )}
            />
          </>
        ) : (
          <EffortRow
            label={t("settings.agent.modelReasoningEffort")}
            value={claudeEffort}
            options={model.claude_reasoning_efforts as ClaudeReasoningEffort[]}
            editable={model.editable && !readOnly}
            disabled={isUpdatingModel}
            onSelect={(next) => onUpdateModel(
              next === null
                ? { clear_claude_reasoning_effort: true }
                : { claude_reasoning_effort: next as ClaudeReasoningEffort }
            )}
          />
        )}
      </ul>
      {!model.editable ? (
        <p className="muted">{t("settings.agent.modelNotEditable")}</p>
      ) : null}
    </section>
  );
}

const NONE_SENTINEL = "__none__";

function normalizedSearch(value: string): string {
  return value.trim().toLocaleLowerCase();
}

function itemMatchesQuery(item: AgentConfigItem, query: string): boolean {
  if (query === "") {
    return true;
  }
  return [
    item.name,
    item.id,
    item.path ?? "",
    item.origin ?? ""
  ].some((value) => value.toLocaleLowerCase().includes(query));
}

function EffortRow({
  label,
  value,
  options,
  editable,
  disabled,
  onSelect
}: {
  label: string;
  value: string | null;
  options: string[];
  editable: boolean;
  disabled: boolean;
  onSelect: (next: string | null) => void;
}) {
  const { t } = useI18n();
  if (!editable) {
    return (
      <li className="agent-config-item agent-config-item-field">
        <div>
          <strong>{label}</strong>
        </div>
        <span className="agent-config-value">{value ?? t("settings.agent.modelEffortNone")}</span>
      </li>
    );
  }
  const selectValue = value === null ? NONE_SENTINEL : value;
  return (
    <li className="agent-config-item agent-config-item-field">
      <div>
        <strong>{label}</strong>
      </div>
      <select
        className="agent-config-select"
        value={selectValue}
        disabled={disabled}
        aria-label={label}
        onChange={(event) => {
          const next = event.target.value === NONE_SENTINEL ? null : event.target.value;
          onSelect(next);
        }}
      >
        <option value={NONE_SENTINEL}>{t("settings.agent.modelEffortNone")}</option>
        {options.map((option) => (
          <option key={option} value={option}>{option}</option>
        ))}
        {value && !options.includes(value) ? (
          <option value={value}>{value}</option>
        ) : null}
      </select>
    </li>
  );
}

function AgentConfigItemRow({
  section,
  item,
  disabled,
  readOnly,
  onToggleItem
}: {
  section: AgentConfigSection;
  item: AgentConfigItem;
  disabled: boolean;
  readOnly: boolean;
  onToggleItem: (sectionId: string, itemId: string, nextEnabled: boolean) => void;
}) {
  const { t } = useI18n();
  const action = item.enabled ? t("common.disable") : t("common.enable");
  return (
    <li className="agent-config-item">
      <div>
        <strong>{item.name}</strong>
        <small>{item.id}</small>
      </div>
      <label className="agent-config-switch">
        <input
          type="checkbox"
          checked={item.enabled}
          disabled={readOnly || disabled}
          aria-label={`${action} ${item.name}`}
          onChange={(event) => onToggleItem(section.id, item.id, event.target.checked)}
        />
        <span>{item.enabled ? t("common.enabled") : t("common.disabled")}</span>
      </label>
    </li>
  );
}

function AgentConfigSectionView({
  section,
  pendingItemId,
  isToggling,
  readOnly,
  onToggleItem
}: {
  section: AgentConfigSection;
  pendingItemId: string | null;
  isToggling: boolean;
  readOnly: boolean;
  onToggleItem: (sectionId: string, itemId: string, nextEnabled: boolean) => void;
}) {
  const { t } = useI18n();
  const [search, setSearch] = useState("");
  const searchQuery = normalizedSearch(search);
  const filteredItems = useMemo(
    () => section.items.filter((item) => itemMatchesQuery(item, searchQuery)),
    [searchQuery, section.items]
  );
  const searchActive = searchQuery.length > 0;
  return (
    <section className="agent-config-section">
      <header>
        <h4>{section.name}</h4>
        <small>
          {searchActive
            ? t("settings.agent.filteredItemsCount", { count: filteredItems.length, total: section.items.length })
            : t("settings.agent.itemsCount", { count: section.items.length })}
        </small>
      </header>
      {section.items.length === 0 ? (
        <p className="muted">{t("settings.agent.noSectionItems", { section: section.name.toLocaleLowerCase() })}</p>
      ) : (
        <>
          <label className="agent-config-search">
            <span>{t("settings.agent.searchSection", { section: section.name })}</span>
            <div className="agent-config-search-row">
              <input
                type="search"
                value={search}
                placeholder={t("settings.agent.searchPlaceholder")}
                onChange={(event) => setSearch(event.target.value)}
              />
              {searchActive ? (
                <button
                  type="button"
                  className="ui-icon-button"
                  aria-label={t("common.clear")}
                  title={t("common.clear")}
                  onClick={() => setSearch("")}
                >
                  <UiIcon name="x" />
                </button>
              ) : null}
            </div>
          </label>
          {filteredItems.length === 0 ? (
            <p className="muted">{t("settings.agent.noMatchingItems")}</p>
          ) : (
            <ul>
              {filteredItems.map((item) => (
                <AgentConfigItemRow
                  key={item.id}
                  section={section}
                  item={item}
                  disabled={isToggling && pendingItemId === item.id}
                  readOnly={readOnly}
                  onToggleItem={onToggleItem}
                />
              ))}
            </ul>
          )}
        </>
      )}
    </section>
  );
}

export function AgentConfigViewer({
  config,
  isLoading = false,
  isError = false,
  isFetching = false,
  pendingItemId = null,
  isToggling = false,
  toggleError = false,
  title = "Agent Config",
  metaPrefix = "user config",
  emptyMessage,
  readOnly = false,
  onToggleItem,
  onUpdateModel,
  isUpdatingModel = false,
  modelUpdateError = false
}: AgentConfigViewerProps) {
  const { t } = useI18n();
  const meta = config
    ? `${agentLabel(config.agent, DEFAULT_AGENT_CLIENTS)} ${metaPrefix}${isFetching && !isLoading ? ` · ${t("settings.agent.configRefreshing")}` : ""}`
    : isLoading
      ? t("settings.agent.configMetaLoading")
      : t("settings.agent.configMetaUnavailable");

  return (
    <section className="agent-config-viewer">
      <div className="agent-record-header">
        <div>
          <h3>{title}</h3>
          <small>{meta}</small>
        </div>
      </div>
      {isLoading ? (
        <p className="muted">{t("settings.agent.configLoading")}</p>
      ) : isError || config === null ? (
        <p className="error" role="alert">{emptyMessage ?? t("settings.agent.loadFailed")}</p>
      ) : (
        <div className="agent-config-sections">
          {config.model && onUpdateModel ? (
            <AgentConfigModelSection
              model={config.model}
              agent={config.agent}
              readOnly={readOnly}
              isUpdatingModel={isUpdatingModel}
              onUpdateModel={onUpdateModel}
            />
          ) : null}
          {config.sections.map((section) => (
            <AgentConfigSectionView
              key={section.id}
              section={section}
              pendingItemId={pendingItemId}
              isToggling={isToggling}
              readOnly={readOnly}
              onToggleItem={onToggleItem}
            />
          ))}
        </div>
      )}
      {toggleError ? <p className="error" role="alert">{t("settings.agent.configUpdateFailed")}</p> : null}
      {modelUpdateError ? <p className="error" role="alert">{t("settings.agent.modelUpdateFailed")}</p> : null}
    </section>
  );
}
