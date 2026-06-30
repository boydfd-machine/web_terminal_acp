import { useMemo, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  deleteSystemProjectTodoType,
  fetchAgentClients,
  fetchAgentProfiles,
  fetchArtifactPlugins,
  fetchProjectTodoTypes,
  updateSystemProjectTodoType,
  upsertSystemProjectTodoType
} from "../api";
import { DEFAULT_AGENT_CLIENTS, agentClientOptions } from "../agentLaunch";
import { useI18n } from "../i18n";
import type { AgentLaunchKind, ProjectTodoType } from "../types";
import { ProjectTodoArtifactKindSelector } from "./ProjectTodoArtifactKindSelector";
import { ProjectTodoDispatchTemplateEditor } from "./ProjectTodoDispatchTemplateEditor";
import { ProjectTodoInputArtifactIdsField } from "./ProjectTodoInputArtifactIdsField";
import { UiIcon } from "./UiIcon";
import { useOverlayFocus } from "./useOverlayFocus";

type ProjectTodoTypeManagerProps = {
  clientId: string;
  projectPath: string;
  title?: string;
  contextLabel?: string;
};

type ProjectTodoTypeManagerModalProps = ProjectTodoTypeManagerProps & {
  isOpen: boolean;
  onClose: () => void;
};

type ProjectTodoTypeDraft = {
  editingId: string | null;
  id: string;
  name: string;
  description: string;
  agent: string;
  agent_profile_id: string;
  artifact_kinds: string[];
  input_artifact_ids: string[];
  dispatch_template: string;
};

const EMPTY_DRAFT: ProjectTodoTypeDraft = {
  editingId: null,
  id: "",
  name: "",
  description: "",
  agent: "",
  agent_profile_id: "",
  artifact_kinds: [],
  input_artifact_ids: [],
  dispatch_template: ""
};

function queryKey(clientId: string, projectPath: string) {
  return ["project-todo-types", clientId, projectPath] as const;
}

