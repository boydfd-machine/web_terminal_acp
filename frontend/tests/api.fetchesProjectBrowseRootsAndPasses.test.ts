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
  updateProjectReviewConfig,
  updateTerminalArtifactPlugin,
  updateManualWorkStatus,
  uiEventsWebSocketUrl,
  uploadProjectFile,
  terminalArtifactHtmlUrl
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

describe("api terminal time ranges", () => {
  it("fetches project browse roots and passes browse roots through project file APIs", async () => {
    window.localStorage.setItem("web-terminal-acp:auth-token", "token-1");
    const fetchMock = vi.spyOn(globalThis, "fetch").mockImplementation(
      () => Promise.resolve(jsonResponse({ roots: [] }))
    );
    const browseRoot = "/workspace/project/.worktrees/feature";

    await fetchProjectBrowseRoots("client-1", "/workspace/project");
    let url = requestUrl(fetchMock.mock.calls[0][0]);
    expect(url.pathname).toBe("/api/clients/client-1/projects/browse-roots");
    expect(url.searchParams.get("project_path")).toBe("/workspace/project");

    await fetchProjectFiles("client-1", "/workspace/project", "docs", browseRoot);
    url = requestUrl(fetchMock.mock.calls[1][0]);
    expect(url.pathname).toBe("/api/clients/client-1/projects/files");
    expect(url.searchParams.get("project_path")).toBe("/workspace/project");
    expect(url.searchParams.get("browse_root")).toBe(browseRoot);
    expect(url.searchParams.get("path")).toBe("docs");

    await fetchProjectFileContent("client-1", "/workspace/project", "README.md", browseRoot);
    url = requestUrl(fetchMock.mock.calls[2][0]);
    expect(url.pathname).toBe("/api/clients/client-1/projects/files/content");
    expect(url.searchParams.get("browse_root")).toBe(browseRoot);
    expect(url.searchParams.get("path")).toBe("README.md");

    await uploadProjectFile("client-1", "/workspace/project", "upload.txt", "dXBsb2FkZWQ=", false, browseRoot);
    url = requestUrl(fetchMock.mock.calls[3][0]);
    expect(url.pathname).toBe("/api/clients/client-1/projects/files/upload");
    expect(url.searchParams.get("browse_root")).toBe(browseRoot);

    await saveProjectFileContent("client-1", "/workspace/project", "README.md", "# Updated", true, browseRoot);
    url = requestUrl(fetchMock.mock.calls[4][0]);
    expect(url.pathname).toBe("/api/clients/client-1/projects/files/content");
    expect(url.searchParams.get("browse_root")).toBe(browseRoot);

    const downloadUrl = new URL(projectFileDownloadUrl("client-1", "/workspace/project", "docs/README.md", browseRoot));
    expect(downloadUrl.pathname).toBe("/api/clients/client-1/projects/files/download");
    expect(downloadUrl.searchParams.get("browse_root")).toBe(browseRoot);
    expect(downloadUrl.searchParams.has("auth_token")).toBe(false);
  });

  it("fetches and uploads project file contents", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(jsonResponse({
      project_path: "/workspace/project",
      path: "README.md",
      content: "# Demo",
      encoding: "utf-8",
      truncated: false,
      size: 6
    }));

    await fetchProjectFileContent("client-1", "/workspace/project", "README.md");
    let url = requestUrl(fetchMock.mock.calls[0][0]);
    expect(url.pathname).toBe("/api/clients/client-1/projects/files/content");
    expect(url.searchParams.get("path")).toBe("README.md");

    fetchMock.mockResolvedValueOnce(jsonResponse({ project_path: "/workspace/project", path: "upload.txt", size: 8 }));
    await uploadProjectFile("client-1", "/workspace/project", "upload.txt", "dXBsb2FkZWQ=", false);
    url = requestUrl(fetchMock.mock.calls[1][0]);
    expect(url.pathname).toBe("/api/clients/client-1/projects/files/upload");
    expect(JSON.parse(String(fetchMock.mock.calls[1][1]?.body))).toEqual({
      path: "upload.txt",
      content_base64: "dXBsb2FkZWQ=",
      overwrite: false
    });

    fetchMock.mockResolvedValueOnce(jsonResponse({ project_path: "/workspace/project", path: "README.md", size: 12 }));
    await saveProjectFileContent("client-1", "/workspace/project", "README.md", "# Updated", true);
    url = requestUrl(fetchMock.mock.calls[2][0]);
    expect(url.pathname).toBe("/api/clients/client-1/projects/files/content");
    expect(fetchMock.mock.calls[2][1]?.method).toBe("PUT");
    expect(JSON.parse(String(fetchMock.mock.calls[2][1]?.body))).toEqual({
      path: "README.md",
      content: "# Updated",
      overwrite: true
    });
  });

  it("passes the selected range to the window activity API", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(jsonResponse({ windows: [] }));

    await fetchWindowActivity("client-1", {
      includeRuntimeTags: true,
      range: "14d",
      projectPath: "/workspace/project"
    });

    const url = requestUrl(fetchMock.mock.calls[0][0]);
    expect(url.pathname).toBe("/api/clients/client-1/windows/activity");
    expect(url.searchParams.get("include_runtime_tags")).toBe("true");
    expect(url.searchParams.get("range")).toBe("14d");
    expect(url.searchParams.get("project_path")).toBe("/workspace/project");
  });

  it("ensures an aux terminal for a selected window", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(jsonResponse({
      status: "ready",
      cwd: "/workspace"
    }));

    await expect(ensureAuxTerminal("client-1", "window-1")).resolves.toEqual({
      status: "ready",
      cwd: "/workspace"
    });

    const [input, init] = fetchMock.mock.calls[0];
    expect(requestUrl(input).pathname).toBe("/api/clients/client-1/windows/window-1/aux-terminal/ensure");
    expect(init?.method).toBe("POST");
  });

  it("clones a terminal with the linked mode payload", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(jsonResponse({
      id: "clone-1",
      client_id: "client-1"
    }));

    await cloneWindow("client-1", "window-1");

    const [input, init] = fetchMock.mock.calls[0];
    expect(requestUrl(input).pathname).toBe("/api/clients/client-1/windows/window-1/clone");
    expect(init?.method).toBe("POST");
    expect(JSON.parse(String(init?.body))).toEqual({
      mode: "linked",
      prompt: null,
      collect_paths: null
    });
  });

  it("fetches agent client descriptors for a client", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(jsonResponse({
      agent_clients: [
        {
          id: "codex",
          provider_id: "codex",
          label: "Codex",
          aliases: [],
          default_command: "codex",
          command_names: ["codex"]
        }
      ]
    }));

    await expect(fetchAgentClients("client-1")).resolves.toEqual({
      agent_clients: [
        {
          id: "codex",
          provider_id: "codex",
          label: "Codex",
          aliases: [],
          default_command: "codex",
          command_names: ["codex"]
        }
      ]
    });

    expect(requestUrl(fetchMock.mock.calls[0][0]).pathname).toBe("/api/clients/client-1/agent-clients");
  });

  it("creates a terminal artifact and builds its html URL without query auth", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(jsonResponse({
      id: "artifact-1",
      client_id: "client-1",
      virtual_window_id: "window-1",
      artifact_kind: "agent_trace_graph",
      status: "PENDING"
    }));

    await createTerminalArtifact("client-1", "window-1", { artifact_kind: "agent_trace_graph" });

    const [input, init] = fetchMock.mock.calls[0];
    expect(requestUrl(input).pathname).toBe("/api/clients/client-1/windows/window-1/artifacts");
    expect(init?.method).toBe("POST");
    expect(JSON.parse(String(init?.body))).toMatchObject({
      artifact_kind: "agent_trace_graph",
      artifact_scope: "terminal",
      project_path: null,
      title: null,
      prompt: null,
      metadata_json: null,
      output_language: "中文",
      terminal_retention_seconds: 600
    });
    expect(JSON.parse(String(init?.body))).not.toHaveProperty("artifact_model_selection");
    const artifactUrl = requestUrl(terminalArtifactHtmlUrl("client-1", "window-1", "artifact-1"));
    expect(artifactUrl.pathname).toBe("/api/clients/client-1/windows/window-1/artifacts/artifact-1/html");
    expect(artifactUrl.searchParams.has("auth_token")).toBe(false);
  });

  it("creates a project-scoped terminal artifact", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(jsonResponse({}));

    await createTerminalArtifact("client-1", "window-1", {
      artifact_kind: "user_journey",
      artifact_scope: "project",
      project_path: "/workspace/project",
      artifact_model_selection: {
        preset_id: "openai-artifacts",
        model: "gpt-5-codex",
        codex_model_reasoning_effort: "high"
      }
    });

    expect(JSON.parse(String(fetchMock.mock.calls[0][1]?.body))).toMatchObject({
      artifact_kind: "user_journey",
      artifact_scope: "project",
      project_path: "/workspace/project",
      artifact_model_selection: {
        preset_id: "openai-artifacts",
        model: "gpt-5-codex",
        codex_model_reasoning_effort: "high"
      }
    });
  });

  it("uses the configured artifact terminal retention when creating artifacts", async () => {
    window.localStorage.setItem("web-terminal-acp:artifact-terminal-retention-seconds", "120");
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(jsonResponse({}));

    await createTerminalArtifact("client-1", "window-1", { artifact_kind: "agent_trace_graph" });

    const body = JSON.parse(String(fetchMock.mock.calls[0][1]?.body));
    expect(body.terminal_retention_seconds).toBe(120);
  });

  it("uses the configured user preference language when creating artifacts", async () => {
    window.localStorage.setItem("web-terminal-acp:summary-output-language", "English");
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(jsonResponse({}));

    await createTerminalArtifact("client-1", "window-1", { artifact_kind: "page_review_cards" });

    const body = JSON.parse(String(fetchMock.mock.calls[0][1]?.body));
    expect(body.output_language).toBe("English");
  });

  it("fetches terminal artifact HTML with bearer auth and injects srcdoc CSP", async () => {
    window.localStorage.setItem("web-terminal-acp:auth-token", "token-1");
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(
      "<html><head><title>Trace</title></head><body>trace</body></html>",
      { status: 200, headers: { "Content-Type": "text/html" } }
    ));

    const html = await fetchTerminalArtifactHtml("client-1", "window-1", "artifact-1");

    const [input, init] = fetchMock.mock.calls[0];
    const url = requestUrl(input);
    expect(url.pathname).toBe("/api/clients/client-1/windows/window-1/artifacts/artifact-1/html");
    expect(url.searchParams.has("auth_token")).toBe(false);
    expect(new Headers(init?.headers).get("Authorization")).toBe("Bearer token-1");
    expect(html).toContain('<meta http-equiv="Content-Security-Policy"');
    expect(html).toContain("<body>trace</body>");
  });

  it("injects srcdoc CSP before body content when artifact HTML has no head element", () => {
    const html = artifactHtmlSrcDoc("<body>trace</body>");

    expect(html.indexOf('<meta http-equiv="Content-Security-Policy"')).toBeGreaterThanOrEqual(0);
    expect(html.indexOf('<meta http-equiv="Content-Security-Policy"')).toBeLessThan(
      html.indexOf("<body>")
    );
  });

  it("sanitizes dangerous nested tags, event handlers, and javascript URLs in artifact HTML", () => {
    const html = artifactHtmlSrcDoc(`
      <html>
        <head><title>Trace</title></head>
        <body>
          <img src="javascript:alert(1)" onerror="alert(2)">
          <a href="javascript:alert(3)" onclick="alert(4)">bad link</a>
          <iframe src="https://example.com"></iframe>
          <object data="https://example.com/object"></object>
          <embed src="https://example.com/embed">
          <script>window.__artifactInteractive = true;</script>
        </body>
      </html>
    `);

    expect(html).toContain("Content-Security-Policy");
    expect(html).toContain("script-src 'unsafe-inline'");
    expect(html).toContain("window.__artifactInteractive = true;");
    expect(html).not.toContain("javascript:");
    expect(html).not.toContain("onerror");
    expect(html).not.toContain("onclick");
    expect(html).not.toContain("<iframe");
    expect(html).not.toContain("<object");
    expect(html).not.toContain("<embed");
  });

  it("builds an aux terminal websocket URL with its own path", () => {
    const url = new URL(auxTerminalWebSocketUrl("client-1", "window-1", "view-1"));

    expect(url.protocol).toBe("ws:");
    expect(url.pathname).toBe("/api/clients/client-1/windows/window-1/aux-terminal");
    expect(url.searchParams.get("view_id")).toBe("view-1");
  });
});
