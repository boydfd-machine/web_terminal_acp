import {
  PROJECT_TODO_BOARD_ALL,
  type ProjectTodoBoardFilters,
  type ProjectTodoBoardGroupingMode,
  type ProjectTodoColumnViewMode
} from "../features/projectTodos/projectTodoBoardModel";
import { useI18n, type TranslateFn } from "../i18n";
import {
  PROJECT_TODO_BOARD_COLUMN_ORDER,
  projectTodoBoardColumnLabel,
  type ProjectTodoBoardColumn
} from "./projectTodoDisplay";
import type { ProjectTodoViewSettings } from "./ProjectTodoBoardTypes";
import { UiIcon } from "./UiIcon";
import type { ProjectTodoListItem } from "../types";

export function ProjectTodoBoardToolbar({
  activeFilterCount,
  childFilterParent,
  filterOptions,
  filters,
  groupingMode,
  settingsOpen,
  viewSettings,
  onCollapseAll,
  onCreateTodo,
  onExpandAll,
  onGroupingModeChange,
  onResetFilters,
  onResetChildFilter,
  onSettingsOpenChange,
  onUpdateFilter,
  onViewSettingsChange
}: {
  activeFilterCount: number;
  childFilterParent: ProjectTodoListItem | null;
  filterOptions: { assignees: string[]; tags: string[] };
  filters: ProjectTodoBoardFilters;
  groupingMode: ProjectTodoBoardGroupingMode;
  settingsOpen: boolean;
  viewSettings: ProjectTodoViewSettings;
  onCollapseAll: () => void;
  onCreateTodo: () => void;
  onExpandAll: () => void;
  onGroupingModeChange: (mode: ProjectTodoBoardGroupingMode) => void;
  onResetFilters: () => void;
  onResetChildFilter: () => void;
  onSettingsOpenChange: (open: boolean) => void;
  onUpdateFilter: <K extends keyof ProjectTodoBoardFilters>(key: K, value: ProjectTodoBoardFilters[K]) => void;
  onViewSettingsChange: (settings: ProjectTodoViewSettings) => void;
}) {
  const { t } = useI18n();
  return (
    <div className="project-todo-board-toolbar">
      <div className="project-todo-board-filters">
        <label>
          <span>{t("projectTodo.board.group")}</span>
          <select value={groupingMode} onChange={(event) => onGroupingModeChange(event.target.value as ProjectTodoBoardGroupingMode)}>
            <option value="tree">{t("projectTodo.board.group.tree")}</option>
            <option value="flat">{t("projectTodo.board.group.normal")}</option>
          </select>
        </label>
        <label>
          <span>{t("projectTodo.board.status")}</span>
          <select
            value={filters.status}
            onChange={(event) => onUpdateFilter("status", event.target.value as ProjectTodoBoardFilters["status"])}
          >
            <option value={PROJECT_TODO_BOARD_ALL}>{t("projectTodo.board.all")}</option>
            {PROJECT_TODO_BOARD_COLUMN_ORDER.map((column) => (
              <option key={column} value={column}>{projectTodoBoardColumnLabel(column, t)}</option>
            ))}
          </select>
        </label>
        <label>
          <span>{t("projectTodo.board.owner")}</span>
          <select value={filters.assignee} onChange={(event) => onUpdateFilter("assignee", event.target.value)}>
            <option value={PROJECT_TODO_BOARD_ALL}>{t("projectTodo.board.all")}</option>
            {filterOptions.assignees.map((assignee) => (
              <option key={assignee} value={assignee}>{assignee}</option>
            ))}
          </select>
        </label>
        <label>
          <span>{t("projectTodo.board.tag")}</span>
          <select value={filters.tag} onChange={(event) => onUpdateFilter("tag", event.target.value)}>
            <option value={PROJECT_TODO_BOARD_ALL}>{t("projectTodo.board.all")}</option>
            {filterOptions.tags.map((tag) => (
              <option key={tag} value={tag}>{tag}</option>
            ))}
          </select>
        </label>
        <label className="project-todo-board-search">
          <span>{t("projectTodo.board.search")}</span>
          <input
            type="search"
            value={filters.search}
            placeholder={t("projectTodo.board.searchPlaceholder")}
            onChange={(event) => onUpdateFilter("search", event.target.value)}
          />
        </label>
        <button
          type="button"
          className="ui-icon-button"
          aria-label={t("projectTodo.board.clearFilters")}
          title={t("projectTodo.board.clearFilters")}
          onClick={onResetFilters}
          disabled={activeFilterCount === 0}
        >
          <UiIcon name="filter-x" />
        </button>
        {childFilterParent !== null && (
          <button
            type="button"
            className="project-todo-board-child-filter"
            title={t("projectTodo.board.clearChildFilter")}
            onClick={onResetChildFilter}
          >
            <UiIcon name="list-tree" />
            <span>{t("projectTodo.board.childrenOf", { title: childFilterParent.title })}</span>
            <UiIcon name="x" />
          </button>
        )}
      </div>
      <div className="project-todo-board-actions">
        <button
          type="button"
          className="ui-icon-button"
          aria-label={t("projectTodo.board.expandAll")}
          title={t("projectTodo.board.expandAll")}
          onClick={onExpandAll}
        >
          <UiIcon name="chevron-down" />
        </button>
        <button
          type="button"
          className="ui-icon-button"
          aria-label={t("projectTodo.board.collapseAll")}
          title={t("projectTodo.board.collapseAll")}
          onClick={onCollapseAll}
        >
          <UiIcon name="chevron-up" />
        </button>
        <div className="project-todo-board-settings">
          <button
            type="button"
            className="ui-icon-button"
            aria-expanded={settingsOpen}
            aria-controls="project-todo-board-view-settings"
            aria-label={t("projectTodo.board.viewSettings")}
            title={t("projectTodo.board.viewSettings")}
            onClick={() => onSettingsOpenChange(!settingsOpen)}
          >
            <UiIcon name="settings" />
          </button>
          {settingsOpen && (
            <div id="project-todo-board-view-settings" className="project-todo-board-settings-popover">
              {(["progress", "totals", "participants"] as const).map((key) => (
                <label key={key}>
                  <input
                    type="checkbox"
                    checked={viewSettings[key]}
                    onChange={(event) => onViewSettingsChange({ ...viewSettings, [key]: event.target.checked })}
                  />
                  <span>{settingLabel(key, t)}</span>
                </label>
              ))}
            </div>
          )}
        </div>
        <button type="button" className="project-todo-board-new-button" onClick={onCreateTodo}>{t("projectTodo.board.newTask")}</button>
      </div>
    </div>
  );
}

