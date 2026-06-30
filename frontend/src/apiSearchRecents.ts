import type { GlobalTerminalRecentPage, ProjectSummary, SearchResponse, TerminalRecent, TerminalRecentPage, VirtualWindow } from "./types";
import { pathSegment, request } from "./apiCore";
import type { SummaryOutputLanguage } from "./userPreferences";

export type RetrySummaryPayload = { allow_title_folder_override: boolean };

export function search(clientId: string, query: string): Promise<SearchResponse> {
  return request<SearchResponse>(`/api/clients/${pathSegment(clientId)}/search?q=${encodeURIComponent(query)}`);
}

export function fetchTerminalRecents(
  clientId: string,
  page = 1,
  pageSize = 20,
  query = ""
): Promise<TerminalRecentPage> {
  const params = new URLSearchParams({
    page: String(page),
    page_size: String(pageSize)
  });
  const trimmedQuery = query.trim();
  if (trimmedQuery.length > 0) {
    params.set("q", trimmedQuery);
  }
  return request<TerminalRecentPage>(
    `/api/clients/${pathSegment(clientId)}/terminal-recents?${params.toString()}`
  );
}

export function fetchGlobalTerminalRecents(
  page = 1,
  pageSize = 20,
  query = ""
): Promise<GlobalTerminalRecentPage> {
  const params = new URLSearchParams({
    page: String(page),
    page_size: String(pageSize)
  });
  const trimmedQuery = query.trim();
  if (trimmedQuery.length > 0) {
    params.set("q", trimmedQuery);
  }
  return request<GlobalTerminalRecentPage>(
    `/api/terminal-recents?${params.toString()}`
  );
}

export function recordTerminalRecent(
  clientId: string,
  payload: Pick<TerminalRecent, "window_id" | "title">
): Promise<TerminalRecent> {
  return request<TerminalRecent>(`/api/clients/${pathSegment(clientId)}/terminal-recents`, {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

export function fetchProjectSummaries(clientId: string): Promise<ProjectSummary[]> {
  return request<ProjectSummary[]>(`/api/clients/${pathSegment(clientId)}/project-summaries`);
}

export function summarizeProject(
  clientId: string,
  projectPath: string,
  outputLanguage: SummaryOutputLanguage
): Promise<ProjectSummary> {
  return request<ProjectSummary>(`/api/clients/${pathSegment(clientId)}/project-summaries/summarize`, {
    method: "POST",
    body: JSON.stringify({
      project_path: projectPath,
      output_language: outputLanguage
    })
  });
}
