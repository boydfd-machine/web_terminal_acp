import type { TranslateFn } from "./i18n";
import type { TerminalNotification as BackendTerminalNotification } from "./types";

export type TerminalNotification = {
  id: string;
  clientId: string;
  windowId: string;
  windowTitle: string;
  completedAt: string;
  status: "FINISHED" | "ABORTED" | "FAILED";
  read: boolean;
};

export function terminalNotificationBody(status: TerminalNotification["status"], t?: TranslateFn): string {
  if (status === "ABORTED") {
    return t?.("notifications.body.aborted") ?? "Agent 可能已中断";
  }
  if (status === "FAILED") {
    return t?.("notifications.body.failed") ?? "Agent 运行失败";
  }
  return t?.("notifications.body.finished") ?? "Agent 任务已完成";
}

export function normalizeTerminalNotifications(
  notifications: BackendTerminalNotification[] | undefined
): TerminalNotification[] {
  if (!notifications) {
    return [];
  }

  return notifications.map((notification) => ({
    id: notification.id,
    clientId: notification.client_id,
    windowId: notification.window_id,
    windowTitle: notification.window_title,
    completedAt: notification.completed_at,
    status: notification.status,
    read: notification.read
  }));
}

export function findNewUnreadNotifications(
  previous: TerminalNotification[],
  next: TerminalNotification[]
): TerminalNotification[] {
  const previousUnreadIds = new Set(
    previous.filter((notification) => !notification.read).map((notification) => notification.id)
  );
  return next.filter((notification) => !notification.read && !previousUnreadIds.has(notification.id));
}
