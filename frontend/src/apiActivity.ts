import type { ClientWindowsActivity, GitWorktreeRunList, TerminalNotificationList, WorkStatus, WorkStatusState } from "./types";
import { pathSegment, request } from "./apiCore";
import type { TerminalTimeRange } from "./terminalTimeRange";

export function fetchWindowActivity(
  clientId: string,
  options?: { includeRuntimeTags?: boolean; range?: TerminalTimeRange; projectPath?: string | null }
): Promise<ClientWindowsActivity> {
  const params = new URLSearchParams();
  if (options?.includeRuntimeTags) {
    params.set("include_runtime_tags", "true");
  }
  if (options?.range !== undefined) {
    params.set("range", options.range);
  }
  if (options?.projectPath) {
    params.set("project_path", options.projectPath);
  }
  const query = params.toString();
  const suffix = query ? `?${query}` : "";
  return request<ClientWindowsActivity>(
    `/api/clients/${pathSegment(clientId)}/windows/activity${suffix}`
  );
}

export function fetchTerminalNotifications(clientId: string): Promise<TerminalNotificationList> {
  return request<TerminalNotificationList>(
    `/api/clients/${pathSegment(clientId)}/terminal-notifications`
  );
}

export function updateManualWorkStatus(
  clientId: string,
  windowId: string,
  state: WorkStatusState | null
): Promise<WorkStatus> {
  return request<WorkStatus>(
    `/api/clients/${pathSegment(clientId)}/windows/${pathSegment(windowId)}/work-status`,
    {
      method: "PATCH",
      body: JSON.stringify({ state })
    }
  );
}

export function markTerminalNotificationRead(
  clientId: string,
  windowId: string,
  completedAt: string
): Promise<TerminalNotificationList> {
  return request<TerminalNotificationList>(
    `/api/clients/${pathSegment(clientId)}/terminal-notifications/read`,
    {
      method: "POST",
      body: JSON.stringify({
        window_id: windowId,
        completed_at: completedAt
      })
    }
  );
}

export function dismissTerminalNotification(
  clientId: string,
  windowId: string,
  completedAt: string
): Promise<TerminalNotificationList> {
  return request<TerminalNotificationList>(
    `/api/clients/${pathSegment(clientId)}/terminal-notifications/dismiss`,
    {
      method: "POST",
      body: JSON.stringify({
        window_id: windowId,
        completed_at: completedAt
      })
    }
  );
}

export function clearTerminalNotifications(clientId: string): Promise<TerminalNotificationList> {
  return request<TerminalNotificationList>(
    `/api/clients/${pathSegment(clientId)}/terminal-notifications`,
    {
      method: "DELETE"
    }
  );
}

export function fetchGitRuns(clientId: string, windowId: string, limit = 50, offset = 0): Promise<GitWorktreeRunList> {
  const params = new URLSearchParams({
    limit: String(limit),
    offset: String(offset)
  });
  return request<GitWorktreeRunList>(
    `/api/clients/${pathSegment(clientId)}/windows/${pathSegment(windowId)}/git-runs?${params.toString()}`
  );
}
