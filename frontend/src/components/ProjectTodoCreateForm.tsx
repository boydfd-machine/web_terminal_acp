import { useMutation, useQuery } from "@tanstack/react-query";
import { useEffect, useState, type Ref } from "react";

import { DEFAULT_AGENT_CLIENTS } from "../agentLaunch";
import {
  artifactModelAgentFromTodoType,
  artifactModelDefaultSelection
} from "../artifactModelSelection";
import { createProjectTodo, fetchArtifactPlugins, fetchProjectTodoTypes } from "../api";
import { useI18n } from "../i18n";
import type {
  AgentClient,
  AgentLaunchKind,
  AgentModelSelection,
  ProjectAgentPreference,
  ProjectTodo,
  ProjectTodoExecutionKind,
  ProjectTodoListItem,
  ProjectTodoReviewStrategy,
  ProjectTodoTerminalPolicy,
  ProjectTodoTriggerStrategy
} from "../types";
import { ArtifactModelSelectionField } from "./ArtifactModelSelectionField";
import { projectTodoTypeLabel } from "./projectTodoDisplay";
import { ProjectTodoDescriptionMentionTextarea } from "./ProjectTodoDescriptionMentionTextarea";
import { ProjectTodoArtifactKindSelector } from "./ProjectTodoArtifactKindSelector";
import { ProjectTodoInputArtifactIdsField } from "./ProjectTodoInputArtifactIdsField";
import { ProjectTodoParentSelector } from "./ProjectTodoParentSelector";
import {
  clearProjectTodoCreateDraft,
  projectTodoCreateDraftStorageKey,
  readProjectTodoCreateDraft,
  writeProjectTodoCreateDraft,
  type ProjectTodoCreateDraft
} from "./projectTodoCreateDraftStorage";

type ProjectTodoCreateFormProps = {
  clientId: string;
  directDispatch?: boolean;
  mode?: "quick" | "full";
  parentTodoId?: string | null;
  agentClients?: AgentClient[];
  projectPreference?: ProjectAgentPreference | null;
  projectPath: string;
  todos?: ProjectTodoListItem[];
  titleInputRef?: Ref<HTMLInputElement>;
  onCreated: (todo: ProjectTodo, action: ProjectTodoCreateAction) => void;
  onPendingChange: (pending: boolean) => void;
};

export type ProjectTodoCreateAction = "add" | "dispatch" | "direct-dispatch";

type StoredProjectTodoCreateDraft = ProjectTodoCreateDraft & {
  storageKey: string;
};

type ProjectTodoCreateInput = {
  title: string;
  description?: string | null;
  parent_todo_id?: string | null;
  todo_type_id?: string;
  status?: "TODO" | "BLOCKED";
  artifact_kinds?: string[];
  input_artifact_ids?: string[];
  execution_kind?: ProjectTodoExecutionKind;
  terminal_policy?: ProjectTodoTerminalPolicy;
  trigger_strategy?: ProjectTodoTriggerStrategy;
  cron_expression?: string | null;
  review_strategy?: ProjectTodoReviewStrategy;
  review_agent?: string | null;
  review_agent_profile_id?: string | null;
  artifact_model_selection?: AgentModelSelection | null;
};

