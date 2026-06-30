import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { fetchProjectArtifacts } from "../apiProjects";
import { useI18n, type TranslateFn } from "../i18n";
import type { TerminalArtifact } from "../types";
import { artifactKindLabel, artifactStatusLabel, formatDateTime } from "./windowDetailData";
import {
  type ProjectTodoMultiSelectSearchItem,
  ProjectTodoMultiSelectSearchField
} from "./ProjectTodoMultiSelectSearchField";

const INPUT_ARTIFACT_LIMIT = 100;

type ProjectTodoInputArtifactIdsFieldProps = {
  clientId: string;
  projectPath: string;
  value: string[];
  className?: string;
  disabled?: boolean;
  onChange: (inputArtifactIds: string[]) => void;
};

export function ProjectTodoInputArtifactIdsField({
  clientId,
  projectPath,
  value,
  className,
  disabled = false,
  onChange
}: ProjectTodoInputArtifactIdsFieldProps) {
  const { t } = useI18n();
  const [loadRequested, setLoadRequested] = useState(false);
  const artifactsQuery = useQuery({
    queryKey: ["project-artifacts", "input-selector", clientId, projectPath, INPUT_ARTIFACT_LIMIT],
    queryFn: () => fetchProjectArtifacts(clientId, projectPath, INPUT_ARTIFACT_LIMIT, 0),
    enabled: loadRequested,
    staleTime: 30000
  });
  const artifactItems = useMemo(
    () => (artifactsQuery.data?.artifacts ?? []).map((artifact) => inputArtifactItem(artifact, t)),
    [artifactsQuery.data?.artifacts, t]
  );
  return (
    <div className={`project-todo-input-artifacts ${className ?? ""}`.trim()}>
      <ProjectTodoMultiSelectSearchField
        items={artifactItems}
        selectedValues={value}
        addLabel={t("projectTodo.inputArtifacts.add")}
        allSelectedLabel={t("projectTodo.inputArtifacts.allSelected")}
        className="project-todo-input-artifact-selector"
        disabled={disabled}
        emptyLabel={t("projectTodo.inputArtifacts.empty")}
        errorLabel={artifactsQuery.isError ? t("projectTodo.inputArtifacts.loadFailed") : null}
        legend={t("projectTodo.inputArtifacts.label")}
        loading={artifactsQuery.isLoading || (loadRequested && artifactsQuery.isFetching && artifactItems.length === 0)}
        loadingLabel={t("common.loading")}
        noSelectionLabel={t("projectTodo.inputArtifacts.noneSelected")}
        openWhenEmpty
        removeLabel={(label) => t("settings.cardTypes.removeArtifact", { label })}
        searchLabel={t("projectTodo.inputArtifacts.search")}
        selectedItemsLabel={t("projectTodo.inputArtifacts.selected")}
        onOpen={() => setLoadRequested(true)}
        onSelectionChange={onChange}
      />
      <small>{t("projectTodo.inputArtifacts.help")}</small>
    </div>
  );
}

function inputArtifactItem(artifact: TerminalArtifact, t: TranslateFn): ProjectTodoMultiSelectSearchItem {
  const kindLabel = artifactKindLabel(artifact.artifact_kind, t);
  const status = artifactStatusLabel(artifact, t);
  const completedOrCreated = artifact.completed_at ?? artifact.created_at;
  const description = `${kindLabel} · ${status} · ${formatDateTime(completedOrCreated)}`;
  return {
    key: artifact.id,
    label: artifact.title.trim() || artifact.id,
    searchText: [
      artifact.id,
      artifact.title,
      artifact.artifact_kind,
      kindLabel,
      status
    ].join(" ").toLowerCase(),
    value: artifact.id,
    description
  };
}
