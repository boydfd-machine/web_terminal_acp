import { useMemo } from "react";

import { useI18n, type TranslateFn } from "../i18n";
import type { ArtifactPluginDescriptor } from "../types";
import { ProjectTodoMultiSelectSearchField } from "./ProjectTodoMultiSelectSearchField";

type ProjectTodoArtifactKindSelectorProps = {
  artifactPlugins: ArtifactPluginDescriptor[];
  selectedKinds: string[];
  className?: string;
  disabled?: boolean;
  legend?: string;
  onSelectionChange: (artifactKinds: string[]) => void;
};

export function ProjectTodoArtifactKindSelector({
  artifactPlugins,
  selectedKinds,
  className = "",
  disabled = false,
  legend,
  onSelectionChange
}: ProjectTodoArtifactKindSelectorProps) {
  const { t } = useI18n();
  const displayLegend = legend ?? t("settings.cardTypes.artifacts");
  const fieldsetClassName = ["project-todo-form-artifacts", className].filter(Boolean).join(" ");
  const artifactItems = useMemo(
    () => artifactPlugins.map((plugin) => {
      const label = artifactPluginLabel(plugin, t);
      return {
        key: `${plugin.domain}:${plugin.artifact_kind}`,
        label,
        searchText: [
          label,
          plugin.artifact_kind,
          plugin.default_title,
          plugin.domain
        ].join(" ").toLowerCase(),
        value: projectTodoArtifactKindValue(plugin)
      };
    }),
    [artifactPlugins, t]
  );
  if (artifactPlugins.length === 0) {
    return null;
  }

  return (
    <ProjectTodoMultiSelectSearchField
      items={artifactItems}
      selectedValues={selectedKinds}
      addLabel={t("settings.cardTypes.addArtifact")}
      allSelectedLabel={t("settings.cardTypes.allArtifactsSelected")}
      className={fieldsetClassName}
      disabled={disabled}
      emptyLabel={t("settings.cardTypes.noArtifactMatches")}
      legend={displayLegend}
      noSelectionLabel={t("settings.cardTypes.noArtifactsSelected")}
      removeLabel={(label) => t("settings.cardTypes.removeArtifact", { label })}
      searchLabel={t("settings.cardTypes.searchArtifacts")}
      selectedItemsLabel={t("settings.cardTypes.selectedArtifacts")}
      onSelectionChange={onSelectionChange}
    />
  );
}

export function projectTodoArtifactKindValue(plugin: ArtifactPluginDescriptor): string {
  return plugin.domain === "project" ? `project:${plugin.artifact_kind}` : plugin.artifact_kind;
}

function artifactPluginLabel(plugin: ArtifactPluginDescriptor, t: TranslateFn): string {
  const label = plugin.label.trim() || plugin.artifact_kind;
  return plugin.domain === "project" ? t("settings.cardTypes.projectArtifact", { label }) : label;
}
