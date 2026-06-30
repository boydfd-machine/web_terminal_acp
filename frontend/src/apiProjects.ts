import type {
  Project,
  ProjectBrowseRootList,
  ProjectFileContent,
  ProjectFileList,
  ProjectFileSearchMode,
  ProjectFileSearchResponse,
  ProjectFileUploadResult,
  ProjectArtifactList,
  ProjectAgentPreference,
  ProjectReviewConfig,
  ProjectReviewMergePolicy,
  ProjectReviewProvider,
  TerminalProject,
  TreeFolderCore
} from "./types";
import { apiUrl, authHeaders, fetchApi, pathSegment, request, throwApiError } from "./apiCore";
import { artifactHtmlSrcDoc } from "./apiWindows";
import type { TerminalTimeRange } from "./terminalTimeRange";

function projectFileParams(projectPath: string, browseRoot?: string | null): URLSearchParams {
  const params = new URLSearchParams({ project_path: projectPath });
  if (browseRoot) {
    params.set("browse_root", browseRoot);
  }
  return params;
}

export function fetchTree(
  clientId: string,
  range?: TerminalTimeRange,
  projectPath?: string | null
): Promise<TreeFolderCore[]> {
  const params = new URLSearchParams();
  if (range !== undefined) {
    params.set("range", range);
  }
  if (projectPath) {
    params.set("project_path", projectPath);
  }
  const query = params.toString();
  const suffix = query ? `?${query}` : "";
  return request<TreeFolderCore[]>(`/api/clients/${pathSegment(clientId)}/tree${suffix}`);
}

export function fetchTerminalProjects(
  clientId: string,
  range?: TerminalTimeRange
): Promise<TerminalProject[]> {
  const params = new URLSearchParams();
  if (range !== undefined) {
    params.set("range", range);
  }
  const query = params.toString();
  const suffix = query ? `?${query}` : "";
  return request<TerminalProject[]>(
    `/api/clients/${pathSegment(clientId)}/terminal-projects${suffix}`
  );
}

export function fetchProjects(clientId: string, range?: TerminalTimeRange): Promise<Project[]> {
  const params = new URLSearchParams();
  if (range !== undefined) {
    params.set("range", range);
  }
  const query = params.toString();
  const suffix = query ? `?${query}` : "";
  return request<Project[]>(`/api/clients/${pathSegment(clientId)}/projects${suffix}`);
}

export function fetchProject(
  clientId: string,
  projectPath: string,
  range?: TerminalTimeRange
): Promise<Project> {
  const params = new URLSearchParams({ project_path: projectPath });
  if (range !== undefined) {
    params.set("range", range);
  }
  return request<Project>(`/api/clients/${pathSegment(clientId)}/projects/detail?${params.toString()}`);
}

export function fetchProjectArtifacts(
  clientId: string,
  projectPath: string,
  limit = 50,
  offset = 0
): Promise<ProjectArtifactList> {
  const params = new URLSearchParams({
    project_path: projectPath,
    limit: String(limit),
    offset: String(offset)
  });
  return request<ProjectArtifactList>(
    `/api/clients/${pathSegment(clientId)}/projects/artifacts?${params.toString()}`
  );
}

function projectArtifactHtmlPath(clientId: string, projectPath: string, artifactId: string): string {
  const params = new URLSearchParams({ project_path: projectPath });
  return `/api/clients/${pathSegment(clientId)}/projects/artifacts/${pathSegment(artifactId)}/html?${params.toString()}`;
}

export function projectArtifactHtmlUrl(clientId: string, projectPath: string, artifactId: string): string {
  return apiUrl(projectArtifactHtmlPath(clientId, projectPath, artifactId));
}

export async function fetchProjectArtifactHtml(
  clientId: string,
  projectPath: string,
  artifactId: string
): Promise<string> {
  const response = await fetchApi(projectArtifactHtmlUrl(clientId, projectPath, artifactId), {
    headers: authHeaders()
  });
  if (!response.ok) {
    await throwApiError(response);
  }
  return artifactHtmlSrcDoc(await response.text());
}

export function fetchProjectBrowseRoots(
  clientId: string,
  projectPath: string
): Promise<ProjectBrowseRootList> {
  const params = new URLSearchParams({ project_path: projectPath });
  return request<ProjectBrowseRootList>(
    `/api/clients/${pathSegment(clientId)}/projects/browse-roots?${params.toString()}`
  );
}

function projectReviewConfigPath(clientId: string, projectPath: string): string {
  const params = new URLSearchParams({ project_path: projectPath });
  return `/api/clients/${pathSegment(clientId)}/projects/review-config?${params.toString()}`;
}

export function fetchProjectReviewConfig(
  clientId: string,
  projectPath: string
): Promise<ProjectReviewConfig> {
  return request<ProjectReviewConfig>(projectReviewConfigPath(clientId, projectPath));
}

export function updateProjectReviewConfig(
  clientId: string,
  projectPath: string,
  input: {
    pr_provider: ProjectReviewProvider;
    pr_provider_config?: Record<string, unknown> | null;
    review_agent?: string | null;
    review_agent_command?: string | null;
    review_agent_profile_id?: string | null;
    auto_create_review_target: boolean;
    auto_dispatch_review: boolean;
    merge_policy: ProjectReviewMergePolicy;
    required_artifact_kinds?: string[];
  }
): Promise<ProjectReviewConfig> {
  return request<ProjectReviewConfig>(projectReviewConfigPath(clientId, projectPath), {
    method: "PUT",
    body: JSON.stringify({
      pr_provider: input.pr_provider,
      pr_provider_config: input.pr_provider_config ?? null,
      review_agent: input.review_agent ?? null,
      review_agent_command: input.review_agent_command ?? null,
      review_agent_profile_id: input.review_agent_profile_id ?? null,
      auto_create_review_target: input.auto_create_review_target,
      auto_dispatch_review: input.auto_dispatch_review,
      merge_policy: input.merge_policy,
      required_artifact_kinds: input.required_artifact_kinds ?? []
    })
  });
}