export function ProjectTodoTypeManager({
  clientId,
  projectPath,
  title,
  contextLabel
}: ProjectTodoTypeManagerProps) {
  const { t } = useI18n();
  const queryClient = useQueryClient();
  const [draft, setDraft] = useState<ProjectTodoTypeDraft>(EMPTY_DRAFT);
  const typesQuery = useQuery({
    queryKey: queryKey(clientId, projectPath),
    queryFn: () => fetchProjectTodoTypes(clientId, projectPath),
    staleTime: 30000
  });
  const agentClientsQuery = useQuery({
    queryKey: ["agent-clients", clientId],
    queryFn: () => fetchAgentClients(clientId),
    staleTime: 60000
  });
  const profilesQuery = useQuery({
    queryKey: ["agent-profiles", clientId],
    queryFn: () => fetchAgentProfiles(clientId),
    staleTime: 10000
  });
  const artifactPluginsQuery = useQuery({
    queryKey: ["artifact-plugins", "project-todo-types"],
    queryFn: fetchArtifactPlugins,
    staleTime: 60000
  });
  const todoTypes = typesQuery.data?.todo_types ?? [];
  const agentOptions = agentClientOptions(agentClientsQuery.data?.agent_clients ?? DEFAULT_AGENT_CLIENTS, "launch");
  const profiles = profilesQuery.data?.profiles ?? [];
  const artifactPlugins = artifactPluginsQuery.data?.plugins ?? [];
  const systemCount = todoTypes.filter((todoType) => todoType.scope === "system").length;
  const projectCount = todoTypes.length - systemCount;
  const canSave = draft.id.trim().length > 0 && draft.name.trim().length > 0;
  const invalidate = () => {
    void queryClient.invalidateQueries({ queryKey: queryKey(clientId, projectPath) });
    void queryClient.invalidateQueries({ queryKey: ["project-todos", clientId, projectPath] });
  };
  const saveMutation = useMutation({
    mutationFn: () => {
      const input = {
        name: draft.name.trim(),
        description: draft.description.trim() || null,
        agent: draft.agent.trim() || null,
        agent_profile_id: draft.agent_profile_id.trim() || null,
        artifact_kinds: draft.artifact_kinds,
        input_artifact_ids: draft.input_artifact_ids,
        dispatch_template: draft.dispatch_template.trim() || null
      };
      return draft.editingId === null
        ? upsertSystemProjectTodoType(clientId, { id: draft.id.trim(), ...input })
        : updateSystemProjectTodoType(clientId, draft.editingId, input);
    },
    onSuccess: () => {
      setDraft(EMPTY_DRAFT);
      invalidate();
    }
  });
  const deleteMutation = useMutation({
    mutationFn: (todoTypeId: string) => deleteSystemProjectTodoType(clientId, todoTypeId),
    onSuccess: () => {
      setDraft(EMPTY_DRAFT);
      invalidate();
    }
  });
  const editing = draft.editingId !== null;
  const status = useMemo(() => {
    if (typesQuery.isLoading) {
      return t("common.loading");
    }
    if (typesQuery.isError) {
      return t("settings.cardTypes.loadFailed");
    }
    return t("settings.cardTypes.status", {
      system: systemCount,
      project: projectCount > 0 ? t("settings.cardTypes.projectSuffix", { project: projectCount }) : ""
    });
  }, [projectCount, systemCount, t, typesQuery.isError, typesQuery.isLoading]);

  return (
    <section className="project-todo-type-manager" aria-label={t("settings.cardTypes.manage")}>
      <header className="project-todo-type-manager-header">
        <div>
          <strong>{title ?? t("settings.cardTypes.manage")}</strong>
          <small>{contextLabel ?? projectPath}</small>
        </div>
        <span>{status}</span>
      </header>
      <form
        className="project-todo-type-form"
        onSubmit={(event) => {
          event.preventDefault();
          if (canSave && !saveMutation.isPending) {
            saveMutation.mutate();
          }
        }}
      >
        <label className="settings-field">
          <span>ID</span>
          <input
            value={draft.id}
            disabled={editing}
            maxLength={64}
            onChange={(event) => setDraft((current) => ({ ...current, id: event.target.value }))}
            placeholder="research"
          />
        </label>
        <label className="settings-field">
          <span>{t("settings.cardTypes.name")}</span>
          <input
            value={draft.name}
            maxLength={255}
            onChange={(event) => setDraft((current) => ({ ...current, name: event.target.value }))}
            placeholder="Research"
          />
        </label>
        <label className="settings-field">
          <span>{t("settings.cardTypes.agent")}</span>
          <select
            value={draft.agent}
            onChange={(event) => setDraft((current) => ({ ...current, agent: event.target.value as AgentLaunchKind }))}
          >
            <option value="">{t("settings.cardTypes.unassigned")}</option>
            {agentOptions.map((option) => <option key={option.id} value={option.id}>{option.label}</option>)}
          </select>
        </label>
        <label className="settings-field">
          <span>{t("settings.cardTypes.profile")}</span>
          <select
            value={draft.agent_profile_id}
            disabled={profilesQuery.isLoading}
            onChange={(event) => {
              const profileId = event.target.value;
              const profile = profiles.find((candidate) => candidate.id === profileId) ?? null;
              setDraft((current) => ({
                ...current,
                agent_profile_id: profileId,
                agent: profile?.default_agent_client ?? current.agent
              }));
            }}
          >
            <option value="">{t("common.none")}</option>
            {profiles.map((profile) => <option key={profile.id} value={profile.id}>{profile.name}</option>)}
          </select>
        </label>
        <label className="settings-field project-todo-type-description">
          <span>{t("settings.cardTypes.description")}</span>
          <textarea
            value={draft.description}
            maxLength={4096}
            onChange={(event) => setDraft((current) => ({ ...current, description: event.target.value }))}
          />
        </label>
        {artifactPlugins.length > 0 && (
          <ProjectTodoArtifactKindSelector
            artifactPlugins={artifactPlugins}
            selectedKinds={draft.artifact_kinds}
            className="project-todo-type-artifacts"
            legend={t("settings.cardTypes.artifacts")}
            onSelectionChange={(artifactKinds) => setDraft((current) => ({
              ...current,
              artifact_kinds: artifactKinds
            }))}
          />
        )}
        <ProjectTodoInputArtifactIdsField
          clientId={clientId}
          projectPath={projectPath}
          value={draft.input_artifact_ids}
          className="project-todo-type-input-artifacts"
          onChange={(inputArtifactIds) => setDraft((current) => ({
            ...current,
            input_artifact_ids: inputArtifactIds
          }))}
        />
        <ProjectTodoDispatchTemplateEditor
          value={draft.dispatch_template}
          onChange={(dispatchTemplate) => setDraft((current) => ({
            ...current,
            dispatch_template: dispatchTemplate
          }))}
          compact
        />
        <div className="project-todo-type-form-actions">
          {saveMutation.isError && <span className="error" role="alert">{t("settings.cardTypes.saveFailed")}</span>}
          {deleteMutation.isError && <span className="error" role="alert">{t("settings.cardTypes.deleteFailed")}</span>}
          {editing && (
            <button
              type="button"
              className="ui-icon-button"
              aria-label={t("common.cancel")}
              title={t("common.cancel")}
              onClick={() => setDraft(EMPTY_DRAFT)}
            >
              <UiIcon name="x" />
            </button>
          )}
          <button
            type="submit"
            className={editing ? "ui-icon-button" : undefined}
            disabled={!canSave || saveMutation.isPending}
            aria-label={editing ? t("common.save") : undefined}
            title={editing ? t("common.save") : undefined}
          >
            {editing ? <UiIcon name="save" /> : t("settings.cardTypes.create")}
          </button>
        </div>
      </form>
      <div className="project-todo-type-list">
        {todoTypes.map((todoType) => (
          <ProjectTodoTypeRow
            key={`${todoType.scope}:${todoType.id}`}
            todoType={todoType}
            deleting={deleteMutation.isPending}
            onEdit={() => setDraft(draftFromType(todoType))}
            onDelete={() => deleteMutation.mutate(todoType.id)}
          />
        ))}
      </div>
    </section>
  );
}

