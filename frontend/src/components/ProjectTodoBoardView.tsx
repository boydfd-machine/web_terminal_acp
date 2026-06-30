import { useEffect, useMemo, useRef, useState, type DragEvent } from "react";

import {
  PROJECT_TODO_BOARD_ALL,
  buildProjectTodoBoardFilterOptions,
  buildProjectTodoBoardGroups,
  buildProjectTodoTree,
  collectProjectTodoTreeNodeKeys,
  filterProjectTodos,
  type ProjectTodoBoardGroupingMode,
  type ProjectTodoColumnViewMode
} from "../features/projectTodos/projectTodoBoardModel";
import { useProjectTodoBoardFilters } from "../features/projectTodos/useProjectTodoBoardFilters";
import { useAppPrompt } from "./AppPromptProvider";
import { useI18n } from "../i18n";
import {
  PROJECT_TODO_BOARD_COLUMN_ORDER,
  projectTodoBoardColumn,
  type ProjectTodoBoardColumn
} from "./projectTodoDisplay";
import type { ProjectTodoListItem, ProjectTodoStatus } from "../types";
import { ProjectTodoBoardToolbar } from "./ProjectTodoBoardToolbar";
import { ProjectTodoBoardGroupView } from "./ProjectTodoBoardGroupView";
import {
  PROJECT_TODO_MERGE_HOVER_MS,
  projectTodoCardDropTodoId,
  projectTodoColumnDropTodoId,
  setProjectTodoDragData
} from "./ProjectTodoBoardDrag";
import type {
  ProjectTodoBoardProps,
  ProjectTodoCardSharedProps,
  ProjectTodoViewSettings
} from "./ProjectTodoBoardTypes";

function defaultColumnViewModes(): Record<ProjectTodoBoardColumn, ProjectTodoColumnViewMode> {
  const modes = {} as Record<ProjectTodoBoardColumn, ProjectTodoColumnViewMode>;
  for (const column of PROJECT_TODO_BOARD_COLUMN_ORDER) {
    modes[column] = "cards";
  }
  return modes;
}

function projectTodoStatusFromBoardColumn(column: ProjectTodoBoardColumn): ProjectTodoStatus | null {
  return column === "PENDING" ? null : column;
}

