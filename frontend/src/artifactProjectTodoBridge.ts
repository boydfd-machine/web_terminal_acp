import type {
  AgentModelSelection,
  ProjectTodoExecutionKind,
  ProjectTodoReviewStrategy,
  ProjectTodoStatus,
  ProjectTodoTerminalPolicy,
  ProjectTodoTriggerStrategy
} from "./types";

export const ARTIFACT_PROJECT_TODO_CREATE_MESSAGE = "web-terminal.project-todo.create";
export const ARTIFACT_PROJECT_TODO_CREATED_MESSAGE = "web-terminal.project-todo.created";
export const ARTIFACT_PROJECT_TODO_CREATE_FAILED_MESSAGE = "web-terminal.project-todo.create_failed";
export const ARTIFACT_PROJECT_TODO_MESSAGE_VERSION = 1;

export type ArtifactProjectTodoCreateInput = {
  title: string;
  description?: string | null;
  status?: Extract<ProjectTodoStatus, "TODO" | "BLOCKED">;
  todo_type_id?: string;
  artifact_kinds?: string[];
  input_artifact_ids?: string[];
  execution_kind?: ProjectTodoExecutionKind;
  terminal_policy?: ProjectTodoTerminalPolicy;
  trigger_strategy?: ProjectTodoTriggerStrategy;
  cron_expression?: string | null;
  schedule_enabled?: boolean;
  review_strategy?: ProjectTodoReviewStrategy;
  review_agent?: string | null;
  review_agent_profile_id?: string | null;
  artifact_model_selection?: AgentModelSelection | null;
};

export type ArtifactProjectTodoCreateMessage = {
  type: typeof ARTIFACT_PROJECT_TODO_CREATE_MESSAGE;
  version: typeof ARTIFACT_PROJECT_TODO_MESSAGE_VERSION;
  request_id?: string;
  card: ArtifactProjectTodoCreateInput;
};

export type ArtifactProjectTodoCreatedMessage = {
  type: typeof ARTIFACT_PROJECT_TODO_CREATED_MESSAGE;
  version: typeof ARTIFACT_PROJECT_TODO_MESSAGE_VERSION;
  request_id?: string;
  todo: {
    id: string;
    project_path: string;
    title: string;
  };
};

export type ArtifactProjectTodoCreateFailedMessage = {
  type: typeof ARTIFACT_PROJECT_TODO_CREATE_FAILED_MESSAGE;
  version: typeof ARTIFACT_PROJECT_TODO_MESSAGE_VERSION;
  request_id?: string;
  detail: string;
};

export type ArtifactProjectTodoResponseMessage =
  | ArtifactProjectTodoCreatedMessage
  | ArtifactProjectTodoCreateFailedMessage;

const TODO_STATUSES = new Set(["TODO", "BLOCKED"]);
const EXECUTION_KINDS = new Set(["ONCE", "PERIODIC"]);
const TERMINAL_POLICIES = new Set(["NEW_TERMINAL", "REUSE_LATEST"]);
const TRIGGER_STRATEGIES = new Set(["MANUAL", "CRON"]);
const REVIEW_STRATEGIES = new Set(["LOCAL_CARD", "GITEA", "GITHUB"]);
const TODO_TYPE_PATTERN = /^[A-Za-z0-9_.-]+$/;
const PROJECT_TODO_DESCRIPTION_MAX_LENGTH = 262144;

export function isArtifactProjectTodoCreateMessage(value: unknown): boolean {
  return isRecord(value)
    && value.type === ARTIFACT_PROJECT_TODO_CREATE_MESSAGE
    && value.version === ARTIFACT_PROJECT_TODO_MESSAGE_VERSION;
}

export function normalizeArtifactProjectTodoCreateMessage(
  value: unknown
): ArtifactProjectTodoCreateMessage | null {
  if (!isArtifactProjectTodoCreateMessage(value) || !isRecord(value)) {
    return null;
  }
  const requestId = optionalString(value.request_id, 128);
  if (requestId === undefined && "request_id" in value) {
    return null;
  }
  const card = normalizeArtifactProjectTodoCard(value.card);
  if (card === null) {
    return null;
  }
  return {
    type: ARTIFACT_PROJECT_TODO_CREATE_MESSAGE,
    version: ARTIFACT_PROJECT_TODO_MESSAGE_VERSION,
    ...(requestId === undefined ? {} : { request_id: requestId }),
    card
  };
}

export function artifactProjectTodoCreatedMessage(
  message: ArtifactProjectTodoCreateMessage,
  todo: { id: string; project_path: string; title: string }
): ArtifactProjectTodoCreatedMessage {
  return {
    type: ARTIFACT_PROJECT_TODO_CREATED_MESSAGE,
    version: ARTIFACT_PROJECT_TODO_MESSAGE_VERSION,
    ...(message.request_id === undefined ? {} : { request_id: message.request_id }),
    todo: {
      id: todo.id,
      project_path: todo.project_path,
      title: todo.title
    }
  };
}

export function artifactProjectTodoCreateFailedMessage(
  message: Pick<ArtifactProjectTodoCreateMessage, "request_id"> | null,
  detail: string
): ArtifactProjectTodoCreateFailedMessage {
  return {
    type: ARTIFACT_PROJECT_TODO_CREATE_FAILED_MESSAGE,
    version: ARTIFACT_PROJECT_TODO_MESSAGE_VERSION,
    ...(message?.request_id === undefined ? {} : { request_id: message.request_id }),
    detail
  };
}

