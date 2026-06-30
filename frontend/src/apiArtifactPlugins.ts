import type {
  ArtifactPluginDomain,
  ArtifactPluginList,
  ArtifactPluginPayload,
  ArtifactPluginPreview,
  ArtifactPluginPreviewList,
  ArtifactPluginPreviewPayload,
  ArtifactPluginSource
} from "./types";
import { apiUrl, authHeaders, fetchApi, pathSegment, request, requestVoid, throwApiError } from "./apiCore";
import { artifactHtmlSrcDoc } from "./apiWindows";

export function fetchArtifactPlugins(): Promise<ArtifactPluginList> {
  return request<ArtifactPluginList>("/api/artifact-plugins");
}

export function fetchArtifactPluginSource(
  domain: ArtifactPluginDomain,
  artifactKind: string
): Promise<ArtifactPluginSource> {
  return request<ArtifactPluginSource>(
    `/api/artifact-plugins/${pathSegment(domain)}/${pathSegment(artifactKind)}`
  );
}

export function fetchArtifactPluginPreviews(
  clientId: string,
  windowId: string,
  limit = 50,
  offset = 0
): Promise<ArtifactPluginPreviewList> {
  const params = new URLSearchParams({
    limit: String(limit),
    offset: String(offset)
  });
  return request<ArtifactPluginPreviewList>(
    `/api/clients/${pathSegment(clientId)}/windows/${pathSegment(windowId)}/artifact-plugin-previews?${params.toString()}`
  );
}

function artifactPluginBody(payload: string | ArtifactPluginPayload): string {
  return JSON.stringify(typeof payload === "string" ? { source: payload } : payload);
}

function artifactPluginPreviewBody(payload: ArtifactPluginPreviewPayload): string {
  return JSON.stringify(payload);
}

export function createArtifactPlugin(
  domain: ArtifactPluginDomain,
  payload: string | ArtifactPluginPayload
): Promise<ArtifactPluginSource> {
  return request<ArtifactPluginSource>(`/api/artifact-plugins/${pathSegment(domain)}`, {
    method: "POST",
    body: artifactPluginBody(payload)
  });
}

export function createTerminalArtifactPlugin(
  payload: string | ArtifactPluginPayload
): Promise<ArtifactPluginSource> {
  return createArtifactPlugin("terminal", payload);
}

export function updateArtifactPlugin(
  domain: ArtifactPluginDomain,
  artifactKind: string,
  payload: string | ArtifactPluginPayload
): Promise<ArtifactPluginSource> {
  return request<ArtifactPluginSource>(
    `/api/artifact-plugins/${pathSegment(domain)}/${pathSegment(artifactKind)}`,
    {
      method: "PUT",
      body: artifactPluginBody(payload)
    }
  );
}

export function updateTerminalArtifactPlugin(
  artifactKind: string,
  payload: string | ArtifactPluginPayload
): Promise<ArtifactPluginSource> {
  return updateArtifactPlugin("terminal", artifactKind, payload);
}

export async function previewArtifactPlugin(
  domain: ArtifactPluginDomain,
  payload: ArtifactPluginPayload
): Promise<string> {
  const response = await fetchApi(apiUrl(`/api/artifact-plugins/${pathSegment(domain)}/preview/html`), {
    method: "POST",
    headers: artifactPluginHeaders(),
    body: artifactPluginBody(payload)
  });
  if (!response.ok) {
    await throwApiError(response);
  }
  return artifactHtmlSrcDoc(await response.text());
}

export function previewTerminalArtifactPlugin(
  payload: ArtifactPluginPayload
): Promise<string> {
  return previewArtifactPlugin("terminal", payload);
}

export function createArtifactPluginPreview(
  payload: ArtifactPluginPreviewPayload
): Promise<ArtifactPluginPreview> {
  return request<ArtifactPluginPreview>("/api/artifact-plugin-previews", {
    method: "POST",
    body: artifactPluginPreviewBody(payload)
  });
}

export function updateArtifactPluginPreview(
  previewId: string,
  payload: ArtifactPluginPreviewPayload
): Promise<ArtifactPluginPreview> {
  return request<ArtifactPluginPreview>(`/api/artifact-plugin-previews/${pathSegment(previewId)}`, {
    method: "PUT",
    body: artifactPluginPreviewBody(payload)
  });
}

export async function fetchArtifactPluginPreviewHtml(previewId: string): Promise<string> {
  const response = await fetchApi(apiUrl(`/api/artifact-plugin-previews/${pathSegment(previewId)}/html`), {
    headers: authHeaders()
  });
  if (!response.ok) {
    await throwApiError(response);
  }
  return artifactHtmlSrcDoc(await response.text());
}

function artifactPluginHeaders(): Headers {
  const headers = authHeaders();
  headers.set("Content-Type", "application/json");
  return headers;
}

export async function deleteArtifactPlugin(
  domain: ArtifactPluginDomain,
  artifactKind: string
): Promise<void> {
  await requestVoid(`/api/artifact-plugins/${pathSegment(domain)}/${pathSegment(artifactKind)}`, {
    method: "DELETE"
  });
}

export function deleteTerminalArtifactPlugin(artifactKind: string): Promise<void> {
  return deleteArtifactPlugin("terminal", artifactKind);
}
