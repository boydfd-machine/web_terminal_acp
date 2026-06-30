import { AgentConfigViewer } from "./AgentConfigViewer";
import { useI18n } from "../i18n";
import type { AgentConfig, AgentConfigSection, AgentConfigSelection } from "../types";
import { updateSelectionItem } from "../agentLaunch";

type AgentConfigPickerProps = {
  config: AgentConfig | null;
  selection: AgentConfigSelection | null;
  isLoading?: boolean;
  isError?: boolean;
  isFetching?: boolean;
  readOnly?: boolean;
  onSelectionChange: (selection: AgentConfigSelection) => void;
};

function mergeConfigWithSelection(
  config: AgentConfig | null,
  selection: AgentConfigSelection | null
): AgentConfig | null {
  if (config === null) {
    return null;
  }
  if (selection === null || selection.agent !== config.agent) {
    return config;
  }

  const selected = new Map<string, boolean>();
  for (const section of selection.sections) {
    for (const item of section.items) {
      selected.set(`${section.id}:${item.id}`, item.enabled);
    }
  }

  return {
    ...config,
    sections: config.sections.map((section) => ({
      ...section,
      items: section.items.map((item) => ({
        ...item,
        enabled: selected.get(`${section.id}:${item.id}`) ?? item.enabled
      }))
    }))
  };
}

export function AgentConfigPicker({
  config,
  selection,
  isLoading = false,
  isError = false,
  isFetching = false,
  readOnly = false,
  onSelectionChange
}: AgentConfigPickerProps) {
  const { t } = useI18n();
  const mergedConfig = mergeConfigWithSelection(config, selection);

  return (
    <AgentConfigViewer
      config={mergedConfig}
      isLoading={isLoading}
      isError={isError}
      isFetching={isFetching}
      title={t("terminal.create.config")}
      metaPrefix="launch config"
      emptyMessage={t("settings.agent.loadFailed")}
      readOnly={readOnly}
      onToggleItem={(sectionId, itemId, nextEnabled) => {
        if (selection === null) {
          return;
        }
        onSelectionChange(updateSelectionItem(selection, sectionId as AgentConfigSection["id"], itemId, nextEnabled));
      }}
    />
  );
}
