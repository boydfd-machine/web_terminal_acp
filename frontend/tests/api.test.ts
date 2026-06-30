import { afterEach, describe, expect, it, vi } from "vitest";
import {
  artifactHtmlSrcDoc,
  auxTerminalWebSocketUrl,
  cloneWindow,
  createArtifactPluginPreview,
  createArtifactPlugin,
  createTerminalArtifactPlugin,
  createTerminalArtifact,
  deleteTerminalArtifactPlugin,
  downloadProjectFile,
  ensureAuxTerminal,
  fetchAgentClients,
  fetchArtifactPluginPreviewHtml,
  fetchArtifactPluginPreviews,
  fetchArtifactPlugins,
  fetchArtifactPluginSource,
  searchAgentRecords,
  searchWindowAgentRecord,
  fetchProjectBrowseRoots,
  fetchProjectArtifactHtml,
  fetchProjectArtifacts,
  fetchProjectFileContent,
  fetchProjectFiles,
  fetchProjectReviewConfig,
  fetchProjects,
  searchProjectFiles,
  fetchTerminalArtifactHtml,
  fetchTerminalProjects,
  fetchTree,
  fetchWindowActivity,
  previewTerminalArtifactPlugin,
  previewArtifactPlugin,
  projectArtifactHtmlUrl,
  projectFileDownloadUrl,
  saveProjectFileContent,
  updateArtifactPluginPreview,
  updateProjectAgentPreference,
  updateProjectReviewConfig,
  updateTerminalArtifactPlugin,
  updateManualWorkStatus,
  terminalSelectionWebSocketUrl,
  terminalWebSocketUrl,
  uiEventsWebSocketUrl,
  uploadProjectFile,
  terminalArtifactHtmlUrl
} from "../src/api";
afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
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
describe("api terminal time ranges", () => {
  it("builds manual work status update requests", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(jsonResponse({
      state: "WORKING",
      label: "Agent 工作中",
      color: "orange",
      source: "manual",
      manual_updated_at: "2026-06-05T00:00:00Z",
      last_activity_at: null,
      last_working_activity_at: null
    }));
    await updateManualWorkStatus("client-1", "window/1", "WORKING");
    let url = requestUrl(fetchMock.mock.calls[0][0]);
    expect(url.pathname).toBe("/api/clients/client-1/windows/window%2F1/work-status");
    expect(fetchMock.mock.calls[0][1]?.method).toBe("PATCH");
    expect(JSON.parse(String(fetchMock.mock.calls[0][1]?.body))).toEqual({ state: "WORKING" });
    fetchMock.mockResolvedValueOnce(jsonResponse({
      state: "LONG_IDLE",
      label: "长时间没有工作了",
      color: "gray",
      source: "activity",
      manual_updated_at: null,
      last_activity_at: null,
      last_working_activity_at: null
    }));
    await updateManualWorkStatus("client-1", "window-1", null);
    url = requestUrl(fetchMock.mock.calls[1][0]);
    expect(url.pathname).toBe("/api/clients/client-1/windows/window-1/work-status");
    expect(JSON.parse(String(fetchMock.mock.calls[1][1]?.body))).toEqual({ state: null });
  });
  it("builds artifact plugin management requests", async () => {
    window.localStorage.setItem("web-terminal-acp:auth-token", "token-1");
    const fetchMock = vi.spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(jsonResponse({ plugins: [] }))
      .mockResolvedValueOnce(jsonResponse({ artifact_kind: "demo", source: "source" }))
      .mockResolvedValueOnce(jsonResponse({ artifact_kind: "demo", source: "source" }))
      .mockResolvedValueOnce(jsonResponse({ artifact_kind: "demo", source: "updated" }))
      .mockResolvedValueOnce(jsonResponse({ artifact_kind: "demo", plugin_format: "template" }))
      .mockResolvedValueOnce(new Response("<html><body>preview</body></html>", { status: 200, headers: { "Content-Type": "text/html" } }))
      .mockResolvedValueOnce(new Response(null, { status: 204 }));
    await fetchArtifactPlugins();
    let url = requestUrl(fetchMock.mock.calls[0][0]);
    expect(url.pathname).toBe("/api/artifact-plugins");
    await fetchArtifactPluginSource("terminal", "demo report");
    url = requestUrl(fetchMock.mock.calls[1][0]);
    expect(url.pathname).toBe("/api/artifact-plugins/terminal/demo%20report");
    await createTerminalArtifactPlugin("source");
    url = requestUrl(fetchMock.mock.calls[2][0]);
    expect(url.pathname).toBe("/api/artifact-plugins/terminal");
    expect(fetchMock.mock.calls[2][1]?.method).toBe("POST");
    expect(JSON.parse(String(fetchMock.mock.calls[2][1]?.body))).toEqual({ source: "source" });
    await updateTerminalArtifactPlugin("demo report", "updated");
    url = requestUrl(fetchMock.mock.calls[3][0]);
    expect(url.pathname).toBe("/api/artifact-plugins/terminal/demo%20report");
    expect(fetchMock.mock.calls[3][1]?.method).toBe("PUT");
    expect(JSON.parse(String(fetchMock.mock.calls[3][1]?.body))).toEqual({ source: "updated" });
    await updateTerminalArtifactPlugin("demo report", {
      python_source: "ARTIFACT_KIND = 'demo'",
      prompt_template: "prompt",
      html_template: "<html></html>",
      json_schema: { type: "object" },
      preview_content_json: { title: "Preview" }
    });
    url = requestUrl(fetchMock.mock.calls[4][0]);
    expect(url.pathname).toBe("/api/artifact-plugins/terminal/demo%20report");
    expect(fetchMock.mock.calls[4][1]?.method).toBe("PUT");
    expect(JSON.parse(String(fetchMock.mock.calls[4][1]?.body))).toEqual({
      python_source: "ARTIFACT_KIND = 'demo'",
      prompt_template: "prompt",
      html_template: "<html></html>",
      json_schema: { type: "object" },
      preview_content_json: { title: "Preview" }
    });

    const srcDoc = await previewTerminalArtifactPlugin({
      python_source: "ARTIFACT_KIND = 'demo'",
      prompt_template: "prompt",
      html_template: "<html></html>",
      json_schema: { type: "object" },
      preview_content_json: { title: "Preview" }
    });
    url = requestUrl(fetchMock.mock.calls[5][0]);
    expect(url.pathname).toBe("/api/artifact-plugins/terminal/preview/html");
    expect(fetchMock.mock.calls[5][1]?.method).toBe("POST");
    expect((fetchMock.mock.calls[5][1]?.headers as Headers).get("Authorization")).toBe("Bearer token-1");
    expect((fetchMock.mock.calls[5][1]?.headers as Headers).get("Content-Type")).toBe("application/json");
    expect(srcDoc).toContain("Content-Security-Policy");
    expect(srcDoc).toContain("preview");

    await deleteTerminalArtifactPlugin("demo report");
    url = requestUrl(fetchMock.mock.calls[6][0]);
    expect(url.pathname).toBe("/api/artifact-plugins/terminal/demo%20report");
    expect(fetchMock.mock.calls[6][1]?.method).toBe("DELETE");

  });

  it("builds project artifact plugin management requests", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(jsonResponse({ artifact_kind: "user_journey", source: "source" }))
      .mockResolvedValueOnce(new Response("<html><body>preview</body></html>", {
        status: 200,
        headers: { "Content-Type": "text/html" }
      }));

    await createArtifactPlugin("project", "source");
    let url = requestUrl(fetchMock.mock.calls[0][0]);
    expect(url.pathname).toBe("/api/artifact-plugins/project");

    const srcDoc = await previewArtifactPlugin("project", {
      python_source: "ARTIFACT_KIND = 'user_journey'",
      prompt_template: "prompt",
      html_template: "<html></html>",
      json_schema: { type: "object" },
      preview_content_json: { title: "Preview" }
    });
    url = requestUrl(fetchMock.mock.calls[1][0]);
    expect(url.pathname).toBe("/api/artifact-plugins/project/preview/html");
    expect(srcDoc).toContain("Content-Security-Policy");
  });

  it("builds artifact plugin preview session requests", async () => {
    window.localStorage.setItem("web-terminal-acp:auth-token", "token-1");
    const preview = {
      id: "preview-1",
      client_id: "client-1",
      window_id: "window/1",
      created_by_window_id: "window/1",
      status: "valid",
      draft_artifact_kind: "demo_report",
      title: "Demo preview",
      components_json: {},
      demo_content_json: { title: "Preview" },
      rendered_content_json: { title: "Preview" },
      display_html: null,
      last_error: null,
      created_at: "2026-06-06T00:00:00Z",
      updated_at: "2026-06-06T00:00:00Z",
      expires_at: "2026-06-07T00:00:00Z"
    };
    const payload = {
      client_id: "client-1",
      window_id: "window/1",
      title: "Demo preview",
      python_source: "ARTIFACT_KIND = 'demo_report'",
      prompt_template: "prompt",
      html_template: "<html></html>",
      json_schema: { type: "object" },
      demo_content_json: { title: "Preview" }
    };
    const fetchMock = vi.spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(jsonResponse({
        window_id: "window/1",
        previews: [preview],
        total: 1,
        limit: 25,
        offset: 50,
        has_more: false
      }))
      .mockResolvedValueOnce(jsonResponse(preview))
      .mockResolvedValueOnce(jsonResponse({ ...preview, title: "Updated preview" }))
      .mockResolvedValueOnce(new Response("<html><body>preview</body></html>", {
        status: 200,
        headers: { "Content-Type": "text/html" }
      }));

    await fetchArtifactPluginPreviews("client-1", "window/1", 25, 50);
    let url = requestUrl(fetchMock.mock.calls[0][0]);
    expect(url.pathname).toBe("/api/clients/client-1/windows/window%2F1/artifact-plugin-previews");
    expect(url.searchParams.get("limit")).toBe("25");
    expect(url.searchParams.get("offset")).toBe("50");

    await createArtifactPluginPreview(payload);
    url = requestUrl(fetchMock.mock.calls[1][0]);
    expect(url.pathname).toBe("/api/artifact-plugin-previews");
    expect(fetchMock.mock.calls[1][1]?.method).toBe("POST");
    expect((fetchMock.mock.calls[1][1]?.headers as Headers).get("Authorization")).toBe("Bearer token-1");
    expect(JSON.parse(String(fetchMock.mock.calls[1][1]?.body))).toEqual(payload);

    await updateArtifactPluginPreview("preview/1", payload);
    url = requestUrl(fetchMock.mock.calls[2][0]);
    expect(url.pathname).toBe("/api/artifact-plugin-previews/preview%2F1");
    expect(fetchMock.mock.calls[2][1]?.method).toBe("PUT");
    expect(JSON.parse(String(fetchMock.mock.calls[2][1]?.body))).toEqual(payload);

    const srcDoc = await fetchArtifactPluginPreviewHtml("preview/1");
    url = requestUrl(fetchMock.mock.calls[3][0]);
    expect(url.pathname).toBe("/api/artifact-plugin-previews/preview%2F1/html");
    expect((fetchMock.mock.calls[3][1]?.headers as Headers).get("Authorization")).toBe("Bearer token-1");
    expect(srcDoc).toContain("Content-Security-Policy");
    expect(srcDoc).toContain("preview");
  });

  it("does not put auth tokens in websocket URLs", () => {
    window.localStorage.setItem("web-terminal-acp:auth-token", "token-1");

    const urls = [
      uiEventsWebSocketUrl(),
      terminalSelectionWebSocketUrl("client-1"),
      auxTerminalWebSocketUrl("client-1", "window-1", "view-1"),
      terminalWebSocketUrl("client-1", "window-1", "view-1", { allowMissingWindowRecreate: true }),
    ].map((value) => new URL(value));

    expect(urls.map((url) => url.pathname)).toEqual([
      "/api/ui-events",
      "/api/clients/client-1/terminal-selection",
      "/api/clients/client-1/windows/window-1/aux-terminal",
      "/api/clients/client-1/terminal/window-1",
    ]);
    for (const url of urls) {
      expect(url.protocol).toBe("ws:");
      expect(url.searchParams.get("auth_token")).toBeNull();
    }
  });

  it("passes the selected range to the tree API", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(jsonResponse([]));

    await fetchTree("client-1", "7d", "/workspace/project");

    const url = requestUrl(fetchMock.mock.calls[0][0]);
    expect(url.pathname).toBe("/api/clients/client-1/tree");
    expect(url.searchParams.get("range")).toBe("7d");
    expect(url.searchParams.get("project_path")).toBe("/workspace/project");
  });

  it("builds agent record search requests", async () => {
    const searchResponse = {
      query: "llama",
      results: [],
      total: 0,
      limit: 10,
      offset: 20,
      has_more: false,
      scope: "window"
    };
    const fetchMock = vi.spyOn(globalThis, "fetch").mockImplementation(() => Promise.resolve(jsonResponse(searchResponse)));

    await searchWindowAgentRecord("client-1", "window/1", "llama", 10, 20);
    let url = requestUrl(fetchMock.mock.calls[0][0]);
    expect(url.pathname).toBe("/api/clients/client-1/windows/window%2F1/agent-record/search");
    expect(url.searchParams.get("q")).toBe("llama");
    expect(url.searchParams.get("limit")).toBe("10");
    expect(url.searchParams.get("offset")).toBe("20");

    await searchAgentRecords("client-1", "alpaca", 5, 0);
    url = requestUrl(fetchMock.mock.calls[1][0]);
    expect(url.pathname).toBe("/api/clients/client-1/agent-record/search");
    expect(url.searchParams.get("q")).toBe("alpaca");
    expect(url.searchParams.get("limit")).toBe("5");
    expect(url.searchParams.get("offset")).toBe("0");
  });

  it("passes the selected range to the terminal projects API", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(jsonResponse([]));

    await fetchTerminalProjects("client-1", "30d");

    const url = requestUrl(fetchMock.mock.calls[0][0]);
    expect(url.pathname).toBe("/api/clients/client-1/terminal-projects");
    expect(url.searchParams.get("range")).toBe("30d");
  });

  it("fetches project domain objects with the selected range", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(jsonResponse([]));

    await fetchProjects("client-1", "7d");

    const url = requestUrl(fetchMock.mock.calls[0][0]);
    expect(url.pathname).toBe("/api/clients/client-1/projects");
    expect(url.searchParams.get("range")).toBe("7d");
  });

  it("builds project review config requests", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(jsonResponse({ id: "config-1" }))
      .mockResolvedValueOnce(jsonResponse({ id: "config-1" }));

    await fetchProjectReviewConfig("client-1", "/workspace/project");
    let url = requestUrl(fetchMock.mock.calls[0][0]);
    expect(url.pathname).toBe("/api/clients/client-1/projects/review-config");
    expect(url.searchParams.get("project_path")).toBe("/workspace/project");

    await updateProjectReviewConfig("client-1", "/workspace/project", {
      pr_provider: "LOCAL_CARD",
      pr_provider_config: { base_branch: "main" },
      review_agent: "codex",
      review_agent_command: "codex",
      review_agent_profile_id: "builtin/pr-review",
      auto_create_review_target: true,
      auto_dispatch_review: true,
      merge_policy: "AUTO_AFTER_PASSED",
      required_artifact_kinds: ["review_report", "test_report"]
    });
    url = requestUrl(fetchMock.mock.calls[1][0]);
    expect(url.pathname).toBe("/api/clients/client-1/projects/review-config");
    expect(fetchMock.mock.calls[1][1]?.method).toBe("PUT");
    expect(JSON.parse(String(fetchMock.mock.calls[1][1]?.body))).toEqual({
      pr_provider: "LOCAL_CARD",
      pr_provider_config: { base_branch: "main" },
      review_agent: "codex",
      review_agent_command: "codex",
      review_agent_profile_id: "builtin/pr-review",
      auto_create_review_target: true,
      auto_dispatch_review: true,
      merge_policy: "AUTO_AFTER_PASSED",
      required_artifact_kinds: ["review_report", "test_report"]
    });
  });

  it("builds project agent preference update requests", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(jsonResponse({
      agent_profile_id: "builtin/developer",
      agent_client: "codex",
      agent_command: "codex --model gpt-5-codex",
      agent_model_selection: { preset_id: "openai-main", model: "gpt-5-codex" }
    }));

    await updateProjectAgentPreference("client-1", "/workspace/project", {
      agent_profile_id: "builtin/developer",
      agent_client: "codex",
      agent_command: "codex --model gpt-5-codex",
      agent_model_selection: { preset_id: "openai-main", model: "gpt-5-codex" }
    });

    const url = requestUrl(fetchMock.mock.calls[0][0]);
    expect(url.pathname).toBe("/api/clients/client-1/projects/agent-preference");
    expect(url.searchParams.get("project_path")).toBe("/workspace/project");
    expect(fetchMock.mock.calls[0][1]?.method).toBe("PUT");
    expect(JSON.parse(String(fetchMock.mock.calls[0][1]?.body))).toEqual({
      agent_profile_id: "builtin/developer",
      agent_client: "codex",
      agent_command: "codex --model gpt-5-codex",
      agent_model_selection: { preset_id: "openai-main", model: "gpt-5-codex" }
    });
  });

  it("builds project artifact list and html requests", async () => {
    window.localStorage.setItem("web-terminal-acp:auth-token", "token-1");
    const fetchMock = vi.spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(jsonResponse({
        project_path: "/workspace/project",
        artifacts: [],
        total: 0,
        limit: 25,
        offset: 50,
        has_more: false
      }))
      .mockResolvedValueOnce(new Response("<html><body>artifact</body></html>", {
        status: 200,
        headers: { "Content-Type": "text/html" }
      }));

    await fetchProjectArtifacts("client-1", "/workspace/project", 25, 50);
    let url = requestUrl(fetchMock.mock.calls[0][0]);
    expect(url.pathname).toBe("/api/clients/client-1/projects/artifacts");
    expect(url.searchParams.get("project_path")).toBe("/workspace/project");
    expect(url.searchParams.get("limit")).toBe("25");
    expect(url.searchParams.get("offset")).toBe("50");

    const artifactUrl = requestUrl(projectArtifactHtmlUrl("client-1", "/workspace/project", "artifact-1"));
    expect(artifactUrl.pathname).toBe("/api/clients/client-1/projects/artifacts/artifact-1/html");
    expect(artifactUrl.searchParams.get("project_path")).toBe("/workspace/project");
    expect(artifactUrl.searchParams.has("auth_token")).toBe(false);

    const html = await fetchProjectArtifactHtml("client-1", "/workspace/project", "artifact-1");
    url = requestUrl(fetchMock.mock.calls[1][0]);
    expect(url.pathname).toBe("/api/clients/client-1/projects/artifacts/artifact-1/html");
    expect(new Headers(fetchMock.mock.calls[1][1]?.headers).get("Authorization")).toBe("Bearer token-1");
    expect(html).toContain("Content-Security-Policy");
  });

  it("builds project file requests and downloads with authorization headers", async () => {
    window.localStorage.setItem("web-terminal-acp:auth-token", "token-1");
    const fetchMock = vi.spyOn(globalThis, "fetch").mockImplementation(
      () => Promise.resolve(jsonResponse({ entries: [] }))
    );
    const clickAnchor = vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => {});
    const createObjectURL = vi.fn(() => "blob:project-file");
    const revokeObjectURL = vi.fn();
    vi.stubGlobal("URL", Object.assign(URL, {
      createObjectURL,
      revokeObjectURL
    }));

    await fetchProjectFiles("client-1", "/workspace/project", "docs");

    const listUrl = requestUrl(fetchMock.mock.calls[0][0]);
    expect(listUrl.pathname).toBe("/api/clients/client-1/projects/files");
    expect(listUrl.searchParams.get("project_path")).toBe("/workspace/project");
    expect(listUrl.searchParams.get("path")).toBe("docs");

    const downloadUrl = new URL(projectFileDownloadUrl("client-1", "/workspace/project", "docs/README.md"));
    expect(downloadUrl.pathname).toBe("/api/clients/client-1/projects/files/download");
    expect(downloadUrl.searchParams.get("project_path")).toBe("/workspace/project");
    expect(downloadUrl.searchParams.get("path")).toBe("docs/README.md");
    expect(downloadUrl.searchParams.has("auth_token")).toBe(false);

    await downloadProjectFile("client-1", "/workspace/project", "docs/README.md");

    const downloadRequestUrl = requestUrl(fetchMock.mock.calls[1][0]);
    expect(downloadRequestUrl.pathname).toBe("/api/clients/client-1/projects/files/download");
    expect(new Headers(fetchMock.mock.calls[1][1]?.headers).get("Authorization")).toBe("Bearer token-1");
    expect(createObjectURL).toHaveBeenCalled();
    expect(clickAnchor).toHaveBeenCalled();
    expect(revokeObjectURL).toHaveBeenCalledWith("blob:project-file");
  });

  it("builds project file search requests", async () => {
    const searchResponse = {
      query: "needle",
      results: [],
      total: 0,
      limit: 50,
      offset: 25,
      has_more: false,
      scanned_files: 0,
      truncated: false
    };
    const fetchMock = vi.spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(jsonResponse(searchResponse))
      .mockResolvedValueOnce(jsonResponse({ ...searchResponse, query: "all files" }));

    await searchProjectFiles("client-1", "needle", 50, 25, "/workspace/project", "filename");

    const url = requestUrl(fetchMock.mock.calls[0][0]);
    expect(url.pathname).toBe("/api/clients/client-1/projects/files/search");
    expect(url.searchParams.get("q")).toBe("needle");
    expect(url.searchParams.get("limit")).toBe("50");
    expect(url.searchParams.get("offset")).toBe("25");
    expect(url.searchParams.get("project_path")).toBe("/workspace/project");
    expect(url.searchParams.get("mode")).toBe("filename");

    await searchProjectFiles("client-1", "all files");
    const globalUrl = requestUrl(fetchMock.mock.calls[1][0]);
    expect(globalUrl.searchParams.get("project_path")).toBeNull();
    expect(globalUrl.searchParams.get("mode")).toBeNull();
  });

});