function projectAgentPreferencePath(clientId: string, projectPath: string): string {
  const params = new URLSearchParams({ project_path: projectPath });
  return `/api/clients/${pathSegment(clientId)}/projects/agent-preference?${params.toString()}`;
}

export function updateProjectAgentPreference(
  clientId: string,
  projectPath: string,
  input: ProjectAgentPreference
): Promise<ProjectAgentPreference> {
  return request<ProjectAgentPreference>(projectAgentPreferencePath(clientId, projectPath), {
    method: "PUT",
    body: JSON.stringify({
      agent_profile_id: input.agent_profile_id,
      agent_client: input.agent_client,
      agent_command: input.agent_command,
      agent_model_selection: input.agent_model_selection
    })
  });
}

export function fetchProjectFiles(
  clientId: string,
  projectPath: string,
  path = ".",
  browseRoot?: string | null
): Promise<ProjectFileList> {
  const params = projectFileParams(projectPath, browseRoot);
  params.set("path", path);
  return request<ProjectFileList>(
    `/api/clients/${pathSegment(clientId)}/projects/files?${params.toString()}`
  );
}

export function searchProjectFiles(
  clientId: string,
  query: string,
  limit = 25,
  offset = 0,
  projectPath?: string,
  mode?: ProjectFileSearchMode
): Promise<ProjectFileSearchResponse> {
  const params = new URLSearchParams({
    q: query,
    limit: String(limit),
    offset: String(offset)
  });
  if (projectPath !== undefined) {
    params.set("project_path", projectPath);
  }
  if (mode !== undefined) {
    params.set("mode", mode);
  }
  return request<ProjectFileSearchResponse>(
    `/api/clients/${pathSegment(clientId)}/projects/files/search?${params.toString()}`
  );
}

export function fetchProjectFileContent(
  clientId: string,
  projectPath: string,
  path: string,
  browseRoot?: string | null
): Promise<ProjectFileContent> {
  const params = projectFileParams(projectPath, browseRoot);
  params.set("path", path);
  return request<ProjectFileContent>(
    `/api/clients/${pathSegment(clientId)}/projects/files/content?${params.toString()}`
  );
}

export function saveProjectFileContent(
  clientId: string,
  projectPath: string,
  path: string,
  content: string,
  overwrite = true,
  browseRoot?: string | null
): Promise<ProjectFileUploadResult> {
  const params = projectFileParams(projectPath, browseRoot);
  return request<ProjectFileUploadResult>(
    `/api/clients/${pathSegment(clientId)}/projects/files/content?${params.toString()}`,
    {
      method: "PUT",
      body: JSON.stringify({
        path,
        content,
        overwrite
      })
    }
  );
}

export function projectFileDownloadUrl(
  clientId: string,
  projectPath: string,
  path: string,
  browseRoot?: string | null
): string {
  const url = new URL(apiUrl(`/api/clients/${pathSegment(clientId)}/projects/files/download`));
  url.searchParams.set("project_path", projectPath);
  if (browseRoot) {
    url.searchParams.set("browse_root", browseRoot);
  }
  url.searchParams.set("path", path);
  return url.toString();
}

export async function downloadProjectFile(
  clientId: string,
  projectPath: string,
  path: string,
  browseRoot?: string | null
): Promise<void> {
  const response = await fetchProjectFileResponse(clientId, projectPath, path, browseRoot);
  triggerBrowserDownload(await response.blob(), fileNameFromPath(path));
}

export async function fetchProjectFileBlob(
  clientId: string,
  projectPath: string,
  path: string,
  browseRoot?: string | null
): Promise<Blob> {
  const response = await fetchProjectFileResponse(clientId, projectPath, path, browseRoot);
  return response.blob();
}

async function fetchProjectFileResponse(
  clientId: string,
  projectPath: string,
  path: string,
  browseRoot?: string | null
): Promise<Response> {
  const response = await fetchApi(projectFileDownloadUrl(clientId, projectPath, path, browseRoot), {
    headers: authHeaders()
  });
  if (!response.ok) {
    await throwApiError(response);
  }
  return response;
}

function fileNameFromPath(path: string): string {
  const parts = path.split("/").filter(Boolean);
  return parts.length > 0 ? parts[parts.length - 1] : "download";
}

function triggerBrowserDownload(blob: Blob, fileName: string): void {
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = fileName;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

export function uploadProjectFile(
  clientId: string,
  projectPath: string,
  path: string,
  contentBase64: string,
  overwrite = true,
  browseRoot?: string | null
): Promise<ProjectFileUploadResult> {
  const params = projectFileParams(projectPath, browseRoot);
  return request<ProjectFileUploadResult>(
    `/api/clients/${pathSegment(clientId)}/projects/files/upload?${params.toString()}`,
    {
      method: "POST",
      body: JSON.stringify({
        path,
        content_base64: contentBase64,
        overwrite
      })
    }
  );
}
