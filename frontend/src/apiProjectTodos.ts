import type {
  AgentLaunchConfig,
  AgentModelSelection,
  ProjectTodo,
  ProjectTodoDispatchMode,
  ProjectTodoExecutionKind,
  ProjectTodoHistory,
  ProjectTodoList,
  ProjectTodoSearchResponse,
  ProjectTodoReviewRunList,
  ProjectTodoReviewStatus,
  ProjectTodoReviewStrategy,
  ProjectTodoReviewTarget,
  ProjectTodoReviewTargetList,
  ProjectTodoStatus,
  ProjectTodoTerminalPolicy,
  ProjectTodoTriggerStrategy,
  ProjectTodoType,
  ProjectTodoTypeList,
  ProjectTodoWorkSnapshotList
} from "./types";
import { pathSegment, request, requestVoid } from "./apiCore";
import { readSummaryOutputLanguage, type SummaryOutputLanguage } from "./userPreferences";

type ProjectTodoDateFilterRequest = {
  range?: string;
  start_date?: string;
  end_date?: string;
};

function projectTodosPath(clientId: string, projectPath: string, dateFilter?: ProjectTodoDateFilterRequest): string {
  const params = new URLSearchParams({ project_path: projectPath });
  if (dateFilter?.range !== undefined) {
    params.set("range", dateFilter.range);
  }
  if (dateFilter?.start_date !== undefined) {
    params.set("start_date", dateFilter.start_date);
  }
  if (dateFilter?.end_date !== undefined) {
    params.set("end_date", dateFilter.end_date);
  }
  return `/api/clients/${pathSegment(clientId)}/projects/todos?${params.toString()}`;
}

export function fetchProjectTodos(
  clientId: string,
  projectPath: string,
  dateFilter?: ProjectTodoDateFilterRequest
): Promise<ProjectTodoList> {
  return request<ProjectTodoList>(projectTodosPath(clientId, projectPath, dateFilter));
}

export function searchProjectTodos(
  clientId: string,
  query: string,
  limit = 25,
  offset = 0,
  projectPath?: string
): Promise<ProjectTodoSearchResponse> {
  const params = new URLSearchParams({
    q: query,
    limit: String(limit),
    offset: String(offset)
  });
  if (projectPath !== undefined) {
    params.set("project_path", projectPath);
  }
  return request<ProjectTodoSearchResponse>(
    `/api/clients/${pathSegment(clientId)}/projects/todos/search?${params.toString()}`
  );
}

export function fetchProjectTodo(clientId: string, projectPath: string, todoId: string): Promise<ProjectTodo> {
  return request<ProjectTodo>(projectTodoPath(clientId, projectPath, todoId));
}

export function fetchProjectTodoHistory(
  clientId: string,
  projectPath: string,
  todoId: string
): Promise<ProjectTodoHistory> {
  return request<ProjectTodoHistory>(projectTodoPath(clientId, projectPath, todoId, "/history"));
}

function projectTodoTypesPath(clientId: string, projectPath: string): string {
  const params = new URLSearchParams({ project_path: projectPath });
  return `/api/clients/${pathSegment(clientId)}/projects/todo-types?${params.toString()}`;
}

export function fetchProjectTodoTypes(clientId: string, projectPath: string): Promise<ProjectTodoTypeList> {
  return request<ProjectTodoTypeList>(projectTodoTypesPath(clientId, projectPath));
}

export function upsertSystemProjectTodoType(
  clientId: string,
  input: {
    id: string;
    name: string;
    description?: string | null;
    agent?: string | null;
    agent_profile_id?: string | null;
    artifact_kinds?: string[];
    input_artifact_ids?: string[];
    dispatch_template?: string | null;
  }
): Promise<ProjectTodoType> {
  return request<ProjectTodoType>(`/api/clients/${pathSegment(clientId)}/projects/todo-types/system`, {
    method: "POST",
    body: JSON.stringify({
      id: input.id,
      name: input.name,
      description: input.description ?? null,
      agent: input.agent ?? null,
      agent_profile_id: input.agent_profile_id ?? null,
      artifact_kinds: input.artifact_kinds ?? [],
      input_artifact_ids: input.input_artifact_ids ?? [],
      dispatch_template: input.dispatch_template ?? null
    })
  });
}

