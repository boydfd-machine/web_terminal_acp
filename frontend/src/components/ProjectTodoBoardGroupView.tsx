import { useEffect, useRef, type DragEvent, type RefObject } from "react";

import {
  buildProjectTodoTree,
  type ProjectTodoBoardGroup,
  type ProjectTodoColumnViewMode
} from "../features/projectTodos/projectTodoBoardModel";
import { useI18n } from "../i18n";
import {
  PROJECT_TODO_BOARD_COLUMN_ORDER,
  projectTodoBoardColumnLabel,
  type ProjectTodoBoardColumn
} from "./projectTodoDisplay";
import { ColumnViewToggle } from "./ProjectTodoBoardToolbar";
import { ProjectTodoCard, ProjectTodoTree } from "./ProjectTodoBoardCards";
import { hasProjectTodoDragData } from "./ProjectTodoBoardDrag";
import type {
  ProjectTodoCardSharedProps,
  ProjectTodoViewSettings
} from "./ProjectTodoBoardTypes";

export function ProjectTodoBoardGroupView({
  cardSharedProps,
  collapsed,
  collapsedTreeNodeKeys,
  columnViewModes,
  dropColumn,
  draggingTodoId,
  group,
  viewSettings,
  onColumnViewModeChange,
  onDropColumn,
  onDropColumnChange,
  onDropTodoId,
  onGroupCollapsedChange,
  onResetDragState,
  onTreeNodeCollapsedChange
}: {
  cardSharedProps: ProjectTodoCardSharedProps;
  collapsed: boolean;
  collapsedTreeNodeKeys: Set<string>;
  columnViewModes: Record<ProjectTodoBoardColumn, ProjectTodoColumnViewMode>;
  dropColumn: ProjectTodoBoardColumn | null;
  draggingTodoId: string | null;
  group: ProjectTodoBoardGroup;
  viewSettings: ProjectTodoViewSettings;
  onColumnViewModeChange: (column: ProjectTodoBoardColumn, mode: ProjectTodoColumnViewMode) => void;
  onDropColumn: (todoId: string, column: ProjectTodoBoardColumn) => void;
  onDropColumnChange: (column: ProjectTodoBoardColumn | null) => void;
  onDropTodoId: (event: DragEvent<HTMLElement>) => string;
  onGroupCollapsedChange: () => void;
  onResetDragState: () => void;
  onTreeNodeCollapsedChange: (nodeKey: string) => void;
}) {
  const { t } = useI18n();
  const boardScrollRef = useRef<HTMLDivElement | null>(null);
  return (
    <section className="project-todo-board-group" aria-label={t("projectTodo.board.groupLabel", { label: group.label })}>
      <header className="project-todo-board-group-header">
        <button
          type="button"
          className="project-todo-board-group-toggle"
          aria-expanded={!collapsed}
          onClick={onGroupCollapsedChange}
        >
          <ChevronIcon collapsed={collapsed} />
          <strong>{group.label}</strong>
          <span>{group.total}</span>
        </button>
        <ProjectTodoGroupSummary group={group} settings={viewSettings} />
      </header>
      {!collapsed && (
        <div className="project-todo-board" ref={boardScrollRef}>
          {PROJECT_TODO_BOARD_COLUMN_ORDER.map((column) => (
            <ProjectTodoBoardColumnView
              key={column}
              boardScrollRef={boardScrollRef}
              cardSharedProps={cardSharedProps}
              collapsedTreeNodeKeys={collapsedTreeNodeKeys}
              column={column}
              dropColumn={dropColumn}
              draggingTodoId={draggingTodoId}
              group={group}
              viewMode={columnViewModes[column]}
              onDropColumn={onDropColumn}
              onDropColumnChange={onDropColumnChange}
              onDropTodoId={onDropTodoId}
              onResetDragState={onResetDragState}
              onTreeNodeCollapsedChange={onTreeNodeCollapsedChange}
              onViewModeChange={(mode) => onColumnViewModeChange(column, mode)}
            />
          ))}
        </div>
      )}
    </section>
  );
}

