import { useI18n, type TranslateFn } from "../i18n";
import type { SystemMcpDetail, SystemSkillDetail } from "../types";
import { UiIcon } from "./UiIcon";

function itemOriginLabel(origin: "system_builtin" | "system_config", t: TranslateFn): string {
  return origin === "system_builtin" ? t("settings.system.origin.builtin") : t("settings.system.origin.config");
}

export function SystemDetailHeader({
  detail,
  onReset
}: {
  detail: SystemSkillDetail | SystemMcpDetail;
  onReset: () => void;
}) {
  const { t } = useI18n();
  const canReset = detail.origin === "system_builtin" || detail.overridden;

  return (
    <header className="system-config-detail-header">
      <div>
        <strong>{detail.name}</strong>
        <small>{detail.id}</small>
      </div>
      <div className="system-config-detail-meta">
        <span>{detail.enabled ? t("common.enabled") : t("common.disabled")}</span>
        <span>{itemOriginLabel(detail.origin, t)}</span>
        {detail.overridden && <span>{t("settings.system.overridden")}</span>}
        <span>{detail.editable ? t("settings.artifacts.editable") : t("settings.artifacts.readOnly")}</span>
        {canReset && (
          <button
            type="button"
            className="system-config-icon-button"
            aria-label={t("settings.system.resetToFactory")}
            title={t("settings.system.resetToFactory")}
            onClick={onReset}
          >
            <UiIcon name="rotate-ccw" />
          </button>
        )}
      </div>
    </header>
  );
}
