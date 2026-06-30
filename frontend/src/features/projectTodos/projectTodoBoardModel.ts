import type { ProjectTodoListItem } from "../../types";
import {
  PROJECT_TODO_BOARD_COLUMN_ORDER,
  projectTodoBoardColumn,
  type ProjectTodoBoardColumn
} from "./projectTodoDisplay";
import { projectTodoLatestFirst } from "./projectTodoPanelUtils";

export const PROJECT_TODO_BOARD_ALL = "ALL";
export type ProjectTodoBoardFilterValue = typeof PROJECT_TODO_BOARD_ALL;
export type ProjectTodoBoardGroupingMode = "flat" | "tree";
export type ProjectTodoColumnViewMode = "cards" | "tree";

export type ProjectTodoBoardFilters = {
  status: ProjectTodoBoardColumn | ProjectTodoBoardFilterValue;
  assignee: string | ProjectTodoBoardFilterValue;
  tag: string | ProjectTodoBoardFilterValue;
  parentTodoId: string | ProjectTodoBoardFilterValue;
  search: string;
};

export type ProjectTodoBoardFilterOptions = {
  assignees: string[];
  tags: string[];
};

export type ProjectTodoBoardRuntimeState = {
  dispatchingTodoIds?: ReadonlySet<string>;
};

export type ProjectTodoBoardGroup = {
  id: string;
  label: string;
  pathSegments: string[];
  todos: ProjectTodoListItem[];
  columns: Map<ProjectTodoBoardColumn, ProjectTodoListItem[]>;
  total: number;
  done: number;
  progressPercent: number;
  participants: string[];
};

export type ProjectTodoTreeNode = {
  key: string;
  label: string;
  depth: number;
  count: number;
  todos: ProjectTodoListItem[];
  children: ProjectTodoTreeNode[];
};

type ProjectTodoMergeCard = {
  title: string;
  description: string | null;
};

type MutableProjectTodoTreeNode = Omit<ProjectTodoTreeNode, "children"> & {
  children: MutableProjectTodoTreeNode[];
  childMap: Map<string, MutableProjectTodoTreeNode>;
};

const UNASSIGNED_TOPIC = "Unassigned";
const UNASSIGNED_ASSIGNEE = "Unassigned";

export function defaultProjectTodoBoardFilters(): ProjectTodoBoardFilters {
  return {
    status: PROJECT_TODO_BOARD_ALL,
    assignee: PROJECT_TODO_BOARD_ALL,
    tag: PROJECT_TODO_BOARD_ALL,
    parentTodoId: PROJECT_TODO_BOARD_ALL,
    search: ""
  };
}

export function projectTodoTerminalTags(todo: ProjectTodoListItem): string[] {
  return uniqueStrings(todo.assigned_terminal?.title_tags ?? []);
}

export function projectTodoAssignee(todo: ProjectTodoListItem): string {
  return todo.assigned_agent?.trim() || UNASSIGNED_ASSIGNEE;
}

export function projectTodoTopicPath(todo: ProjectTodoListItem): string {
  const value = todo.assigned_terminal?.topic_path?.trim();
  return value && value.startsWith("/") ? value : `/${UNASSIGNED_TOPIC}`;
}

export function projectTodoTopicSegments(todo: ProjectTodoListItem): string[] {
  const segments = projectTodoTopicPath(todo)
    .split("/")
    .map((segment) => segment.trim())
    .filter(Boolean);
  return segments.length > 0 ? segments : [UNASSIGNED_TOPIC];
}

export function projectTodoTopicLabel(todo: ProjectTodoListItem): string {
  return projectTodoTopicSegments(todo).join(" / ");
}

export function buildProjectTodoBoardFilterOptions(todos: ProjectTodoListItem[]): ProjectTodoBoardFilterOptions {
  return {
    assignees: uniqueStrings(todos.map(projectTodoAssignee)).sort(compareLabels),
    tags: uniqueStrings(todos.flatMap(projectTodoTerminalTags)).sort(compareLabels)
  };
}

export function filterProjectTodos(
  todos: ProjectTodoListItem[],
  filters: ProjectTodoBoardFilters,
  runtimeState: ProjectTodoBoardRuntimeState = {}
): ProjectTodoListItem[] {
  const normalizedSearch = normalizeSearch(filters.search);
  return todos.filter((todo) => {
    if (filters.status !== PROJECT_TODO_BOARD_ALL && projectTodoBoardColumnForRuntime(todo, runtimeState) !== filters.status) {
      return false;
    }
    if (filters.assignee !== PROJECT_TODO_BOARD_ALL && projectTodoAssignee(todo) !== filters.assignee) {
      return false;
    }
    if (filters.tag !== PROJECT_TODO_BOARD_ALL && !projectTodoTerminalTags(todo).includes(filters.tag)) {
      return false;
    }
    if (
      filters.parentTodoId !== PROJECT_TODO_BOARD_ALL
      && todo.id !== filters.parentTodoId
      && todo.parent_todo_id !== filters.parentTodoId
    ) {
      return false;
    }
    if (normalizedSearch.length > 0 && !projectTodoMatchesSearch(todo, normalizedSearch)) {
      return false;
    }
    return true;
  });
}

export function projectTodoMatchesSearch(todo: ProjectTodoListItem, normalizedQuery: string): boolean {
  if (normalizedQuery.length === 0) {
    return true;
  }
  return [
    todo.title,
    todo.todo_type_id,
    todo.todo_type.name,
    todo.todo_type.description ?? "",
    todo.agent_profile_id ?? "",
    todo.assigned_terminal?.title ?? "",
    todo.assigned_terminal?.summary ?? "",
    todo.assigned_terminal?.topic_path ?? "",
    projectTodoTopicLabel(todo),
    ...projectTodoTerminalTags(todo)
  ]
    .join(" ")
    .toLocaleLowerCase()
    .includes(normalizedQuery);
}

