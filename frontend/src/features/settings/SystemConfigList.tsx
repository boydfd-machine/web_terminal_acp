import { useMemo, useState, type ReactNode } from "react";

import { useI18n, type TranslateFn } from "../../i18n";
import type { AgentConfigItem } from "../../types";
import { UiIcon } from "../../components/UiIcon";

export type SystemConfigSectionId = "skills" | "plugins" | "mcp";
export type SystemStatus = { message: string; kind: "info" | "error" };

function itemOriginLabel(item: AgentConfigItem, t: TranslateFn): string {
  if (item.origin === "system_builtin") {
    return t("settings.system.origin.builtin");
  }
  if (item.origin === "system_config") {
    return t("settings.system.origin.config");
  }
  return t("settings.system.origin.clientDirectory");
}

function normalizedSearch(value: string): string {
  return value.trim().toLocaleLowerCase();
}

function itemMatchesQuery(item: AgentConfigItem, query: string): boolean {
  if (query === "") {
    return true;
  }
  return [
    item.name,
    item.id,
    item.path ?? "",
    item.origin ?? "",
    item.overridden === true ? "overridden" : ""
  ].some((value) => value.toLocaleLowerCase().includes(query));
}

function SystemDownloadIcon() {
  return (
    <svg aria-hidden="true" viewBox="0 0 24 24" className="system-config-row-action-icon">
      <path d="M12 4v11" />
      <path d="m7.5 10.5 4.5 4.5 4.5-4.5" />
      <path d="M5 20h14" />
    </svg>
  );
}

function SystemDeleteIcon() {
  return (
    <svg aria-hidden="true" viewBox="0 0 24 24" className="system-config-row-action-icon">
      <path d="M5 7h14" />
      <path d="M9 7V5h6v2" />
      <path d="M8 10v8" />
      <path d="M16 10v8" />
      <path d="M7 7l1 13h8l1-13" />
    </svg>
  );
}

function SystemItemIcon({ sectionId }: { sectionId: SystemConfigSectionId }) {
  return (
    <span className="system-config-item-icon" aria-hidden="true">
      {sectionId === "skills" ? (
        <svg viewBox="0 0 24 24">
          <path d="M12 3 5 6.5v6.8c0 3.5 2.8 6.3 7 7.7 4.2-1.4 7-4.2 7-7.7V6.5L12 3Z" />
          <path d="m9 12 2 2 4-5" />
        </svg>
      ) : sectionId === "plugins" ? (
        <svg viewBox="0 0 24 24">
          <path d="M8 4h8l4 4v8l-4 4H8l-4-4V8Z" />
          <path d="M9 9h6v6H9Z" />
          <path d="M12 4v5" />
          <path d="M12 15v5" />
        </svg>
      ) : (
        <svg viewBox="0 0 24 24">
          <rect x="5" y="4" width="14" height="6" rx="2" />
          <rect x="5" y="14" width="14" height="6" rx="2" />
          <path d="M8 7h.01" />
          <path d="M8 17h.01" />
          <path d="M12 10v4" />
        </svg>
      )}
    </span>
  );
}