function ProjectTodoBoardColumnView({
  boardScrollRef,
  cardSharedProps,
  collapsedTreeNodeKeys,
  column,
  dropColumn,
  draggingTodoId,
  group,
  viewMode,
  onDropColumn,
  onDropColumnChange,
  onDropTodoId,
  onResetDragState,
  onTreeNodeCollapsedChange,
  onViewModeChange
}: {
  boardScrollRef: RefObject<HTMLDivElement>;
  cardSharedProps: ProjectTodoCardSharedProps;
  collapsedTreeNodeKeys: Set<string>;
  column: ProjectTodoBoardColumn;
  dropColumn: ProjectTodoBoardColumn | null;
  draggingTodoId: string | null;
  group: ProjectTodoBoardGroup;
  viewMode: ProjectTodoColumnViewMode;
  onDropColumn: (todoId: string, column: ProjectTodoBoardColumn) => void;
  onDropColumnChange: (column: ProjectTodoBoardColumn | null) => void;
  onDropTodoId: (event: DragEvent<HTMLElement>) => string;
  onResetDragState: () => void;
  onTreeNodeCollapsedChange: (nodeKey: string) => void;
  onViewModeChange: (mode: ProjectTodoColumnViewMode) => void;
}) {
  const { t } = useI18n();
  const cardListRef = useRef<HTMLDivElement | null>(null);
  const columnTodos = group.columns.get(column) ?? [];
  const cardCountLabelKey = columnTodos.length === 1
    ? "projectTodo.board.cardCountOne"
    : "projectTodo.board.cardCount";
  const treeNodes = buildProjectTodoTree(columnTodos, group);
  const columnLabel = projectTodoBoardColumnLabel(column, t);
  const acceptsDrop = column !== "PENDING";
  const className = [
    "project-todo-column",
    acceptsDrop && draggingTodoId !== null ? "drop-available" : "",
    dropColumn === column ? "drop-target" : ""
  ].filter(Boolean).join(" ");
  useEffect(() => {
    const cardList = cardListRef.current;
    if (cardList === null) {
      return undefined;
    }
    const handleCardListWheel = (event: WheelEvent) => {
      const board = boardScrollRef.current;
      if (board === null || Math.abs(event.deltaX) <= Math.abs(event.deltaY)) {
        return;
      }
      const maxScrollLeft = board.scrollWidth - board.clientWidth;
      if (maxScrollLeft <= 0) {
        return;
      }
      const nextScrollLeft = Math.min(Math.max(board.scrollLeft + event.deltaX, 0), maxScrollLeft);
      if (nextScrollLeft === board.scrollLeft) {
        return;
      }
      board.scrollLeft = nextScrollLeft;
      if (event.cancelable) {
        event.preventDefault();
      }
    };
    cardList.addEventListener("wheel", handleCardListWheel, { passive: false });
    return () => cardList.removeEventListener("wheel", handleCardListWheel);
  }, [boardScrollRef]);
  return (
    <section
      className={className}
      data-debug-id="project-todo-column"
      data-project-todo-column={column}
      aria-label={columnLabel}
      onDragOver={(event) => {
        if (!acceptsDrop || !hasProjectTodoDragData(event, draggingTodoId)) {
          return;
        }
        event.preventDefault();
        event.dataTransfer.dropEffect = "move";
        onDropColumnChange(column);
      }}
      onDrop={(event) => {
        if (!acceptsDrop) {
          return;
        }
        event.preventDefault();
        const todoId = onDropTodoId(event);
        onResetDragState();
        if (todoId) {
          onDropColumn(todoId, column);
        }
      }}
      onDragLeave={(event) => {
        const nextTarget = event.relatedTarget;
        if (nextTarget instanceof Node && event.currentTarget.contains(nextTarget)) {
          return;
        }
        onDropColumnChange(dropColumn === column ? null : dropColumn);
      }}
    >
      <header>
        <strong>{columnLabel}</strong>
        <span className="project-todo-column-card-count" data-debug-id="project-todo-column-card-count">
          {t(cardCountLabelKey, { count: columnTodos.length })}
        </span>
        <ColumnViewToggle column={column} value={viewMode} onChange={onViewModeChange} />
      </header>
      <div className="project-todo-column-cards" ref={cardListRef}>
        {viewMode === "tree" ? (
          <ProjectTodoTree
            cardProps={cardSharedProps}
            collapsedKeys={collapsedTreeNodeKeys}
            nodes={treeNodes}
            onToggleNode={onTreeNodeCollapsedChange}
          />
        ) : (
          columnTodos.map((todo) => <ProjectTodoCard key={todo.id} todo={todo} {...cardSharedProps} />)
        )}
        {columnTodos.length === 0 && <p className="project-todo-column-empty">{t("projectTodo.board.noTasks")}</p>}
      </div>
    </section>
  );
}

function ProjectTodoGroupSummary({
  group,
  settings
}: { group: ProjectTodoBoardGroup; settings: ProjectTodoViewSettings }) {
  const { t } = useI18n();
  if (!settings.progress && !settings.totals && !settings.participants) {
    return null;
  }
  return (
    <div className="project-todo-board-group-summary">
      {settings.progress && (
        <>
          <div className="project-todo-board-progress" aria-label={t("projectTodo.board.progress", { percent: group.progressPercent })}>
            <span style={{ width: `${group.progressPercent}%` }} />
          </div>
          <span>{group.progressPercent}%</span>
        </>
      )}
      {settings.totals && <span>{t("projectTodo.board.tasksCount", { count: group.total })}</span>}
      {settings.participants && <span>{t("projectTodo.board.peopleCount", { count: group.participants.length })}</span>}
    </div>
  );
}

function ChevronIcon({ collapsed }: { collapsed: boolean }) {
  return (
    <svg
      aria-hidden="true"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      {collapsed ? <path d="m9 6 6 6-6 6" /> : <path d="m6 9 6 6 6-6" />}
    </svg>
  );
}