function normalizeArtifactProjectTodoCard(value: unknown): ArtifactProjectTodoCreateInput | null {
  if (!isRecord(value)) {
    return null;
  }
  const title = requiredString(value.title, 255);
  if (title === null) {
    return null;
  }
  const input: ArtifactProjectTodoCreateInput = { title };
  if (!assignOptionalString(input, value, "description", PROJECT_TODO_DESCRIPTION_MAX_LENGTH, true)) {
    return null;
  }
  if (!assignOptionalEnum(input, value, "status", TODO_STATUSES)) {
    return null;
  }
  if (!assignTodoTypeId(input, value)) {
    return null;
  }
  if (!assignArtifactKinds(input, value)) {
    return null;
  }
  if (!assignStringList(input, value, "input_artifact_ids", 50, 128)) {
    return null;
  }
  if (!assignOptionalEnum(input, value, "execution_kind", EXECUTION_KINDS)) {
    return null;
  }
  if (!assignOptionalEnum(input, value, "terminal_policy", TERMINAL_POLICIES)) {
    return null;
  }
  if (!assignOptionalEnum(input, value, "trigger_strategy", TRIGGER_STRATEGIES)) {
    return null;
  }
  if (!assignOptionalString(input, value, "cron_expression", 128, true)) {
    return null;
  }
  if (!assignOptionalBoolean(input, value, "schedule_enabled")) {
    return null;
  }
  if (!assignOptionalEnum(input, value, "review_strategy", REVIEW_STRATEGIES)) {
    return null;
  }
  if (!assignOptionalString(input, value, "review_agent", 64, true)) {
    return null;
  }
  if (!assignOptionalString(input, value, "review_agent_profile_id", 128, true)) {
    return null;
  }
  if (!assignArtifactModelSelection(input, value)) {
    return null;
  }
  return input;
}

function assignOptionalString(
  target: ArtifactProjectTodoCreateInput,
  source: Record<string, unknown>,
  key: keyof ArtifactProjectTodoCreateInput,
  maxLength: number,
  nullable: boolean
): boolean {
  if (!(key in source)) {
    return true;
  }
  if (source[key] === null && nullable) {
    target[key] = null as never;
    return true;
  }
  const value = optionalString(source[key], maxLength);
  if (value === undefined) {
    return false;
  }
  target[key] = value as never;
  return true;
}

function assignOptionalEnum(
  target: ArtifactProjectTodoCreateInput,
  source: Record<string, unknown>,
  key: keyof ArtifactProjectTodoCreateInput,
  allowed: Set<string>
): boolean {
  if (!(key in source)) {
    return true;
  }
  if (typeof source[key] !== "string" || !allowed.has(source[key])) {
    return false;
  }
  target[key] = source[key] as never;
  return true;
}

function assignOptionalBoolean(
  target: ArtifactProjectTodoCreateInput,
  source: Record<string, unknown>,
  key: keyof ArtifactProjectTodoCreateInput
): boolean {
  if (!(key in source)) {
    return true;
  }
  if (typeof source[key] !== "boolean") {
    return false;
  }
  target[key] = source[key] as never;
  return true;
}

function assignTodoTypeId(target: ArtifactProjectTodoCreateInput, source: Record<string, unknown>): boolean {
  if (!("todo_type_id" in source)) {
    return true;
  }
  const value = optionalString(source.todo_type_id, 64);
  if (value === undefined || !TODO_TYPE_PATTERN.test(value)) {
    return false;
  }
  target.todo_type_id = value;
  return true;
}

function assignArtifactKinds(target: ArtifactProjectTodoCreateInput, source: Record<string, unknown>): boolean {
  if (!("artifact_kinds" in source)) {
    return true;
  }
  if (!Array.isArray(source.artifact_kinds) || source.artifact_kinds.length > 20) {
    return false;
  }
  const values: string[] = [];
  for (const item of source.artifact_kinds) {
    const value = optionalString(item, 64);
    if (value === undefined || value.length === 0) {
      return false;
    }
    values.push(value);
  }
  target.artifact_kinds = values;
  return true;
}

function assignStringList(
  target: ArtifactProjectTodoCreateInput,
  source: Record<string, unknown>,
  key: keyof ArtifactProjectTodoCreateInput,
  maxItems: number,
  maxLength: number
): boolean {
  if (!(key in source)) {
    return true;
  }
  const rawValues = source[key];
  if (!Array.isArray(rawValues) || rawValues.length > maxItems) {
    return false;
  }
  const values: string[] = [];
  for (const item of rawValues) {
    const value = optionalString(item, maxLength);
    if (value === undefined || value.length === 0) {
      return false;
    }
    values.push(value);
  }
  target[key] = values as never;
  return true;
}

function assignArtifactModelSelection(target: ArtifactProjectTodoCreateInput, source: Record<string, unknown>): boolean {
  if (!("artifact_model_selection" in source)) {
    return true;
  }
  if (source.artifact_model_selection === null) {
    target.artifact_model_selection = null;
    return true;
  }
  if (!isAgentModelSelection(source.artifact_model_selection)) {
    return false;
  }
  target.artifact_model_selection = source.artifact_model_selection;
  return true;
}

function isAgentModelSelection(value: unknown): value is AgentModelSelection {
  if (!isRecord(value)) {
    return false;
  }
  return typeof value.preset_id === "string"
    && value.preset_id.trim().length > 0
    && optionalString(value.preset_id, 128) !== undefined;
}

function requiredString(value: unknown, maxLength: number): string | null {
  const text = optionalString(value, maxLength);
  return text === undefined || text.length === 0 ? null : text;
}

function optionalString(value: unknown, maxLength: number): string | undefined {
  if (typeof value !== "string") {
    return undefined;
  }
  const text = value.trim();
  return text.length <= maxLength ? text : undefined;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}