export function ColumnViewToggle({
  column,
  value,
  onChange
}: {
  column: ProjectTodoBoardColumn;
  value: ProjectTodoColumnViewMode;
  onChange: (value: ProjectTodoColumnViewMode) => void;
}) {
  const { t } = useI18n();
  const columnLabel = projectTodoBoardColumnLabel(column, t);
  const isTreeView = value === "tree";
  return (
    <label className="project-todo-column-view-toggle">
      <span className={`project-todo-column-view-toggle-label ${isTreeView ? "" : "active"}`}>
        {t("projectTodo.board.cards")}
      </span>
      <input
        type="checkbox"
        role="switch"
        aria-label={t("projectTodo.board.columnView", { label: columnLabel })}
        checked={isTreeView}
        onChange={(event) => onChange(event.currentTarget.checked ? "tree" : "cards")}
      />
      <span className={`project-todo-column-view-toggle-label ${isTreeView ? "active" : ""}`}>
        {t("projectTodo.board.tree")}
      </span>
    </label>
  );
}

export function settingLabel(key: keyof ProjectTodoViewSettings, t?: TranslateFn): string {
  if (key === "progress") {
    return t?.("projectTodo.board.setting.progress") ?? "Progress";
  }
  if (key === "totals") {
    return t?.("projectTodo.board.setting.totals") ?? "Task totals";
  }
  return t?.("projectTodo.board.setting.participants") ?? "Participants";
}
