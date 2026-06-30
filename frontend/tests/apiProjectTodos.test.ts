import { afterEach, describe, expect, it, vi } from "vitest";

import {
  createProjectTodoFromArtifactCard,
  createProjectTodoFromPageReviewCard,
  createProjectTodo,
  deleteProjectTodo,
  deleteProjectTodoAttachment,
  deleteSystemProjectTodoType,
  downloadProjectTodoAttachment,
  commentProjectTodo,
  dispatchProjectTodo,
  dispatchProjectTodoReview,
  fetchProjectTodo,
  fetchProjectTodoTypes,
  fetchProjectTodos,
  moveProjectTodoToProject,
  uploadProjectTodoAttachmentFile,
  linkProjectTodoArtifact,
  retryProjectTodoArtifact,
  searchProjectTodos,
  updateSystemProjectTodoType,
  upsertSystemProjectTodoType,
  updateProjectTodo
} from "../src/api";

afterEach(() => {
  vi.restoreAllMocks();
  window.localStorage.clear();
});

function jsonResponse(body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status: 200,
    headers: { "Content-Type": "application/json" }
  });
}

function requestUrl(input: RequestInfo | URL): URL {
  return new URL(input.toString());
}

function latestCall(fetchMock: { mock: { calls: Parameters<typeof fetch>[] } }) {
  const call = fetchMock.mock.calls.at(-1);
  if (call === undefined) {
    throw new Error("fetch was not called");
  }
  return call;
}