export function updateSystemProjectTodoType(
  clientId: string,
  todoTypeId: string,
  input: {
    name?: string;
    description?: string | null;
    agent?: string | null;
    agent_profile_id?: string | null;
    artifact_kinds?: string[];
    input_artifact_ids?: string[];
    dispatch_template?: string | null;
  }
): Promise<ProjectTodoType> {
  return request<ProjectTodoType>(
    `/api/clients/${pathSegment(clientId)}/projects/todo-types/system/${pathSegment(todoTypeId)}`,
    {
      method: "PATCH",
      body: JSON.stringify(input)
    }
  );
}

export function deleteSystemProjectTodoType(clientId: string, todoTypeId: string): Promise<void> {
  return requestVoid(
    `/api/clients/${pathSegment(clientId)}/projects/todo-types/system/${pathSegment(todoTypeId)}`,
    { method: "DELETE" }
  );
}

function projectTodoPath(clientId: string, projectPath: string, todoId: string, suffix = ""): string {
  const params = new URLSearchParams({ project_path: projectPath });
  return `/api/clients/${pathSegment(clientId)}/projects/todos/${pathSegment(todoId)}${suffix}?${params.toString()}`;
}

export function fetchProjectTodoWorkSnapshots(
  clientId: string,
  projectPath: string,
  todoId: string
): Promise<ProjectTodoWorkSnapshotList> {
  return request<ProjectTodoWorkSnapshotList>(projectTodoPath(clientId, projectPath, todoId, "/work-snapshots"));
}

export function fetchProjectTodoReviewTargets(
  clientId: string,
  projectPath: string,
  todoId: string
): Promise<ProjectTodoReviewTargetList> {
  return request<ProjectTodoReviewTargetList>(projectTodoPath(clientId, projectPath, todoId, "/review-targets"));
}

export function createProjectTodoReviewTarget(
  clientId: string,
  projectPath: string,
  todoId: string
): Promise<ProjectTodoReviewTarget> {
  return request<ProjectTodoReviewTarget>(projectTodoPath(clientId, projectPath, todoId, "/review-targets"), {
    method: "POST"
  });
}

export function fetchProjectTodoReviewRuns(
  clientId: string,
  projectPath: string,
  todoId: string
): Promise<ProjectTodoReviewRunList> {
  return request<ProjectTodoReviewRunList>(projectTodoPath(clientId, projectPath, todoId, "/review-runs"));
}

export function createProjectTodo(
  clientId: string,
  projectPath: string,
  input: {
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
    schedule_enabled?: boolean;
    review_strategy?: ProjectTodoReviewStrategy;
    review_agent?: string | null;
    review_agent_profile_id?: string | null;
    artifact_model_selection?: AgentModelSelection | null;
  }
): Promise<ProjectTodo> {
  const body: Record<string, unknown> = {
    title: input.title,
    description: input.description ?? null,
    parent_todo_id: input.parent_todo_id ?? null,
    todo_type_id: input.todo_type_id ?? "default",
    status: input.status ?? "TODO",
    execution_kind: input.execution_kind ?? "ONCE",
    terminal_policy: input.terminal_policy ?? "NEW_TERMINAL",
    trigger_strategy: input.trigger_strategy ?? "MANUAL",
    cron_expression: input.cron_expression ?? null,
    schedule_enabled: input.schedule_enabled ?? null,
    review_strategy: input.review_strategy ?? "LOCAL_CARD",
    review_agent: input.review_agent ?? null,
    review_agent_profile_id: input.review_agent_profile_id ?? null
  };
  if (input.artifact_kinds !== undefined) {
    body.artifact_kinds = input.artifact_kinds;
  }
  if (input.input_artifact_ids !== undefined) {
    body.input_artifact_ids = input.input_artifact_ids;
  }
  if (input.artifact_model_selection !== undefined) {
    body.artifact_model_selection = input.artifact_model_selection;
  }
  return request<ProjectTodo>(projectTodosPath(clientId, projectPath), {
    method: "POST",
    body: JSON.stringify(body)
  });
}