export function ProjectTodoBoard({
  agentWorkStatusByWindowId,
  busy,
  clientId,
  commentingTodoIds,
  dispatchErrors,
  dispatchingTodoIds,
  initialLoading,
  projectPath,
  selectedTodoId,
  todos,
  registerTodoRef,
  onCreateChildTodo,
  onCreateTodo,
  onComment,
  onDispatch,
  onMergeTodo,
  onOpenTodo,
  onOpenTerminalWindow,
  onRetryArtifact,
  onToggleSchedule,
  onUploadAttachment,
  retryingArtifactLinkId,
  uploadingAttachmentTodoIds,
  onMoveTodo,
}: ProjectTodoBoardProps) {
  const { t } = useI18n();
  const { confirm } = useAppPrompt();
  const [groupingMode, setGroupingMode] = useState<ProjectTodoBoardGroupingMode>("flat");
  const {
    childFilterParent,
    childFilterParentId,
    filters,
    resetChildFilter,
    resetFilters,
    setFilters,
    showChildTodos,
    todoById
  } = useProjectTodoBoardFilters(todos);
  const [collapsedGroupIds, setCollapsedGroupIds] = useState<Set<string>>(() => new Set());
  const [collapsedTreeNodeKeys, setCollapsedTreeNodeKeys] = useState<Set<string>>(() => new Set());
  const [columnViewModes, setColumnViewModes] = useState(defaultColumnViewModes);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [viewSettings, setViewSettings] = useState<ProjectTodoViewSettings>({
    progress: true,
    totals: true,
    participants: true
  });
  const [draggingTodoId, setDraggingTodoId] = useState<string | null>(null);
  const [dropColumn, setDropColumn] = useState<ProjectTodoBoardColumn | null>(null);
  const [mergeTargetTodoId, setMergeTargetTodoId] = useState<string | null>(null);
  const mergeHoverTimeoutRef = useRef<number | null>(null);
  const filterOptions = useMemo(() => buildProjectTodoBoardFilterOptions(todos), [todos]);
  const filteredTodos = useMemo(
    () => filterProjectTodos(todos, filters, { dispatchingTodoIds }),
    [dispatchingTodoIds, filters, todos]
  );
  const groups = useMemo(
    () => buildProjectTodoBoardGroups(filteredTodos, groupingMode, { dispatchingTodoIds }),
    [dispatchingTodoIds, filteredTodos, groupingMode]
  );
  const allTreeNodeKeys = useMemo(() => groups.flatMap((group) => (
    PROJECT_TODO_BOARD_COLUMN_ORDER.flatMap((column) => (
      collectProjectTodoTreeNodeKeys(buildProjectTodoTree(group.columns.get(column) ?? [], group))
    ))
  )), [groups]);

  const clearMergeHover = () => {
    if (mergeHoverTimeoutRef.current !== null) {
      window.clearTimeout(mergeHoverTimeoutRef.current);
      mergeHoverTimeoutRef.current = null;
    }
    setMergeTargetTodoId(null);
  };
  useEffect(() => () => {
    if (mergeHoverTimeoutRef.current !== null) {
      window.clearTimeout(mergeHoverTimeoutRef.current);
    }
  }, []);
  const resetDragState = () => {
    setDraggingTodoId(null);
    setDropColumn(null);
    clearMergeHover();
  };
  const confirmTodoMerge = (sourceTodo: ProjectTodoListItem, targetTodo: ProjectTodoListItem): Promise<boolean> => (
    confirm({
      title: t("projectTodo.board.mergeConfirmTitle"),
      message: t("projectTodo.board.mergeConfirm", { source: sourceTodo.title, target: targetTodo.title }),
      confirmLabel: t("projectTodo.board.mergeConfirmSubmit")
    })
  );
  const mergeableSourceTodo = (event: DragEvent<HTMLElement>, targetTodoId: string): ProjectTodoListItem | null => {
    const sourceTodoId = projectTodoCardDropTodoId(event, draggingTodoId);
    const sourceTodo = sourceTodoId.length === 0 ? undefined : todoById.get(sourceTodoId);
    if (
      sourceTodo === undefined
      || sourceTodo.id === targetTodoId
      || projectTodoBoardColumn(sourceTodo) !== "TODO"
    ) {
      return null;
    }
    return sourceTodo;
  };
  const requestTodoMerge = async (sourceTodo: ProjectTodoListItem, targetTodo: ProjectTodoListItem) => {
    if (!(await confirmTodoMerge(sourceTodo, targetTodo))) {
      return;
    }
    onMergeTodo(sourceTodo.id, targetTodo.id);
  };
  const scheduleTodoMerge = (event: DragEvent<HTMLElement>, targetTodo: ProjectTodoListItem) => {
    const sourceTodo = mergeableSourceTodo(event, targetTodo.id);
    if (sourceTodo === null) {
      clearMergeHover();
      return;
    }
    event.preventDefault();
    event.stopPropagation();
    event.dataTransfer.dropEffect = "move";
    if (mergeTargetTodoId === targetTodo.id && mergeHoverTimeoutRef.current !== null) {
      return;
    }
    clearMergeHover();
    setMergeTargetTodoId(targetTodo.id);
    mergeHoverTimeoutRef.current = window.setTimeout(() => {
      mergeHoverTimeoutRef.current = null;
      requestTodoMerge(sourceTodo, targetTodo);
      setMergeTargetTodoId(null);
    }, PROJECT_TODO_MERGE_HOVER_MS);
  };
  const cardSharedProps: ProjectTodoCardSharedProps = {
    agentWorkStatusByWindowId,
    busy,
    clientId,
    commentingTodoIds,
    dispatchErrors,
    dispatchingTodoIds,
    draggingTodoId,
    highlightedParentTodoId: childFilterParentId,
    mergeTargetTodoId,
    projectPath,
    selectedTodoId,
    registerTodoRef,
    onDragEnd: resetDragState,
    onDragStart: (event, todo) => {
      setDraggingTodoId(todo.id);
      setProjectTodoDragData(event, todo.id);
    },
    onMergeDragEnter: (event, todo) => scheduleTodoMerge(event, todo),
    onMergeDragLeave: (event, todo) => {
      if (mergeTargetTodoId !== todo.id) {
        return;
      }
      const nextTarget = event.relatedTarget;
      if (nextTarget instanceof Node && event.currentTarget.contains(nextTarget)) {
        return;
      }
      clearMergeHover();
    },
    onMergeDragOver: (event, todo) => {
      if (mergeableSourceTodo(event, todo.id) !== null) {
        event.preventDefault();
        event.stopPropagation();
        event.dataTransfer.dropEffect = "move";
      }
    },
    onMergeDrop: (event, todo) => {
      const sourceTodo = mergeableSourceTodo(event, todo.id);
      if (sourceTodo === null) {
        return;
      }
      event.preventDefault();
      event.stopPropagation();
      clearMergeHover();
      resetDragState();
    },
    onComment,
    onCreateChildTodo,
    onDispatch,
    onOpenTodo,
    onOpenTerminalWindow,
    onShowChildTodos: showChildTodos,
    onRetryArtifact,
    onToggleSchedule,
    onUploadAttachment,
    retryingArtifactLinkId,
    uploadingAttachmentTodoIds
  };
  const activeFilterCount = [
    filters.status !== PROJECT_TODO_BOARD_ALL,
    filters.assignee !== PROJECT_TODO_BOARD_ALL,
    filters.tag !== PROJECT_TODO_BOARD_ALL,
    filters.parentTodoId !== PROJECT_TODO_BOARD_ALL,
    filters.search.trim().length > 0
  ].filter(Boolean).length;

  return (
    <div className="project-todo-board-shell" data-debug-id="project-todo-board">
      <ProjectTodoBoardToolbar
        activeFilterCount={activeFilterCount}
        childFilterParent={childFilterParent}
        filterOptions={filterOptions}
        filters={filters}
        groupingMode={groupingMode}
        settingsOpen={settingsOpen}
        viewSettings={viewSettings}
        onCollapseAll={() => {
          setCollapsedGroupIds(new Set(groups.map((group) => group.id)));
          setCollapsedTreeNodeKeys(new Set(allTreeNodeKeys));
        }}
        onCreateTodo={onCreateTodo}
        onExpandAll={() => {
          setCollapsedGroupIds(new Set());
          setCollapsedTreeNodeKeys(new Set());
        }}
        onGroupingModeChange={setGroupingMode}
        onResetFilters={resetFilters}
        onResetChildFilter={resetChildFilter}
        onSettingsOpenChange={setSettingsOpen}
        onUpdateFilter={(key, value) => setFilters((current) => ({ ...current, [key]: value }))}
        onViewSettingsChange={setViewSettings}
      />
      <div className="project-todo-board-groups" aria-label={t("workspace.projectKanban")}>
        {initialLoading ? (
          <div className="project-todo-board-loading" role="status" aria-live="polite">
            <span className="project-todo-board-loading-spinner" aria-hidden="true" />
            <span className="visually-hidden">{t("common.loading")}</span>
          </div>
        ) : groups.map((group) => (
          <ProjectTodoBoardGroupView
            key={group.id}
            cardSharedProps={cardSharedProps}
            collapsed={collapsedGroupIds.has(group.id)}
            collapsedTreeNodeKeys={collapsedTreeNodeKeys}
            columnViewModes={columnViewModes}
            dropColumn={dropColumn}
            draggingTodoId={draggingTodoId}
            group={group}
            viewSettings={viewSettings}
            onDropColumn={(todoId, column) => {
              const status = projectTodoStatusFromBoardColumn(column);
              if (status !== null) {
                onMoveTodo(todoId, status);
              }
            }}
            onGroupCollapsedChange={() => setCollapsedGroupIds((current) => toggleSetValue(current, group.id))}
            onTreeNodeCollapsedChange={(nodeKey) => setCollapsedTreeNodeKeys((current) => toggleSetValue(current, nodeKey))}
            onColumnViewModeChange={(column, mode) => setColumnViewModes((current) => ({ ...current, [column]: mode }))}
            onDropColumnChange={setDropColumn}
            onDropTodoId={(event) => projectTodoColumnDropTodoId(event, draggingTodoId)}
            onResetDragState={resetDragState}
          />
        ))}
        {!initialLoading && groups.length === 0 && <p className="project-todo-board-empty">{t("projectTodo.board.noMatches")}</p>}
      </div>
    </div>
  );
}

function toggleSetValue(current: Set<string>, value: string): Set<string> {
  const next = new Set(current);
  if (next.has(value)) {
    next.delete(value);
  } else {
    next.add(value);
  }
  return next;
}
