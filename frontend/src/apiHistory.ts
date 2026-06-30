import type { AgentRecordSearchResponse, CommandHistory, WindowTitleHistory, VirtualWindow } from "./types";
import { pathSegment, request } from "./apiCore";
import type { RetrySummaryPayload } from "./apiSearchRecents";

export function fetchCommandHistory(clientId: string, windowId: string, limit = 100, offset = 0): Promise<CommandHistory> {
  const params = new URLSearchParams({
    commands_limit: String(limit),
    commands_offset: String(offset)
  });
  return request<CommandHistory>(
    `/api/clients/${pathSegment(clientId)}/windows/${pathSegment(windowId)}/command-history?${params.toString()}`
  );
}

export function fetchWindowTitleHistory(
  clientId: string,
  windowId: string,
  limit = 100,
  offset = 0
): Promise<WindowTitleHistory> {
  const params = new URLSearchParams({
    limit: String(limit),
    offset: String(offset)
  });
  return request<WindowTitleHistory>(
    `/api/clients/${pathSegment(clientId)}/windows/${pathSegment(windowId)}/title-history?${params.toString()}`
  );
}

export function searchWindowAgentRecord(
  clientId: string,
  windowId: string,
  query: string,
  limit = 25,
  offset = 0
): Promise<AgentRecordSearchResponse> {
  const params = new URLSearchParams({
    q: query,
    limit: String(limit),
    offset: String(offset)
  });
  return request<AgentRecordSearchResponse>(
    `/api/clients/${pathSegment(clientId)}/windows/${pathSegment(windowId)}/agent-record/search?${params.toString()}`
  );
}

export function searchAgentRecords(
  clientId: string,
  query: string,
  limit = 25,
  offset = 0
): Promise<AgentRecordSearchResponse> {
  const params = new URLSearchParams({
    q: query,
    limit: String(limit),
    offset: String(offset)
  });
  return request<AgentRecordSearchResponse>(
    `/api/clients/${pathSegment(clientId)}/agent-record/search?${params.toString()}`
  );
}

export function retrySummary(
  clientId: string,
  windowId: string,
  payload?: RetrySummaryPayload
): Promise<VirtualWindow> {
  return request<VirtualWindow>(
    `/api/clients/${pathSegment(clientId)}/windows/${pathSegment(windowId)}/summary_jobs`,
    {
      method: "POST",
      ...(payload ? { body: JSON.stringify(payload) } : {})
    }
  );
}