export function appendProjectTodoAnnotation(
  clientId: string,
  projectPath: string,
  todoId: string,
  input: { annotation: string }
): Promise<ProjectTodo> {
  return request<ProjectTodo>(projectTodoPath(clientId, projectPath, todoId, "/annotations"), {
    method: "POST",
    body: JSON.stringify({ annotation: input.annotation })
  });
}

export function createProjectTodoFromPageReviewCard(
  clientId: string,
  projectPath: string,
  input: {
    artifact_id: string;
    card_id: string;
    purpose?: string;
  }
): Promise<ProjectTodo> {
  const params = new URLSearchParams({ project_path: projectPath });
  return request<ProjectTodo>(
    `/api/clients/${pathSegment(clientId)}/projects/todos/from-page-review-card?${params.toString()}`,
    {
      method: "POST",
      body: JSON.stringify({
        artifact_id: input.artifact_id,
        card_id: input.card_id,
        purpose: input.purpose ?? "page_review"
      })
    }
  );
}

export function createProjectTodoFromArtifactCard(
  clientId: string,
  projectPath: string,
  input: {
    artifact_id: string;
    card: Parameters<typeof createProjectTodo>[2];
    purpose?: string;
  }
): Promise<ProjectTodo> {
  const params = new URLSearchParams({ project_path: projectPath });
  return request<ProjectTodo>(
    `/api/clients/${pathSegment(clientId)}/projects/todos/from-artifact-card?${params.toString()}`,
    {
      method: "POST",
      body: JSON.stringify({
        artifact_id: input.artifact_id,
        card: input.card,
        purpose: input.purpose ?? "artifact_card"
      })
    }
  );
}

export function updateProjectTodo(
  clientId: string,
  projectPath: string,
  todoId: string,
  input: {
    title?: string;
    description?: string | null;
    parent_todo_id?: string | null;
    todo_type_id?: string;
    status?: ProjectTodoStatus;
    sort_order?: number;
    artifact_kinds?: string[];
    input_artifact_ids?: string[];
    execution_kind?: ProjectTodoExecutionKind;
    terminal_policy?: ProjectTodoTerminalPolicy;
    trigger_strategy?: ProjectTodoTriggerStrategy;
    cron_expression?: string | null;
    schedule_enabled?: boolean;
    review_strategy?: ProjectTodoReviewStrategy;
    review_status?: ProjectTodoReviewStatus;
    review_agent?: string | null;
    review_agent_profile_id?: string | null;
    review_unseen?: boolean;
    needs_human_review?: boolean;
    review_notes?: string | null;
  }
): Promise<ProjectTodo> {
  const params = new URLSearchParams({ project_path: projectPath });
  return request<ProjectTodo>(
    `/api/clients/${pathSegment(clientId)}/projects/todos/${pathSegment(todoId)}?${params.toString()}`,
    {
      method: "PATCH",
      body: JSON.stringify(input)
    }
  );
}

export function restoreProjectTodoVersion(
  clientId: string,
  projectPath: string,
  todoId: string,
  versionNumber: number
): Promise<ProjectTodo> {
  return request<ProjectTodo>(
    projectTodoPath(clientId, projectPath, todoId, `/versions/${pathSegment(String(versionNumber))}/restore`),
    { method: "POST" }
  );
}

export function moveProjectTodoToProject(
  clientId: string,
  projectPath: string,
  todoId: string,
  targetProjectPath: string
): Promise<ProjectTodo> {
  const params = new URLSearchParams({ project_path: projectPath });
  return request<ProjectTodo>(
    `/api/clients/${pathSegment(clientId)}/projects/todos/${pathSegment(todoId)}/move-project?${params.toString()}`,
    {
      method: "POST",
      body: JSON.stringify({ project_path: targetProjectPath })
    }
  );
}