function SystemConfigItemRow({
  item,
  sectionId,
  selected,
  pendingKey,
  onSelect,
  onToggle,
  onDelete,
  onDownload
}: {
  item: AgentConfigItem;
  sectionId: SystemConfigSectionId;
  selected: boolean;
  pendingKey: string | null;
  onSelect: (sectionId: SystemConfigSectionId, itemId: string) => void;
  onToggle: (sectionId: SystemConfigSectionId, itemId: string, enabled: boolean) => void;
  onDelete: (sectionId: SystemConfigSectionId, itemId: string) => void;
  onDownload?: (itemId: string) => void;
}) {
  const { t } = useI18n();
  const key = `${sectionId}:${item.id}`;
  const pending = pendingKey === key;
  const builtIn = item.origin === "system_builtin" || item.overridden === true;
  const canDelete = sectionId !== "plugins" && !builtIn;
  return (
    <li className={`system-config-item${selected ? " selected" : ""}`}>
      <button
        type="button"
        className="system-config-item-content"
        aria-pressed={selected}
        onClick={() => onSelect(sectionId, item.id)}
      >
        <SystemItemIcon sectionId={sectionId} />
        <div className="system-config-item-main">
          <strong>{item.name}</strong>
          <small>{item.id}</small>
          <em>{itemOriginLabel(item, t)}</em>
        </div>
      </button>
      <div className="system-config-item-actions">
        <label className="agent-config-switch">
          <input
            type="checkbox"
            checked={item.enabled}
            disabled={pending}
            aria-label={`${item.enabled ? t("common.disable") : t("common.enable")} ${item.name}`}
            onChange={(event) => onToggle(sectionId, item.id, event.target.checked)}
          />
          <span>{item.enabled ? t("common.enabled") : t("common.disable")}</span>
        </label>
        {sectionId === "skills" && onDownload !== undefined && (
          <button
            type="button"
            className="system-config-icon-button"
            disabled={pending}
            aria-label={`${t("common.download")} ${item.name}`}
            title={t("common.download")}
            onClick={() => onDownload(item.id)}
          >
            <SystemDownloadIcon />
          </button>
        )}
        {canDelete && (
          <button
            type="button"
            className="system-config-icon-button danger"
            disabled={pending}
            aria-label={`${t("common.delete")} ${item.name}`}
            title={t("common.delete")}
            onClick={() => onDelete(sectionId, item.id)}
          >
            <SystemDeleteIcon />
          </button>
        )}
      </div>
    </li>
  );
}

export function SystemConfigList({
  children,
  emptyMessage,
  items,
  pendingKey,
  selectedItemId,
  sectionId,
  status,
  title,
  onSelect,
  onToggle,
  onDelete,
  onDownload
}: {
  children?: ReactNode;
  emptyMessage: string;
  items: AgentConfigItem[];
  pendingKey: string | null;
  selectedItemId: string | null;
  sectionId: SystemConfigSectionId;
  status: SystemStatus | null;
  title: string;
  onSelect: (sectionId: SystemConfigSectionId, itemId: string) => void;
  onToggle: (sectionId: SystemConfigSectionId, itemId: string, enabled: boolean) => void;
  onDelete: (sectionId: SystemConfigSectionId, itemId: string) => void;
  onDownload?: (itemId: string) => void;
}) {
  const { t } = useI18n();
  const [search, setSearch] = useState("");
  const searchQuery = normalizedSearch(search);
  const filteredItems = useMemo(
    () => items.filter((item) => itemMatchesQuery(item, searchQuery)),
    [items, searchQuery]
  );
  const searchActive = searchQuery.length > 0;
  return (
    <aside className="system-config-sidebar">
      <div className="system-config-sidebar-heading">
        <strong>{title}</strong>
        <span>{items.length}</span>
      </div>
      {children ?? null}
      <div className="system-config-list">
        <label className="system-config-search">
          <span>{t("settings.system.searchItems")}</span>
          <div className="system-config-search-row">
            <input
              type="search"
              value={search}
              placeholder={t("settings.system.searchPlaceholder")}
              onChange={(event) => setSearch(event.target.value)}
            />
            {searchActive ? (
              <button
                type="button"
                className="ui-icon-button"
                aria-label={t("common.clear")}
                title={t("common.clear")}
                onClick={() => setSearch("")}
              >
                <UiIcon name="x" />
              </button>
            ) : null}
          </div>
        </label>
        {items.length === 0 ? (
          <p className="muted quick-key-empty-state">{emptyMessage}</p>
        ) : filteredItems.length === 0 ? (
          <p className="muted quick-key-empty-state">{t("settings.system.noMatchingItems")}</p>
        ) : (
          <ul>
            {filteredItems.map((item) => (
              <SystemConfigItemRow
                key={item.id}
                item={item}
                sectionId={sectionId}
                selected={selectedItemId === item.id}
                pendingKey={pendingKey}
                onSelect={onSelect}
                onToggle={onToggle}
                onDelete={onDelete}
                onDownload={sectionId === "skills" ? onDownload : undefined}
              />
            ))}
          </ul>
        )}
        {status !== null && <p className={status.kind === "error" ? "error" : "muted"}>{status.message}</p>}
      </div>
    </aside>
  );
}