export function ProjectTodoTypeManagerModal({
  isOpen,
  onClose,
  clientId,
  projectPath,
  title,
  contextLabel
}: ProjectTodoTypeManagerModalProps) {
  const { t } = useI18n();
  const panelRef = useRef<HTMLElement | null>(null);
  useOverlayFocus({
    isOpen,
    ref: panelRef,
    onEscape: onClose
  });

  if (!isOpen) {
    return null;
  }

  return (
    <div
      className="project-todo-type-manager-modal-backdrop"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) {
          onClose();
        }
      }}
    >
      <section
        ref={panelRef}
        className="project-todo-type-manager-modal"
        role="dialog"
        aria-modal="true"
        aria-label={t("settings.cardTypes.manage")}
      >
        <header className="project-todo-type-manager-modal-header">
          <div>
            <h2>{title ?? t("settings.cardTypes.manage")}</h2>
            {contextLabel && <p>{contextLabel}</p>}
          </div>
          <button
            type="button"
            className="ui-icon-button"
            aria-label={t("common.close")}
            title={t("common.close")}
            onClick={onClose}
          >
            <UiIcon name="x" />
          </button>
        </header>
        <ProjectTodoTypeManager
          clientId={clientId}
          projectPath={projectPath}
          contextLabel={contextLabel}
        />
      </section>
    </div>
  );
}

function draftFromType(todoType: ProjectTodoType): ProjectTodoTypeDraft {
  return {
    editingId: todoType.id,
    id: todoType.id,
    name: todoType.name,
    description: todoType.description ?? "",
    agent: todoType.agent ?? "",
    agent_profile_id: todoType.agent_profile_id ?? "",
    artifact_kinds: todoType.artifact_kinds ?? [],
    input_artifact_ids: todoType.input_artifact_ids ?? [],
    dispatch_template: todoType.dispatch_template ?? ""
  };
}

function ProjectTodoTypeRow({
  todoType,
  deleting,
  onEdit,
  onDelete
}: {
  todoType: ProjectTodoType;
  deleting: boolean;
  onEdit: () => void;
  onDelete: () => void;
}) {
  const { t } = useI18n();
  const readOnly = todoType.scope === "project";
  const agent = todoType.agent ?? "-";
  const profile = todoType.agent_profile_id ?? "-";
  const artifactKinds = todoType.artifact_kinds ?? [];
  const inputArtifactIds = todoType.input_artifact_ids ?? [];
  const artifacts = artifactKinds.length > 0 ? artifactKinds.join(", ") : "-";
  const inputs = inputArtifactIds.length > 0
    ? ` · ${t("settings.cardTypes.inputArtifactsCount", { count: inputArtifactIds.length })}`
    : "";
  const template = todoType.dispatch_template === null ? "-" : t("settings.cardTypes.template");
  return (
    <article className={`project-todo-type-row ${readOnly ? "read-only" : ""}`}>
      <div>
        <strong>{todoType.name}</strong>
        <small>{todoType.id} · {todoType.scope === "system" ? t("settings.cardTypes.systemScope") : t("settings.cardTypes.projectScope")}</small>
      </div>
      <span>{agent}{profile !== "-" ? ` / ${profile}` : ""}</span>
      <span>{artifacts}{inputs} · {template}</span>
      {!readOnly && (
        <div className="project-todo-type-row-actions">
          <button
            type="button"
            className="ui-icon-button"
            aria-label={t("settings.cardTypes.edit", { name: todoType.name })}
            title={t("common.edit")}
            onClick={onEdit}
          >
            <UiIcon name="edit" />
          </button>
          <button
            type="button"
            className="ui-icon-button"
            disabled={todoType.id === "default" || deleting}
            aria-label={t("settings.cardTypes.delete", { name: todoType.name })}
            title={t("common.delete")}
            onClick={onDelete}
          >
            <UiIcon name="trash" />
          </button>
        </div>
      )}
    </article>
  );
}