export function dispatchProjectTodo(
  clientId: string,
  projectPath: string,
  todoId: string,
  input: {
    agent_launch: AgentLaunchConfig;
    dispatch_mode?: ProjectTodoDispatchMode;
    dispatch_after_todo_ids?: string[];
    output_language?: SummaryOutputLanguage | null;
    prompt?: string | null;
    artifact_model_selection?: AgentModelSelection | null;
  }
): Promise<ProjectTodo> {
  const params = new URLSearchParams({ project_path: projectPath });
  return request<ProjectTodo>(
    `/api/clients/${pathSegment(clientId)}/projects/todos/${pathSegment(todoId)}/dispatch?${params.toString()}`,
    {
      method: "POST",
      body: JSON.stringify({
        agent_launch: input.agent_launch,
        dispatch_mode: input.dispatch_mode ?? "submit",
        dispatch_after_todo_ids: input.dispatch_after_todo_ids ?? [],
        output_language: input.output_language ?? readSummaryOutputLanguage(),
        prompt: input.prompt ?? null,
        ...(input.artifact_model_selection !== undefined
          ? { artifact_model_selection: input.artifact_model_selection }
          : {})
      })
    }
  );
}

export function dispatchProjectTodoReview(
  clientId: string,
  projectPath: string,
  todoId: string,
  input: { agent_launch: AgentLaunchConfig; output_language?: SummaryOutputLanguage | null; prompt?: string | null }
): Promise<ProjectTodo> {
  const params = new URLSearchParams({ project_path: projectPath });
  return request<ProjectTodo>(
    `/api/clients/${pathSegment(clientId)}/projects/todos/${pathSegment(todoId)}/review/dispatch?${params.toString()}`,
    {
      method: "POST",
      body: JSON.stringify({
        agent_launch: input.agent_launch,
        output_language: input.output_language ?? readSummaryOutputLanguage(),
        prompt: input.prompt ?? null
      })
    }
  );
}

export function commentProjectTodo(
  clientId: string,
  projectPath: string,
  todoId: string,
  input: { comment: string; artifact_kinds?: string[] }
): Promise<ProjectTodo> {
  const params = new URLSearchParams({ project_path: projectPath });
  const body: Record<string, unknown> = { comment: input.comment };
  if (input.artifact_kinds !== undefined) {
    body.artifact_kinds = input.artifact_kinds;
  }
  return request<ProjectTodo>(
    `/api/clients/${pathSegment(clientId)}/projects/todos/${pathSegment(todoId)}/comment?${params.toString()}`,
    {
      method: "POST",
      body: JSON.stringify(body)
    }
  );
}

export function linkProjectTodoArtifact(
  clientId: string,
  projectPath: string,
  todoId: string,
  input: { artifact_id: string; purpose?: string }
): Promise<ProjectTodo> {
  const params = new URLSearchParams({ project_path: projectPath });
  return request<ProjectTodo>(
    `/api/clients/${pathSegment(clientId)}/projects/todos/${pathSegment(todoId)}/artifacts?${params.toString()}`,
    {
      method: "POST",
      body: JSON.stringify({
        artifact_id: input.artifact_id,
        purpose: input.purpose ?? "review"
      })
    }
  );
}

export function retryProjectTodoArtifact(
  clientId: string,
  projectPath: string,
  todoId: string,
  artifactLinkId: string
): Promise<ProjectTodo> {
  return request<ProjectTodo>(
    projectTodoPath(clientId, projectPath, todoId, `/artifacts/${pathSegment(artifactLinkId)}/retry`),
    { method: "POST" }
  );
}

export async function deleteProjectTodo(clientId: string, projectPath: string, todoId: string): Promise<void> {
  const params = new URLSearchParams({ project_path: projectPath });
  await requestVoid(
    `/api/clients/${pathSegment(clientId)}/projects/todos/${pathSegment(todoId)}?${params.toString()}`,
    { method: "DELETE" }
  );
}
