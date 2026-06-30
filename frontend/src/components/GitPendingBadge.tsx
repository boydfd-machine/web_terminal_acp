import { useI18n } from "../i18n";

type GitPendingBadgeProps = {
  visible: boolean;
};

export function GitPendingBadge({ visible }: GitPendingBadgeProps) {
  const { t } = useI18n();

  if (!visible) {
    return null;
  }

  return (
    <span className="git-pending-badge" title={t("git.pending.title")} aria-label={t("git.pending.label")}>
      G
    </span>
  );
}
