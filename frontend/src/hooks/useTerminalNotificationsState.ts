import { useCallback, useEffect, useRef, useState } from "react";
import type { QueryClient, UseQueryResult } from "@tanstack/react-query";

import {
  clearTerminalNotifications,
  dismissTerminalNotification,
  markTerminalNotificationRead,
} from "../api";
import { ensureDesktopNotificationPermission, showAgentTaskDesktopNotification } from "../desktopNotifications";
import { useI18n } from "../i18n";
import {
  findNewUnreadNotifications,
  normalizeTerminalNotifications,
  terminalNotificationBody,
  type TerminalNotification,
} from "../terminalNotifications";
import type { TerminalNotificationList } from "../types";

type UseTerminalNotificationsStateArgs = {
  desktopNotificationsEnabled: boolean;
  queryClient: QueryClient;
  selectedClientId: string | null;
  selectedWindowId: string | null;
  terminalNotificationsQuery: UseQueryResult<TerminalNotificationList, Error>;
};

export type TerminalNotificationsState = ReturnType<typeof useTerminalNotificationsState>;

export function useTerminalNotificationsState({
  desktopNotificationsEnabled,
  queryClient,
  selectedClientId,
  selectedWindowId,
  terminalNotificationsQuery,
}: UseTerminalNotificationsStateArgs) {
  const { t } = useI18n();
  const [terminalNotifications, setTerminalNotifications] = useState<TerminalNotification[]>([]);
  const notificationPreviousRef = useRef<TerminalNotification[]>([]);
  const notificationHydratedClientRef = useRef<string | null>(null);

  useEffect(() => {
    if (selectedClientId === null) {
      setTerminalNotifications([]);
      notificationPreviousRef.current = [];
      notificationHydratedClientRef.current = null;
      return;
    }
    if (!terminalNotificationsQuery.isSuccess) {
      if (notificationHydratedClientRef.current !== selectedClientId) {
        setTerminalNotifications([]);
        notificationPreviousRef.current = [];
      }
      return;
    }

    const next = normalizeTerminalNotifications(terminalNotificationsQuery.data?.notifications);
    const previous = notificationPreviousRef.current;
    const hydrated = notificationHydratedClientRef.current === selectedClientId;
    const newlyUnread = hydrated ? findNewUnreadNotifications(previous, next) : [];
    notificationHydratedClientRef.current = selectedClientId;
    notificationPreviousRef.current = next;
    setTerminalNotifications(next);

    if (!desktopNotificationsEnabled || newlyUnread.length === 0) {
      return;
    }

    void ensureDesktopNotificationPermission().then((permission) => {
      if (permission !== "granted") {
        return;
      }

      for (const notification of newlyUnread) {
        showAgentTaskDesktopNotification(
          notification,
          terminalNotificationBody(notification.status, t),
          desktopNotificationsEnabled,
        );
      }
    });
  }, [
    desktopNotificationsEnabled,
    selectedClientId,
    terminalNotificationsQuery.data,
    terminalNotificationsQuery.isSuccess,
    t,
  ]);

  useEffect(() => {
    if (selectedClientId === null || selectedWindowId === null) {
      return;
    }

    if (typeof document !== "undefined" && document.visibilityState !== "visible") {
      return;
    }

    const notification = terminalNotifications.find(
      (item) => item.windowId === selectedWindowId && !item.read,
    );
    if (notification === undefined) {
      return;
    }

    void markTerminalNotificationRead(
      selectedClientId,
      notification.windowId,
      notification.completedAt,
    ).then((result) => {
      const next = normalizeTerminalNotifications(result.notifications);
      notificationPreviousRef.current = next;
      setTerminalNotifications(next);
      queryClient.setQueriesData({ queryKey: ["terminal-notifications", selectedClientId] }, () => result);
    }).catch(() => {});
  }, [queryClient, selectedClientId, selectedWindowId, terminalNotifications]);

  const removeClientNotifications = useCallback((clientId: string) => {
    setTerminalNotifications((current) => current.filter((notification) => notification.clientId !== clientId));
    notificationPreviousRef.current = notificationPreviousRef.current.filter(
      (notification) => notification.clientId !== clientId,
    );
  }, []);

  const removeWindowNotifications = useCallback((windowId: string) => {
    setTerminalNotifications((current) => current.filter((notification) => notification.windowId !== windowId));
  }, []);

  const markNotificationRead = useCallback((notification: TerminalNotification) => {
    void markTerminalNotificationRead(
      notification.clientId,
      notification.windowId,
      notification.completedAt,
    ).then((result) => {
      const next = normalizeTerminalNotifications(result.notifications);
      notificationPreviousRef.current = next;
      setTerminalNotifications(next);
      queryClient.setQueriesData({ queryKey: ["terminal-notifications", notification.clientId] }, () => result);
    }).catch(() => {});
  }, [queryClient]);

  const deleteNotification = useCallback((notification: TerminalNotification) => {
    void dismissTerminalNotification(
      notification.clientId,
      notification.windowId,
      notification.completedAt,
    ).then((result) => {
      const next = normalizeTerminalNotifications(result.notifications);
      notificationPreviousRef.current = next;
      setTerminalNotifications(next);
      queryClient.setQueriesData({ queryKey: ["terminal-notifications", notification.clientId] }, () => result);
    }).catch(() => {});
  }, [queryClient]);

  const clearNotifications = useCallback(() => {
    if (selectedClientId === null) {
      return;
    }

    void clearTerminalNotifications(selectedClientId)
      .then((result) => {
        const next = normalizeTerminalNotifications(result.notifications);
        notificationPreviousRef.current = next;
        setTerminalNotifications(next);
        queryClient.setQueriesData({ queryKey: ["terminal-notifications", selectedClientId] }, () => result);
      })
      .catch(() => {});
  }, [queryClient, selectedClientId]);

  return {
    clearNotifications,
    deleteNotification,
    markNotificationRead,
    removeClientNotifications,
    removeWindowNotifications,
    terminalNotifications,
  };
}