export function buildProjectTodoBoardGroups(
  todos: ProjectTodoListItem[],
  mode: ProjectTodoBoardGroupingMode,
  runtimeState: ProjectTodoBoardRuntimeState = {}
): ProjectTodoBoardGroup[] {
  const grouped = new Map<string, { label: string; pathSegments: string[]; todos: ProjectTodoListItem[] }>();
  for (const todo of todos) {
    const pathSegments = projectTodoTopicSegments(todo);
    const key = mode === "tree" ? pathSegments[0] : "all";
    const label = mode === "tree" ? pathSegments[0] : "All tasks";
    const group = grouped.get(key) ?? { label, pathSegments: mode === "tree" ? [pathSegments[0]] : [], todos: [] };
    group.todos.push(todo);
    grouped.set(key, group);
  }

  return Array.from(grouped.entries())
    .sort((left, right) => compareLabels(left[1].label, right[1].label))
    .map(([id, group]) => projectTodoBoardGroup(id, group.label, group.pathSegments, group.todos, runtimeState));
}

export function buildProjectTodoTree(todos: ProjectTodoListItem[], group: ProjectTodoBoardGroup): ProjectTodoTreeNode[] {
  const roots: MutableProjectTodoTreeNode[] = [];
  const rootMap = new Map<string, MutableProjectTodoTreeNode>();
  const groupPrefixLength = group.pathSegments.length;

  for (const todo of [...todos].sort(projectTodoLatestFirst)) {
    const fullSegments = projectTodoTopicSegments(todo);
    const relativeSegments = fullSegments.slice(groupPrefixLength);
    const segments = relativeSegments.length > 0 ? relativeSegments : [todo.assigned_terminal?.title ?? "Task"];
    let nodes = roots;
    let nodeMap = rootMap;
    let pathKey = `group:${group.id}`;

    for (const [index, segment] of segments.entries()) {
      pathKey = `${pathKey}/${segment}`;
      let node = nodeMap.get(segment);
      if (node === undefined) {
        node = {
          key: pathKey,
          label: segment,
          depth: index,
          count: 0,
          todos: [],
          children: [],
          childMap: new Map()
        };
        nodeMap.set(segment, node);
        nodes.push(node);
      }
      node.count += 1;
      if (index === segments.length - 1) {
        node.todos.push(todo);
      }
      nodes = node.children;
      nodeMap = node.childMap;
    }
  }

  return roots.map(freezeTreeNode);
}

export function collectProjectTodoTreeNodeKeys(nodes: ProjectTodoTreeNode[]): string[] {
  const keys: string[] = [];
  const visit = (node: ProjectTodoTreeNode) => {
    if (node.children.length > 0) {
      keys.push(node.key);
      for (const child of node.children) {
        visit(child);
      }
    }
  };
  for (const node of nodes) {
    visit(node);
  }
  return keys;
}

export function projectTodoMergePayload({
  target,
  source
}: {
  target: ProjectTodoMergeCard;
  source: ProjectTodoMergeCard;
}): { title: string; description: string | null } {
  return {
    title: [target.title, source.title].map((title) => title.trim()).filter(Boolean).join(" / "),
    description: [target.description, source.description]
      .map((description) => description?.trim() ?? "")
      .filter(Boolean)
      .join("\n\n") || null
  };
}

function projectTodoBoardGroup(
  id: string,
  label: string,
  pathSegments: string[],
  todos: ProjectTodoListItem[],
  runtimeState: ProjectTodoBoardRuntimeState
): ProjectTodoBoardGroup {
  const sortedTodos = [...todos].sort(projectTodoLatestFirst);
  const columns = new Map<ProjectTodoBoardColumn, ProjectTodoListItem[]>();
  for (const column of PROJECT_TODO_BOARD_COLUMN_ORDER) {
    columns.set(column, []);
  }
  for (const todo of sortedTodos) {
    columns.get(projectTodoBoardColumnForRuntime(todo, runtimeState))?.push(todo);
  }

  const done = sortedTodos.filter((todo) => todo.status === "DONE").length;
  const participants = uniqueStrings(sortedTodos.map(projectTodoAssignee)).sort(compareLabels);
  return {
    id,
    label,
    pathSegments,
    todos: sortedTodos,
    columns,
    total: sortedTodos.length,
    done,
    progressPercent: sortedTodos.length === 0 ? 0 : Math.round((done / sortedTodos.length) * 100),
    participants
  };
}

function projectTodoBoardColumnForRuntime(
  todo: ProjectTodoListItem,
  runtimeState: ProjectTodoBoardRuntimeState
): ProjectTodoBoardColumn {
  if (runtimeState.dispatchingTodoIds?.has(todo.id)) {
    return "PENDING";
  }
  return projectTodoBoardColumn(todo);
}

function freezeTreeNode(node: MutableProjectTodoTreeNode): ProjectTodoTreeNode {
  node.children.sort((left, right) => compareLabels(left.label, right.label));
  node.todos.sort(projectTodoLatestFirst);
  return {
    key: node.key,
    label: node.label,
    depth: node.depth,
    count: node.count,
    todos: node.todos,
    children: node.children.map(freezeTreeNode)
  };
}

function uniqueStrings(values: Array<string | null | undefined>): string[] {
  return Array.from(new Set(values.map((value) => value?.trim() ?? "").filter(Boolean)));
}

function compareLabels(left: string, right: string): number {
  return left.localeCompare(right, undefined, { numeric: true, sensitivity: "base" });
}

function normalizeSearch(value: string): string {
  return value.trim().toLocaleLowerCase();
}
