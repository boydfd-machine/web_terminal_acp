import { useI18n } from "../i18n";
import type { ProjectFileTab } from "../projectFileTabs";
import { UiIcon } from "./UiIcon";

export type ProjectFileTabsBarProps = {
  activeKey: string | null;
  tabs: ProjectFileTab[];
  onCloseTab: (key: string) => void;
  onSelectTab: (tab: ProjectFileTab) => void;
};

export function ProjectFileTabsBar({
  activeKey,
  tabs,
  onCloseTab,
  onSelectTab,
}: ProjectFileTabsBarProps) {
  const { t } = useI18n();
  if (tabs.length === 0) {
    return null;
  }

  return (
    <div className="project-file-tabs" role="tablist" aria-label={t("projectFiles.tabs")}>
      {tabs.map((tab) => {
        const selected = tab.key === activeKey;
        return (
          <div key={tab.key} className={selected ? "project-file-tab selected" : "project-file-tab"}>
            <button
              type="button"
              role="tab"
              aria-selected={selected}
              className="project-file-tab-select"
              title={tab.path}
              onClick={() => onSelectTab(tab)}
            >
              <UiIcon name="file" />
              <span>{tab.name}</span>
            </button>
            <button
              type="button"
              className="project-file-tab-close ui-icon-button"
              aria-label={t("projectFiles.closeTab", { name: tab.name })}
              title={t("projectFiles.closeTab", { name: tab.name })}
              onClick={(event) => {
                event.stopPropagation();
                onCloseTab(tab.key);
              }}
            >
              <UiIcon name="x" />
            </button>
          </div>
        );
      })}
    </div>
  );
}
