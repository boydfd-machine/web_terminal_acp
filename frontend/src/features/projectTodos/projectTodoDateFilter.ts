import { isTerminalTimeRange, type TerminalTimeRange } from "../../terminalTimeRange";

export const PROJECT_TODO_CUSTOM_DATE_RANGE = "custom";

export type ProjectTodoDateRange = TerminalTimeRange | typeof PROJECT_TODO_CUSTOM_DATE_RANGE;

export type ProjectTodoDateFilter = {
  range: ProjectTodoDateRange;
  customStart: string;
  customEnd: string;
};

export type ProjectTodoDateFilterRequest = {
  range: ProjectTodoDateRange;
  start_date?: string;
  end_date?: string;
};

export const PROJECT_TODO_DATE_FILTER_STORAGE_KEY = "web-terminal-acp:project-todo-date-filter";

export const DEFAULT_PROJECT_TODO_DATE_FILTER: Readonly<ProjectTodoDateFilter> = Object.freeze({
  range: "all",
  customStart: "",
  customEnd: ""
});

export function defaultProjectTodoDateFilter(): ProjectTodoDateFilter {
  return { ...DEFAULT_PROJECT_TODO_DATE_FILTER };
}

export function readProjectTodoDateFilter(): ProjectTodoDateFilter {
  if (typeof window === "undefined") {
    return defaultProjectTodoDateFilter();
  }

  try {
    return storedProjectTodoDateFilter(window.localStorage.getItem(PROJECT_TODO_DATE_FILTER_STORAGE_KEY));
  } catch {
    return defaultProjectTodoDateFilter();
  }
}

export function writeProjectTodoDateFilter(filter: ProjectTodoDateFilter): void {
  if (typeof window === "undefined") {
    return;
  }

  window.localStorage.setItem(PROJECT_TODO_DATE_FILTER_STORAGE_KEY, JSON.stringify({
    range: supportedProjectTodoDateRange(filter.range) ?? DEFAULT_PROJECT_TODO_DATE_FILTER.range,
    customStart: normalizedDateInput(filter.customStart) ?? "",
    customEnd: normalizedDateInput(filter.customEnd) ?? ""
  }));
}

export function projectTodoDateFilterActive(filter: ProjectTodoDateFilter): boolean {
  if (filter.range === "all") {
    return false;
  }
  if (filter.range === PROJECT_TODO_CUSTOM_DATE_RANGE) {
    return filter.customStart.trim().length > 0 || filter.customEnd.trim().length > 0;
  }
  return true;
}

export function projectTodoDateFilterRequest(
  filter: ProjectTodoDateFilter | undefined
): ProjectTodoDateFilterRequest | undefined {
  if (filter === undefined) {
    return undefined;
  }
  if (filter.range === "all") {
    return undefined;
  }
  if (filter.range !== PROJECT_TODO_CUSTOM_DATE_RANGE) {
    return isTerminalTimeRange(filter.range) ? { range: filter.range } : undefined;
  }

  const startDate = normalizedDateInput(filter.customStart);
  const endDate = normalizedDateInput(filter.customEnd);
  if (startDate === undefined && endDate === undefined) {
    return undefined;
  }
  return {
    range: PROJECT_TODO_CUSTOM_DATE_RANGE,
    ...(startDate === undefined ? {} : { start_date: startDate }),
    ...(endDate === undefined ? {} : { end_date: endDate })
  };
}

export function projectTodoDateFilterQueryKey(
  filter: ProjectTodoDateFilter | undefined
): readonly [ProjectTodoDateRange, string, string] | null {
  const request = projectTodoDateFilterRequest(filter);
  return request === undefined
    ? null
    : [request.range, request.start_date ?? "", request.end_date ?? ""];
}

export function projectTodoUpdatedAtMatchesDateFilter(
  todo: { updated_at: string },
  filter: ProjectTodoDateFilter | undefined,
  now: Date = new Date()
): boolean {
  const request = projectTodoDateFilterRequest(filter);
  if (request === undefined) {
    return true;
  }

  const updatedAt = Date.parse(todo.updated_at);
  if (!Number.isFinite(updatedAt)) {
    return false;
  }

  if (request.range === PROJECT_TODO_CUSTOM_DATE_RANGE) {
    const start = request.start_date === undefined ? null : dateInputStartMs(request.start_date);
    const end = request.end_date === undefined ? null : dateInputStartMs(request.end_date) + DAY_MS;
    return (start === null || updatedAt >= start) && (end === null || updatedAt < end);
  }

  const days = terminalTimeRangeDays(request.range);
  return days === null ? true : updatedAt >= now.getTime() - days * DAY_MS;
}

const DAY_MS = 24 * 60 * 60 * 1000;

function dateInputStartMs(value: string): number {
  const [year, month, day] = value.split("-").map(Number);
  return Date.UTC(year, month - 1, day);
}

function terminalTimeRangeDays(range: string | undefined): number | null {
  if (range === undefined || range === "all") {
    return null;
  }
  const match = /^(\d+)d$/.exec(range);
  return match === null ? null : Number(match[1]);
}

function normalizedDateInput(value: string): string | undefined {
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(value.trim());
  if (match === null) {
    return undefined;
  }
  const year = Number(match[1]);
  const month = Number(match[2]);
  const day = Number(match[3]);
  const date = new Date(year, month - 1, day);
  if (
    date.getFullYear() !== year
    || date.getMonth() !== month - 1
    || date.getDate() !== day
  ) {
    return undefined;
  }
  return value.trim();
}

function storedProjectTodoDateFilter(rawValue: string | null): ProjectTodoDateFilter {
  if (rawValue === null) {
    return defaultProjectTodoDateFilter();
  }

  const parsed = JSON.parse(rawValue) as Record<string, unknown>;
  const range = supportedProjectTodoDateRange(parsed.range);
  if (range === null) {
    return defaultProjectTodoDateFilter();
  }

  return {
    range,
    customStart: typeof parsed.customStart === "string" ? normalizedDateInput(parsed.customStart) ?? "" : "",
    customEnd: typeof parsed.customEnd === "string" ? normalizedDateInput(parsed.customEnd) ?? "" : ""
  };
}

function supportedProjectTodoDateRange(value: unknown): ProjectTodoDateRange | null {
  if (isTerminalTimeRange(value)) {
    return value;
  }
  return value === PROJECT_TODO_CUSTOM_DATE_RANGE ? PROJECT_TODO_CUSTOM_DATE_RANGE : null;
}