export function ProjectTodoCreateForm({
  clientId,
  directDispatch = false,
  mode = "full",
  parentTodoId: initialParentTodoId = null,
  agentClients = DEFAULT_AGENT_CLIENTS,
  projectPreference = null,
  projectPath,
  todos = [],
  titleInputRef,
  onCreated,
  onPendingChange
}: ProjectTodoCreateFormProps) {
  const { t } = useI18n();
  const storageKey = projectTodoCreateDraftStorageKey(clientId, projectPath);
  const initialParentKey = initialParentTodoId ?? "";
  const [draft, setDraft] = useState<StoredProjectTodoCreateDraft>(() => (
    initialProjectTodoCreateDraft(storageKey, initialParentKey)
  ));
  const title = draft.storageKey === storageKey ? draft.title : "";
  const description = draft.storageKey === storageKey ? draft.description : "";
  const parentTodoId = draft.storageKey === storageKey ? draft.parent_todo_id : "";
  const fullDraft = draft.storageKey === storageKey && mode === "full";
  const todoTypeId = draft.storageKey === storageKey ? draft.todo_type_id : "default";
  const executionKind = fullDraft ? draft.execution_kind : "ONCE";
  const terminalPolicy = fullDraft ? draft.terminal_policy : "NEW_TERMINAL";
  const triggerStrategy = fullDraft ? draft.trigger_strategy : "MANUAL";
  const showArtifactSelector = mode === "full" || directDispatch;
  const cronExpression = fullDraft ? draft.cron_expression : "";
  const artifactKinds = draft.storageKey === storageKey && showArtifactSelector ? draft.artifact_kinds : [];
  const inputArtifactIds = draft.storageKey === storageKey && showArtifactSelector ? draft.input_artifact_ids : [];
  const artifactModelSelection = draft.storageKey === storageKey ? draft.artifact_model_selection : null;
  const artifactPluginsQuery = useQuery({
    queryKey: ["artifact-plugins", "project-todo-create"],
    queryFn: fetchArtifactPlugins,
    enabled: showArtifactSelector,
    staleTime: 60000
  });
  const todoTypesQuery = useQuery({
    queryKey: ["project-todo-types", clientId, projectPath],
    queryFn: () => fetchProjectTodoTypes(clientId, projectPath),
    staleTime: 30000
  });
  const todoTypes = todoTypesQuery.data?.todo_types ?? [];
  const selectedTodoTypeId = todoTypes.some((todoType) => todoType.id === todoTypeId) ? todoTypeId : "default";
  const selectedTodoType = todoTypes.find((todoType) => todoType.id === selectedTodoTypeId) ?? null;
  const artifactModelAgent = artifactModelAgentFromTodoType(selectedTodoType, projectPreference, agentClients);
  const artifactPlugins = artifactPluginsQuery.data?.plugins ?? [];
  const createMutation = useMutation({
    mutationFn: (_action: ProjectTodoCreateAction) => createProjectTodo(
      clientId,
      projectPath,
      projectTodoCreateInput({
        title,
        description,
        parentTodoId,
        todoTypeId: selectedTodoTypeId,
        executionKind,
        terminalPolicy,
        triggerStrategy,
        cronExpression,
        artifactKinds: showArtifactSelector ? artifactKinds : [],
        todoTypeArtifactKinds: showArtifactSelector ? selectedTodoType?.artifact_kinds ?? [] : [],
        inputArtifactIds: showArtifactSelector ? inputArtifactIds : [],
        todoTypeInputArtifactIds: showArtifactSelector ? selectedTodoType?.input_artifact_ids ?? [] : [],
        artifactModelAgent,
        artifactModelSelection
      })
    ),
    onSuccess: (todo, action) => {
      setDraft({ storageKey, ...emptyProjectTodoCreateDraft() });
      clearProjectTodoCreateDraft(storageKey);
      onCreated(todo, action);
    }
  });

  const updateDraft = (patch: Partial<ProjectTodoCreateDraft>) => {
    const nextDraft = {
      title,
      description,
      parent_todo_id: parentTodoId,
      todo_type_id: selectedTodoTypeId,
      execution_kind: executionKind,
      terminal_policy: terminalPolicy,
      trigger_strategy: triggerStrategy,
      cron_expression: cronExpression,
      artifact_kinds: artifactKinds,
      input_artifact_ids: inputArtifactIds,
      artifact_model_selection: artifactModelSelection,
      ...patch
    };
    if (nextDraft.execution_kind === "ONCE") {
      nextDraft.trigger_strategy = "MANUAL";
      nextDraft.cron_expression = "";
    }
    if (nextDraft.trigger_strategy === "MANUAL") {
      nextDraft.cron_expression = "";
    }
    setDraft({ storageKey, ...nextDraft });
    writeProjectTodoCreateDraft(storageKey, nextDraft);
  };
  const updateTodoType = (nextTodoTypeId: string) => {
    const nextTodoType = todoTypes.find((todoType) => todoType.id === nextTodoTypeId) ?? null;
    updateDraft({
      todo_type_id: nextTodoTypeId,
      ...(showArtifactSelector ? {
        artifact_kinds: nextTodoType?.artifact_kinds ?? [],
        input_artifact_ids: nextTodoType?.input_artifact_ids ?? []
      } : {})
    });
  };

  useEffect(() => {
    setDraft((current) => {
      if (current.storageKey === storageKey && (
        initialParentKey.length === 0 || current.parent_todo_id === initialParentKey
      )) {
        return current;
      }
      return initialProjectTodoCreateDraft(storageKey, initialParentKey);
    });
  }, [initialParentKey, storageKey]);

  useEffect(() => {
    onPendingChange(createMutation.isPending);
  }, [createMutation.isPending, onPendingChange]);

  useEffect(() => () => onPendingChange(false), [onPendingChange]);

  return (
    <form
      className={`project-todo-form project-todo-form-${mode}`}
      onSubmit={(event) => {
        event.preventDefault();
        if (title.trim().length > 0 && !createMutation.isPending) {
          const action = projectTodoCreateAction(
            (event.nativeEvent as SubmitEvent).submitter?.getAttribute("data-create-action")
          );
          createMutation.mutate(action);
        }
      }}
    >
      <input
        ref={titleInputRef}
        value={title}
        onChange={(event) => updateDraft({ title: event.target.value })}
        placeholder={mode === "quick" ? t("projectTodo.create.titlePlaceholder.quick") : t("projectTodo.create.titlePlaceholder.full")}
        maxLength={255}
      />
      {mode === "quick" && (
        <label className="project-todo-quick-type">
          <span>{t("projectTodo.create.type")}</span>
          <select
            value={selectedTodoTypeId}
            disabled={todoTypesQuery.isLoading}
            onChange={(event) => updateTodoType(event.target.value)}
          >
            {todoTypes.length === 0 && <option value="default">{t("projectTodo.create.default")}</option>}
            {todoTypes.map((todoType) => (
              <option key={`${todoType.scope}:${todoType.id}`} value={todoType.id}>
                {projectTodoTypeLabel(todoType, t)}
              </option>
            ))}
          </select>
        </label>
      )}
      <ProjectTodoDescriptionMentionTextarea
        value={description}
        todos={todos}
        onChange={(nextDescription) => updateDraft({ description: nextDescription })}
        placeholder={mode === "quick" ? t("projectTodo.create.descriptionPlaceholder.quick") : t("projectTodo.create.descriptionPlaceholder.full")}
        rows={3}
      />
      <ProjectTodoParentSelector
        todos={todos}
        value={parentTodoId}
        onChange={(nextParentTodoId) => updateDraft({ parent_todo_id: nextParentTodoId })}
      />
      {mode === "full" && (
        <>
          <fieldset className="project-todo-form-schedule">
            <label>
              <span>{t("projectTodo.create.type")}</span>
              <select
                value={selectedTodoTypeId}
                disabled={todoTypesQuery.isLoading}
                onChange={(event) => updateTodoType(event.target.value)}
              >
                {todoTypes.length === 0 && <option value="default">{t("projectTodo.create.default")}</option>}
                {todoTypes.map((todoType) => (
                  <option key={`${todoType.scope}:${todoType.id}`} value={todoType.id}>
                    {projectTodoTypeLabel(todoType, t)}
                  </option>
                ))}
              </select>
            </label>
            <label>
              <span>{t("projectTodo.create.execution")}</span>
              <select
                value={executionKind}
                onChange={(event) => updateDraft({
                  execution_kind: event.target.value as ProjectTodoExecutionKind
                })}
              >
                <option value="ONCE">{t("projectTodo.create.execution.once")}</option>
                <option value="PERIODIC">{t("projectTodo.create.execution.periodic")}</option>
              </select>
            </label>
            <label>
              <span>{t("projectTodo.create.terminal")}</span>
              <select
                value={terminalPolicy}
                onChange={(event) => updateDraft({
                  terminal_policy: event.target.value as ProjectTodoTerminalPolicy
                })}
              >
                <option value="NEW_TERMINAL">{t("projectTodo.create.terminal.new")}</option>
                <option value="REUSE_LATEST">{t("projectTodo.create.terminal.reuse")}</option>
              </select>
            </label>
            <label>
              <span>{t("projectTodo.create.trigger")}</span>
              <select
                value={triggerStrategy}
                disabled={executionKind === "ONCE"}
                onChange={(event) => updateDraft({
                  trigger_strategy: event.target.value as ProjectTodoTriggerStrategy
                })}
              >
                <option value="MANUAL">{t("projectTodo.create.trigger.manual")}</option>
                <option value="CRON">{t("projectTodo.create.trigger.cron")}</option>
              </select>
            </label>
            {triggerStrategy === "CRON" && (
              <label className="project-todo-form-cron">
                <span>Cron</span>
                <input
                  value={cronExpression}
                  onChange={(event) => updateDraft({ cron_expression: event.target.value })}
                  placeholder="0 9 * * 1"
                  maxLength={128}
                />
              </label>
            )}
          </fieldset>
        </>
      )}
      {showArtifactSelector && (
        <>
          <ProjectTodoArtifactKindSelector
            artifactPlugins={artifactPlugins}
            selectedKinds={artifactKinds}
            onSelectionChange={(artifactKinds) => updateDraft({ artifact_kinds: artifactKinds })}
          />
          <ProjectTodoInputArtifactIdsField
            clientId={clientId}
            projectPath={projectPath}
            value={inputArtifactIds}
            onChange={(inputArtifactIds) => updateDraft({ input_artifact_ids: inputArtifactIds })}
          />
        </>
      )}
      <ArtifactModelSelectionField
        agent={artifactModelAgent}
        className="project-todo-form-artifact-model"
        value={artifactModelSelection}
        onChange={(nextSelection) => updateDraft({ artifact_model_selection: nextSelection })}
      />
      <div className="project-todo-form-actions">
        <button
          type="submit"
          className="project-todo-create-action-button"
          data-create-action="add"
          aria-label={t("projectTodo.create.addTodo")}
          title={t("projectTodo.create.addTodo")}
          disabled={title.trim().length === 0 || createMutation.isPending}
        >
          <AddIcon />
          <span className="visually-hidden">{t("projectTodo.create.add")}</span>
        </button>
        {directDispatch && (
          <button
            type="submit"
            className="project-todo-create-action-button direct-dispatch"
            data-create-action="direct-dispatch"
            aria-label={t("projectTodo.create.addAndDirectDispatchTodo")}
            title={t("projectTodo.create.addAndDirectDispatchTodo")}
            disabled={title.trim().length === 0 || createMutation.isPending}
          >
            <DirectDispatchIcon />
            <span className="visually-hidden">{t("projectTodo.create.addAndDirectDispatch")}</span>
          </button>
        )}
        <button
          type="submit"
          className="project-todo-create-action-button dispatch"
          data-create-action="dispatch"
          aria-label={t("projectTodo.create.addAndDispatchTodo")}
          title={t("projectTodo.create.addAndDispatchTodo")}
          disabled={title.trim().length === 0 || createMutation.isPending}
        >
          <AddDispatchIcon />
          <span className="visually-hidden">{t("projectTodo.create.addAndDispatch")}</span>
        </button>
      </div>
    </form>
  );
}

