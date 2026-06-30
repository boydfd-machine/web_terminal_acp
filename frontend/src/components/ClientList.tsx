import { useState } from "react";

import type { TranslateFn } from "../i18n";
import { useI18n } from "../i18n";
import type { Client } from "../types";

type ClientListProps = {
  clients: Client[];
  selectedClientId: string | null;
  onSelectClient: (clientId: string) => void;
  onUpdateClient: (clientId: string) => void;
  onReregisterClient: (client: Client) => void;
  onDeleteClient: (client: Client) => void;
  updatingClientId: string | null;
  reregisteringClientId: string | null;
  deletingClientId: string | null;
};

function formatHostname(client: Client, t: TranslateFn): string {
  return client.hostname ?? t("client.list.noHostname");
}

function formatVersion(client: Client, t: TranslateFn): string {
  if (!client.version) {
    return t("client.list.noVersion");
  }
  return client.version.startsWith("v") ? client.version : `v${client.version}`;
}

function formatLastUpdate(client: Client, t: TranslateFn): string {
  if (!client.last_update_at) {
    return t("client.list.noUpdateTime");
  }

  const updatedAt = new Date(client.last_update_at);
  if (Number.isNaN(updatedAt.getTime())) {
    return t("client.list.unknown");
  }

  return updatedAt.toLocaleString(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
    hour12: false
  });
}

export function ClientList({
  clients,
  selectedClientId,
  onSelectClient,
  onUpdateClient,
  onReregisterClient,
  onDeleteClient,
  updatingClientId,
  reregisteringClientId,
  deletingClientId
}: ClientListProps) {
  const { t } = useI18n();
  const [hoveredClientId, setHoveredClientId] = useState<string | null>(null);
  const [focusedClientId, setFocusedClientId] = useState<string | null>(null);

  const dismissClientActions = (clientId: string): void => {
    setHoveredClientId((currentClientId) => (currentClientId === clientId ? null : currentClientId));
    setFocusedClientId((currentClientId) => (currentClientId === clientId ? null : currentClientId));
  };

  if (clients.length === 0) {
    return <p className="muted client-empty">{t("client.list.empty")}</p>;
  }

  return (
    <div className="client-cards">
      {clients.map((client) => {
        const isSelected = client.id === selectedClientId;
        const isDeleting = deletingClientId === client.id;
        const isUpdating = updatingClientId === client.id;
        const isReregistering = reregisteringClientId === client.id;
        const actionsOpen = hoveredClientId === client.id || focusedClientId === client.id;
        return (
          <div
            key={client.id}
            aria-current={isSelected ? "true" : undefined}
            className={isSelected ? "client-card selected" : "client-card"}
            onMouseEnter={() => setHoveredClientId(client.id)}
            onMouseLeave={() => setHoveredClientId((currentClientId) => (
              currentClientId === client.id ? null : currentClientId
            ))}
            onFocus={() => setFocusedClientId(client.id)}
            onBlur={(event) => {
              const nextTarget = event.relatedTarget;
              if (nextTarget instanceof Node && event.currentTarget.contains(nextTarget)) {
                return;
              }
              setFocusedClientId((currentClientId) => (
                currentClientId === client.id ? null : currentClientId
              ));
            }}
          >
            <button type="button" className="client-card-main" onClick={() => onSelectClient(client.id)}>
              <span className="client-card-header">
                <strong>{client.name}</strong>
                <span className={`client-status ${client.status.toLowerCase()}`}>{client.status}</span>
              </span>
              {isSelected && (
                  <span className="client-details">
                    <span className="client-meta">
                      <span>{client.runtime}</span>
                    <span>{formatHostname(client, t)}</span>
                  </span>
                  <span className="client-version">{formatVersion(client, t)}</span>
                  <span className="client-update-time">{formatLastUpdate(client, t)}</span>
                </span>
              )}
            </button>
            {isSelected && client.runtime === "remote" && actionsOpen && (
              <span
                className="client-actions-menu"
                role="menu"
                aria-label={t("client.actions", { name: client.name })}
                data-onboarding-id="remote-client-update"
              >
                <button
                  type="button"
                  role="menuitem"
                  disabled={client.status !== "ONLINE" || isUpdating || isDeleting}
                  onClick={() => {
                    onUpdateClient(client.id);
                    dismissClientActions(client.id);
                  }}
                >
                  {isUpdating ? t("client.updating") : t("client.update")}
                </button>
                <button
                  type="button"
                  role="menuitem"
                  className="client-card-reregister"
                  disabled={isReregistering || isUpdating || isDeleting}
                  onClick={() => {
                    onReregisterClient(client);
                    dismissClientActions(client.id);
                  }}
                >
                  {isReregistering ? t("client.reregistering") : t("client.reregister")}
                </button>
                <button
                  type="button"
                  role="menuitem"
                  className="client-card-delete"
                  disabled={isDeleting}
                  onClick={() => {
                    onDeleteClient(client);
                  }}
                >
                  {isDeleting ? t("client.deleting") : t("common.delete")}
                </button>
              </span>
            )}
          </div>
        );
      })}
    </div>
  );
}
