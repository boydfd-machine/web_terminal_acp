import { afterEach, describe, expect, it, vi } from "vitest";

import {
  createProjectTodoReviewTarget,
  deleteAgentProfile,
  fetchAgentProfileConfig,
  fetchProjectTodoReviewRuns,
  fetchProjectTodoReviewTargets,
  fetchProjectTodoWorkSnapshots,
  updateAgentProfile,
  updateAgentProfileConfigItem
} from "../src/api";

afterEach(() => {
  vi.restoreAllMocks();
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

describe("review workflow API helpers", () => {
  it("uses query routes for slash-containing built-in agent profile ids", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(jsonResponse({ sections: [] }))
      .mockResolvedValueOnce(jsonResponse({ id: "builtin/pr-review" }))
      .mockResolvedValueOnce(jsonResponse({ sections: [] }))
      .mockResolvedValueOnce(new Response(null, { status: 204 }));

    await fetchAgentProfileConfig("client-1", "builtin/pr-review", "codex");
    let url = requestUrl(fetchMock.mock.calls[0][0]);
    expect(url.pathname).toBe("/api/clients/client-1/agent-profile-config");
    expect(url.searchParams.get("profile_id")).toBe("builtin/pr-review");
    expect(url.searchParams.get("agent")).toBe("codex");

    await updateAgentProfile("client-1", "builtin/pr-review", { name: "Readonly" });
    url = requestUrl(fetchMock.mock.calls[1][0]);
    expect(url.pathname).toBe("/api/clients/client-1/agent-profiles/detail");
    expect(url.searchParams.get("profile_id")).toBe("builtin/pr-review");
    expect(fetchMock.mock.calls[1][1]?.method).toBe("PATCH");

    await updateAgentProfileConfigItem("client-1", "builtin/pr-review", "codex", "skills", "pr-review", false);
    url = requestUrl(fetchMock.mock.calls[2][0]);
    expect(url.pathname).toBe("/api/clients/client-1/agent-profile-config/codex/skills/pr-review");
    expect(url.searchParams.get("profile_id")).toBe("builtin/pr-review");
    expect(fetchMock.mock.calls[2][1]?.method).toBe("PATCH");

    await deleteAgentProfile("client-1", "builtin/pr-review");
    url = requestUrl(fetchMock.mock.calls[3][0]);
    expect(url.pathname).toBe("/api/clients/client-1/agent-profiles/detail");
    expect(url.searchParams.get("profile_id")).toBe("builtin/pr-review");
    expect(fetchMock.mock.calls[3][1]?.method).toBe("DELETE");
  });

  it("builds project todo review history requests", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(jsonResponse({ work_snapshots: [] }))
      .mockResolvedValueOnce(jsonResponse({ review_targets: [] }))
      .mockResolvedValueOnce(jsonResponse({ id: "target-1" }))
      .mockResolvedValueOnce(jsonResponse({ review_runs: [] }));

    await fetchProjectTodoWorkSnapshots("client-1", "/workspace/project", "todo-1");
    let url = requestUrl(fetchMock.mock.calls[0][0]);
    expect(url.pathname).toBe("/api/clients/client-1/projects/todos/todo-1/work-snapshots");
    expect(url.searchParams.get("project_path")).toBe("/workspace/project");

    await fetchProjectTodoReviewTargets("client-1", "/workspace/project", "todo-1");
    url = requestUrl(fetchMock.mock.calls[1][0]);
    expect(url.pathname).toBe("/api/clients/client-1/projects/todos/todo-1/review-targets");

    await createProjectTodoReviewTarget("client-1", "/workspace/project", "todo-1");
    url = requestUrl(fetchMock.mock.calls[2][0]);
    expect(url.pathname).toBe("/api/clients/client-1/projects/todos/todo-1/review-targets");
    expect(fetchMock.mock.calls[2][1]?.method).toBe("POST");

    await fetchProjectTodoReviewRuns("client-1", "/workspace/project", "todo-1");
    url = requestUrl(fetchMock.mock.calls[3][0]);
    expect(url.pathname).toBe("/api/clients/client-1/projects/todos/todo-1/review-runs");
  });
});