function projectTodoCreateAction(value: string | null | undefined): ProjectTodoCreateAction {
  return value === "dispatch" || value === "direct-dispatch" ? value : "add";
}

function initialProjectTodoCreateDraft(storageKey: string, parentTodoId: string): StoredProjectTodoCreateDraft {
  if (parentTodoId.length === 0) {
    return {
      storageKey,
      ...readProjectTodoCreateDraft(storageKey)
    };
  }
  return {
    storageKey,
    ...emptyProjectTodoCreateDraft(),
    parent_todo_id: parentTodoId
  };
}

function emptyProjectTodoCreateDraft(): ProjectTodoCreateDraft {
  return {
    title: "",
    description: "",
    parent_todo_id: "",
    todo_type_id: "default",
    execution_kind: "ONCE",
    terminal_policy: "NEW_TERMINAL",
    trigger_strategy: "MANUAL",
    cron_expression: "",
    artifact_kinds: [],
    input_artifact_ids: [],
    artifact_model_selection: null
  };
}

function projectTodoCreateInput({
  title,
  description,
  parentTodoId,
  todoTypeId,
  executionKind,
  terminalPolicy,
  triggerStrategy,
  cronExpression,
  artifactKinds,
  todoTypeArtifactKinds,
  inputArtifactIds,
  todoTypeInputArtifactIds,
  artifactModelAgent,
  artifactModelSelection
}: {
  title: string;
  description: string;
  parentTodoId: string;
  todoTypeId: string;
  executionKind: ProjectTodoExecutionKind;
  terminalPolicy: ProjectTodoTerminalPolicy;
  triggerStrategy: ProjectTodoTriggerStrategy;
  cronExpression: string;
  artifactKinds: string[];
  todoTypeArtifactKinds: string[];
  inputArtifactIds: string[];
  todoTypeInputArtifactIds: string[];
  artifactModelAgent: AgentLaunchKind | null;
  artifactModelSelection: AgentModelSelection | null;
}): ProjectTodoCreateInput {
  const input: ProjectTodoCreateInput = {
    title: title.trim(),
    description: description.trim() || null
  };
  if (parentTodoId) {
    input.parent_todo_id = parentTodoId;
  }
  if (todoTypeId !== "default") {
    input.todo_type_id = todoTypeId;
  }
  if (artifactKinds.length > 0 || todoTypeArtifactKinds.length > 0) {
    input.artifact_kinds = artifactKinds;
  }
  if (inputArtifactIds.length > 0 || todoTypeInputArtifactIds.length > 0) {
    input.input_artifact_ids = inputArtifactIds;
  }
  if (executionKind !== "ONCE") {
    input.execution_kind = executionKind;
  }
  if (terminalPolicy !== "NEW_TERMINAL") {
    input.terminal_policy = terminalPolicy;
  }
  if (triggerStrategy !== "MANUAL") {
    input.trigger_strategy = triggerStrategy;
    input.cron_expression = triggerStrategy === "CRON" ? cronExpression.trim() : null;
  }
  const effectiveArtifactModelSelection = artifactModelSelection ?? artifactModelDefaultSelection(artifactModelAgent);
  if (effectiveArtifactModelSelection !== null) {
    input.artifact_model_selection = effectiveArtifactModelSelection;
  }
  return input;
}

function AddIcon() {
  return (
    <svg
      aria-hidden="true"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d="M12 5v14" />
      <path d="M5 12h14" />
    </svg>
  );
}

function DirectDispatchIcon() {
  return (
    <svg
      aria-hidden="true"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d="M5 12h9" />
      <path d="m11 6 6 6-6 6" />
      <path d="M18 5v14" />
    </svg>
  );
}

function AddDispatchIcon() {
  return (
    <svg
      aria-hidden="true"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d="M5 12h11" />
      <path d="m12 6 6 6-6 6" />
      <path d="M6 5v6" />
      <path d="M3 8h6" />
    </svg>
  );
}