describe("project todo api requests", () => {
  it("builds project todo requests", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(jsonResponse({ todos: [] }));

    await fetchProjectTodos("client-1", "/workspace/project");
    let call = latestCall(fetchMock);
    let url = requestUrl(call[0]);
    expect(url.pathname).toBe("/api/clients/client-1/projects/todos");
    expect(url.searchParams.get("project_path")).toBe("/workspace/project");

    fetchMock.mockResolvedValueOnce(jsonResponse({ todos: [] }));
    await fetchProjectTodos("client-1", "/workspace/project", {
      range: "custom",
      start_date: "2026-06-01",
      end_date: "2026-06-03"
    });
    call = latestCall(fetchMock);
    url = requestUrl(call[0]);
    expect(url.pathname).toBe("/api/clients/client-1/projects/todos");
    expect(url.searchParams.get("project_path")).toBe("/workspace/project");
    expect(url.searchParams.get("range")).toBe("custom");
    expect(url.searchParams.get("start_date")).toBe("2026-06-01");
    expect(url.searchParams.get("end_date")).toBe("2026-06-03");

    fetchMock.mockResolvedValueOnce(jsonResponse({ query: "llama", results: [] }));
    await searchProjectTodos("client-1", "llama", 10, 20, "/workspace/project");
    call = latestCall(fetchMock);
    url = requestUrl(call[0]);
    expect(url.pathname).toBe("/api/clients/client-1/projects/todos/search");
    expect(url.searchParams.get("q")).toBe("llama");
    expect(url.searchParams.get("limit")).toBe("10");
    expect(url.searchParams.get("offset")).toBe("20");
    expect(url.searchParams.get("project_path")).toBe("/workspace/project");

    fetchMock.mockResolvedValueOnce(jsonResponse({ id: "todo-1" }));
    await fetchProjectTodo("client-1", "/workspace/project", "todo-1");
    call = latestCall(fetchMock);
    url = requestUrl(call[0]);
    expect(url.pathname).toBe("/api/clients/client-1/projects/todos/todo-1");
    expect(url.searchParams.get("project_path")).toBe("/workspace/project");

    fetchMock.mockResolvedValueOnce(jsonResponse({ id: "todo-1" }));
    await createProjectTodo("client-1", "/workspace/project", {
      title: "Follow up",
      description: "Blocked by dependency",
      parent_todo_id: "todo-parent",
      status: "BLOCKED",
      input_artifact_ids: ["artifact-current"],
      artifact_model_selection: {
        preset_id: "openai-artifacts",
        model: "gpt-5-codex",
        codex_model_reasoning_effort: "high"
      }
    });
    call = latestCall(fetchMock);
    url = requestUrl(call[0]);
    expect(url.pathname).toBe("/api/clients/client-1/projects/todos");
    expect(call[1]?.method).toBe("POST");
    expect(JSON.parse(String(call[1]?.body))).toEqual({
      title: "Follow up",
      description: "Blocked by dependency",
      parent_todo_id: "todo-parent",
      todo_type_id: "default",
      status: "BLOCKED",
      execution_kind: "ONCE",
      terminal_policy: "NEW_TERMINAL",
      trigger_strategy: "MANUAL",
      cron_expression: null,
      schedule_enabled: null,
      review_strategy: "LOCAL_CARD",
      review_agent: null,
      review_agent_profile_id: null,
      input_artifact_ids: ["artifact-current"],
      artifact_model_selection: {
        preset_id: "openai-artifacts",
        model: "gpt-5-codex",
        codex_model_reasoning_effort: "high"
      }
    });

    fetchMock.mockResolvedValueOnce(jsonResponse({ id: "todo-1" }));
    await createProjectTodo("client-1", "/workspace/project", {
      title: "Trace follow up",
      parent_todo_id: null,
      todo_type_id: "research",
      artifact_kinds: ["agent_trace_graph"],
      input_artifact_ids: ["artifact-input"]
    });
    call = latestCall(fetchMock);
    expect(JSON.parse(String(call[1]?.body))).toMatchObject({
      title: "Trace follow up",
      todo_type_id: "research",
      artifact_kinds: ["agent_trace_graph"],
      input_artifact_ids: ["artifact-input"]
    });

    fetchMock.mockResolvedValueOnce(jsonResponse({ id: "todo-1" }));
    await updateProjectTodo("client-1", "/workspace/project", "todo-1", {
      description: null,
      parent_todo_id: "todo-parent",
      status: "AWAITING_REVIEW",
      review_unseen: false
    });
    call = latestCall(fetchMock);
    url = requestUrl(call[0]);
    expect(url.pathname).toBe("/api/clients/client-1/projects/todos/todo-1");
    expect(call[1]?.method).toBe("PATCH");
    expect(JSON.parse(String(call[1]?.body))).toEqual({
      description: null,
      parent_todo_id: "todo-parent",
      status: "AWAITING_REVIEW",
      review_unseen: false
    });

    fetchMock.mockResolvedValueOnce(jsonResponse({ id: "todo-1" }));
    await updateProjectTodo("client-1", "/workspace/project", "todo-1", {
      execution_kind: "PERIODIC",
      terminal_policy: "REUSE_LATEST",
      trigger_strategy: "CRON",
      cron_expression: "0 9 * * 1",
      schedule_enabled: false
    });
    call = latestCall(fetchMock);
    url = requestUrl(call[0]);
    expect(url.pathname).toBe("/api/clients/client-1/projects/todos/todo-1");
    expect(call[1]?.method).toBe("PATCH");
    expect(JSON.parse(String(call[1]?.body))).toEqual({
      execution_kind: "PERIODIC",
      terminal_policy: "REUSE_LATEST",
      trigger_strategy: "CRON",
      cron_expression: "0 9 * * 1",
      schedule_enabled: false
    });

    fetchMock.mockResolvedValueOnce(jsonResponse({ id: "todo-1" }));
    await moveProjectTodoToProject("client-1", "/workspace/project", "todo-1", "/workspace/target");
    call = latestCall(fetchMock);
    url = requestUrl(call[0]);
    expect(url.pathname).toBe("/api/clients/client-1/projects/todos/todo-1/move-project");
    expect(url.searchParams.get("project_path")).toBe("/workspace/project");
    expect(call[1]?.method).toBe("POST");
    expect(JSON.parse(String(call[1]?.body))).toEqual({
      project_path: "/workspace/target"
    });

    fetchMock.mockResolvedValueOnce(jsonResponse({ id: "todo-1" }));
    window.localStorage.setItem("web-terminal-acp:summary-output-language", "English");
    await dispatchProjectTodo("client-1", "/workspace/project", "todo-1", {
      agent_launch: { agent: "codex", command: "codex", config: null, profile_id: null },
      artifact_model_selection: {
        preset_id: "openai-dispatch-artifacts",
        model: "gpt-5-codex",
        codex_plan_mode_reasoning_effort: "xhigh"
      }
    });
    call = latestCall(fetchMock);
    url = requestUrl(call[0]);
    expect(url.pathname).toBe("/api/clients/client-1/projects/todos/todo-1/dispatch");
    expect(call[1]?.method).toBe("POST");
    expect(JSON.parse(String(call[1]?.body))).toEqual({
      agent_launch: { agent: "codex", command: "codex", config: null, profile_id: null },
      dispatch_mode: "submit",
      dispatch_after_todo_ids: [],
      output_language: "English",
      prompt: null,
      artifact_model_selection: {
        preset_id: "openai-dispatch-artifacts",
        model: "gpt-5-codex",
        codex_plan_mode_reasoning_effort: "xhigh"
      }
    });

    fetchMock.mockResolvedValueOnce(jsonResponse({ id: "todo-1" }));
    await dispatchProjectTodo("client-1", "/workspace/project", "todo-1", {
      agent_launch: { agent: "codex", command: "codex", config: null, profile_id: null },
      dispatch_mode: "compose",
      output_language: "中文"
    });
    call = latestCall(fetchMock);
    url = requestUrl(call[0]);
    expect(url.pathname).toBe("/api/clients/client-1/projects/todos/todo-1/dispatch");
    expect(JSON.parse(String(call[1]?.body))).toEqual({
      agent_launch: { agent: "codex", command: "codex", config: null, profile_id: null },
      dispatch_mode: "compose",
      dispatch_after_todo_ids: [],
      output_language: "中文",
      prompt: null
    });

    fetchMock.mockResolvedValueOnce(jsonResponse({ id: "todo-1" }));
    await dispatchProjectTodoReview("client-1", "/workspace/project", "todo-1", {
      agent_launch: { agent: "codex", command: "codex", config: null, profile_id: null }
    });
    call = latestCall(fetchMock);
    url = requestUrl(call[0]);
    expect(url.pathname).toBe("/api/clients/client-1/projects/todos/todo-1/review/dispatch");
    expect(call[1]?.method).toBe("POST");
    expect(JSON.parse(String(call[1]?.body))).toEqual({
      agent_launch: { agent: "codex", command: "codex", config: null, profile_id: null },
      output_language: "English",
      prompt: null
    });

    fetchMock.mockResolvedValueOnce(jsonResponse({ id: "todo-1" }));
    await commentProjectTodo("client-1", "/workspace/project", "todo-1", {
      comment: "Please check logs"
    });
    call = latestCall(fetchMock);
    url = requestUrl(call[0]);
    expect(url.pathname).toBe("/api/clients/client-1/projects/todos/todo-1/comment");
    expect(call[1]?.method).toBe("POST");
    expect(JSON.parse(String(call[1]?.body))).toEqual({
      comment: "Please check logs"
    });

    fetchMock.mockResolvedValueOnce(jsonResponse({ id: "todo-1" }));
    await commentProjectTodo("client-1", "/workspace/project", "todo-1", {
      comment: "Generate a follow-up artifact",
      artifact_kinds: ["agent_trace_graph"]
    });
    call = latestCall(fetchMock);
    expect(JSON.parse(String(call[1]?.body))).toEqual({
      comment: "Generate a follow-up artifact",
      artifact_kinds: ["agent_trace_graph"]
    });

    fetchMock.mockResolvedValueOnce(jsonResponse({ id: "todo-1" }));
    await linkProjectTodoArtifact("client-1", "/workspace/project", "todo-1", {
      artifact_id: "artifact-1"
    });
    call = latestCall(fetchMock);
    url = requestUrl(call[0]);
    expect(url.pathname).toBe("/api/clients/client-1/projects/todos/todo-1/artifacts");
    expect(call[1]?.method).toBe("POST");
    expect(JSON.parse(String(call[1]?.body))).toEqual({
      artifact_id: "artifact-1",
      purpose: "review"
    });

    fetchMock.mockResolvedValueOnce(jsonResponse({ id: "todo-2" }));
    await createProjectTodoFromPageReviewCard("client-1", "/workspace/project", {
      artifact_id: "artifact-1",
      card_id: "PRC-001"
    });
    call = latestCall(fetchMock);
    url = requestUrl(call[0]);
    expect(url.pathname).toBe("/api/clients/client-1/projects/todos/from-page-review-card");
    expect(call[1]?.method).toBe("POST");
    expect(JSON.parse(String(call[1]?.body))).toEqual({
      artifact_id: "artifact-1",
      card_id: "PRC-001",
      purpose: "page_review"
    });

    fetchMock.mockResolvedValueOnce(jsonResponse({ id: "todo-1" }));
    await retryProjectTodoArtifact(
      "client-1",
      "/workspace/project",
      "todo-1",
      "todo-artifact-link-1"
    );
    call = latestCall(fetchMock);
    url = requestUrl(call[0]);
    expect(url.pathname).toBe("/api/clients/client-1/projects/todos/todo-1/artifacts/todo-artifact-link-1/retry");
    expect(url.searchParams.get("project_path")).toBe("/workspace/project");
    expect(call[1]?.method).toBe("POST");

    fetchMock.mockResolvedValueOnce(new Response(null, { status: 204 }));
    await deleteProjectTodo("client-1", "/workspace/project", "todo-1");
    call = latestCall(fetchMock);
    url = requestUrl(call[0]);
    expect(url.pathname).toBe("/api/clients/client-1/projects/todos/todo-1");
    expect(call[1]?.method).toBe("DELETE");
  });

  it("builds artifact card todo creation requests", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(jsonResponse({ id: "todo-2" }));

    await createProjectTodoFromArtifactCard("client-1", "/workspace/project", {
      artifact_id: "artifact-1",
      card: {
        title: "Created from artifact",
        description: "Use this as the card body",
        todo_type_id: "small-feature",
        artifact_kinds: ["qa_regression_suite"],
        input_artifact_ids: ["artifact-context"],
        artifact_model_selection: {
          preset_id: "anthropic-artifacts",
          claude: { mode: "all", model: "claude-sonnet-4.5" },
          claude_reasoning_effort: "max"
        }
      }
    });

    const url = requestUrl(fetchMock.mock.calls[0][0]);
    expect(url.pathname).toBe("/api/clients/client-1/projects/todos/from-artifact-card");
    expect(url.searchParams.get("project_path")).toBe("/workspace/project");
    expect(fetchMock.mock.calls[0][1]?.method).toBe("POST");
    expect(JSON.parse(String(fetchMock.mock.calls[0][1]?.body))).toEqual({
      artifact_id: "artifact-1",
      card: {
        title: "Created from artifact",
        description: "Use this as the card body",
        todo_type_id: "small-feature",
        artifact_kinds: ["qa_regression_suite"],
        input_artifact_ids: ["artifact-context"],
        artifact_model_selection: {
          preset_id: "anthropic-artifacts",
          claude: { mode: "all", model: "claude-sonnet-4.5" },
          claude_reasoning_effort: "max"
        }
      },
      purpose: "artifact_card"
    });
  });

  it("builds project todo attachment requests and uploads via presigned url", async () => {
    const file = new File(["pdf"], "requirements.pdf", { type: "application/pdf" });
    const fetchMock = vi.spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(jsonResponse({
        attachment: {
          id: "attachment-1",
          todo_id: "todo-1",
          filename: "requirements.pdf",
          content_type: "application/pdf",
          size_bytes: 3,
          status: "pending",
          uploaded_at: null,
          created_at: "2026-06-07T00:00:00Z",
          updated_at: "2026-06-07T00:00:00Z"
        },
        upload_url: "https://objects.example/upload",
        upload_headers: { "Content-Type": "application/pdf" },
        expires_at: "2026-06-07T00:15:00Z"
      }))
      .mockResolvedValueOnce(new Response(null, { status: 200 }))
      .mockResolvedValueOnce(jsonResponse({
        id: "attachment-1",
        todo_id: "todo-1",
        filename: "requirements.pdf",
        content_type: "application/pdf",
        size_bytes: 3,
        status: "uploaded",
        uploaded_at: "2026-06-07T00:01:00Z",
        created_at: "2026-06-07T00:00:00Z",
        updated_at: "2026-06-07T00:01:00Z"
      }))
      .mockResolvedValueOnce(jsonResponse({
        attachment: {
          id: "attachment-1",
          todo_id: "todo-1",
          filename: "requirements.pdf",
          content_type: "application/pdf",
          size_bytes: 3,
          status: "uploaded",
          uploaded_at: "2026-06-07T00:01:00Z",
          created_at: "2026-06-07T00:00:00Z",
          updated_at: "2026-06-07T00:01:00Z"
        },
        download_url: "https://objects.example/download",
        expires_at: "2026-06-07T00:15:00Z"
      }))
      .mockResolvedValueOnce(new Response(null, { status: 204 }));

    const uploaded = await uploadProjectTodoAttachmentFile("client-1", "/workspace/project", "todo-1", file);
    expect(uploaded.status).toBe("uploaded");

    let url = requestUrl(fetchMock.mock.calls[0][0]);
    expect(url.pathname).toBe("/api/clients/client-1/projects/todos/todo-1/attachments");
    expect(url.searchParams.get("project_path")).toBe("/workspace/project");
    expect(fetchMock.mock.calls[0][1]?.method).toBe("POST");
    expect(JSON.parse(String(fetchMock.mock.calls[0][1]?.body))).toEqual({
      filename: "requirements.pdf",
      content_type: "application/pdf",
      size_bytes: 3
    });

    expect(fetchMock.mock.calls[1][0]).toBe("https://objects.example/upload");
    expect(fetchMock.mock.calls[1][1]?.method).toBe("PUT");
    expect(fetchMock.mock.calls[1][1]?.headers).toEqual({ "Content-Type": "application/pdf" });
    expect(fetchMock.mock.calls[1][1]?.body).toBe(file);

    url = requestUrl(fetchMock.mock.calls[2][0]);
    expect(url.pathname).toBe("/api/clients/client-1/projects/todos/todo-1/attachments/attachment-1/complete");
    expect(fetchMock.mock.calls[2][1]?.method).toBe("POST");

    const download = await downloadProjectTodoAttachment("client-1", "/workspace/project", "todo-1", "attachment-1");
    expect(download.download_url).toBe("https://objects.example/download");
    url = requestUrl(fetchMock.mock.calls[3][0]);
    expect(url.pathname).toBe("/api/clients/client-1/projects/todos/todo-1/attachments/attachment-1/download");

    await deleteProjectTodoAttachment("client-1", "/workspace/project", "todo-1", "attachment-1");
    url = requestUrl(fetchMock.mock.calls[4][0]);
    expect(url.pathname).toBe("/api/clients/client-1/projects/todos/todo-1/attachments/attachment-1");
    expect(fetchMock.mock.calls[4][1]?.method).toBe("DELETE");
  });

  it("builds project todo type requests", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(jsonResponse({ todo_types: [] }));

    await fetchProjectTodoTypes("client-1", "/workspace/project");
    let url = requestUrl(fetchMock.mock.calls[0][0]);
    expect(url.pathname).toBe("/api/clients/client-1/projects/todo-types");
    expect(url.searchParams.get("project_path")).toBe("/workspace/project");

    fetchMock.mockResolvedValueOnce(jsonResponse({ id: "research" }));
    await upsertSystemProjectTodoType("client-1", {
      id: "research",
      name: "Research",
      description: "Collect context first",
      agent: "codex",
      agent_profile_id: "builtin/research",
      artifact_kinds: [],
      input_artifact_ids: ["project-user-journey"],
      dispatch_template: null
    });
    url = requestUrl(fetchMock.mock.calls[1][0]);
    expect(url.pathname).toBe("/api/clients/client-1/projects/todo-types/system");
    expect(fetchMock.mock.calls[1][1]?.method).toBe("POST");
    expect(JSON.parse(String(fetchMock.mock.calls[1][1]?.body))).toEqual({
      id: "research",
      name: "Research",
      description: "Collect context first",
      agent: "codex",
      agent_profile_id: "builtin/research",
      artifact_kinds: [],
      input_artifact_ids: ["project-user-journey"],
      dispatch_template: null
    });

    fetchMock.mockResolvedValueOnce(jsonResponse({ id: "research" }));
    await updateSystemProjectTodoType("client-1", "research", {
      name: "Research Card",
      agent: null,
      artifact_kinds: ["deep_research_report"],
      input_artifact_ids: [],
      dispatch_template: "Research {{ title }}"
    });
    url = requestUrl(fetchMock.mock.calls[2][0]);
    expect(url.pathname).toBe("/api/clients/client-1/projects/todo-types/system/research");
    expect(fetchMock.mock.calls[2][1]?.method).toBe("PATCH");
    expect(JSON.parse(String(fetchMock.mock.calls[2][1]?.body))).toEqual({
      name: "Research Card",
      agent: null,
      artifact_kinds: ["deep_research_report"],
      input_artifact_ids: [],
      dispatch_template: "Research {{ title }}"
    });

    fetchMock.mockResolvedValueOnce(new Response(null, { status: 204 }));
    await deleteSystemProjectTodoType("client-1", "research");
    url = requestUrl(fetchMock.mock.calls[3][0]);
    expect(url.pathname).toBe("/api/clients/client-1/projects/todo-types/system/research");
    expect(fetchMock.mock.calls[3][1]?.method).toBe("DELETE");
  });
});
