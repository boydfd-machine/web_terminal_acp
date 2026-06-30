import { useI18n } from "../i18n";

export type DetailPanelTab = "overview" | "agent" | "history" | "artifacts" | "git";

type DetailPanelTabsProps = {
  activeTab: DetailPanelTab;
  showGitTab: boolean;
  onTabChange: (tab: DetailPanelTab) => void;
};

export function DetailPanelTabs({ activeTab, showGitTab, onTabChange }: DetailPanelTabsProps) {
  const { t } = useI18n();

  return (
    <div className="detail-panel-tabs" role="tablist" aria-label={t("detail.tabs.window")}>
      <button
        type="button"
        role="tab"
        aria-selected={activeTab === "overview"}
        className={activeTab === "overview" ? "selected" : undefined}
        onClick={() => onTabChange("overview")}
      >
        {t("detail.tabs.overview")}
      </button>
      <button
        type="button"
        role="tab"
        aria-selected={activeTab === "agent"}
        className={activeTab === "agent" ? "selected" : undefined}
        onClick={() => onTabChange("agent")}
      >
        {t("detail.tabs.agent")}
      </button>
      <button
        type="button"
        role="tab"
        aria-selected={activeTab === "history"}
        className={activeTab === "history" ? "selected" : undefined}
        onClick={() => onTabChange("history")}
      >
        {t("detail.tabs.history")}
      </button>
      <button
        type="button"
        role="tab"
        aria-selected={activeTab === "artifacts"}
        className={activeTab === "artifacts" ? "selected" : undefined}
        onClick={() => onTabChange("artifacts")}
      >
        {t("detail.tabs.artifacts")}
      </button>
      {showGitTab && (
        <button
          type="button"
          role="tab"
          aria-selected={activeTab === "git"}
          className={activeTab === "git" ? "selected" : undefined}
          onClick={() => onTabChange("git")}
        >
          Git
        </button>
      )}
    </div>
  );
}
