import { afterEach, describe, expect, it, vi } from "vitest";

import { fetchProjectTodoHistory, restoreProjectTodoVersion } from "../src/api";

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

function latestCall(fetchMock: { mock: { calls: Parameters<typeof fetch>[] } }) {
  const call = fetchMock.mock.calls.at(-1);
  if (call === undefined) {
    throw new Error("fetch was not called");
  }
  return call;
}

describe("project todo history api requests", () => {
  it("builds history and restore requests", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch");

    fetchMock.mockResolvedValueOnce(jsonResponse({ todo_id: "todo-1", versions: [], audit_logs: [] }));
    await fetchProjectTodoHistory("client-1", "/workspace/project", "todo-1");
    let call = latestCall(fetchMock);
    let url = requestUrl(call[0]);
    expect(url.pathname).toBe("/api/clients/client-1/projects/todos/todo-1/history");
    expect(url.searchParams.get("project_path")).toBe("/workspace/project");

    fetchMock.mockResolvedValueOnce(jsonResponse({ id: "todo-1" }));
    await restoreProjectTodoVersion("client-1", "/workspace/project", "todo-1", 2);
    call = latestCall(fetchMock);
    url = requestUrl(call[0]);
    expect(url.pathname).toBe("/api/clients/client-1/projects/todos/todo-1/versions/2/restore");
    expect(url.searchParams.get("project_path")).toBe("/workspace/project");
    expect(call[1]?.method).toBe("POST");
  });
});
