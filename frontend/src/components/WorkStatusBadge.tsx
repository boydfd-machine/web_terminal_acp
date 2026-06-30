import { useI18n } from "../i18n";
import type { WorkStatus } from "../types";

type WorkStatusBadgeProps = {
  status: WorkStatus;
};

function formatDateTime(value: string | null | undefined, fallback: string): string {
  if (value == null) {
    return fallback;
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return date.toLocaleString();
}

export function WorkStatusBadge({ status }: WorkStatusBadgeProps) {
  const { t } = useI18n();
  const className = `work-status-badge ${status.color}`;
  const title = t("workStatus.recentActivity", {
    time: formatDateTime(status.last_activity_at, t("workStatus.noActivity"))
  });

  return (
    <span className={className} title={title}>
      <span aria-hidden="true" />
      {status.label}
    </span>
  );
}

export function WorkStatusDot({ status }: WorkStatusBadgeProps) {
  const { t } = useI18n();
  const className = `work-status-dot ${status.color}`;
  const title = t("workStatus.labelWithRecent", {
    label: status.label,
    time: formatDateTime(status.last_activity_at, t("workStatus.noActivity"))
  });

  return <span className={className} title={title} aria-label={status.label} />;
}
