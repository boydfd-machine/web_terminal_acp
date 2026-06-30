import type {
  AgentLaunchConfig,
  AgentModelSelection,
  ArtifactScope,
  TerminalArtifact,
  TerminalArtifactList,
  VirtualWindow
} from "./types";
import { ARTIFACT_HTML_CSP, HTML_FILE_CSP, sanitizeArtifactHtml } from "./artifactHtmlSecurity";
import { readArtifactTerminalRetentionSeconds, readSummaryOutputLanguage, type SummaryOutputLanguage } from "./userPreferences";
import { authHeaders, apiUrl, fetchApi, pathSegment, request, requestVoid, throwApiError } from "./apiCore";

export type CreateWindowInput = {
  cwd?: string | null;
  shell_command?: string | null;
  folder_path?: string | null;
  agent_launch?: AgentLaunchConfig | null;
};

export type CloneWindowInput = {
  mode?: "linked" | "ephemeral";
  prompt?: string | null;
  collect_paths?: string[] | null;
};

export type CreateTerminalArtifactInput = {
  artifact_kind?: string;
  artifact_scope?: ArtifactScope;
  project_path?: string | null;
  title?: string | null;
  prompt?: string | null;
  output_language?: SummaryOutputLanguage | null;
  metadata_json?: Record<string, unknown> | null;
  artifact_model_selection?: AgentModelSelection | null;
  terminal_retention_seconds?: number | null;
};

export const TERMINAL_ARTIFACT_HTML_CSP = ARTIFACT_HTML_CSP;
export const PROJECT_FILE_HTML_CSP = HTML_FILE_CSP;

function terminalArtifactHtmlPath(clientId: string, windowId: string, artifactId: string): string {
  return `/api/clients/${pathSegment(clientId)}/windows/${pathSegment(windowId)}/artifacts/${pathSegment(artifactId)}/html`;
}

function buildHtmlSrcDoc(html: string, csp: string): string {
  const cspMeta = `<meta http-equiv="Content-Security-Policy" content="${csp}">`;
  const sanitized = sanitizeArtifactHtml(html);
  if (/<head(\s[^>]*)?>/i.test(sanitized)) {
    return sanitized.replace(/<head(\s[^>]*)?>/i, (match) => `${match}${cspMeta}`);
  }
  return `${cspMeta}${sanitized}`;
}

export function artifactHtmlSrcDoc(html: string): string {
  return buildHtmlSrcDoc(html, TERMINAL_ARTIFACT_HTML_CSP);
}

export function htmlFileSrcDoc(html: string): string {
  return buildHtmlSrcDoc(html, PROJECT_FILE_HTML_CSP);
}

export function createWindow(clientId: string, input: CreateWindowInput = {}): Promise<VirtualWindow> {
  return request<VirtualWindow>(`/api/clients/${pathSegment(clientId)}/windows`, {
    method: "POST",
    body: JSON.stringify({
      cwd: input.cwd ?? null,
      shell_command: input.shell_command ?? null,
      folder_path: input.folder_path ?? null,
      agent_launch: input.agent_launch ?? null
    })
  });
}

export function cloneWindow(
  clientId: string,
  windowId: string,
  input: CloneWindowInput = {}
): Promise<VirtualWindow> {
  return request<VirtualWindow>(
    `/api/clients/${pathSegment(clientId)}/windows/${pathSegment(windowId)}/clone`,
    {
      method: "POST",
      body: JSON.stringify({
        mode: input.mode ?? "linked",
        prompt: input.prompt ?? null,
        collect_paths: input.collect_paths ?? null
      })
    }
  );
}

export async function deleteWindow(clientId: string, windowId: string): Promise<void> {
  await requestVoid(`/api/clients/${pathSegment(clientId)}/windows/${pathSegment(windowId)}`, {
    method: "DELETE"
  });
}

export function fetchWindow(clientId: string, windowId: string): Promise<VirtualWindow> {
  return request<VirtualWindow>(`/api/clients/${pathSegment(clientId)}/windows/${pathSegment(windowId)}`);
}

export function fetchTerminalArtifacts(
  clientId: string,
  windowId: string,
  limit = 50,
  offset = 0,
  artifactScope: ArtifactScope = "terminal",
  projectPath?: string | null
): Promise<TerminalArtifactList> {
  const params = new URLSearchParams({
    limit: String(limit),
    offset: String(offset),
    artifact_scope: artifactScope
  });
  if (artifactScope === "project" && projectPath) {
    params.set("project_path", projectPath);
  }
  return request<TerminalArtifactList>(
    `/api/clients/${pathSegment(clientId)}/windows/${pathSegment(windowId)}/artifacts?${params.toString()}`
  );
}

export function createTerminalArtifact(
  clientId: string,
  windowId: string,
  input: CreateTerminalArtifactInput = {}
): Promise<TerminalArtifact> {
  const body: Record<string, unknown> = {
    artifact_kind: input.artifact_kind ?? "agent_trace_graph",
    artifact_scope: input.artifact_scope ?? "terminal",
    project_path: input.project_path ?? null,
    title: input.title ?? null,
    prompt: input.prompt ?? null,
    output_language: input.output_language ?? readSummaryOutputLanguage(),
    metadata_json: input.metadata_json ?? null,
    terminal_retention_seconds: input.terminal_retention_seconds ?? readArtifactTerminalRetentionSeconds()
  };
  if (input.artifact_model_selection !== undefined && input.artifact_model_selection !== null) {
    body.artifact_model_selection = input.artifact_model_selection;
  }
  return request<TerminalArtifact>(
    `/api/clients/${pathSegment(clientId)}/windows/${pathSegment(windowId)}/artifacts`,
    {
      method: "POST",
      body: JSON.stringify(body)
    }
  );
}

export function terminalArtifactHtmlUrl(clientId: string, windowId: string, artifactId: string): string {
  return apiUrl(terminalArtifactHtmlPath(clientId, windowId, artifactId));
}

export async function fetchTerminalArtifactHtml(
  clientId: string,
  windowId: string,
  artifactId: string
): Promise<string> {
  const response = await fetchApi(terminalArtifactHtmlUrl(clientId, windowId, artifactId), {
    headers: authHeaders()
  });
  if (!response.ok) {
    await throwApiError(response);
  }
  return artifactHtmlSrcDoc(await response.text());
}

export function updateWindowTitle(clientId: string, windowId: string, title: string): Promise<VirtualWindow> {
  return request<VirtualWindow>(`/api/clients/${pathSegment(clientId)}/windows/${pathSegment(windowId)}`, {
    method: "PATCH",
    body: JSON.stringify({ title })
  });
}
