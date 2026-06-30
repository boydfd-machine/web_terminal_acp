import { useCallback, useEffect, useRef } from "react";

import { useI18n } from "../i18n";
import type { TerminalNotification } from "../terminalNotifications";
import { UiIcon } from "./UiIcon";
import { useOverlayFocus } from "./useOverlayFocus";

type NotificationCenterProps = {
  isOpen: boolean;
  notifications: TerminalNotification[];
  onClose: () => void;
  onSelectNotification: (notification: TerminalNotification) => void;
  onDeleteNotification: (notification: TerminalNotification) => void;
  onClearNotifications: () => void;
};

export function NotificationCenter({
  isOpen,
  notifications,
  onClose,
  onSelectNotification,
  onDeleteNotification,
  onClearNotifications
}: NotificationCenterProps) {
  const { t } = useI18n();
  const panelRef = useRef<HTMLDivElement | null>(null);
  const unreadCount = notifications.filter((notification) => !notification.read).length;
  const handleEscape = useCallback(() => {
    onClose();
  }, [onClose]);

  useOverlayFocus({
    isOpen,
    ref: panelRef,
    onEscape: handleEscape
  });

  useEffect(() => {
    if (!isOpen) {
      return;
    }

    const handlePointerDown = (event: PointerEvent) => {
      const target = event.target;
      if (!(target instanceof Node) || panelRef.current?.contains(target)) {
        return;
      }
      onClose();
    };

    window.addEventListener("pointerdown", handlePointerDown);
    return () => {
      window.removeEventListener("pointerdown", handlePointerDown);
    };
  }, [isOpen, onClose]);

  if (!isOpen) {
    return null;
  }

  return (
    <div className="notification-center-backdrop" role="presentation">
      <div ref={panelRef} className="notification-center" role="dialog" aria-modal="true" aria-label={t("notifications.center")}>
        <div className="notification-center-header">
          <div>
            <h2>{t("notifications.center")}</h2>
            <p className="muted">
              {unreadCount > 0 ? t("notifications.unread", { count: unreadCount }) : t("notifications.noUnread")}
            </p>
          </div>
          <div className="notification-center-actions">
            <button
              type="button"
              className="ui-icon-button"
              disabled={notifications.length === 0}
              aria-label={t("notifications.clearAll")}
              title={t("notifications.clearAll")}
              onClick={onClearNotifications}
            >
              <UiIcon name="trash" />
            </button>
            <button
              type="button"
              className="ui-icon-button"
              aria-label={t("notifications.close")}
              title={t("notifications.close")}
              onClick={onClose}
            >
              <UiIcon name="x" />
            </button>
          </div>
        </div>

        {notifications.length === 0 ? (
          <p className="notification-center-empty">
            {t("notifications.empty")}
          </p>
        ) : (
          <ul className="notification-center-list">
            {notifications.map((notification) => (
              <li
                key={notification.id}
                className={notification.read ? "notification-item read" : "notification-item unread"}
              >
                <button
                  type="button"
                  className="notification-item-main"
                  onClick={() => onSelectNotification(notification)}
                >
                  <span className="notification-item-title">{notification.windowTitle}</span>
                  <span className="notification-item-body">
                    {notification.status === "ABORTED"
                      ? t("notifications.body.aborted")
                      : notification.status === "FAILED"
                        ? t("notifications.body.failed")
                        : t("notifications.body.finished")}
                  </span>
                  <span className="notification-item-time">
                    {new Date(notification.completedAt).toLocaleString()}
                  </span>
                </button>
                <button
                  type="button"
                  className="notification-item-delete"
                  aria-label={t("notifications.deleteNamed", { title: notification.windowTitle })}
                  title={t("notifications.delete")}
                  onClick={() => onDeleteNotification(notification)}
                >
                  <UiIcon name="trash" className="notification-trash-icon" />
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}

export function NotificationBellButton({
  unreadCount,
  isOpen,
  onClick
}: {
  unreadCount: number;
  isOpen: boolean;
  onClick: () => void;
}) {
  const { t } = useI18n();
  const className = [
    "notification-bell",
    isOpen ? "active" : "",
    unreadCount > 0 ? "unread" : ""
  ].filter(Boolean).join(" ");

  return (
    <button
      type="button"
      className={className}
      data-onboarding-id="notification-bell"
      aria-expanded={isOpen}
      aria-label={unreadCount > 0 ? t("notifications.bellUnread", { count: unreadCount }) : t("notifications.center")}
      onClick={onClick}
    >
      <NotificationBellIcon />
      {unreadCount > 0 && <span className="notification-bell-badge">{unreadCount}</span>}
    </button>
  );
}

export function TerminalUnreadDot({ visible }: { visible: boolean }) {
  const { t } = useI18n();

  if (!visible) {
    return null;
  }

  return <span className="terminal-unread-dot" aria-label={t("notifications.new")} />;
}

function NotificationBellIcon() {
  return (
    <svg
      className="notification-bell-icon"
      aria-hidden="true"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d="M18 8a6 6 0 0 0-12 0c0 6.2-2.2 7.3-3 8h18c-.8-.7-3-1.8-3-8Z" />
      <path d="M10 20a2.4 2.4 0 0 0 4 0" />
      <path className="notification-bell-shine" d="M19.4 3.6 21 2m.2 5h-2.1" />
    </svg>
  );
}
